from rest_framework.routers import DefaultRouter
from .views import ProduceOrderViewSet

router = DefaultRouter()
router.register("", ProduceOrderViewSet, basename="produce-order")

urlpatterns = router.urls
