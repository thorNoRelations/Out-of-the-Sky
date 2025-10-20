from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

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