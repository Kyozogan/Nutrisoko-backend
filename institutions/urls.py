from django.urls import path
from .views import MyInstitutionViewSet

urlpatterns = [
    path("me/", MyInstitutionViewSet.as_view({"get": "list", "patch": "partial_update"}), name="institution-me"),
    path("me/dietary-profile/", MyInstitutionViewSet.as_view({"patch": "dietary_profile"}), name="institution-dietary-profile"),
    path("me/sites/", MyInstitutionViewSet.as_view({"get": "sites", "post": "sites"}), name="institution-sites"),
]
