from rest_framework.routers import DefaultRouter
from .views import MenuPlanViewSet

router = DefaultRouter()
router.register("", MenuPlanViewSet, basename="menu-plan")

urlpatterns = router.urls
