from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import ApiUsage
from .models import Flight

@admin.register(ApiUsage)
class ApiUsageAdmin(admin.ModelAdmin):
    list_display = ("provider", "yyyymmdd", "count")
    list_filter = ("provider", "yyyymmdd")
    search_fields = ("provider",)
    ordering = ("-yyyymmdd", "provider")


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