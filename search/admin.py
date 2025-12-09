from django.contrib import admin
from .models import Flight


@admin.register(Flight)
class FlightAdmin(admin.ModelAdmin):
    list_display = ['flight_number', 'airline', 'origin', 'destination', 'status', 'scheduled_departure']
    list_filter = ['status', 'airline', 'origin', 'destination']
    search_fields = ['flight_number', 'airline', 'origin', 'destination']
    date_hierarchy = 'scheduled_departure'
    ordering = ['-scheduled_departure']

    fieldsets = (
        ('Flight Information', {
            'fields': ('flight_number', 'airline', 'status')
        }),
        ('Route', {
            'fields': (('origin', 'origin_city'), ('destination', 'destination_city'))
        }),
        ('Schedule', {
            'fields': (('scheduled_departure', 'actual_departure'),
                       ('scheduled_arrival', 'actual_arrival'))
        }),
        ('Details', {
            'fields': ('aircraft', 'gate', 'terminal')
        }),
    )
