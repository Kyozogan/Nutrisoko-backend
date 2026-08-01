from django.contrib import admin
from django.urls import reverse
from django.shortcuts import redirect

from .models import SystemConfiguration


@admin.register(SystemConfiguration)
class SystemConfigurationAdmin(admin.ModelAdmin):
    """Singleton admin: always edits the one row, never lists/adds/deletes."""

    fieldsets = (
        ("AI engine (Groq)", {
            "fields": ("groq_api_key", "groq_model", "groq_timeout_seconds"),
            "description": (
                "Every AI feature in SokoPulse (menu planning, product recommendations, "
                "supplier/farmer insights, and the in-app assistant) calls Groq directly — "
                "there is no rule-based fallback. If the key below is missing or invalid, "
                "those features will return an error instead of a result."
            ),
        }),
        ("Platform", {
            "fields": ("platform_margin_percent", "support_email", "site_name"),
        }),
        ("Subscriptions / payments", {
            "fields": (
                "payments_enabled", "subscription_price_institution",
                "subscription_price_supplier", "subscription_price_farmer",
                "subscription_period_days",
            ),
            "description": (
                "When 'payments enabled' is on, institutions/suppliers/farmers must have an active "
                "subscription to use the premium actions listed in the Subscriptions section of this "
                "admin — everything else in the app keeps working normally either way."
            ),
        }),
        ("Last updated", {"fields": ("updated_at",)}),
    )
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        # Block "Add" once the singleton row exists.
        return not SystemConfiguration.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        # Skip the list page entirely — go straight to the single config row.
        SystemConfiguration.load()
        return redirect(reverse("admin:configuration_systemconfiguration_change", args=[1]))
