from django.urls import path
from .views import RecommendIngredientsView, GenerateAIMenuView, SupplierInsightsView, FarmerInsightsView, AskAssistantView

urlpatterns = [
    path("recommend-products/", RecommendIngredientsView.as_view(), name="ai-recommend-products"),
    path("generate-weekly-menu/", GenerateAIMenuView.as_view(), name="ai-generate-weekly-menu"),
    path("supplier-insights/", SupplierInsightsView.as_view(), name="ai-supplier-insights"),
    path("farmer-insights/", FarmerInsightsView.as_view(), name="ai-farmer-insights"),
    path("ask/", AskAssistantView.as_view(), name="ai-ask"),
]
