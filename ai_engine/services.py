"""
AI-powered features for SokoPulse, backed entirely by Groq. There is no
rule-based fallback: every function here either returns an AI-generated
result or raises ai_engine.groq_client.GroqUnavailable, which the view layer
(ai_engine/views.py) turns into a proper error response.
"""
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Sum

from nutrition.models import Ingredient, Recipe, RecipeIngredient
from nutrition.utils import recipe_profile
from suppliers.models import SupplierListing
from farmers.models import DemandSignal, SupplyCommitment
from menus.models import MenuPlan, MenuItem
from . import groq_client as groq

MEALS_PER_DAY = 3
DAYS_PER_WEEK = 7


# --------------------------------------------------------------------------
# Shared helpers
# --------------------------------------------------------------------------

def _best_listing(ingredient, county=None):
    qs = SupplierListing.objects.filter(ingredient=ingredient, is_active=True).select_related("supplier")
    if county:
        local = qs.filter(supplier__county__iexact=county).order_by("price_per_unit").first()
        if local:
            return local
    return qs.order_by("price_per_unit").first()


def _candidate_ingredients(county=None, restrictions=None):
    """Every ingredient with at least one active listing, priced via the best available listing."""
    candidates = []
    for ingredient in Ingredient.objects.all():
        if restrictions:
            r = [x.lower() for x in restrictions]
            if ("vegetarian" in r or "vegan" in r) and ingredient.contains_meat:
                continue
            if "vegan" in r and ingredient.contains_dairy:
                continue
            if "dairy-free" in r and ingredient.contains_dairy:
                continue
            if "gluten-free" in r and ingredient.contains_gluten:
                continue
        listing = _best_listing(ingredient, county)
        price = listing.price_per_unit if listing else ingredient.default_price_per_unit
        if not price:
            continue
        candidates.append({
            "ingredient": ingredient,
            "price": price,
            "supplier_name": listing.supplier.name if listing else None,
        })
    return candidates


def _serialize_ingredient(ingredient, price=None, supplier_name=None, reason=""):
    return {
        "id": ingredient.id,
        "name": ingredient.name,
        "unit": ingredient.unit,
        "category": ingredient.category,
        "price_per_unit": str(price if price is not None else ingredient.default_price_per_unit),
        "supplier_name": supplier_name,
        "calories_per_unit": str(ingredient.calories_per_unit),
        "protein_g_per_unit": str(ingredient.protein_g_per_unit),
        "reason": reason,
    }


# --------------------------------------------------------------------------
# 1. Product / ingredient recommendation for institutions
# --------------------------------------------------------------------------

