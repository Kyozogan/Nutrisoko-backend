from rest_framework import viewsets, permissions
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from accounts.permissions import IsFarmer
from billing.services import require_active_subscription, SubscriptionRequired
from .models import Farmer, DemandSignal, SupplyCommitment
from .serializers import FarmerSerializer, DemandSignalSerializer, SupplyCommitmentSerializer


class SubscriptionRequiredAPIException(APIException):
    status_code = 402
    default_detail = "An active subscription is required to commit supply."

    def __init__(self, detail=None):
        message = str(detail or self.default_detail)
        super().__init__({"detail": message, "subscription_required": True})


class FarmerMeView(viewsets.ViewSet):
    permission_classes = [IsFarmer]

    def list(self, request):
        return Response(FarmerSerializer(request.user.farmer).data)


class DemandSignalViewSet(viewsets.ReadOnlyModelViewSet):
    """Forward-looking demand feed, visible to any authenticated farmer."""
    queryset = DemandSignal.objects.select_related("ingredient").prefetch_related("commitments").all()
    serializer_class = DemandSignalSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        county = self.request.query_params.get("county")
        if county:
            qs = qs.filter(county__iexact=county)
        return qs


class SupplyCommitmentViewSet(viewsets.ModelViewSet):
    serializer_class = SupplyCommitmentSerializer
    permission_classes = [IsFarmer]

    def get_queryset(self):
        return SupplyCommitment.objects.filter(farmer=self.request.user.farmer).select_related("demand_signal__ingredient")

    def perform_create(self, serializer):
        try:
            require_active_subscription(self.request.user)
        except SubscriptionRequired as exc:
            raise SubscriptionRequiredAPIException(exc)
        serializer.save(farmer=self.request.user.farmer)
