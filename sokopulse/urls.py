from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/institutions/", include("institutions.urls")),
    path("api/suppliers/", include("suppliers.urls")),
    path("api/farmers/", include("farmers.urls")),
    path("api/nutrition/", include("nutrition.urls")),
    path("api/menu-plans/", include("menus.urls")),
    path("api/orders/", include("orders.urls")),
    path("api/ai/", include("ai_engine.urls")),
    path("api/billing/", include("billing.urls")),
    path("api/admin/", include("configuration.urls")),
    path("api/notifications/", include("notifications.urls")),
    path("api/", include("core.urls")),
]