def recommend_ingredients(institution, budget_override=None, max_items=14):
    profile = getattr(institution, "dietary_profile", None)
    restrictions = profile.restrictions if profile else []
    county = institution.county
    if budget_override:
        weekly_budget = Decimal(str(budget_override))
    else:
        headcount = institution.headcount or 1
        configured = [b for b in (institution.budget_breakfast, institution.budget_lunch, institution.budget_supper) if b is not None]
        per_person_daily = sum(configured) if configured else (institution.budget_per_meal or Decimal("0")) * MEALS_PER_DAY
        weekly_budget = per_person_daily * DAYS_PER_WEEK * headcount

    candidates = _candidate_ingredients(county, restrictions)
    if not candidates:
        return {
            "summary": "No supplier listings are available yet — ask a supplier to add ingredients first.",
            "selected_ingredients": [], "estimated_weekly_cost": 0, "weekly_budget_total": float(weekly_budget),
        }

    candidate_lines = [
        f"id={c['ingredient'].id} | {c['ingredient'].name} | category={c['ingredient'].category} | "
        f"unit={c['ingredient'].unit} | price_per_unit={c['price']} | "
        f"kcal/unit={c['ingredient'].calories_per_unit} | protein_g/unit={c['ingredient'].protein_g_per_unit} | "
        f"carbs_g/unit={c['ingredient'].carbs_g_per_unit} | fat_g/unit={c['ingredient'].fat_g_per_unit}"
        for c in candidates
    ]
    system_prompt = (
        "You are SokoPulse's procurement and nutrition assistant, selecting a weekly shopping basket of "
        "ingredients for a Kenyan institutional kitchen (school, hospital, or canteen), balancing nutrition "
        "targets against a hard budget ceiling and favouring the most cost-effective ('favourable') priced "
        "options.\n\n"
        "KENYAN DIET RULE — this basket must be able to build real Kenyan meals, not just hit macros: every "
        "Kenyan meal is a staple/starch (e.g. maize flour for ugali, rice, wheat flour for chapati/mandazi, "
        "bread, potatoes, sweet potatoes) plus one or more escorts (a protein — meat, fish, eggs, beans/legumes "
        "— and/or vegetables). You MUST select at least 2 staple/starch (category=grain) ingredients, at least "
        "2 protein or legume ingredients, at least 2 vegetable ingredients, and at least one fat/oil, so a full "
        "week of proper starch-plus-escort meals can be built — never a basket that is mostly proteins and "
        "vegetables with no staple, or mostly starch with no escort.\n\n"
        "Respond with strict JSON only, matching this shape: "
        '{"selected_ingredient_ids": [int, ...], "summary": "<2-3 sentence explanation>", '
        '"estimated_weekly_cost": <number>}. Select between 8 and 14 ingredients.'
    )
    user_prompt = (
        f"Institution type: {institution.type}. Headcount: {institution.headcount}. "
        f"Weekly ingredient budget (for the whole institution): KSh {weekly_budget}. "
        f"Daily nutrition targets per person: {profile.target_calories if profile else 'n/a'} kcal, "
        f"{profile.target_protein_g if profile else 'n/a'}g protein, "
        f"{profile.target_carbs_g if profile else 'n/a'}g carbs, {profile.target_fat_g if profile else 'n/a'}g fat. "
        f"Dietary restrictions: {profile.restrictions if profile else 'none'}.\n\n"
        f"Available ingredients (already filtered for restrictions):\n" + "\n".join(candidate_lines)
    )
    result = groq.chat_json(system_prompt, user_prompt, temperature=0.3, max_tokens=1200)

    by_id = {c["ingredient"].id: c for c in candidates}
    selected_ids = [i for i in result.get("selected_ingredient_ids", []) if i in by_id][:max_items]
    if not selected_ids:
        raise groq.GroqUnavailable("The AI returned no valid ingredient selections. Please try again.")

    # Safety net: a basket with no staple/starch can't build real Kenyan meals, regardless of what
    # the AI intended. If it forgot one, add the cheapest available grain from the same candidate
    # pool rather than rejecting the whole recommendation.
    if not any(by_id[i]["ingredient"].category == Ingredient.Category.GRAIN for i in selected_ids):
        grains = sorted(
            (c for c in candidates if c["ingredient"].category == Ingredient.Category.GRAIN),
            key=lambda c: c["price"],
        )
        if grains:
            selected_ids.append(grains[0]["ingredient"].id)

    selected = [
        _serialize_ingredient(by_id[i]["ingredient"], by_id[i]["price"], by_id[i]["supplier_name"])
        for i in selected_ids
    ]
    return {
        "summary": result.get("summary", "AI-recommended basket generated."),
        "selected_ingredients": selected,
        "estimated_weekly_cost": result.get("estimated_weekly_cost"),
        "weekly_budget_total": float(weekly_budget),
    }


# --------------------------------------------------------------------------
# 2. AI-generated weekly menu from a chosen (AI-recommended or manual) basket
# --------------------------------------------------------------------------

