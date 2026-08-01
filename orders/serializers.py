from rest_framework import serializers
from .models import ProduceOrder, ProduceOrderItem
from nutrition.serializers import IngredientSerializer
from core.geo import estimate_distance_and_eta


class ProduceOrderItemSerializer(serializers.ModelSerializer):
    ingredient_detail = IngredientSerializer(source="ingredient", read_only=True)

    class Meta:
        model = ProduceOrderItem
        fields = ["id", "ingredient", "ingredient_detail", "quantity", "unit_price", "subtotal"]


class ProduceOrderSerializer(serializers.ModelSerializer):
    items = ProduceOrderItemSerializer(many=True, read_only=True)
    institution_name = serializers.CharField(source="institution.name", read_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    supplier_county = serializers.CharField(source="supplier.county", read_only=True)
    institution_county = serializers.CharField(source="institution.county", read_only=True)
    distance_km = serializers.SerializerMethodField()
    estimated_delivery_hours = serializers.SerializerMethodField()

    class Meta:
        model = ProduceOrder
        fields = [
            "id", "institution", "institution_name", "institution_county", "menu_plan",
            "supplier", "supplier_name", "supplier_county",
            "status", "total_value", "platform_margin", "is_paid", "payment_method",
            "payment_reference", "paid_at", "confirmed_at", "delivered_at", "cancelled_at",
            "distance_km", "estimated_delivery_hours", "created_at", "items",
        ]
        read_only_fields = [f for f in fields if f != "status"]

    def _geo(self, obj):
        if not hasattr(obj, "_geo_cache"):
            obj._geo_cache = estimate_distance_and_eta(obj.supplier.county, obj.institution.county)
        return obj._geo_cache

    def get_distance_km(self, obj):
        return self._geo(obj)["distance_km"]

    def get_estimated_delivery_hours(self, obj):
        return self._geo(obj)["estimated_delivery_hours"]


class OrderCheckoutSerializer(serializers.Serializer):
    """Payload for the institution's own checkout/record-payment action. No live gateway is
    wired in — this just records that payment for the order was collected, and how."""
    payment_method = serializers.ChoiceField(choices=ProduceOrder.PaymentMethod.choices)
    payment_reference = serializers.CharField(required=False, allow_blank=True, max_length=64)
