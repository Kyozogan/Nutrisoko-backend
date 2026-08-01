from rest_framework import viewsets, permissions
from .models import Ingredient, Recipe
from .serializers import IngredientSerializer, RecipeSerializer


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    permission_classes = [permissions.IsAuthenticated]


class RecipeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Recipe.objects.all().prefetch_related("recipeingredient_set__ingredient")
    serializer_class = RecipeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["county"] = self.request.query_params.get("county")
        return ctx