INSTITUTION_FOOD_CULTURE_NOTES = {
    "school": (
        "This is a Kenyan school. Keep meals simple, hearty, and true to standard Kenyan school feeding: "
        "breakfast is porridge (uji), or tea with bread/mandazi/boiled eggs/sweet potatoes/arrowroots — never "
        "a Western-style dish like scrambled eggs, an omelette, pancakes, or cereal served on its own. Lunch "
        "and supper are ugali, rice, githeri (maize & beans), or chapati, always paired with a stew, beans, "
        "vegetables, or meat as the escort."
    ),
    "hospital": (
        "This is a Kenyan hospital kitchen serving patients. Meals should still follow normal Kenyan staple-"
        "plus-escort structure (ugali/rice/bread/porridge with a protein or vegetable escort), just with "
        "portions and ingredient choices adjusted to be gentle and appropriate for patients, and strictly "
        "respecting any dietary restrictions given below."
    ),
    "canteen": (
        "This is a Kenyan staff/organisational canteen. A wider variety of standard Kenyan lunch and supper "
        "dishes is appropriate (ugali, rice, pilau, chapati, githeri, matoke), each with a proper escort. "
        "Breakfast should still be a typical Kenyan breakfast — porridge, bread/mandazi, tea, boiled eggs, or "
        "sweet potatoes/arrowroots — not a Western-style standalone egg dish."
    ),
}


def _staple_ingredient_ids(ingredients):
    return {i.id for i in ingredients if i.category == Ingredient.Category.GRAIN}


