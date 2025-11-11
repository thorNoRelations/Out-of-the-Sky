from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from backend.APICalls import fetchOpenSkyFlights
from django.views.decorators.http import require_http_methods
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
    API endpoint for searching flights.
    Accepts query parameters: flight_number, airline, origin, destination, status
    Returns JSON with matching flights.
    """
    # Get search parameters
    flight_number = request.GET.get('flight_number', '').strip()
    airline = request.GET.get('airline', '').strip()
    origin = request.GET.get('origin', '').strip()
    destination = request.GET.get('destination', '').strip()
    status = request.GET.get('status', '').strip()
    
    # Mock flight data - Replace with actual database queries
    mock_flights = [
        {
            'id': 1,
            'flight_number': 'AA101',
            'airline': 'American Airlines',
            'origin': 'JFK',
            'origin_city': 'New York',
            'destination': 'LAX',
            'destination_city': 'Los Angeles',
            'status': 'airborne',
            'departure_time': '14:30',
            'arrival_time': '17:45',
            'aircraft': 'Boeing 737-800',
            'gate': 'B12',
        },
        {
            'id': 2,
            'flight_number': 'UA205',
            'airline': 'United Airlines',
            'origin': 'ORD',
            'origin_city': 'Chicago',
            'destination': 'SFO',
            'destination_city': 'San Francisco',
            'status': 'delayed',
            'departure_time': '09:15',
            'arrival_time': '11:30',
            'aircraft': 'Airbus A320',
            'gate': 'C24',
        },
        {
            'id': 3,
            'flight_number': 'DL450',
            'airline': 'Delta Air Lines',
            'origin': 'ATL',
            'origin_city': 'Atlanta',
            'destination': 'MIA',
            'destination_city': 'Miami',
            'status': 'on-time',
            'departure_time': '16:00',
            'arrival_time': '18:15',
            'aircraft': 'Boeing 757-200',
            'gate': 'A8',
        },
        {
            'id': 4,
            'flight_number': 'AA102',
            'airline': 'American Airlines',
            'origin': 'LAX',
            'origin_city': 'Los Angeles',
            'destination': 'JFK',
            'destination_city': 'New York',
            'status': 'boarding',
            'departure_time': '20:00',
            'arrival_time': '04:25',
            'aircraft': 'Boeing 737-800',
            'gate': 'D15',
        },
        {
            'id': 5,
            'flight_number': 'SW789',
            'airline': 'Southwest Airlines',
            'origin': 'DEN',
            'origin_city': 'Denver',
            'destination': 'PHX',
            'destination_city': 'Phoenix',
            'status': 'airborne',
            'departure_time': '12:45',
            'arrival_time': '14:20',
            'aircraft': 'Boeing 737-700',
            'gate': 'B7',
        },
    ]
    
    # Filter flights based on search parameters
    results = mock_flights
    
    if flight_number:
        results = [f for f in results if flight_number.upper() in f['flight_number'].upper()]
    
    if airline:
        results = [f for f in results if airline.lower() in f['airline'].lower()]
    
    if origin:
        results = [f for f in results if origin.upper() in f['origin'].upper()]
    
    if destination:
        results = [f for f in results if destination.upper() in f['destination'].upper()]
    
    if status:
        results = [f for f in results if f['status'] == status]
    
    return JsonResponse({
        'success': True,
        'count': len(results),
        'flights': results
    })

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
        
        # FIX: Get states from the 'raw' nested object
        raw_data = opensky_data.get('raw', {})
        states = raw_data.get('states', [])
        
        print(f"✈️ Number of states found: {len(states) if states else 0}")
        
        flights = []
        
        for state in states:
            if len(state) < 11:
                print(f"⚠️ Skipping state - too short: {len(state)} elements")
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
        
        print(f"🎯 Total flights to return: {len(flights)}")
        print("=" * 50)
        
        return JsonResponse({
            'success': True,
            'count': len(flights),
            'flights': flights,
            'timestamp': raw_data.get('time', None)
        })
        
    except Exception as e:
        print("=" * 50)
        print(f"❌ ERROR in get_live_flights: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 50)
        return JsonResponse({
            'success': False,
            'error': str(e),
            'flights': []
        }, status=500)

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