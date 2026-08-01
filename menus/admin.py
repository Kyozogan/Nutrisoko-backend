from django.contrib import admin
from .models import MenuPlan, MenuItem


class MenuItemInline(admin.TabularInline):
    model = MenuItem
    extra = 0


@admin.register(MenuPlan)
class MenuPlanAdmin(admin.ModelAdmin):
    inlines = [MenuItemInline]
    list_display = ["institution", "week_start", "status", "total_cost"]
