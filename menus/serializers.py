from rest_framework import serializers
from .models import MenuPlan, MenuItem
from nutrition.serializers import RecipeSerializer


class MenuItemSerializer(serializers.ModelSerializer):
    recipe_detail = RecipeSerializer(source="recipe", read_only=True)
    day_display = serializers.CharField(source="get_day_display", read_only=True)

    class Meta:
        model = MenuItem
        fields = ["id", "day", "day_display", "meal_slot", "recipe", "recipe_detail", "servings", "estimated_cost"]


class MenuPlanSerializer(serializers.ModelSerializer):
    items = MenuItemSerializer(many=True, read_only=True)
    institution_name = serializers.CharField(source="institution.name", read_only=True)

    class Meta:
        model = MenuPlan
        fields = [
            "id", "institution", "institution_name", "week_start", "status", "source",
            "selected_ingredient_ids", "ai_summary", "total_cost", "duplicated_from",
            "nutrient_summary", "generation_notes", "created_at", "approved_at", "items",
        ]
        read_only_fields = ["id", "institution", "institution_name", "status", "source", "selected_ingredient_ids", "ai_summary", "total_cost", "duplicated_from", "nutrient_summary", "generation_notes", "created_at", "approved_at", "items"]


class GenerateMenuPlanSerializer(serializers.Serializer):
    week_start = serializers.DateField()


class DuplicateMenuPlanSerializer(serializers.Serializer):
    week_start = serializers.DateField()


class PlaceOrdersSerializer(serializers.Serializer):
    # {ingredient_id: supplier_id} — DictField keys arrive as strings from JSON; the service
    # layer checks both string and int forms of each key against the aggregated ingredient needs.
    selections = serializers.DictField(child=serializers.IntegerField())
