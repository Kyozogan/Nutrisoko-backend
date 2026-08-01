from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Sum, Count
from django.utils import timezone

from accounts.permissions import IsAdminRole
from accounts.models import User
from institutions.models import Institution
from suppliers.models import Supplier
from farmers.models import Farmer
from menus.models import MenuPlan
from orders.models import ProduceOrder
from billing.models import Subscription

from .models import SystemConfiguration
from .serializers import SystemConfigurationSerializer


class SystemConfigurationView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        return Response(SystemConfigurationSerializer(SystemConfiguration.load()).data)

    def put(self, request):
        serializer = SystemConfigurationSerializer(
            SystemConfiguration.load(), data=request.data, partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class SystemOverviewView(APIView):
    """Aggregate counts for the admin panel's overview page — 'general control of full system operations'."""
    permission_classes = [IsAdminRole]

    def get(self, request):
        cfg = SystemConfiguration.load()
        now = timezone.now()

        all_subs = Subscription.objects.all()
        total_revenue = all_subs.aggregate(total=Sum("amount"))["total"] or 0
        active_subs = all_subs.filter(expires_at__gt=now)
        active_revenue = active_subs.aggregate(total=Sum("amount"))["total"] or 0
        by_role = list(
            all_subs.values("role").annotate(revenue=Sum("amount"), count=Count("id")).order_by("-revenue")
        )
        order_margin_total = ProduceOrder.objects.aggregate(total=Sum("platform_margin"))["total"] or 0

        return Response({
            "counts": {
                "institutions": Institution.objects.count(),
                "suppliers": Supplier.objects.count(),
                "farmers": Farmer.objects.count(),
                "menu_plans": MenuPlan.objects.count(),
                "produce_orders": ProduceOrder.objects.count(),
                "active_subscriptions": active_subs.count(),
                "total_users": User.objects.count(),
            },
            "revenue": {
                "subscriptions_total": total_revenue,
                "subscriptions_active_total": active_revenue,
                "subscriptions_by_role": by_role,
                "order_platform_margin_total": order_margin_total,
            },
            "ai_configured": bool(cfg.groq_api_key),
            "payments_enabled": cfg.payments_enabled,
        })
