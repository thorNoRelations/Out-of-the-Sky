import os
from django.http import JsonResponse
from django.db.models import Sum
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from django.shortcuts import render, get_object_or_404
from datetime import timezone as _tz, datetime
from .models import ApiUsage
from .models import Flight, AirportWeather
from django.db.models import Q
from django.views.decorators.http import require_http_methods
from backend.APICalls import OpenWeatherClient, fetchOpenSkyFlights
import json


def index(request):
    """
    View function for the landing page.
    Renders the main index.html template.
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
    q = (request.GET.get("q") or request.GET.get("search") or "").strip()
    weather = None         # keep if you also show the small banner at top
    airports_weather = []  # <-- template expects this list
    error = None

    if q:
        try:
            data = OpenWeatherClient().fetch_city(q)

            # small banner (optional)
            weather = {
                "city": data.get("name"),
                "country": (data.get("sys") or {}).get("country"),
                "temp": (data.get("main") or {}).get("temp"),
                "condition": ((data.get("weather") or [{}])[0] or {}).get("description"),
            }

            # build the list item the template loops over
            w = data.get("weather") or [{}]
            desc = (w[0] or {}).get("description", "")
            airports_weather = [{
                "airport_code": q.upper(),                          # e.g. "DENVER,US"
                "airport_name": data.get("name"),                   # "Denver"
                "temperature": (data.get("main") or {}).get("temp"),
                "wind_speed": (data.get("wind") or {}).get("speed"),
                "visibility": data.get("visibility"),               # template prints "mi" – set units as you like
                "precipitation_chance": 0,                          # /weather often lacks POP; default 0
                "forecast_time": datetime.fromtimestamp(data.get("dt", 0)),
                "delay_risk": "low",                                # string used in class "risk-{{ weather.delay_risk }}"
                "delay_probability": 0,
                "estimated_delay_minutes": 0,
                "forecast_description": desc.title(),
                "last_updated": timezone.now(),

                # fields the template *calls* but are fine as plain strings
                "get_weather_icon": "🌤️",
                "get_condition_display": desc.title(),
                "get_delay_risk_display": "Low",
            }]

        except Exception as e:
            error = str(e)

    return render(request, "home/weather_insights.html", {
        "search_query": q,
        "weather": weather,                 # small banner at top (optional)
        "airports_weather": airports_weather,  # <-- critical
        "total_airports": len(airports_weather),
        "error": error,
    })


def _budgets_from_env():
    return {
        "openweathermap": int(os.getenv("BUDGET_OPENWEATHERMAP_PER_DAY", 900)),
        "aviationweather": int(os.getenv("BUDGET_AVIATIONWEATHER_PER_DAY", 2000)),
        "aviationstack": int(os.getenv("BUDGET_AVIATIONSTACK_PER_DAY", 1000)),
        "opensky": int(os.getenv("BUDGET_OPENSKY_PER_DAY", int(os.getenv("BUDGET_OPENSPY_PER_DAY", 380)))),
    }


@staff_member_required
def api_usage_readout(request):
    today = timezone.now().astimezone(_tz.utc).strftime("%Y%m%d")
    budgets = _budgets_from_env()
    rows = ApiUsage.objects.filter(yyyymmdd=today).values("provider").annotate(total=Sum("count"))
    used = {r["provider"]: r["total"] for r in rows}
    out = []
    for provider, budget in budgets.items():
        u = int(used.get(provider, 0))
        remaining = max(0, budget - u)
        pct = (u / budget * 100.0) if budget else None
        out.append({
            "provider": provider,
            "used_today": u,
            "budget_today": budget,
            "remaining_today": remaining,
            "used_pct": round(pct, 1) if pct is not None else None,
        })
    return JsonResponse({"date": today, "providers": out})


# Begin interactiveMap task
# View function for the interactive flight map
def interactive_map(request):
    context = {
        'page_title': 'Interactive Flight Map',
        'map_center_lat': 39.8283,  # Center of USA
        'map_center_lon': -98.5795,
        'default_zoom': 4,
    }
    return render(request, 'search/interactive_map.html', context)


# API endpoint to get live flight data for the interactive map
# Returns JSON data with flight positions and details
@require_http_methods(["GET"])
def get_live_flights(request):
    try:
        # Get optional bounding box for map viewport
        bounds_str = request.GET.get('bounds', '')
        bbox = None
        
        if bounds_str:
            try:
                # Parse bounds: lat_min,lon_min,lat_max,lon_max
                coords = [float(x.strip()) for x in bounds_str.split(',')]
                if len(coords) == 4:
                    bbox = tuple(coords)
            except (ValueError, AttributeError):
                pass
        
        # Fetch live flight data from OpenSky
        # For US coverage, use a bounding box if none provided
        if bbox is None:
            # Continental US approximate bounds
            bbox = (24.396308, -125.0, 49.384358, -66.93457)
        
        opensky_data = fetchOpenSkyFlights(bbox=bbox)
        
        # Transform OpenSky data to map-friendly format
        flights = []
        states = opensky_data.get('states', [])
        
        for state in states:
            # OpenSky state vector format:
            # [0]=icao24, [1]=callsign, [5]=longitude, [6]=latitude, 
            # [7]=baro_altitude, [9]=velocity, [10]=true_track
            
            if len(state) < 11:
                continue
            
            icao24 = state[0]
            callsign = (state[1] or '').strip()
            longitude = state[5]
            latitude = state[6]
            altitude = state[7]  # meters
            velocity = state[9]  # m/s
            heading = state[10]  # degrees
            
            # Skip if missing critical position data
            if longitude is None or latitude is None:
                continue
            
            # Convert units
            altitude_ft = int(altitude * 3.28084) if altitude else 0
            speed_knots = int(velocity * 1.94384) if velocity else 0
            
            flight_data = {
                'icao24': icao24,
                'callsign': callsign or 'N/A',
                'latitude': latitude,
                'longitude': longitude,
                'altitude': altitude_ft,
                'speed': speed_knots,
                'heading': heading if heading else 0,
                'status': 'airborne',
            }
            
            flights.append(flight_data)
        
        return JsonResponse({
            'success': True,
            'count': len(flights),
            'flights': flights,
            'timestamp': opensky_data.get('time', None)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'flights': []
        }, status=500)


@require_http_methods(["GET"])
def get_flight_details(request, icao24):
    try:
        # Fetch flight data filtered by icao24
        flight_data = fetchOpenSkyFlights(icao24=icao24)
        
        states = flight_data.get('states', [])
        if not states or len(states) == 0:
            return JsonResponse({
                'success': False,
                'error': 'Flight not found'
            }, status=404)
        
        state = states[0]
        
        # Parse state vector
        details = {
            'icao24': state[0],
            'callsign': (state[1] or '').strip(),
            'origin_country': state[2],
            'longitude': state[5],
            'latitude': state[6],
            'baro_altitude': int(state[7] * 3.28084) if state[7] else 0,
            'on_ground': state[8],
            'velocity': int(state[9] * 1.94384) if state[9] else 0,
            'true_track': state[10],
            'vertical_rate': state[11],
            'last_contact': state[4],
        }
        
        return JsonResponse({
            'success': True,
            'flight': details
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)