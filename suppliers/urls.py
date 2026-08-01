from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import SupplierMeView, SupplierListingViewSet, PublicSupplierListingViewSet

router = DefaultRouter()
router.register("listings", SupplierListingViewSet, basename="supplier-listing")
router.register("catalogue", PublicSupplierListingViewSet, basename="supplier-catalogue")

urlpatterns = [
    path("me/", SupplierMeView.as_view({"get": "list"}), name="supplier-me"),
    path("", include(router.urls)),
]
