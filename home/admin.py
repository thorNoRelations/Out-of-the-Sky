from django.contrib import admin
from .models import Flight


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