def generate_ai_weekly_menu(institution, ingredient_ids, week_start, source):
    ingredients = list(Ingredient.objects.filter(id__in=ingredient_ids))
    if not ingredients:
        raise ValueError("No valid ingredients were provided to build a menu from.")

    profile = getattr(institution, "dietary_profile", None)
    lines = [
        f"id={i.id} | {i.name} | category={i.category} | unit={i.unit} | kcal/unit={i.calories_per_unit} | "
        f"protein_g/unit={i.protein_g_per_unit} | carbs_g/unit={i.carbs_g_per_unit} | fat_g/unit={i.fat_g_per_unit}"
        for i in ingredients
    ]
    staple_ids = _staple_ingredient_ids(ingredients)
    staple_names = ", ".join(sorted(i.name for i in ingredients if i.id in staple_ids)) or "none available in this basket"
    culture_note = INSTITUTION_FOOD_CULTURE_NOTES.get(institution.type, INSTITUTION_FOOD_CULTURE_NOTES["canteen"])

    system_prompt = (
        "You are SokoPulse's menu-planning assistant. Build a full 7-day weekly menu (breakfast, lunch, dinner "
        "each day) for an institutional kitchen, using ONLY the ingredients provided — do not invent new "
        "ingredients.\n\n"
        "KENYAN DIET RULE (mandatory, every single meal): a real Kenyan meal is always a staple/starch base "
        "(examples from category=grain: ugali from maize flour, rice, chapati/mandazi from wheat flour, bread, "
        "potatoes, sweet potatoes) PLUS one or more escorts (a protein — meat, fish, eggs, beans/legumes — "
        "and/or vegetables, cooked as a stew or side). Never build a meal from escorts alone with no staple "
        "(e.g. 'beef and cabbage' on its own is wrong — it must be 'ugali with beef and cabbage stew'). Never "
        "serve a bare protein dish like 'scrambled eggs' as a whole meal — pair it with a staple such as bread, "
        "mandazi, sweet potatoes, or porridge. The staple ingredients available in this basket are: "
        f"{staple_names}. Use them across the week.\n\n"
        f"{culture_note}\n\n"
        "Combine ingredients into realistic, named Kenyan dishes (e.g. 'Ugali with beef & cabbage stew', "
        "'Githeri', 'Chapati with beans', 'Uji porridge', 'Rice & lentil stew'), reusing ingredients across "
        "days as needed, while keeping each day close to the given daily nutrition targets. Respond with "
        'strict JSON only: {"days": [{"day": 0, "meals": [{"slot": "breakfast", "dish_name": "...", '
        '"description": "...", "ingredients": [{"ingredient_id": 1, "quantity_per_portion": 0.15}]}, ...]}, '
        '...], "summary": "<2-3 sentence explanation of how the week balances nutrition and the ingredient '
        'basket>"}. `day` is 0=Monday .. 6=Sunday. quantity_per_portion is in the ingredient\'s own unit, per '
        "single person. Every lunch and dinner meal's ingredients list MUST include at least one staple "
        "ingredient id from the list above (unless the basket truly has none)."
    )
    user_prompt = (
        f"Institution type: {institution.type}. Headcount: {institution.headcount}. "
        f"Daily targets per person: {profile.target_calories if profile else 2000} kcal, "
        f"{profile.target_protein_g if profile else 50}g protein, {profile.target_carbs_g if profile else 250}g carbs, "
        f"{profile.target_fat_g if profile else 65}g fat. Restrictions: {profile.restrictions if profile else []}. "
        f"Week starting: {week_start}.\n\nIngredients available to build the menu from:\n" + "\n".join(lines)
    )
    result = groq.chat_json(system_prompt, user_prompt, temperature=0.5, max_tokens=3500)
    days_plan = result.get("days", [])
    if not days_plan:
        raise groq.GroqUnavailable("The AI returned an empty weekly plan. Please try again.")
    summary = result.get("summary", "AI-generated weekly menu.")

    MenuPlan.objects.filter(institution=institution, week_start=week_start).delete()
    plan = MenuPlan.objects.create(
        institution=institution, week_start=week_start, source=source,
        selected_ingredient_ids=[i.id for i in ingredients],
    )

    by_id = {i.id: i for i in ingredients}
    # Cheapest available staple, used to repair any meal the AI forgot to give one to.
    cheapest_staple = min(
        (i for i in ingredients if i.id in staple_ids),
        key=lambda i: i.default_price_per_unit, default=None,
    )
    county = institution.county
    total_cost = Decimal("0")
    total_cal = total_prot = total_carb = total_fat = 0.0
    repaired_meals = 0

    for day_entry in days_plan:
        day = day_entry["day"]
        for meal in day_entry["meals"]:
            valid_items = [m for m in meal.get("ingredients", []) if m.get("ingredient_id") in by_id]
            if not valid_items:
                continue

            # Kenyan-diet safeguard: lunch/dinner (and breakfast) must include a staple. If the AI
            # forgot one and the basket actually has one available, add it here rather than serving
            # an escort-only "meal" — this is enforced in code, not just requested in the prompt.
            has_staple = any(item["ingredient_id"] in staple_ids for item in valid_items)
            if not has_staple and cheapest_staple is not None:
                valid_items.append({"ingredient_id": cheapest_staple.id, "quantity_per_portion": 0.12})
                repaired_meals += 1

            recipe = Recipe.objects.create(
                name=meal.get("dish_name", "AI-suggested dish")[:200],
                description=meal.get("description", "")[:2000],
                meal_type=meal["slot"],
                portion_size="1 plate",
                ai_generated=True,
            )
            for item in valid_items:
                RecipeIngredient.objects.create(
                    recipe=recipe, ingredient=by_id[item["ingredient_id"]],
                    quantity_per_portion=Decimal(str(item.get("quantity_per_portion", 0.1))),
                )
            prof = recipe_profile(recipe, county)
            servings = institution.headcount or 1
            MenuItem.objects.create(
                menu_plan=plan, day=day, meal_slot=meal["slot"], recipe=recipe,
                servings=servings, estimated_cost=prof["cost"] * servings,
            )
            total_cost += prof["cost"] * servings
            total_cal += float(prof["calories"])
            total_prot += float(prof["protein_g"])
            total_carb += float(prof["carbs_g"])
            total_fat += float(prof["fat_g"])

    plan.total_cost = round(total_cost, 2)
    plan.nutrient_summary = {
        "avg_daily_calories": round(total_cal / DAYS_PER_WEEK, 1),
        "avg_daily_protein_g": round(total_prot / DAYS_PER_WEEK, 1),
        "avg_daily_carbs_g": round(total_carb / DAYS_PER_WEEK, 1),
        "avg_daily_fat_g": round(total_fat / DAYS_PER_WEEK, 1),
        "target_calories": profile.target_calories if profile else None,
        "target_protein_g": profile.target_protein_g if profile else None,
        "target_carbs_g": profile.target_carbs_g if profile else None,
        "target_fat_g": profile.target_fat_g if profile else None,
    }
    plan.ai_summary = summary
    notes = "Generated by AI from the selected product basket."
    if repaired_meals:
        notes += (
            f" {repaired_meals} meal(s) were missing a staple/starch and had one added automatically "
            "to keep every meal to a proper Kenyan staple-plus-escort structure."
        )
    plan.generation_notes = notes
    plan.save()
    return plan


