from django.contrib import admin
from .models import ProduceOrder, ProduceOrderItem


class ProduceOrderItemInline(admin.TabularInline):
    model = ProduceOrderItem
    extra = 0


@admin.register(ProduceOrder)
class ProduceOrderAdmin(admin.ModelAdmin):
    inlines = [ProduceOrderItemInline]
    list_display = ["id", "institution", "supplier", "status", "total_value"]
