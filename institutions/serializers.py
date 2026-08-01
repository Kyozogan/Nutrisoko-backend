from rest_framework import serializers
from .models import Institution, Site, DietaryProfile


class DietaryProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = DietaryProfile
        fields = ["id", "restrictions", "target_calories", "target_protein_g", "target_carbs_g", "target_fat_g", "guideline_reference"]


class SiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Site
        fields = ["id", "name", "address"]


class InstitutionSerializer(serializers.ModelSerializer):
    dietary_profile = DietaryProfileSerializer(read_only=True)
    sites = SiteSerializer(many=True, read_only=True)

    class Meta:
        model = Institution
        fields = [
            "id", "name", "type", "county", "headcount",
            "billing_cycle", "budget_mode", "budget_total_per_cycle", "budget_per_meal",
            "budget_breakfast", "budget_lunch", "budget_supper",
            "contact_phone", "created_at", "dietary_profile", "sites",
        ]
        read_only_fields = ["id", "created_at", "budget_per_meal"]

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        # budget_per_meal is derived, not directly editable — keep it in sync whenever anything
        # that feeds it changes (which meal budgets are set, the cycle total, or the mode/cycle itself).
        budget_inputs = ("budget_breakfast", "budget_lunch", "budget_supper", "budget_total_per_cycle", "budget_mode", "billing_cycle")
        if any(k in validated_data for k in budget_inputs):
            instance.recompute_budget_per_meal()
            instance.save(update_fields=["budget_per_meal"])
        return instance
