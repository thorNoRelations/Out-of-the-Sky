from django.db import models
from django.utils import timezone

#Test comment to see if correclty syncs up with github

# Create your models here.

#Flight model for flight information feature
class Flight(models.Model):

    #Flight NUmber
    flight_number = models.CharField(

        max_length=25,
        help_text="Flight NUmber: (AB1234)"

    )

    #Departing City information
    departing_city = models.CharField(

        max_length = 50, 
        help_text = "City of Departure"

    )

    #Arriving City Information 
    arriving_city = models.CharField(

        max_length = 50, 
        help_text = "City of Arrival"

    )

    #Scheduled departure time 
    scheduled_departure = models.DateTimeField(

        help_text="Originally scheduled departure time"

    )

    #Scheduled arrival time
    scheduled_arrival = models.DateTimeField(

        help_text="Originally arrival departure time"

    )

    #Updated departure time as this is constantly changing
    estimated_departure = models.DateTimeField(

        null=True,  #Can be left empty
        blank=True,  #Can be left empty
        help_text="Current estimated departure time (based on weather/delays) "

    )

    #Updated arrival time as this is constantly changing
    estimated_departure = models.DateTimeField(

        null=True,  #Can be left empty
        blank=True,  #Can be left empty
        help_text="Current estimated arrival time (based on weather/delays) "

    )

    #Information about when the flight was created, incase of cancellation issues
    time_created = models.DataTimeField(

        auto_now_add=True,
        help_text="Last updated"

    )

    #Information about when flight was most recently updated (updated by an API)
    last_updated = models.DateTimeField(

        auto_now=True,
        help_text="Last updated"

    )

    class Meta:

        #Order flights by current scheduled departure time
        ordering = ['scheduled_departure']

        #Get information back about the flight as a string
        return f"Flight {self.flight_number}: {self.origin} → {self.destination}"
        
        #Returns estimated departure/arrival time as thats the most important aspect of this feature
        def get_departure_time(self):
        
            return self.estimated_departure or self.scheduled_departure
    
        def get_arrival_time(self):
            
            return self.estimated_arrival or self.scheduled_arrival


