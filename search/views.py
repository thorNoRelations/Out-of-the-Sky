from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from backend.APICalls import fetchOpenSkyFlights, ai_flight_search
from .models import Flight
import json


def search(request):
    """
    View function for the flight search page.
    Renders the search interface with filters.
    """
    context = {
        'page_title': 'Search Flights',
    }
    return render(request, 'search/search.html', context)


@require_http_methods(["GET"])
def search_flights(request):
    """
    AI-powered flight search endpoint.
    Accepts query parameters: flight_number, airline, origin, destination, status, q
    Returns JSON with matching flights.
    """
    try:
        # Collect filters from request
        filters = {
            "flight_number": request.GET.get("flight_number", "").strip(),
            "airline": request.GET.get("airline", "").strip(),
            "origin_airport": request.GET.get("origin", "").strip(),
            "destination_airport": request.GET.get("destination", "").strip(),
            "status": request.GET.get("status", "").strip(),
            "free_text": request.GET.get("q", "").strip(),
        }

        has_filters = any(value for value in filters.values())
        if not has_filters:
            # Empty search should return LIVE OpenSky flights (what tests expect)
            opensky_data = fetchOpenSkyFlights()

            raw = opensky_data.get("raw", {}) if isinstance(opensky_data, dict) else {}
            states = raw.get("states", []) or opensky_data.get("states", [])

            flights = states if isinstance(states, list) else []

            return JsonResponse({
                "success": True,
                "count": len(flights),
                "flights": flights,
            })
        # Call OpenAI flight search
        ai_result = ai_flight_search(filters)
        flights = ai_result.get("flights", [])

        return JsonResponse({
            "success": True,
            "count": len(flights),
            "flights": flights
        })

    except Exception as e:
        return JsonResponse({
            "success": False,
            "error": str(e),
            "flights": []
        }, status=500)



def interactive_map(request):
    """
    View function for the interactive flight map page.
    Renders the map interface showing live flights.
    """
    context = {
        'page_title': 'Interactive Flight Map',
        'map_center_lat': 39.8283,  # Center of USA
        'map_center_lon': -98.5795,
        'default_zoom': 4,
    }
    return render(request, 'search/interactive_map.html', context)


@require_http_methods(["GET"])
def get_flight_details(request, icao24):
    """
    API endpoint for getting detailed information about a specific flight.
    """
    try:
        flight_data = fetchOpenSkyFlights(icao24=icao24)

        states = flight_data.get('states', [])
        if not states or len(states) == 0:
            return JsonResponse({
                'success': False,
                'error': 'Flight not found'
            }, status=404)

        state = states[0]

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


@require_http_methods(["GET"])
def get_live_flights(request):
    """
    API endpoint for fetching live flight data for the map.
    Returns JSON with flight positions and details.
    """
    try:
        bounds_str = request.GET.get('bounds', '')
        bbox = None

        if bounds_str:
            try:
                coords = [float(x.strip()) for x in bounds_str.split(',')]
                if len(coords) == 4:
                    bbox = tuple(coords)
            except (ValueError, AttributeError):
                pass

        if bbox is None:
            bbox = (24.396308, -125.0, 49.384358, -66.93457)

        print("=" * 50)
        print(f"🗺️ Requesting flights with bbox: {bbox}")

        opensky_data = fetchOpenSkyFlights(bbox=bbox)

        print(f"📡 OpenSky raw response keys: {opensky_data.keys()}")

        raw_data = opensky_data.get('raw', {})
        states = raw_data.get('states', [])

        print(f"✈️ Number of states found: {len(states) if states else 0}")

        flights = []

        for state in states:
            if len(state) < 11:
                continue

            icao24 = state[0]
            callsign = (state[1] or '').strip()
            longitude = state[5]
            latitude = state[6]
            altitude = state[7]
            velocity = state[9]
            heading = state[10]

            if longitude is None or latitude is None:
                continue

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

        # Limit to 50 flights - randomly sample for variety
        if len(flights) > 100:
            import random
            flights = random.sample(flights, 100)

        print(f"🎯 Total flights to return: {len(flights)}")
        print("=" * 100)

        return JsonResponse({
            'success': True,
            'count': len(flights),
            'flights': flights,
            'timestamp': raw_data.get('time', None)
        })

    except Exception as e:
        print("=" * 100)
        print(f"❌ ERROR in get_live_flights: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 100)
        return JsonResponse({
            'success': False,
            'error': str(e),
            'flights': []
        }, status=500)
