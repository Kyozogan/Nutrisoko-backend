from django.urls import path

from .views import BillingStatusView, SubscribeView, AdminSubscriptionListView

urlpatterns = [
    path("status/", BillingStatusView.as_view(), name="billing-status"),
    path("subscribe/", SubscribeView.as_view(), name="billing-subscribe"),
    path("admin/subscriptions/", AdminSubscriptionListView.as_view(), name="billing-admin-list"),
]
