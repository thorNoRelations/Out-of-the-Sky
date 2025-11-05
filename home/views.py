from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from .models import Flight, AirportWeather
from django.db.models import Q

def index(request):
    """
    View function for the landing page.
    """
    context = {
        'project_name': 'TaskFlow Pro',
        'tagline': 'Streamline Your Workflow, Amplify Your Productivity',
    }
    return render(request, 'home/index.html', context)


def flight_detail(request, flight_id):
    flight = get_object_or_404(Flight, id=flight_id)
    all_flights = Flight.objects.all()
    other_flights = all_flights.exclude(id=flight_id)[:5]

    on_time_count = all_flights.filter(estimated_departure__isnull=True).count()
    delayed_count = all_flights.exclude(estimated_departure__isnull=True).count()
    upcoming_count = all_flights.filter(scheduled_departure__gte=timezone.now()).count()

    context = {
        'flight': flight,
        'all_flights': all_flights,
        'other_flights': other_flights,
        'on_time_count': on_time_count,
        'delayed_count': delayed_count,
        'upcoming_count': upcoming_count,
    }
    return render(request, 'home/flight_detail.html', context)


def weather_insights(request):
    """Weather insights page showing forecasts for all airports"""
    search_query = request.GET.get('search', '')

    if search_query:
        weather_data = AirportWeather.objects.filter(
            Q(airport_code__icontains=search_query) |
            Q(airport_name__icontains=search_query)
        ).order_by('airport_code', '-forecast_time').distinct('airport_code')
    else:
        weather_data = AirportWeather.objects.order_by('airport_code', '-forecast_time').distinct('airport_code')

    airports_weather = {}
    for weather in weather_data:
        if weather.airport_code not in airports_weather:
            airports_weather[weather.airport_code] = weather

    context = {
        'airports_weather': airports_weather.values(),
        'search_query': search_query,
        'total_airports': len(airports_weather),
    }
    return render(request, 'home/weather_insights.html', context)
