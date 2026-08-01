from rest_framework import serializers
from .models import Farmer, DemandSignal, SupplyCommitment
from nutrition.serializers import IngredientSerializer


class FarmerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Farmer
        fields = ["id", "name", "county", "crop_focus", "contact_phone", "created_at"]
        read_only_fields = ["id", "created_at"]


class DemandSignalSerializer(serializers.ModelSerializer):
    ingredient_detail = IngredientSerializer(source="ingredient", read_only=True)
    committed_quantity = serializers.SerializerMethodField()

    class Meta:
        model = DemandSignal
        fields = [
            "id", "ingredient", "ingredient_detail", "forecast_quantity", "county",
            "window_start", "window_end", "created_at", "committed_quantity",
        ]

    def get_committed_quantity(self, obj):
        return sum((c.quantity_committed for c in obj.commitments.all()), start=0)


class SupplyCommitmentSerializer(serializers.ModelSerializer):
    demand_signal_detail = DemandSignalSerializer(source="demand_signal", read_only=True)
    farmer_name = serializers.CharField(source="farmer.name", read_only=True)

    class Meta:
        model = SupplyCommitment
        fields = ["id", "demand_signal", "demand_signal_detail", "farmer_name", "quantity_committed", "status", "created_at"]
        read_only_fields = ["id", "farmer_name", "created_at"]
