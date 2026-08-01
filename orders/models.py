from django.db import models


class ProduceOrder(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    class PaymentMethod(models.TextChoices):
        MPESA = "mpesa", "M-Pesa"
        BANK_TRANSFER = "bank_transfer", "Bank transfer"
        CARD = "card", "Card"
        CASH = "cash", "Cash"

    institution = models.ForeignKey("institutions.Institution", on_delete=models.CASCADE, related_name="orders")
    menu_plan = models.ForeignKey("menus.MenuPlan", on_delete=models.SET_NULL, null=True, blank=True, related_name="orders")
    supplier = models.ForeignKey("suppliers.Supplier", on_delete=models.CASCADE, related_name="orders")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    total_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    platform_margin = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    # Payment placeholder: no live gateway is wired in yet — checkout() in views.py is the single
    # call site where one (M-Pesa STK push, card, etc.) would plug in later, same pattern as
    # billing.services.create_subscription for platform subscriptions.
    is_paid = models.BooleanField(default=False)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, blank=True)
    payment_reference = models.CharField(max_length=64, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    # Set as the order moves through its lifecycle — feeds the step-by-step tracking timeline
    # (see orders.services.build_order_tracking) rather than a live moving map.
    confirmed_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.id} — {self.institution.name} → {self.supplier.name}"


class ProduceOrderItem(models.Model):
    order = models.ForeignKey(ProduceOrder, on_delete=models.CASCADE, related_name="items")
    ingredient = models.ForeignKey("nutrition.Ingredient", on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.ingredient.name} x{self.quantity}"
