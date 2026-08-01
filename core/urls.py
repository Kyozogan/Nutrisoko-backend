from django.urls import path
from .views import PublicStatsView, ComplianceReportView, CountiesView

urlpatterns = [
    path("stats/", PublicStatsView.as_view(), name="public-stats"),
    path("counties/", CountiesView.as_view(), name="counties"),
    path("reports/compliance/", ComplianceReportView.as_view(), name="compliance-report"),
]
