from django.conf import settings
from django.db import models


class Farmer(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="farmer")
    name = models.CharField(max_length=200)
    county = models.CharField(max_length=64, blank=True)
    crop_focus = models.CharField(max_length=200, blank=True, help_text="e.g. Cabbage, Tomatoes")
    contact_phone = models.CharField(max_length=32, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class DemandSignal(models.Model):
    ingredient = models.ForeignKey("nutrition.Ingredient", on_delete=models.CASCADE, related_name="demand_signals")
    forecast_quantity = models.DecimalField(max_digits=10, decimal_places=2)
    county = models.CharField(max_length=64, blank=True)
    window_start = models.DateField()
    window_end = models.DateField()
    source_menu_plan = models.ForeignKey(
        "menus.MenuPlan", on_delete=models.SET_NULL, null=True, blank=True, related_name="demand_signals"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.ingredient.name}: {self.forecast_quantity}{self.ingredient.unit} by {self.window_end}"


class SupplyCommitment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        DELIVERED = "delivered", "Delivered"

    farmer = models.ForeignKey(Farmer, on_delete=models.CASCADE, related_name="commitments")
    demand_signal = models.ForeignKey(DemandSignal, on_delete=models.CASCADE, related_name="commitments")
    quantity_committed = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.farmer.name} → {self.quantity_committed} ({self.status})"
