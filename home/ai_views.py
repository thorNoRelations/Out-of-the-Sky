# home/ai_views.py
"""
Views for AI-powered delay predictions and route recommendations
Integrated with OpenAI flight data service
"""

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.shortcuts import render
from datetime import datetime, timedelta
# import json

from backend.APICalls import OpenWeatherClient
from backend.ai_models import DelayPredictor, RouteOptimizer
from backend.openai_flight_service import get_flight_service


@require_http_methods(["GET"])
def predict_delay(request):
    """
    API endpoint for flight delay prediction.

    Query params:
        - flight_number: Flight number (optional)
        - origin: Origin airport code (optional, defaults to DEN)
        - destination: Destination airport code (optional, defaults to LAX)
        - departure_time: ISO format datetime (optional)
        - airline: Airline name (optional)
    """

    try:
        # Get request parameters with defaults
        origin = request.GET.get('origin', 'DEN').strip().upper()
        destination = request.GET.get('destination', 'LAX').strip().upper()
        departure_time_str = request.GET.get('departure_time', '')
        airline = request.GET.get('airline', 'United Airlines')
        flight_number = request.GET.get('flight_number', f'UA{hash(origin + destination) % 900 + 100}')

        # Parse departure time
        if departure_time_str:
            try:
                departure_time = datetime.fromisoformat(departure_time_str.replace('Z', '+00:00'))
            except ValueError:
                departure_time = datetime.now() + timedelta(hours=2)
        else:
            departure_time = datetime.now() + timedelta(hours=2)

        # Get flight service
        flight_service = get_flight_service()

        # Get flight info
        flight_info = flight_service.get_flight_info(
            flight_number=flight_number,
            origin=origin,
            destination=destination,
            date=departure_time
        )

        # Get weather data for origin
        weather_client = OpenWeatherClient()
        try:
            weather_data = weather_client.fetch_city(f"{origin},US")
        except Exception:
            # If weather API fails, use defaults
            weather_data = {
                'main': {'temp': 65},
                'wind': {'speed': 5},
                'visibility': 10000,
                'weather': [{'main': 'Clear'}]
            }

        # Prepare flight data
        flight_data = {
            'flight_number': flight_info.get('flight_number', flight_number),
            'origin': origin,
            'destination': destination,
            'scheduled_departure': departure_time,
            'airline': flight_info.get('airline', airline)
        }

        # Get airline statistics
        airline_stats = flight_service.get_airline_stats(flight_data['airline'])

        # Run prediction
        predictor = DelayPredictor()
        prediction = predictor.predict_delay_probability(
            flight_data=flight_data,
            weather_data=weather_data,
            airline_stats=airline_stats
        )

        return JsonResponse({
            'success': True,
            'prediction': prediction,
            'flight_info': {
                'flight_number': flight_info.get('flight_number'),
                'airline': flight_info.get('airline'),
                'aircraft': flight_info.get('aircraft'),
                'origin': origin,
                'destination': destination,
                'departure_time': departure_time.isoformat(),
                'gate': flight_info.get('gate'),
                'terminal': flight_info.get('terminal')
            }
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def recommend_routes(request):
    """
    API endpoint for route recommendations.

    Query params:
        - origin: Origin airport code (optional, defaults to DEN)
        - destination: Destination airport code (optional, defaults to LAX)
        - date: Departure date (YYYY-MM-DD) (optional)
    """

    try:
        origin = request.GET.get('origin', 'DEN').strip().upper()
        destination = request.GET.get('destination', 'LAX').strip().upper()
        date_str = request.GET.get('date', '')

        # Parse date
        if date_str:
            try:
                departure_date = datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                departure_date = datetime.now()
        else:
            departure_date = datetime.now()

        # Get flight service
        flight_service = get_flight_service()

        # Get available routes
        available_routes = flight_service.get_available_routes(
            origin=origin,
            destination=destination,
            date=departure_date
        )

        # Initialize optimizer
        predictor = DelayPredictor()
        optimizer = RouteOptimizer(predictor)

        # Get recommendations
        recommendations = optimizer.recommend_routes(
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            available_routes=available_routes
        )

        return JsonResponse({
            'success': True,
            'origin': origin,
            'destination': destination,
            'date': departure_date.date().isoformat(),
            'routes': recommendations
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


def delay_prediction_page(request):
    """
    Render the delay prediction interface page
    """
    context = {
        'page_title': 'AI Delay Prediction',
        'airports': get_major_airports()  # Helper function for airport list
    }
    return render(request, 'home/delay_prediction.html', context)


def route_optimizer_page(request):
    """
    Render the route optimizer interface page
    """
    context = {
        'page_title': 'Smart Route Recommendations',
        'airports': get_major_airports()
    }
    return render(request, 'home/route_optimizer.html', context)


# Helper functions

def generate_mock_routes(origin: str, destination: str, departure_date: datetime) -> list:
    """
    Generate mock route options.
    In production, this would query actual flight schedules.
    """

    base_time = departure_date.replace(hour=8, minute=0)

    routes = [
        {
            'route_id': 1,
            'description': f'{origin} → {destination} (Direct)',
            'connections': [],
            'segments': [
                {
                    'origin': origin,
                    'destination': destination,
                    'departure': base_time,
                    'arrival': base_time + timedelta(hours=3),
                    'flight_number': 'AA101'
                }
            ],
            'total_duration_minutes': 180,
            'direct': True
        },
        {
            'route_id': 2,
            'description': f'{origin} → DEN → {destination}',
            'connections': ['DEN'],
            'segments': [
                {
                    'origin': origin,
                    'destination': 'DEN',
                    'departure': base_time,
                    'arrival': base_time + timedelta(hours=2),
                    'flight_number': 'UA205'
                },
                {
                    'origin': 'DEN',
                    'destination': destination,
                    'departure': base_time + timedelta(hours=3),
                    'arrival': base_time + timedelta(hours=5),
                    'flight_number': 'UA206'
                }
            ],
            'total_duration_minutes': 300,
            'direct': False
        },
        {
            'route_id': 3,
            'description': f'{origin} → ORD → {destination}',
            'connections': ['ORD'],
            'segments': [
                {
                    'origin': origin,
                    'destination': 'ORD',
                    'departure': base_time + timedelta(hours=1),
                    'arrival': base_time + timedelta(hours=3),
                    'flight_number': 'AA350'
                },
                {
                    'origin': 'ORD',
                    'destination': destination,
                    'departure': base_time + timedelta(hours=4),
                    'arrival': base_time + timedelta(hours=6, minutes=30),
                    'flight_number': 'AA351'
                }
            ],
            'total_duration_minutes': 330,
            'direct': False
        }
    ]

    return routes


def get_major_airports() -> list:
    """Return list of major US airports for dropdown menus"""
    return [
        {'code': 'ATL', 'name': 'Atlanta (ATL)'},
        {'code': 'LAX', 'name': 'Los Angeles (LAX)'},
        {'code': 'ORD', 'name': 'Chicago O\'Hare (ORD)'},
        {'code': 'DFW', 'name': 'Dallas/Fort Worth (DFW)'},
        {'code': 'DEN', 'name': 'Denver (DEN)'},
        {'code': 'JFK', 'name': 'New York JFK (JFK)'},
        {'code': 'SFO', 'name': 'San Francisco (SFO)'},
        {'code': 'LAS', 'name': 'Las Vegas (LAS)'},
        {'code': 'SEA', 'name': 'Seattle (SEA)'},
        {'code': 'MIA', 'name': 'Miami (MIA)'},
        {'code': 'PHX', 'name': 'Phoenix (PHX)'},
        {'code': 'BOS', 'name': 'Boston (BOS)'},
    ]
