from django.db import models

# Flight models will be added here when integrating with real flight data API
# For now, the search functionality uses mock data in views.py

class Flight(models.Model):
    """
    Model for storing flight information.
    This will be used when integrating with real flight tracking APIs.
    """
    flight_number = models.CharField(max_length=10)
    airline = models.CharField(max_length=100)
    origin = models.CharField(max_length=3)  # IATA code
    origin_city = models.CharField(max_length=100)
    destination = models.CharField(max_length=3)  # IATA code
    destination_city = models.CharField(max_length=100)
    
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('boarding', 'Boarding'),
        ('departed', 'Departed'),
        ('airborne', 'Airborne'),
        ('landed', 'Landed'),
        ('delayed', 'Delayed'),
        ('cancelled', 'Cancelled'),
        ('on-time', 'On Time'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    
    scheduled_departure = models.DateTimeField()
    actual_departure = models.DateTimeField(null=True, blank=True)
    scheduled_arrival = models.DateTimeField()
    actual_arrival = models.DateTimeField(null=True, blank=True)
    
    aircraft = models.CharField(max_length=50, blank=True)
    gate = models.CharField(max_length=10, blank=True)
    terminal = models.CharField(max_length=10, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-scheduled_departure']
        indexes = [
            models.Index(fields=['flight_number']),
            models.Index(fields=['airline']),
            models.Index(fields=['origin', 'destination']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.flight_number} - {self.origin} to {self.destination}"