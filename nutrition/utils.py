"""Helpers for computing a recipe's per-portion cost and nutrition profile."""
from decimal import Decimal


def best_price_for_ingredient(ingredient, county=None):
    """Return the cheapest active supplier price for an ingredient, preferring
    listings in the given county, falling back to the ingredient's default price."""
    from suppliers.models import SupplierListing

    qs = SupplierListing.objects.filter(ingredient=ingredient, is_active=True)
    if county:
        local = qs.filter(supplier__county__iexact=county).order_by("price_per_unit").first()
        if local:
            return local.price_per_unit
    cheapest = qs.order_by("price_per_unit").first()
    if cheapest:
        return cheapest.price_per_unit
    return ingredient.default_price_per_unit or Decimal("0")


def recipe_profile(recipe, county=None):
    """Compute { cost, calories, protein_g, carbs_g, fat_g } for one portion of a recipe."""
    cost = Decimal("0")
    calories = Decimal("0")
    protein = Decimal("0")
    carbs = Decimal("0")
    fat = Decimal("0")

    for ri in recipe.recipeingredient_set.select_related("ingredient").all():
        qty = ri.quantity_per_portion
        ing = ri.ingredient
        price = best_price_for_ingredient(ing, county)
        cost += qty * price
        calories += qty * ing.calories_per_unit
        protein += qty * ing.protein_g_per_unit
        carbs += qty * ing.carbs_g_per_unit
        fat += qty * ing.fat_g_per_unit

    return {
        "cost": round(cost, 2),
        "calories": round(calories, 1),
        "protein_g": round(protein, 1),
        "carbs_g": round(carbs, 1),
        "fat_g": round(fat, 1),
    }


def recipe_violates_restrictions(recipe, restrictions):
    restrictions = [r.lower() for r in (restrictions or [])]
    if "vegetarian" in restrictions or "vegan" in restrictions:
        if recipe.contains_meat:
            return True
    if "vegan" in restrictions and recipe.contains_dairy:
        return True
    if "dairy-free" in restrictions and recipe.contains_dairy:
        return True
    if "gluten-free" in restrictions and recipe.contains_gluten:
        return True
    return False
