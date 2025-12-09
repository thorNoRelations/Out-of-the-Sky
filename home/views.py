import os
import requests
from django.http import JsonResponse
from django.conf import settings
from django.db.models import Sum
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from datetime import timezone as _tz, datetime
from .models import ApiUsage
from .models import TrackedFlight
from django.views.decorators.http import require_http_methods
from backend.APICalls import OpenWeatherClient, ai_delay_insights, fetchOpenSkyFlights


def index(request):
    first_flight = TrackedFlight.objects.first()
    """
    View function for the landing page.
    Renders the main index.html template.
    """
    context = {
        'project_name': 'TaskFlow Pro',
        'tagline': 'Streamline Your Workflow, Amplify Your Productivity',
        'first_flight': first_flight,
    }
    return render(request, 'home/index.html', context)


def flight_detail_view(request, flight_id):
    flight = get_object_or_404(TrackedFlight, id=flight_id)
    all_flights = TrackedFlight.objects.all()
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


# Alias to maintain backward compatibility if other apps import it
flight_detail = flight_detail_view


@login_required
def track_flight(request, flight_number):
    """
    View to track a flight for the logged-in user.
    Creates a TrackedFlight instance if it doesn't exist for the user.
    """
    # Mock flight data - same as in search/views.py
    mock_flights = {
        'AA101': {'origin_city': 'New York', 'destination_city': 'Los Angeles'},
        'UA205': {'origin_city': 'Chicago', 'destination_city': 'San Francisco'},
        'DL450': {'origin_city': 'Atlanta', 'destination_city': 'Miami'},
        'AA102': {'origin_city': 'Los Angeles', 'destination_city': 'New York'},
        'SW789': {'origin_city': 'Denver', 'destination_city': 'Phoenix'},
    }

    # Check if the flight is already tracked by this user
    flight_exists = TrackedFlight.objects.filter(
        user=request.user,
        flight_number=flight_number
    ).exists()

    if not flight_exists:
        # Get flight data from mock data, or use Unknown as fallback
        flight_data = mock_flights.get(flight_number.upper(), {})
        departing = flight_data.get('origin_city', 'Unknown')
        arriving = flight_data.get('destination_city', 'Unknown')

        TrackedFlight.objects.create(
            user=request.user,
            flight_number=flight_number,
            departing_city=departing,
            arriving_city=arriving,
            scheduled_departure=timezone.now(),
            scheduled_arrival=timezone.now() + timezone.timedelta(hours=2)
        )

    return redirect('profile')

