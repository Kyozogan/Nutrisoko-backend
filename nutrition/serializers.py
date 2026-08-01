from rest_framework import serializers
from .models import Ingredient, Recipe, RecipeIngredient
from .utils import recipe_profile


class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = [
            "id", "name", "unit", "category", "calories_per_unit", "protein_g_per_unit",
            "carbs_g_per_unit", "fat_g_per_unit", "default_price_per_unit",
            "contains_meat", "contains_dairy", "contains_gluten",
        ]


class RecipeIngredientSerializer(serializers.ModelSerializer):
    ingredient = IngredientSerializer(read_only=True)

    class Meta:
        model = RecipeIngredient
        fields = ["id", "ingredient", "quantity_per_portion"]


class RecipeSerializer(serializers.ModelSerializer):
    recipe_ingredients = RecipeIngredientSerializer(source="recipeingredient_set", many=True, read_only=True)
    profile = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = [
            "id", "name", "description", "meal_type", "portion_size", "prep_notes",
            "recipe_ingredients", "profile", "contains_meat", "contains_dairy", "contains_gluten", "ai_generated",
        ]

    def get_profile(self, obj):
        county = self.context.get("county")
        return recipe_profile(obj, county)
