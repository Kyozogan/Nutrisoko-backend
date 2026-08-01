from rest_framework import permissions
from rest_framework.views import APIView
from rest_framework.response import Response

from accounts.permissions import IsAdminRole
from configuration.models import SystemConfiguration
from .models import Subscription
from .services import billing_status, create_subscription


class BillingStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(billing_status(request.user))


class SubscribeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        cfg = SystemConfiguration.load()
        if not cfg.payments_enabled:
            return Response({"detail": "Payments are not currently enabled."}, status=400)
        create_subscription(request.user)
        return Response(billing_status(request.user), status=201)


class AdminSubscriptionListView(APIView):
    """All subscriptions, newest first — for the admin panel's Subscriptions page."""
    permission_classes = [IsAdminRole]

    def get(self, request):
        subs = Subscription.objects.select_related("user").order_by("-started_at")[:200]
        return Response([
            {
                "id": s.id, "username": s.user.username, "role": s.role,
                "amount": str(s.amount), "reference": s.reference,
                "started_at": s.started_at.isoformat(), "expires_at": s.expires_at.isoformat(),
                "is_active": s.is_active,
            }
            for s in subs
        ])