def weather_insights(request):
    q = (request.GET.get("q") or request.GET.get("search") or "").strip()
    weather = None
    airports_weather = []
    error = None

    if q:
        try:
            data = OpenWeatherClient().fetch_city(q)

            # -------------------------
            # Top banner (FAHRENHEIT)
            # -------------------------
            weather = {
                "city": data.get("name"),
                "country": (data.get("sys") or {}).get("country"),
                "temp": round((data.get("main") or {}).get("temp", 0)),  # ✅ Fahrenheit
                "condition": ((data.get("weather") or [{}])[0] or {}).get("description"),
            }

            # -------------------------
            # VISIBILITY FIX (meters → miles)
            # -------------------------
            raw_visibility = data.get("visibility", 16093)  # meters
            visibility_miles = round(raw_visibility / 1609.34, 1)

            # -------------------------
            # AI RISK ASSESSMENT HOOKED UP
            # -------------------------
            ai_result = ai_delay_insights(
                location=data.get("name", q),
                weather_data=data
            )

            delay_risk = ai_result.get("delay_risk", "low")
            delay_probability = int(ai_result.get("probability_percent", 0))
            forecast_description = ai_result.get("summary", "")

            # Delay minutes mapping
            if delay_probability >= 80:
                est_delay = 60
            elif delay_probability >= 60:
                est_delay = 45
            elif delay_probability >= 40:
                est_delay = 30
            elif delay_probability >= 20:
                est_delay = 15
            else:
                est_delay = 0

            # -------------------------
            # ✅ LIST ITEM FOR TEMPLATE
            # -------------------------
            w = data.get("weather") or [{}]
            desc = (w[0] or {}).get("description", "")

            airports_weather = [{
                "airport_code": q.upper(),
                "airport_name": data.get("name"),

                # ✅ FAHRENHEIT
                "temperature": round((data.get("main") or {}).get("temp", 0)),

                "wind_speed": round((data.get("wind") or {}).get("speed", 0)),

                # ✅ VISIBILITY IN MILES
                "visibility": visibility_miles,

                "precipitation_chance": 0,
                "forecast_time": datetime.fromtimestamp(data.get("dt", 0)),

                # ✅ REAL AI DATA (NO MORE HARDCODED VALUES)
                "delay_risk": delay_risk,
                "delay_probability": delay_probability,
                "estimated_delay_minutes": est_delay,
                "forecast_description": forecast_description or desc.title(),

                "last_updated": timezone.now(),

                # template helpers
                "get_weather_icon": "🌤️",
                "get_condition_display": desc.title(),
                "get_delay_risk_display": delay_risk.title(),
            }]

        except Exception as e:
            error = str(e)

    return render(request, "home/weather_insights.html", {
        "weather": weather,
        "airports_weather": airports_weather,
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

        for state in states[:200]:  # LIMIT to first 200 states for performance

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

        # ADDITIONAL LIMIT: Cap total flights returned to 200 max
        flights = flights[:200]

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


def dashboard(request):
    """Dashboard view that shows all flights or a message if none exist"""
    flights = TrackedFlight.objects.all()

    context = {
        'flights': flights,
        'total_flights': flights.count(),
        'on_time_count': flights.filter(estimated_departure__isnull=True).count(),
        'delayed_count': flights.exclude(estimated_departure__isnull=True).count(),
        'upcoming_count': flights.filter(scheduled_departure__gte=timezone.now()).count(),
    }
    return render(request, 'home/dashboard.html', context)


def debug_config(request):
    """Debug endpoint to check configuration - REMOVE IN PRODUCTION"""

    # Check Django settings
    has_setting = hasattr(settings, 'OPENWEATHER_API_KEY')
    setting_value = getattr(settings, 'OPENWEATHER_API_KEY', None) if has_setting else None

    # Check environment directly
    env_keys_weather = [k for k in os.environ.keys() if 'WEATHER' in k.upper()]
    env_keys_open = [k for k in os.environ.keys() if k.startswith('OPEN')]

    debug_info = {
        'django_settings': {
            'has_OPENWEATHER_API_KEY': has_setting,
            'value_exists': bool(setting_value),
            'value_length': len(setting_value) if setting_value else 0,
        },
        'environment_direct': {
            'OPENWEATHER_API_KEY_exists': 'OPENWEATHER_API_KEY' in os.environ,
            'OPENWEATHERMAP_API_KEY_exists': 'OPENWEATHERMAP_API_KEY' in os.environ,
            'keys_with_WEATHER': env_keys_weather,
            'keys_starting_OPEN': env_keys_open,
        },
        'all_env_keys_count': len(os.environ.keys()),
        'render_env_set': bool(os.environ.get('RENDER')),
    }

    return JsonResponse(debug_info, json_dumps_params={'indent': 2})


# Helper function for date formatting
def format_iso8601(dt: datetime) -> str:
    """
    Formats a datetime object to ISO 8601 string 'YYYY-MM-DDTHH:MM:SSZ'.
    """
    # Ensure timezone awareness (default to UTC if naive)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_tz.utc)

    # Convert to UTC
    dt_utc = dt.astimezone(_tz.utc)

    # Format: YYYY-MM-DDTHH:MM:SSZ
    return dt_utc.strftime('%Y-%m-%dT%H:%M:%SZ')


@require_http_methods(["GET", "POST"])
def assess_delay_risk_view(request, flight_id):
    """
    Assess delay risk for a specific flight using an external AI API.
    """
    flight = get_object_or_404(TrackedFlight, id=flight_id)

    # API Configuration
    api_url = "https://api.thirdparty.com/delay-risk"
    api_key = getattr(settings, 'THIRD_PARTY_API_KEY', None)

    if not api_key:
        return JsonResponse({
            'error': 'Configuration Error',
            'message': 'Third-party API key is missing.'
        }, status=500)

    # Construct Payload
    # extracting first 3 chars as airport code based on template logic
    payload = {
        "departure_airport_code": flight.departing_city[:3].upper(),
        "arrival_airport_code": flight.arriving_city[:3].upper(),
        "scheduled_departure_time": format_iso8601(flight.scheduled_departure)
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(api_url, json=payload, headers=headers, timeout=10)

        # Check for successful response
        if response.status_code == 200:
            return JsonResponse(response.json())
        else:
            return JsonResponse({
                'error': 'API Error',
                'status_code': response.status_code,
                'message': response.text
            }, status=response.status_code)

    except requests.exceptions.RequestException as e:
        return JsonResponse({
            'error': 'Network Error',
            'message': str(e)
        }, status=503)


@login_required
def account_view(request):
    """
    View for the user account page.
    Displays a list of tracked flights for the logged-in user.
    """
    flights = TrackedFlight.objects.filter(user=request.user)
    return render(request, 'home/account_page.html', {'flights': flights})
