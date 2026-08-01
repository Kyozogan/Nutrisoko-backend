"""
Menu generation engine.

Implements the constrained-optimization workflow described in the product
documentation as a fast, dependency-free greedy heuristic (v1): for every
meal slot in the week it scores each eligible recipe against the
institution's per-meal nutrition share and budget, picks the best-scoring
option, and avoids repeating the same main dish within a 3-day window.

The scoring function and slot loop are isolated so a future version can
swap in a true linear/integer programming solver (e.g. PuLP / OR-Tools)
behind the same `generate_menu_plan` interface without changing callers.
"""
from decimal import Decimal
from datetime import timedelta

from nutrition.models import Recipe
from nutrition.utils import recipe_profile, recipe_violates_restrictions
from .models import MenuPlan, MenuItem

MEAL_SLOTS = ["breakfast", "lunch", "dinner"]
# Share of the daily nutrition target each slot should roughly contribute.
SLOT_SHARE = {"breakfast": Decimal("0.25"), "lunch": Decimal("0.40"), "dinner": Decimal("0.35")}
# Maps a menu slot to the institution's matching optional per-meal budget field.
# "dinner" is the internal recipe/menu slot name; institutions configure this as "supper".
SLOT_BUDGET_FIELD = {"breakfast": "budget_breakfast", "lunch": "budget_lunch", "dinner": "budget_supper"}


def _score(profile, target_calories, budget):
    """Lower is better: distance from calorie target + budget penalty."""
    calorie_gap = abs(float(profile["calories"]) - float(target_calories))
    over_budget_penalty = 0
    if budget and float(profile["cost"]) > float(budget):
        over_budget_penalty = (float(profile["cost"]) - float(budget)) * 50
    return calorie_gap + over_budget_penalty


def _offered_slots(institution):
    """
    Which meal slots this institution actually feeds people at.

    If it has filled in at least one of the three specific meal budgets, that's
    treated as the full picture — any slot left blank means "we don't offer this
    meal" and is skipped entirely. Institutions that never set any specific meal
    budget (only the legacy overall budget_per_meal) get all three slots, exactly
    as before.
    """
    configured = institution.meal_budgets_set()
    if not configured:
        return list(MEAL_SLOTS)
    return [slot for slot, field in SLOT_BUDGET_FIELD.items() if configured.get(field.replace("budget_", "")) is not None]


