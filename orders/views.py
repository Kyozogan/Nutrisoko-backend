from django.utils import timezone
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, PermissionDenied
from rest_framework.response import Response

from billing.services import require_active_subscription, SubscriptionRequired
from notifications.models import Notification
from notifications.services import notify
from .models import ProduceOrder
from .serializers import ProduceOrderSerializer, OrderCheckoutSerializer
from .services import build_order_tracking


class SubscriptionRequiredAPIException(APIException):
    """402 with the same {detail, subscription_required} shape the frontend expects everywhere else."""
    status_code = 402
    default_detail = "An active subscription is required to update order status."

    def __init__(self, detail=None):
        message = str(detail or self.default_detail)
        super().__init__({"detail": message, "subscription_required": True})


class ProduceOrderViewSet(viewsets.ModelViewSet):
    serializer_class = ProduceOrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "patch", "post", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        if user.role == "institution":
            return ProduceOrder.objects.filter(institution=user.institution).prefetch_related("items__ingredient")
        if user.role == "supplier":
            return ProduceOrder.objects.filter(supplier=user.supplier).prefetch_related("items__ingredient")
        if user.role == "admin":
            return ProduceOrder.objects.all().prefetch_related("items__ingredient")
        raise PermissionDenied("Orders are only visible to institutions and suppliers.")

    def perform_update(self, serializer):
        # Suppliers may update order status (confirm / mark delivered); admins can also
        # manage/override any order's status. Institutions remain read-only.
        user = self.request.user
        if user.role not in ("supplier", "admin"):
            raise PermissionDenied("Only the fulfilling supplier or an admin can update order status.")
        if user.role == "supplier":
            try:
                require_active_subscription(user)
            except SubscriptionRequired as exc:
                raise SubscriptionRequiredAPIException(exc)

        previous_status = serializer.instance.status
        order = serializer.save()

        if order.status != previous_status:
            if order.status == ProduceOrder.Status.CONFIRMED and not order.confirmed_at:
                order.confirmed_at = timezone.now()
                order.save(update_fields=["confirmed_at"])
            elif order.status == ProduceOrder.Status.DELIVERED and not order.delivered_at:
                order.delivered_at = timezone.now()
                order.save(update_fields=["delivered_at"])
            elif order.status == ProduceOrder.Status.CANCELLED and not order.cancelled_at:
                order.cancelled_at = timezone.now()
                order.save(update_fields=["cancelled_at"])

            notify(
                order.institution.user,
                "Order status updated",
                f"Your order #{order.id} with {order.supplier.name} is now '{order.get_status_display()}'.",
                notification_type=Notification.NotificationType.ORDER_STATUS,
                level=Notification.Level.SUCCESS if order.status == "delivered" else Notification.Level.INFO,
                related_order=order,
                link="/institution/orders",
            )

    @action(detail=True, methods=["get"])
    def tracking(self, request, pk=None):
        """
        Supplier location (for the map) + distance/ETA + a step-by-step delivery timeline —
        NOT a live-moving map. See core.geo and orders.services.build_order_tracking.
        """
        order = self.get_object()
        return Response(build_order_tracking(order))

    @action(detail=True, methods=["post"])
    def checkout(self, request, pk=None):
        """
        The institution that placed this order pays for it here and records how. There's no
        live payment gateway wired in yet — this is the single place one (M-Pesa STK push, card,
        bank) would plug in later, same pattern as billing.services.create_subscription for
        platform subscriptions.
        """
        order = self.get_object()
        if request.user.role != "institution" or order.institution_id != request.user.institution.id:
            raise PermissionDenied("Only the institution that placed this order can check it out.")
        if order.status == ProduceOrder.Status.CANCELLED:
            return Response({"detail": "Cancelled orders can't be checked out."}, status=400)
        if order.is_paid:
            return Response({"detail": "This order has already been marked as paid."}, status=400)

        serializer = OrderCheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order.is_paid = True
        order.payment_method = serializer.validated_data["payment_method"]
        order.payment_reference = serializer.validated_data.get("payment_reference", "")
        order.paid_at = timezone.now()
        order.save(update_fields=["is_paid", "payment_method", "payment_reference", "paid_at"])

        notify(
            order.supplier.user,
            "Payment received for an order",
            f"{order.institution.name} paid for order #{order.id} (KSh {order.total_value:,.2f}) "
            f"via {order.get_payment_method_display()}.",
            notification_type=Notification.NotificationType.ORDER_STATUS,
            level=Notification.Level.SUCCESS,
            related_order=order,
            link="/supplier/orders",
        )
        return Response(ProduceOrderSerializer(order).data)
