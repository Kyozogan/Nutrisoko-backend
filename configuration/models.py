"""
A single, admin-editable row holding operational configuration that used to
live only in environment variables (or hard-coded constants) — chiefly the
Groq API key, but also a couple of other values that materially affect the
platform's behaviour. Everything here is managed from the Django admin at
/admin/configuration/systemconfiguration/, so it can be changed without a
redeploy.
"""
import os
from decimal import Decimal

from django.db import models


class SystemConfiguration(models.Model):
    """Singleton: there is always exactly one row, with pk=1."""

    # --- AI (Groq) ---------------------------------------------------------
    groq_api_key = models.CharField(
        max_length=200, blank=True, default="",
        help_text="Secret key from console.groq.com. Required for every AI feature — "
                   "menu planning, product recommendations, supplier/farmer insights, "
                   "and the in-app assistant. Leave blank to disable AI features.",
    )
    groq_model = models.CharField(
        max_length=100, default="llama-3.3-70b-versatile",
        help_text="Groq model id used for all AI calls (e.g. llama-3.3-70b-versatile).",
    )
    groq_timeout_seconds = models.PositiveIntegerField(
        default=30, help_text="How long to wait for a Groq response before treating the call as failed.",
    )

    # --- Business / platform performance -----------------------------------
    platform_margin_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("8.00"),
        help_text="Service fee applied to every produce order placed through the platform, as a percentage (e.g. 8.00 = 8%).",
    )
    support_email = models.EmailField(
        blank=True, default="hello@sokopulse.co.ke",
        help_text="Shown to users and used as the reply-to for system notifications.",
    )
    site_name = models.CharField(max_length=100, default="SokoPulse")

    # --- Subscriptions / payments --------------------------------------------
    payments_enabled = models.BooleanField(
        default=False,
        help_text="When ON, the premium actions below require an active subscription. When OFF, "
                   "every account can use the full platform for free — no payment modal is ever shown.",
    )
    subscription_price_institution = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("5000.00"),
        help_text="Monthly subscription price (KSh) for institution accounts.",
    )
    subscription_price_supplier = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("2500.00"),
        help_text="Monthly subscription price (KSh) for supplier accounts.",
    )
    subscription_price_farmer = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("1000.00"),
        help_text="Monthly subscription price (KSh) for farmer accounts.",
    )
    subscription_period_days = models.PositiveIntegerField(
        default=30, help_text="How many days a subscription payment covers.",
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "System configuration"
        verbose_name_plural = "System configuration"

    def __str__(self):
        return "System configuration"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass  # the singleton is never deleted

    def price_for_role(self, role: str) -> Decimal:
        return {
            "institution": self.subscription_price_institution,
            "supplier": self.subscription_price_supplier,
            "farmer": self.subscription_price_farmer,
        }.get(role, Decimal("0.00"))

    @classmethod
    def load(cls) -> "SystemConfiguration":
        """Fetch the singleton row, creating it on first use.

        On first creation only, GROQ_API_KEY / GROQ_MODEL / GROQ_TIMEOUT_SECONDS
        environment variables (if set) are used to seed the initial values, so
        existing env-var based deployments keep working until an admin edits
        the values here. After that, this row is always the source of truth.
        """
        obj, _created = cls.objects.get_or_create(pk=1, defaults={
            "groq_api_key": os.environ.get("GROQ_API_KEY", ""),
            "groq_model": os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
            "groq_timeout_seconds": int(os.environ.get("GROQ_TIMEOUT_SECONDS", "30")),
        })
        return obj
