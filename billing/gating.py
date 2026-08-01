"""
One-line gate for use at the top of any view that performs a "premium"
action. Returns a 402 Response (with subscription_required: true, which the
frontend uses to pop the payment modal) if a subscription is missing and
required; otherwise returns None and the view proceeds normally.
"""
from rest_framework.response import Response

from .services import require_active_subscription, SubscriptionRequired


def subscription_gate(request):
    try:
        require_active_subscription(request.user)
    except SubscriptionRequired as exc:
        return Response({"detail": str(exc), "subscription_required": True}, status=402)
    return None