# --------------------------------------------------------------------------
# 3. Supplier insights — demand & pricing competitiveness
# --------------------------------------------------------------------------

def build_supplier_insights(supplier):
    cutoff = date.today() - timedelta(days=28)
    listings = SupplierListing.objects.filter(supplier=supplier, is_active=True).select_related("ingredient")
    if not listings:
        return {"headline": "You don't have any active listings yet.", "insights": []}

    stats = []
    for listing in listings:
        ingredient = listing.ingredient
        demand_qty = DemandSignal.objects.filter(ingredient=ingredient, window_end__gte=cutoff).aggregate(
            total=Sum("forecast_quantity"))["total"] or 0
        competitor_qs = SupplierListing.objects.filter(ingredient=ingredient, is_active=True).exclude(supplier=supplier)
        competitor_prices = [c.price_per_unit for c in competitor_qs]
        market_min = min(competitor_prices) if competitor_prices else None
        market_avg = (sum(competitor_prices) / len(competitor_prices)) if competitor_prices else None
        stats.append({
            "ingredient": ingredient.name, "unit": ingredient.unit, "your_price": listing.price_per_unit,
            "recent_demand": float(demand_qty), "competitor_count": len(competitor_prices),
            "market_min": float(market_min) if market_min is not None else None,
            "market_avg": float(market_avg) if market_avg is not None else None,
        })

    lines = [
        f"{s['ingredient']}: your price={s['your_price']}/{s['unit']}, recent institutional demand={s['recent_demand']}{s['unit']}, "
        f"competing suppliers={s['competitor_count']}, market min={s['market_min']}, market avg={s['market_avg']}"
        for s in stats
    ]
    system_prompt = (
        "You are SokoPulse's market-intelligence assistant for produce suppliers. Given recent institutional "
        "demand and competitor pricing for a supplier's own listings, identify which products are in high "
        "demand, where their pricing is uncompetitive, and where there's a clear opportunity. Respond with "
        'strict JSON only: {"headline": "<one sentence>", "insights": [{"ingredient": "...", "message": "...", '
        '"action": "..."}]}. Keep each message and action under 30 words. Include at most 6 insights, prioritised by importance.'
    )
    user_prompt = f"Supplier: {supplier.name} ({supplier.county}).\n\n" + "\n".join(lines)
    result = groq.chat_json(system_prompt, user_prompt, temperature=0.4, max_tokens=1200)
    return {"headline": result.get("headline", ""), "insights": result.get("insights", [])}


# --------------------------------------------------------------------------
# 4. Farmer insights — demand trends & supply gaps
# --------------------------------------------------------------------------

