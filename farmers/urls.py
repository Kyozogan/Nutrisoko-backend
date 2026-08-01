from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import FarmerMeView, DemandSignalViewSet, SupplyCommitmentViewSet

router = DefaultRouter()
router.register("demand-signals", DemandSignalViewSet, basename="demand-signal")
router.register("commitments", SupplyCommitmentViewSet, basename="supply-commitment")

urlpatterns = [
    path("me/", FarmerMeView.as_view({"get": "list"}), name="farmer-me"),
    path("", include(router.urls)),
]
