from django.contrib import admin
from .models import ApiUsage

@admin.register(ApiUsage)
class ApiUsageAdmin(admin.ModelAdmin):
    list_display = ("provider", "yyyymmdd", "count")
    list_filter = ("provider", "yyyymmdd")
    search_fields = ("provider",)
    ordering = ("-yyyymmdd", "provider")