def build_farmer_insights(farmer):
    recent_cutoff = date.today() - timedelta(days=14)
    prior_cutoff = date.today() - timedelta(days=42)

    county_signals = DemandSignal.objects.filter(county__iexact=farmer.county)
    recent = county_signals.filter(window_end__gte=recent_cutoff)
    prior = county_signals.filter(window_end__gte=prior_cutoff, window_end__lt=recent_cutoff)

    by_ingredient_recent = defaultdict(float)
    for s in recent.select_related("ingredient"):
        by_ingredient_recent[s.ingredient] += float(s.forecast_quantity)
    by_ingredient_prior = defaultdict(float)
    for s in prior.select_related("ingredient"):
        by_ingredient_prior[s.ingredient] += float(s.forecast_quantity)

    committed_by_ingredient = defaultdict(float)
    for c in SupplyCommitment.objects.filter(farmer=farmer).select_related("demand_signal__ingredient"):
        committed_by_ingredient[c.demand_signal.ingredient] += float(c.quantity_committed)

    stats = []
    for ingredient, qty in by_ingredient_recent.items():
        prior_qty = by_ingredient_prior.get(ingredient, 0)
        trend = "increasing" if qty > prior_qty * 1.1 else ("decreasing" if qty < prior_qty * 0.9 else "stable")
        stats.append({
            "ingredient": ingredient.name, "unit": ingredient.unit, "recent_demand": qty,
            "prior_demand": prior_qty, "trend": trend,
            "committed": committed_by_ingredient.get(ingredient, 0),
            "gap": max(qty - committed_by_ingredient.get(ingredient, 0), 0),
        })

    if not stats:
        return {"headline": "No recent demand signals in your county yet.", "insights": []}

    lines = [
        f"{s['ingredient']}: recent demand={s['recent_demand']}{s['unit']}, prior period={s['prior_demand']}{s['unit']}, "
        f"trend={s['trend']}, your commitments so far={s['committed']}{s['unit']}, uncommitted gap={s['gap']}{s['unit']}"
        for s in stats
    ]
    system_prompt = (
        "You are SokoPulse's farm-planning assistant. Given local institutional demand trends and a farmer's "
        "current supply commitments, recommend what to prioritise planting/harvesting or committing supply "
        "for next. Respond with strict JSON only: "
        '{"headline": "<one sentence>", "insights": [{"ingredient": "...", "message": "...", "action": "..."}]}. '
        "Keep each message and action under 30 words. Include at most 6 insights, prioritised by uncommitted gap and rising trend."
    )
    user_prompt = f"Farmer: {farmer.name}, county: {farmer.county}, crop focus: {farmer.crop_focus}.\n\n" + "\n".join(lines)
    result = groq.chat_json(system_prompt, user_prompt, temperature=0.4, max_tokens=1200)
    return {"headline": result.get("headline", ""), "insights": result.get("insights", [])}


# --------------------------------------------------------------------------
# 5. General contextual assistant
# --------------------------------------------------------------------------

def answer_question(user, question):
    role = user.role
    context = ""
    if role == "institution" and hasattr(user, "institution"):
        inst = user.institution
        profile = getattr(inst, "dietary_profile", None)
        latest_plan = inst.menu_plans.order_by("-week_start").first()
        context = (
            f"Institution: {inst.name} ({inst.type}), headcount {inst.headcount}, budget/meal KSh {inst.budget_per_meal}. "
            f"Dietary targets: {profile.target_calories if profile else 'n/a'} kcal, restrictions {profile.restrictions if profile else []}. "
            f"Latest menu plan: week of {latest_plan.week_start if latest_plan else 'none yet'}, status {latest_plan.status if latest_plan else 'n/a'}."
        )
    elif role == "supplier" and hasattr(user, "supplier"):
        sup = user.supplier
        context = f"Supplier: {sup.name} ({sup.county}), {sup.listings.filter(is_active=True).count()} active listings."
    elif role == "farmer" and hasattr(user, "farmer"):
        farmer = user.farmer
        context = f"Farmer: {farmer.name} ({farmer.county}), crop focus: {farmer.crop_focus}."

    system_prompt = (
        "You are the in-app assistant for SokoPulse, a nutrition-planning and procurement platform connecting "
        "institutions, suppliers, and farmers. Answer the user's question helpfully and concisely (under 120 words), "
        "using only the account context given — never invent specific figures you weren't given. If the question "
        "needs data you don't have, say so plainly and suggest where in the app they can find it."
    )
    user_prompt = f"Account context: {context or 'No account context available.'}\n\nQuestion: {question}"

    answer = groq.chat_text(system_prompt, user_prompt, temperature=0.5, max_tokens=400)
    return {"answer": answer}
