from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.permissions import IsInstitution
from billing.gating import subscription_gate
from .models import MenuPlan
from .serializers import MenuPlanSerializer, GenerateMenuPlanSerializer, PlaceOrdersSerializer, DuplicateMenuPlanSerializer
from .services import generate_menu_plan, duplicate_menu_plan
from orders.services import approve_menu_plan, get_supplier_recommendations, place_orders_from_selection


class MenuPlanViewSet(viewsets.ModelViewSet):
    serializer_class = MenuPlanSerializer
    permission_classes = [IsInstitution]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        return MenuPlan.objects.filter(institution=self.request.user.institution).prefetch_related("items__recipe")

    @action(detail=False, methods=["post"])
    def generate(self, request):
        serializer = GenerateMenuPlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        institution = request.user.institution
        if not hasattr(institution, "dietary_profile"):
            return Response({"detail": "Set up a dietary profile before generating a menu."}, status=400)
        plan = generate_menu_plan(institution, serializer.validated_data["week_start"])
        return Response(MenuPlanSerializer(plan).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def duplicate(self, request, pk=None):
        """Reuse this plan's exact menu for another week in the same billing cycle, instead of
        regenerating from scratch — e.g. a school on a termly cycle repeating the same weekly
        rotation for 13 weeks. Ingredient prices are recalculated at today's rates."""
        serializer = DuplicateMenuPlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        source_plan = self.get_object()
        new_plan = duplicate_menu_plan(source_plan, serializer.validated_data["week_start"])
        return Response(MenuPlanSerializer(new_plan).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        """Locks the menu in and sends demand signals to farmers — does NOT pick suppliers or
        place orders. Suppliers are chosen by the institution via supplier_recommendations +
        place_orders below."""
        gate = subscription_gate(request)
        if gate:
            return gate
        plan = self.get_object()
        if plan.status != MenuPlan.Status.DRAFT:
            return Response({"detail": "Only draft menus can be approved."}, status=400)
        approve_menu_plan(plan)
        plan.refresh_from_db()
        return Response(MenuPlanSerializer(plan).data)

    @action(detail=True, methods=["get"])
    def supplier_recommendations(self, request, pk=None):
        """Read-only: every ingredient this plan needs, every supplier offering it (with location
        & price), and which one is cheapest — the institution picks from these, nothing is
        auto-selected or ordered here."""
        plan = self.get_object()
        if plan.status == MenuPlan.Status.DRAFT:
            return Response({"detail": "Approve this menu first to see supplier recommendations."}, status=400)
        return Response(get_supplier_recommendations(plan))

    @action(detail=True, methods=["post"])
    def place_orders(self, request, pk=None):
        """Turns the institution's own supplier choices (from supplier_recommendations) into
        real orders. `selections` maps ingredient_id -> the supplier_id the institution picked."""
        gate = subscription_gate(request)
        if gate:
            return gate
        plan = self.get_object()
        if plan.status != MenuPlan.Status.APPROVED:
            return Response({"detail": "This menu isn't awaiting supplier selection."}, status=400)
        serializer = PlaceOrdersSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            orders = place_orders_from_selection(plan, serializer.validated_data["selections"])
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        plan.refresh_from_db()
        from orders.serializers import ProduceOrderSerializer
        return Response({
            "menu_plan": MenuPlanSerializer(plan).data,
            "orders_created": ProduceOrderSerializer(orders, many=True).data,
        })
