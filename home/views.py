from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from .models import Flight, TrackedFlight
from django.contrib.auth.models import User


def index(request):
    """
    View function for the landing page.
    """
    context = {
        'project_name': 'Out of the Sky',
        'tagline': 'Track Every Flight, Anywhere in the World',
    }
    return render(request, 'home/index.html', context)


def dashboard(request):
    """Main dashboard view showing all tracked flights"""
    # Get or create a default user for demo purposes
    user, created = User.objects.get_or_create(username='demo_user')
    
    tracked_flights = TrackedFlight.objects.filter(
        user=user
    ).select_related('flight').order_by('-added_at')
    
    # Get some stats
    total_tracked = tracked_flights.count()
    active_flights = tracked_flights.filter(flight__status='active').count()
    delayed_flights = tracked_flights.filter(flight__delay_minutes__gt=0).count()
    
    context = {
        'tracked_flights': tracked_flights,
        'total_tracked': total_tracked,
        'active_flights': active_flights,
        'delayed_flights': delayed_flights,
    }
    
    return render(request, 'home/dashboard.html', context)


def add_flight(request):
    """View to search and add flights to tracking"""
    # Get or create demo user
    user, created = User.objects.get_or_create(username='demo_user')
    
    if request.method == 'POST':
        flight_id = request.POST.get('flight_id')
        notes = request.POST.get('notes', '')
        
        try:
            flight = Flight.objects.get(id=flight_id)
            
            # Check if already tracking
            if TrackedFlight.objects.filter(user=user, flight=flight).exists():
                messages.warning(request, f'You are already tracking {flight.flight_number}')
            else:
                TrackedFlight.objects.create(
                    user=user,
                    flight=flight,
                    notes=notes
                )
                messages.success(request, f'Successfully added {flight.flight_number} to your dashboard')
            
            return redirect('home:dashboard')
            
        except Flight.DoesNotExist:
            messages.error(request, 'Flight not found')
    
    # GET request - show search form
    search_query = request.GET.get('search', '')
    flights = []
    
    if search_query:
        flights = Flight.objects.filter(
            Q(flight_number__icontains=search_query) |
            Q(departure_airport_code__icontains=search_query) |
            Q(arrival_airport_code__icontains=search_query) |
            Q(airline__icontains=search_query)
        )[:20]
    
    context = {
        'search_query': search_query,
        'flights': flights,
    }
    
    return render(request, 'home/add_flight.html', context)


def remove_flight(request, tracked_flight_id):
    """Remove a flight from tracking"""
    user, created = User.objects.get_or_create(username='demo_user')
    
    tracked_flight = get_object_or_404(
        TrackedFlight, 
        id=tracked_flight_id, 
        user=user
    )
    
    flight_number = tracked_flight.flight.flight_number
    tracked_flight.delete()
    
    messages.success(request, f'Removed {flight_number} from your dashboard')
    return redirect('home:dashboard')


def flight_detail(request, tracked_flight_id):
    """Detailed view of a tracked flight"""
    user, created = User.objects.get_or_create(username='demo_user')
    
    tracked_flight = get_object_or_404(
        TrackedFlight,
        id=tracked_flight_id,
        user=user
    )
    
    # Update last viewed
    tracked_flight.last_viewed = timezone.now()
    tracked_flight.save()
    
    context = {
        'tracked_flight': tracked_flight,
        'flight': tracked_flight.flight,
    }
    
    return render(request, 'home/flight_detail.html', context)