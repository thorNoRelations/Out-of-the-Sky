from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import ApiUsage
from .models import Flight
from backend.models import APIRequestLog, AirportWeather

@admin.register(APIRequestLog)
class APIRequestLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "provider", "endpoint", "status_code", "bytes", "latency_ms")
    list_filter = ("provider", "status_code", "endpoint", "created_at")
    search_fields = ("error_message",)

@admin.register(ApiUsage)
class ApiUsageAdmin(admin.ModelAdmin):
    list_display = ("yyyymmdd", "provider", "count")
    list_filter = ("provider", "yyyymmdd")
    ordering = ("-yyyymmdd", "provider")

@admin.register(AirportWeather)
class AirportWeatherAdmin(admin.ModelAdmin):
    list_display = ("providerSource", "key", "updated_at")
    search_fields = ("key",)
    list_filter = ("providerSource",)


@admin.register(Flight)
class FlightAdmin(admin.ModelAdmin):
    list_display = [
        'flight_number',
        'departing_city',
        'arriving_city',
        'scheduled_departure',
        'scheduled_arrival',
    ]

    list_filter = [
        'departing_city',
        'arriving_city',
        'scheduled_departure',
    ]

    search_fields = [
        'flight_number',
        'departing_city',
        'arriving_city',
    ]

    ordering = ['-scheduled_departure']
# Register your models here.