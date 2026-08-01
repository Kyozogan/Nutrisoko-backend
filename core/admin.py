from django.contrib import admin

from .models import County


@admin.register(County)
class CountyAdmin(admin.ModelAdmin):
    list_display = ["code", "name"]
    search_fields = ["name"]
    ordering = ["code"]
