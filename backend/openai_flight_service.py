# backend/openai_flight_service.py
"""
Service to fetch flight information using OpenAI API.
Uses AI to generate realistic flight data and schedules.
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from django.conf import settings


class OpenAIFlightService:
    """
    Service to get flight information using OpenAI.
    In production, this would call real flight APIs.
    For now, generates intelligent mock data.
    """
    
    def __init__(self):
        self.openai_api_key = getattr(settings, 'OPENAI_API_KEY', None)
        # For now, we'll use intelligent mock data
        # When you have OpenAI API, uncomment the API integration below
        
    def get_flight_info(
        self, 
        flight_number: str = None,
        origin: str = None,
        destination: str = None,
        date: datetime = None
    ) -> Dict[str, Any]:
        """
        Get flight information for a specific flight or route.
        
        Args:
            flight_number: Specific flight number (e.g., "UA205")
            origin: Origin airport code (e.g., "DEN")
            destination: Destination airport code (e.g., "LAX")
            date: Flight date
            
        Returns:
            Dict with flight information including schedule, airline, aircraft
        """
        
        # Generate intelligent flight data
        if flight_number and origin and destination:
            return self._generate_specific_flight(flight_number, origin, destination, date)
        elif origin and destination:
            return self._generate_route_flights(origin, destination, date)
        else:
            return {"error": "Insufficient flight information"}
    
    def _generate_specific_flight(
        self, 
        flight_number: str, 
        origin: str, 
        destination: str,
        date: datetime = None
    ) -> Dict[str, Any]:
        """Generate data for a specific flight"""
        
        if date is None:
            date = datetime.now()
        
        # Extract airline from flight number
        airline_code = ''.join(c for c in flight_number if c.isalpha())
        airlines = {
            'UA': 'United Airlines',
            'AA': 'American Airlines',
            'DL': 'Delta Air Lines',
            'SW': 'Southwest Airlines',
            'B6': 'JetBlue Airways',
            'AS': 'Alaska Airlines',
            'NK': 'Spirit Airlines',
            'F9': 'Frontier Airlines'
        }
        airline = airlines.get(airline_code.upper(), 'Major Airline')
        
        # Generate realistic flight times
        base_hour = 8 + (hash(flight_number) % 12)  # Consistent but varied
        departure_time = date.replace(hour=base_hour, minute=0, second=0)
        
        # Calculate flight duration based on rough distance
        duration_hours = self._estimate_flight_duration(origin, destination)
        arrival_time = departure_time + timedelta(hours=duration_hours)
        
        # Determine status
        now = datetime.now()
        if departure_time > now + timedelta(hours=2):
            status = 'scheduled'
        elif departure_time > now:
            status = 'boarding'
        elif arrival_time > now:
            status = 'airborne'
        else:
            status = 'landed'
        
        return {
            'flight_number': flight_number.upper(),
            'airline': airline,
            'airline_code': airline_code.upper(),
            'origin': origin.upper(),
            'destination': destination.upper(),
            'scheduled_departure': departure_time.isoformat(),
            'scheduled_arrival': arrival_time.isoformat(),
            'status': status,
            'aircraft': self._get_aircraft_type(airline_code),
            'gate': self._generate_gate(),
            'terminal': self._generate_terminal(origin),
            'duration_minutes': int(duration_hours * 60),
            'distance_miles': self._estimate_distance(origin, destination)
        }
    
    def _generate_route_flights(
        self, 
        origin: str, 
        destination: str,
        date: datetime = None
    ) -> List[Dict[str, Any]]:
        """Generate multiple flight options for a route"""
        
        if date is None:
            date = datetime.now()
        
        flights = []
        airlines = ['UA', 'AA', 'DL', 'SW']
        
        # Generate 4-6 flights throughout the day
        for i, airline_code in enumerate(airlines):
            flight_num = f"{airline_code}{100 + i * 50}"
            flight = self._generate_specific_flight(flight_num, origin, destination, date)
            flights.append(flight)
        
        return flights
    
    def get_available_routes(
        self,
        origin: str,
        destination: str,
        date: datetime = None
    ) -> List[Dict[str, Any]]:
        """
        Get all available route options including connections.
        Returns direct flights and common connection options.
        """
        
        if date is None:
            date = datetime.now().replace(hour=8, minute=0, second=0)
        
        routes = []
        
        # Direct flight
        direct_flight = self._generate_specific_flight(
            f"AA{hash(origin + destination) % 900 + 100}",
            origin,
            destination,
            date
        )
        
        routes.append({
            'route_id': 1,
            'description': f'{origin} → {destination} (Direct)',
            'connections': [],
            'segments': [direct_flight],
            'total_duration_minutes': direct_flight['duration_minutes'],
            'direct': True,
            'total_distance': direct_flight['distance_miles']
        })
        
        # Add connection routes through major hubs
        hubs = self._get_connection_hubs(origin, destination)
        
        for idx, hub in enumerate(hubs[:2], start=2):  # Max 2 connection options
            # First leg
            leg1 = self._generate_specific_flight(
                f"UA{200 + idx * 10}",
                origin,
                hub,
                date
            )
            
            # Second leg (1-2 hours after first arrival)
            connection_time = datetime.fromisoformat(leg1['scheduled_arrival']) + timedelta(hours=1.5)
            leg2 = self._generate_specific_flight(
                f"UA{300 + idx * 10}",
                hub,
                destination,
                connection_time
            )
            
            total_duration = (
                datetime.fromisoformat(leg2['scheduled_arrival']) - 
                datetime.fromisoformat(leg1['scheduled_departure'])
            ).total_seconds() / 60
            
            routes.append({
                'route_id': idx,
                'description': f'{origin} → {hub} → {destination}',
                'connections': [hub],
                'segments': [leg1, leg2],
                'total_duration_minutes': int(total_duration),
                'direct': False,
                'total_distance': leg1['distance_miles'] + leg2['distance_miles']
            })
        
        return routes
    
    def _get_connection_hubs(self, origin: str, destination: str) -> List[str]:
        """Get logical connection hubs between two airports"""
        major_hubs = ['DEN', 'ORD', 'DFW', 'ATL', 'IAH', 'PHX']
        
        # Filter out origin and destination
        hubs = [h for h in major_hubs if h not in [origin, destination]]
        
        # Return up to 2 hubs
        return hubs[:2]
    
    def _estimate_flight_duration(self, origin: str, destination: str) -> float:
        """Estimate flight duration in hours based on rough distances"""
        # Simplified distance-based estimation
        # In production, use actual airport coordinates
        
        distance = self._estimate_distance(origin, destination)
        
        # Average commercial jet speed ~500 mph
        # Add 30 minutes for taxi/climb/descent
        hours = (distance / 500.0) + 0.5
        
        return round(hours, 1)
    
    def _estimate_distance(self, origin: str, destination: str) -> int:
        """Rough distance estimation between airports"""
        # Simplified - in production use actual lat/long
        
        # Create a simple hash-based distance that's consistent
        hash_val = hash(origin + destination) % 2000
        base_distance = 500 + hash_val
        
        return base_distance
    
    def _get_aircraft_type(self, airline_code: str) -> str:
        """Get typical aircraft for airline"""
        aircraft_map = {
            'UA': 'Boeing 737-900',
            'AA': 'Airbus A321',
            'DL': 'Boeing 757-200',
            'SW': 'Boeing 737-800',
            'B6': 'Airbus A320',
            'AS': 'Boeing 737-900ER',
            'NK': 'Airbus A320neo',
            'F9': 'Airbus A320'
        }
        return aircraft_map.get(airline_code.upper(), 'Boeing 737-800')
    
    def _generate_gate(self) -> str:
        """Generate a realistic gate number"""
        import random
        terminal = random.choice(['A', 'B', 'C', 'D'])
        gate_num = random.randint(1, 30)
        return f"{terminal}{gate_num}"
    
    def _generate_terminal(self, airport: str) -> str:
        """Generate terminal based on airport"""
        # Major airports often have multiple terminals
        major_airports = ['LAX', 'JFK', 'ORD', 'ATL', 'DFW']
        
        if airport.upper() in major_airports:
            return 'Terminal ' + str(hash(airport) % 5 + 1)
        else:
            return 'Main Terminal'
    
    def get_airline_stats(self, airline: str) -> Dict[str, Any]:
        """Get historical performance stats for an airline"""
        # Mock airline statistics
        # In production, query from historical database
        
        airline_reliability = {
            'United Airlines': {'on_time_percentage': 82, 'avg_delay_minutes': 15},
            'American Airlines': {'on_time_percentage': 79, 'avg_delay_minutes': 18},
            'Delta Air Lines': {'on_time_percentage': 85, 'avg_delay_minutes': 12},
            'Southwest Airlines': {'on_time_percentage': 81, 'avg_delay_minutes': 16},
            'JetBlue Airways': {'on_time_percentage': 78, 'avg_delay_minutes': 19},
            'Alaska Airlines': {'on_time_percentage': 87, 'avg_delay_minutes': 11},
        }
        
        return airline_reliability.get(
            airline, 
            {'on_time_percentage': 80, 'avg_delay_minutes': 15}
        )


# Singleton instance
_flight_service = None

def get_flight_service() -> OpenAIFlightService:
    """Get or create flight service instance"""
    global _flight_service
    if _flight_service is None:
        _flight_service = OpenAIFlightService()
    return _flight_service