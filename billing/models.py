"""
A minimal, self-contained subscription ledger.

There is no live payment gateway wired in here — "subscribing" records a
payment as confirmed and opens/extends an active window. That single call
site (services.create_subscription) is exactly where a real gateway
(M-Pesa STK push, Stripe, Paystack, etc.) would be plugged in later; nothing
else in the codebase needs to change to add one.
"""
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Subscription(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscriptions")
    role = models.CharField(max_length=20, help_text="Snapshot of the user's role at the time of payment.")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reference = models.CharField(max_length=64, unique=True, default=uuid.uuid4)
    started_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.user.username} — {self.reference} (expires {self.expires_at:%Y-%m-%d})"

    @property
    def is_active(self) -> bool:
        return self.expires_at > timezone.now()
