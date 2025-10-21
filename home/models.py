from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Flight(models.Model):
    """
    Model to store flight information
    """
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('active', 'Active'),
        ('landed', 'Landed'),
        ('cancelled', 'Cancelled'),
        ('delayed', 'Delayed'),
        ('diverted', 'Diverted'),
    ]
    
    # Flight identification
    flight_number = models.CharField(max_length=20)
    airline = models.CharField(max_length=100)
    aircraft_type = models.CharField(max_length=50, blank=True, null=True)
    
    # Departure information
    departure_airport = models.CharField(max_length=100)
    departure_airport_code = models.CharField(max_length=10)
    departure_terminal = models.CharField(max_length=10, blank=True, null=True)
    departure_gate = models.CharField(max_length=10, blank=True, null=True)
    scheduled_departure = models.DateTimeField()
    actual_departure = models.DateTimeField(blank=True, null=True)
    estimated_departure = models.DateTimeField(blank=True, null=True)
    
    # Arrival information
    arrival_airport = models.CharField(max_length=100)
    arrival_airport_code = models.CharField(max_length=10)
    arrival_terminal = models.CharField(max_length=10, blank=True, null=True)
    arrival_gate = models.CharField(max_length=10, blank=True, null=True)
    scheduled_arrival = models.DateTimeField()
    actual_arrival = models.DateTimeField(blank=True, null=True)
    estimated_arrival = models.DateTimeField(blank=True, null=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    delay_minutes = models.IntegerField(default=0)
    
    # Metadata
    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['scheduled_departure']
    
    def __str__(self):
        return f"{self.airline} {self.flight_number} - {self.departure_airport_code} to {self.arrival_airport_code}"
    
    @property
    def is_delayed(self):
        return self.delay_minutes > 0
    
    @property
    def current_status_display(self):
        if self.status == 'delayed':
            return f"Delayed {self.delay_minutes} minutes"
        return self.get_status_display()


class TrackedFlight(models.Model):
    """
    Model to track which flights a user is monitoring
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tracked_flights')
    flight = models.ForeignKey(Flight, on_delete=models.CASCADE, related_name='tracking_users')
    
    # User preferences
    notes = models.TextField(blank=True)
    notify_on_status_change = models.BooleanField(default=True)
    notify_on_gate_change = models.BooleanField(default=True)
    notify_on_delay = models.BooleanField(default=True)
    
    # Tracking metadata
    added_at = models.DateTimeField(auto_now_add=True)
    last_viewed = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'flight']
        ordering = ['-added_at']
    
    def __str__(self):
        return f"{self.user.username} tracking {self.flight.flight_number}"