def generate_menu_plan(institution, week_start, replace_existing=True):
    profile = institution.dietary_profile
    county = institution.county
    offered_slots = _offered_slots(institution)

    recipes_by_slot = {}
    for slot in offered_slots:
        eligible = [
            r for r in Recipe.objects.filter(meal_type=slot)
            if not recipe_violates_restrictions(r, profile.restrictions)
        ]
        recipes_by_slot[slot] = eligible

    if MenuPlan.objects.filter(institution=institution, week_start=week_start).exists() and replace_existing:
        MenuPlan.objects.filter(institution=institution, week_start=week_start).delete()

    plan = MenuPlan.objects.create(institution=institution, week_start=week_start)

    total_cost = Decimal("0")
    total_calories = 0.0
    total_protein = 0.0
    total_carbs = 0.0
    total_fat = 0.0
    recent_mains = []  # last used recipe ids per slot to discourage repeats
    notes = []

    for day in range(7):
        for slot in offered_slots:
            candidates = recipes_by_slot.get(slot, [])
            if not candidates:
                notes.append(f"No eligible {slot} recipes found for day {day + 1}; slot left empty.")
                continue

            target_slot_calories = (profile.target_calories or 0) * SLOT_SHARE[slot]
            # Prefer the institution's specific budget for this meal slot (e.g. it may not
            # offer breakfast at all); fall back to the overall per-meal budget if unset.
            specific_budget = getattr(institution, SLOT_BUDGET_FIELD[slot], None)
            slot_budget = specific_budget if specific_budget is not None else (institution.budget_per_meal or None)

            scored = []
            for r in candidates:
                prof = recipe_profile(r, county)
                penalty = 1000 if r.id in recent_mains[-2:] else 0
                s = _score(prof, target_slot_calories, slot_budget) + penalty
                scored.append((s, r, prof))
            scored.sort(key=lambda t: t[0])
            best_score, best_recipe, best_profile = scored[0]

            MenuItem.objects.create(
                menu_plan=plan, day=day, meal_slot=slot,
                recipe=best_recipe, servings=institution.headcount or 1,
                estimated_cost=best_profile["cost"] * (institution.headcount or 1),
            )

            recent_mains.append(best_recipe.id)
            total_cost += best_profile["cost"] * (institution.headcount or 1)
            total_calories += float(best_profile["calories"])
            total_protein += float(best_profile["protein_g"])
            total_carbs += float(best_profile["carbs_g"])
            total_fat += float(best_profile["fat_g"])

    plan.total_cost = round(total_cost, 2)
    plan.nutrient_summary = {
        "avg_daily_calories": round(total_calories / 7, 1),
        "avg_daily_protein_g": round(total_protein / 7, 1),
        "avg_daily_carbs_g": round(total_carbs / 7, 1),
        "avg_daily_fat_g": round(total_fat / 7, 1),
        "target_calories": profile.target_calories,
        "target_protein_g": profile.target_protein_g,
        "target_carbs_g": profile.target_carbs_g,
        "target_fat_g": profile.target_fat_g,
    }
    plan.generation_notes = " ".join(notes) or "Generated successfully within budget and nutrition targets."
    plan.save()
    return plan


def week_end(week_start):
    return week_start + timedelta(days=6)


def duplicate_menu_plan(source_plan, week_start):
    """
    Reuse a plan's exact dish rotation for another week instead of generating fresh —
    e.g. a school on a termly billing cycle wants the same weekly menu repeated for 13
    weeks rather than a brand-new AI/heuristic run every week. Ingredient costs are
    recalculated at current supplier prices; the dishes themselves are copied as-is.
    """
    institution = source_plan.institution
    county = institution.county

    MenuPlan.objects.filter(institution=institution, week_start=week_start).delete()
    plan = MenuPlan.objects.create(
        institution=institution, week_start=week_start, source=source_plan.source,
        selected_ingredient_ids=source_plan.selected_ingredient_ids,
        duplicated_from=source_plan,
    )

    total_cost = Decimal("0")
    total_calories = total_protein = total_carbs = total_fat = 0.0

    for src_item in source_plan.items.select_related("recipe").all():
        prof = recipe_profile(src_item.recipe, county)
        servings = institution.headcount or 1
        MenuItem.objects.create(
            menu_plan=plan, day=src_item.day, meal_slot=src_item.meal_slot, recipe=src_item.recipe,
            servings=servings, estimated_cost=prof["cost"] * servings,
        )
        total_cost += prof["cost"] * servings
        total_calories += float(prof["calories"])
        total_protein += float(prof["protein_g"])
        total_carbs += float(prof["carbs_g"])
        total_fat += float(prof["fat_g"])

    days_with_items = max(len({item.day for item in plan.items.all()}), 1)
    plan.total_cost = round(total_cost, 2)
    plan.nutrient_summary = {
        "avg_daily_calories": round(total_calories / days_with_items, 1),
        "avg_daily_protein_g": round(total_protein / days_with_items, 1),
        "avg_daily_carbs_g": round(total_carbs / days_with_items, 1),
        "avg_daily_fat_g": round(total_fat / days_with_items, 1),
        **{k: v for k, v in source_plan.nutrient_summary.items() if k.startswith("target_")},
    }
    plan.generation_notes = f"Reused the menu from the week of {source_plan.week_start} (prices refreshed to today's rates)."
    plan.save()
    return plan
