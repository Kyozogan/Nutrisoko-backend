from django.conf import settings
from django.db import models


class Notification(models.Model):
    """
    A single in-app notification for one user. Created by other apps via
    notifications.services.notify()/notify_many() whenever something the
    recipient cares about happens — a produce order being placed, its status
    changing, or a new demand signal appearing in their county.
    """

    class Level(models.TextChoices):
        INFO = "info", "Info"
        SUCCESS = "success", "Success"
        WARNING = "warning", "Warning"

    class NotificationType(models.TextChoices):
        ORDER_PLACED = "order_placed", "Order placed"
        ORDER_STATUS = "order_status", "Order status changed"
        DEMAND_SIGNAL = "demand_signal", "New demand signal"
        MENU_APPROVED = "menu_approved", "Menu approved"
        SYSTEM = "system", "System"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    notification_type = models.CharField(
        max_length=32, choices=NotificationType.choices, default=NotificationType.SYSTEM
    )
    level = models.CharField(max_length=10, choices=Level.choices, default=Level.INFO)
    title = models.CharField(max_length=200)
    message = models.CharField(max_length=500, blank=True)
    link = models.CharField(
        max_length=200, blank=True,
        help_text="Frontend route this notification should take the user to when clicked, e.g. /institution/orders.",
    )
    related_order = models.ForeignKey(
        "orders.ProduceOrder", on_delete=models.CASCADE, null=True, blank=True, related_name="notifications"
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["recipient", "is_read"])]

    def __str__(self):
        return f"{self.recipient.username}: {self.title}"
