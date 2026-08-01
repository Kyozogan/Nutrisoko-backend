from django.urls import path

from .views import SystemConfigurationView, SystemOverviewView

urlpatterns = [
    path("settings/", SystemConfigurationView.as_view(), name="admin-settings"),
    path("overview/", SystemOverviewView.as_view(), name="admin-overview"),
]
