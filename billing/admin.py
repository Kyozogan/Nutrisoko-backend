from django.contrib import admin

from .models import Subscription


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "amount", "started_at", "expires_at", "is_active")
    list_filter = ("role",)
    search_fields = ("user__username", "user__email", "reference")
    readonly_fields = ("reference", "started_at")

    def has_add_permission(self, request):
        return False  # subscriptions are only created via the mock-payment flow
