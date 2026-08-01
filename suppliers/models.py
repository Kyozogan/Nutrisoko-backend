from django.conf import settings
from django.db import models


class Supplier(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="supplier")
    name = models.CharField(max_length=200)
    county = models.CharField(max_length=64, blank=True)
    contact_phone = models.CharField(max_length=32, blank=True)
    verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class SupplierListing(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name="listings")
    ingredient = models.ForeignKey("nutrition.Ingredient", on_delete=models.CASCADE, related_name="listings")
    price_per_unit = models.DecimalField(max_digits=10, decimal_places=2)
    quantity_available = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    available_from = models.DateField(null=True, blank=True)
    available_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["price_per_unit"]

    def __str__(self):
        return f"{self.ingredient.name} — {self.supplier.name} @ {self.price_per_unit}"
