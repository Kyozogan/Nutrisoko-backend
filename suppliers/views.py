from rest_framework import viewsets, permissions
from accounts.permissions import IsSupplier
from .models import Supplier, SupplierListing
from .serializers import SupplierSerializer, SupplierListingSerializer


class SupplierMeView(viewsets.ViewSet):
    permission_classes = [IsSupplier]

    def list(self, request):
        from rest_framework.response import Response
        return Response(SupplierSerializer(request.user.supplier).data)


class SupplierListingViewSet(viewsets.ModelViewSet):
    serializer_class = SupplierListingSerializer
    permission_classes = [IsSupplier]

    def get_queryset(self):
        return SupplierListing.objects.filter(supplier=self.request.user.supplier).select_related("ingredient")

    def perform_create(self, serializer):
        serializer.save(supplier=self.request.user.supplier)


class PublicSupplierListingViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only catalogue view used by institutions when reviewing sourcing options."""
    queryset = SupplierListing.objects.filter(is_active=True).select_related("ingredient", "supplier")
    serializer_class = SupplierListingSerializer
    permission_classes = [permissions.IsAuthenticated]
