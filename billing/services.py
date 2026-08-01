"""
Subscription gating used by the "premium" actions across the app (see the
GATED_ACTIONS description in configuration.admin and the docstring on
requires_active_subscription below for exactly which actions those are).
"""
import uuid
from datetime import timedelta

from django.utils import timezone

from configuration.models import SystemConfiguration
from .models import Subscription


class SubscriptionRequired(Exception):
    """Raised when payments are enabled and the user has no active subscription."""


def has_active_subscription(user) -> bool:
    return Subscription.objects.filter(user=user, expires_at__gt=timezone.now()).exists()


def current_subscription(user):
    return Subscription.objects.filter(user=user, expires_at__gt=timezone.now()).order_by("-expires_at").first()


def billing_status(user) -> dict:
    cfg = SystemConfiguration.load()
    sub = current_subscription(user)
    return {
        "payments_enabled": cfg.payments_enabled,
        "has_active_subscription": (not cfg.payments_enabled) or sub is not None,
        "price": str(cfg.price_for_role(user.role)),
        "period_days": cfg.subscription_period_days,
        "expires_at": sub.expires_at.isoformat() if sub else None,
    }


def create_subscription(user) -> Subscription:
    """Mock payment confirmation: records the payment as received and opens/extends the active window."""
    cfg = SystemConfiguration.load()
    price = cfg.price_for_role(user.role)
    now = timezone.now()
    existing = current_subscription(user)
    start_from = existing.expires_at if existing else now
    expires_at = start_from + timedelta(days=cfg.subscription_period_days)
    return Subscription.objects.create(
        user=user, role=user.role, amount=price,
        reference=f"MOCK-{uuid.uuid4().hex[:10].upper()}", expires_at=expires_at,
    )


def require_active_subscription(user) -> None:
    """
    Raises SubscriptionRequired if payments are enabled system-wide and this
    user doesn't currently have one. A no-op whenever payments are disabled.
    """
    cfg = SystemConfiguration.load()
    if not cfg.payments_enabled:
        return
    if not has_active_subscription(user):
        raise SubscriptionRequired(
            "This feature requires an active SokoPulse subscription. Subscribe to continue."
        )
