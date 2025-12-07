from django.db import models
# models.py
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User


class ApiUsage(models.Model):
    provider = models.CharField(max_length=40, db_index=True)
    yyyymmdd = models.CharField(max_length=8, db_index=True)
    count = models.IntegerField(default=0)

    class Meta:
        unique_together = ("provider", "yyyymmdd")
        indexes = [models.Index(fields=["provider", "yyyymmdd"])]

    def __str__(self):
        return f"{self.provider} {self.yyyymmdd}: {self.count}"


# Test comment to see if correctly syncs up with github

# Create your models here.

# Flight model for flight information feature
class TrackedFlight(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tracked_flights', null=True, blank=True)
    # Flight Number
    flight_number = models.CharField(
        max_length=25,
        help_text="Flight Number: (AB1234)"
    )

    # Departing City information
    departing_city = models.CharField(
        max_length=50,
        help_text="City of Departure"
    )

    # Arriving City Information
    arriving_city = models.CharField(
        max_length=50,
        help_text="City of Arrival"
    )

    # Scheduled departure time
    scheduled_departure = models.DateTimeField(
        help_text="Originally scheduled departure time"
    )

    # Scheduled arrival time
    scheduled_arrival = models.DateTimeField(
        help_text="Originally scheduled arrival time"
    )

    # Updated departure time as this is constantly changing
    estimated_departure = models.DateTimeField(
        null=True,  # Can be left empty
        blank=True,  # Can be left empty
        help_text="Current estimated departure time (based on weather/delays) "
    )

    # Updated arrival time as this is constantly changing
    estimated_arrival = models.DateTimeField(
        null=True,  # Can be left empty
        blank=True,  # Can be left empty
        help_text="Current estimated arrival time (based on weather/delays) "
    )

    # Information about when the flight was created, in case of cancellation issues
    time_created = models.DateTimeField(
        auto_now_add=True,
        help_text="When flight record was created"
    )

    # Information about when flight was most recently updated (updated by an API)
    last_updated = models.DateTimeField(
        auto_now=True,
        help_text="Last updated"
    )

    class Meta:
        # Order flights by current scheduled departure time
        ordering = ['scheduled_departure']

    # String representation of the flight
    def __str__(self):
        return f"Flight {self.flight_number}: {self.departing_city} → {self.arriving_city}"

    # Returns estimated departure/arrival time as that's the most important aspect of this feature
    def get_departure_time(self):
        return self.estimated_departure or self.scheduled_departure

    def get_arrival_time(self):
        return self.estimated_arrival or self.scheduled_arrival

class AirportWeather(models.Model):
    """
    Model to store weather information for airports
    """
    WEATHER_CONDITION_CHOICES = [
        ('clear', 'Clear'),
        ('partly_cloudy', 'Partly Cloudy'),
        ('cloudy', 'Cloudy'),
        ('rain', 'Rain'),
        ('heavy_rain', 'Heavy Rain'),
        ('snow', 'Snow'),
        ('thunderstorm', 'Thunderstorm'),
        ('fog', 'Fog'),
        ('wind', 'Windy'),
    ]
    
    DELAY_RISK_CHOICES = [
        ('low', 'Low Risk'),
        ('moderate', 'Moderate Risk'),
        ('high', 'High Risk'),
        ('severe', 'Severe Risk'),
    ]
    
    # Airport information
    airport_code = models.CharField(
        max_length=10,
        help_text="Airport code (e.g., DEN, LAX)"
    )
    airport_name = models.CharField(
        max_length=100,
        help_text="Full airport name"
    )
    
    # Weather data
    condition = models.CharField(
        max_length=20,
        choices=WEATHER_CONDITION_CHOICES,
        default='clear',
        help_text="Current weather condition"
    )
    temperature = models.IntegerField(
        help_text="Temperature in Fahrenheit"
    )
    wind_speed = models.IntegerField(
        default=0,
        help_text="Wind speed in mph"
    )
    visibility = models.FloatField(
        default=10.0,
        help_text="Visibility in miles"
    )
    precipitation_chance = models.IntegerField(
        default=0,
        help_text="Chance of precipitation (0-100%)"
    )
    
    # Delay prediction
    delay_risk = models.CharField(
        max_length=20,
        choices=DELAY_RISK_CHOICES,
        default='low',
        help_text="Predicted delay risk level"
    )
    delay_probability = models.IntegerField(
        default=0,
        help_text="Probability of delays (0-100%)"
    )
    estimated_delay_minutes = models.IntegerField(
        default=0,
        help_text="Estimated delay in minutes"
    )
    
    # Forecast information
    forecast_time = models.DateTimeField(
        help_text="Time this forecast is for"
    )
    forecast_description = models.TextField(
        blank=True,
        help_text="Detailed forecast description"
    )
    
    # Metadata
    last_updated = models.DateTimeField(
        auto_now=True,
        help_text="Last time weather data was updated"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this weather record was created"
    )
    
    class Meta:
        ordering = ['forecast_time']
        # Prevent duplicate forecasts for same airport/time
        unique_together = ['airport_code', 'forecast_time']
    
    def __str__(self):
        return f"{self.airport_code} - {self.condition} at {self.forecast_time}"
    
    # Helper method to get weather icon emoji
    def get_weather_icon(self):
        """Return emoji icon for weather condition"""
        icons = {
            'clear': '☀️',
            'partly_cloudy': '⛅',
            'cloudy': '☁️',
            'rain': '🌧️',
            'heavy_rain': '⛈️',
            'snow': '❄️',
            'thunderstorm': '⚡',
            'fog': '🌫️',
            'wind': '💨',
        }
        return icons.get(self.condition, '🌤️')
    
    # Helper method to get delay risk color
    def get_risk_color(self):
        """Return CSS color class for delay risk"""
        colors = {
            'low': 'success',      # Green
            'moderate': 'warning', # Yellow
            'high': 'danger',      # Orange
            'severe': 'critical',  # Red
        }
        return colors.get(self.delay_risk, 'info')
    
    # Check if weather is suitable for flying
    def is_flight_friendly(self):
        """Determine if weather conditions are good for flying"""
        return (
            self.delay_risk in ['low', 'moderate'] and
            self.visibility >= 3.0 and
            self.condition not in ['thunderstorm', 'heavy_rain', 'snow']
        )
