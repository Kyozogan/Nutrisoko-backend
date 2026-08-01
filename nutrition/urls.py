from rest_framework.routers import DefaultRouter
from .views import IngredientViewSet, RecipeViewSet

router = DefaultRouter()
router.register("ingredients", IngredientViewSet, basename="ingredient")
router.register("recipes", RecipeViewSet, basename="recipe")

urlpatterns = router.urls
