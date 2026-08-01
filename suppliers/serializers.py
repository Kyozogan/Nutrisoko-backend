from rest_framework import serializers
from .models import Supplier, SupplierListing
from nutrition.serializers import IngredientSerializer


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ["id", "name", "county", "contact_phone", "verified", "created_at"]
        read_only_fields = ["id", "verified", "created_at"]


class SupplierListingSerializer(serializers.ModelSerializer):
    ingredient_detail = IngredientSerializer(source="ingredient", read_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)

    class Meta:
        model = SupplierListing
        fields = [
            "id", "ingredient", "ingredient_detail", "supplier", "supplier_name", "price_per_unit",
            "quantity_available", "available_from", "available_to", "is_active", "created_at",
        ]
        read_only_fields = ["id", "supplier", "supplier_name", "created_at"]
