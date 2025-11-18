# backend/ai_models.py
"""
AI-Powered Delay Prediction using Machine Learning
Predicts flight delays based on historical data and current conditions
"""

import os
import pickle
from datetime import datetime
from typing import Dict, Any, Tuple
from pathlib import Path

# Simple ML model without external dependencies initially
class DelayPredictor:
    """
    Flight delay prediction model using historical patterns and current conditions.
    Uses a rules-based approach initially, can be upgraded to ML model later.
    """
    
    def __init__(self):
        self.model_path = Path(__file__).parent / 'models' / 'delay_model.pkl'
        self.model = None
        self.feature_names = [
            'hour_of_day',
            'day_of_week',
            'weather_severity',
            'visibility',
            'wind_speed',
            'precipitation',
            'airline_reliability',
            'airport_congestion',
            'season'
        ]
        
    def predict_delay_probability(
        self,
        flight_data: Dict[str, Any],
        weather_data: Dict[str, Any],
        airline_stats: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Predict delay probability and estimated delay time.
        
        Args:
            flight_data: Flight details (time, airline, airports)
            weather_data: Current weather conditions
            airline_stats: Historical airline performance (optional)
            
        Returns:
            Dictionary with prediction results
        """
        
        # Extract features
        features = self._extract_features(flight_data, weather_data, airline_stats)
        
        # Calculate delay probability (rules-based for now)
        delay_prob = self._calculate_delay_probability(features)
        
        # Estimate delay duration
        estimated_delay = self._estimate_delay_minutes(features, delay_prob)
        
        # Determine risk level
        risk_level = self._get_risk_level(delay_prob)
        
        # Get contributing factors
        factors = self._get_contributing_factors(features)
        
        return {
            'delay_probability': round(delay_prob * 100, 1),  # as percentage
            'estimated_delay_minutes': estimated_delay,
            'risk_level': risk_level,  # low, moderate, high, severe
            'confidence': self._calculate_confidence(features),
            'contributing_factors': factors,
            'recommendations': self._generate_recommendations(risk_level, factors)
        }
    
    def _extract_features(
        self,
        flight_data: Dict[str, Any],
        weather_data: Dict[str, Any],
        airline_stats: Dict[str, Any] = None
    ) -> Dict[str, float]:
        """Extract numerical features from raw data"""
        
        # Parse departure time
        dep_time = flight_data.get('scheduled_departure')
        if isinstance(dep_time, str):
            dep_time = datetime.fromisoformat(dep_time.replace('Z', '+00:00'))
        
        features = {
            'hour_of_day': dep_time.hour,
            'day_of_week': dep_time.weekday(),
            'season': (dep_time.month % 12 + 3) // 3,  # 1=Winter, 2=Spring, etc.
        }
        
        # Weather features
        weather_main = weather_data.get('main', {})
        weather_wind = weather_data.get('wind', {})
        weather_conditions = weather_data.get('weather', [{}])[0]
        
        features['visibility'] = weather_data.get('visibility', 10000) / 10000  # normalize
        features['wind_speed'] = weather_wind.get('speed', 0)
        features['precipitation'] = 1 if 'rain' in weather_conditions.get('main', '').lower() else 0
        
        # Weather severity score (0-1)
        condition = weather_conditions.get('main', '').lower()
        severity_map = {
            'clear': 0.0,
            'clouds': 0.1,
            'mist': 0.3,
            'rain': 0.6,
            'snow': 0.8,
            'thunderstorm': 1.0
        }
        features['weather_severity'] = severity_map.get(condition, 0.2)
        
        # Airline reliability (0-1, higher is better)
        if airline_stats:
            features['airline_reliability'] = airline_stats.get('on_time_percentage', 80) / 100
        else:
            features['airline_reliability'] = 0.85  # default assumption
        
        # Airport congestion (mock for now, would use real-time data)
        features['airport_congestion'] = self._estimate_airport_congestion(
            flight_data.get('origin'),
            dep_time
        )
        
        return features
    
    def _calculate_delay_probability(self, features: Dict[str, float]) -> float:
        """Calculate delay probability using feature weights"""
        
        # Base probability
        prob = 0.15  # 15% baseline
        
        # Time of day factors
        hour = features['hour_of_day']
        if 6 <= hour <= 8:  # Morning rush
            prob += 0.10
        elif 16 <= hour <= 19:  # Evening rush
            prob += 0.15
        elif hour >= 22 or hour <= 5:  # Late night/early morning
            prob += 0.05
        
        # Day of week
        if features['day_of_week'] in [4, 6]:  # Friday, Sunday
            prob += 0.08
        
        # Weather impact (most significant)
        weather_impact = features['weather_severity'] * 0.35
        prob += weather_impact
        
        # Visibility
        if features['visibility'] < 0.5:  # Less than 5km
            prob += 0.20
        elif features['visibility'] < 0.8:
            prob += 0.10
        
        # Wind speed
        if features['wind_speed'] > 25:  # mph
            prob += 0.15
        elif features['wind_speed'] > 15:
            prob += 0.08
        
        # Precipitation
        if features['precipitation'] > 0:
            prob += 0.12
        
        # Airline reliability
        airline_factor = (1 - features['airline_reliability']) * 0.20
        prob += airline_factor
        
        # Airport congestion
        prob += features['airport_congestion'] * 0.15
        
        # Seasonal factors
        if features['season'] == 1:  # Winter
            prob += 0.10
        
        # Cap probability at 0.95
        return min(prob, 0.95)
    
    def _estimate_delay_minutes(self, features: Dict[str, float], probability: float) -> int:
        """Estimate delay duration in minutes"""
        
        if probability < 0.3:
            return 0
        
        # Base delay increases with probability
        base_delay = int(probability * 45)  # Up to 45 minutes
        
        # Weather multiplier
        weather_multiplier = 1 + (features['weather_severity'] * 0.5)
        
        # Visibility impact
        if features['visibility'] < 0.3:
            weather_multiplier += 0.5
        
        # Wind impact
        if features['wind_speed'] > 25:
            weather_multiplier += 0.3
        
        estimated = int(base_delay * weather_multiplier)
        
        # Round to nearest 5 minutes
        return (estimated // 5) * 5
    
    def _get_risk_level(self, probability: float) -> str:
        """Determine risk level from probability"""
        if probability < 0.25:
            return 'low'
        elif probability < 0.50:
            return 'moderate'
        elif probability < 0.75:
            return 'high'
        else:
            return 'severe'
    
    def _calculate_confidence(self, features: Dict[str, float]) -> float:
        """Calculate prediction confidence score"""
        # Higher confidence when we have more data
        confidence = 0.7  # base confidence
        
        # Increase confidence for clear patterns
        if features['weather_severity'] > 0.7 or features['weather_severity'] < 0.2:
            confidence += 0.1
        
        if features['airline_reliability'] != 0.85:  # We have real airline data
            confidence += 0.1
        
        return min(confidence, 0.95)
    
    def _get_contributing_factors(self, features: Dict[str, float]) -> list:
        """Identify main factors contributing to delay risk"""
        factors = []
        
        if features['weather_severity'] > 0.5:
            factors.append({
                'factor': 'Adverse Weather',
                'impact': 'high',
                'description': 'Poor weather conditions at airport'
            })
        
        if features['visibility'] < 0.5:
            factors.append({
                'factor': 'Low Visibility',
                'impact': 'high',
                'description': 'Reduced visibility may slow operations'
            })
        
        if features['wind_speed'] > 20:
            factors.append({
                'factor': 'High Winds',
                'impact': 'moderate',
                'description': f"{features['wind_speed']:.0f} mph winds may affect operations"
            })
        
        if features['airport_congestion'] > 0.6:
            factors.append({
                'factor': 'Airport Congestion',
                'impact': 'moderate',
                'description': 'High traffic volume at airport'
            })
        
        hour = features['hour_of_day']
        if 16 <= hour <= 19:
            factors.append({
                'factor': 'Peak Travel Time',
                'impact': 'moderate',
                'description': 'Evening rush hour increases delays'
            })
        
        if features['airline_reliability'] < 0.75:
            factors.append({
                'factor': 'Airline History',
                'impact': 'moderate',
                'description': 'Airline has below-average on-time performance'
            })
        
        return factors
    
    def _generate_recommendations(self, risk_level: str, factors: list) -> list:
        """Generate actionable recommendations based on risk"""
        recommendations = []
        
        if risk_level in ['high', 'severe']:
            recommendations.append('Consider rebooking if schedule is critical')
            recommendations.append('Arrive at airport extra early')
            recommendations.append('Check flight status frequently')
        
        if risk_level == 'moderate':
            recommendations.append('Monitor flight status closely')
            recommendations.append('Have backup plans ready')
        
        # Specific recommendations based on factors
        for factor in factors:
            if factor['factor'] == 'Adverse Weather':
                recommendations.append('Check weather forecasts at both airports')
            elif factor['factor'] == 'Airport Congestion':
                recommendations.append('Consider earlier or later flights')
        
        return list(set(recommendations))  # Remove duplicates
    
    def _estimate_airport_congestion(self, airport_code: str, departure_time: datetime) -> float:
        """
        Estimate airport congestion level (0-1).
        In production, this would query real-time FAA data.
        """
        hour = departure_time.hour
        
        # Major hub airports are generally more congested
        major_hubs = ['ATL', 'ORD', 'LAX', 'DFW', 'DEN', 'JFK', 'SFO']
        base_congestion = 0.6 if airport_code in major_hubs else 0.3
        
        # Peak hours
        if 6 <= hour <= 9 or 16 <= hour <= 20:
            return min(base_congestion + 0.3, 1.0)
        elif 10 <= hour <= 15:
            return base_congestion
        else:
            return max(base_congestion - 0.2, 0.1)


class RouteOptimizer:
    """
    AI-based route and connection recommendations.
    Analyzes multiple routing options and recommends the best based on various factors.
    """
    
    def __init__(self, delay_predictor: DelayPredictor):
        self.delay_predictor = delay_predictor
    
    def recommend_routes(
        self,
        origin: str,
        destination: str,
        departure_date: datetime,
        available_routes: list
    ) -> list:
        """
        Analyze and rank available routes by reliability, speed, and safety.
        
        Args:
            origin: Origin airport code
            destination: Destination airport code
            departure_date: Desired departure datetime
            available_routes: List of possible routing options
            
        Returns:
            Ranked list of routes with scores and recommendations
        """
        
        scored_routes = []
        
        for route in available_routes:
            score = self._score_route(route, departure_date)
            scored_routes.append({
                'route': route,
                'overall_score': score['overall'],
                'reliability_score': score['reliability'],
                'speed_score': score['speed'],
                'weather_score': score['weather'],
                'recommendation': self._generate_route_recommendation(score),
                'risks': score['risks']
            })
        
        # Sort by overall score (descending)
        scored_routes.sort(key=lambda x: x['overall_score'], reverse=True)
        
        return scored_routes
    
    def _score_route(self, route: Dict[str, Any], departure_date: datetime) -> Dict[str, Any]:
        """Score a route based on multiple criteria"""
        
        scores = {
            'reliability': 0.0,
            'speed': 0.0,
            'weather': 0.0,
            'overall': 0.0,
            'risks': []
        }
        
        # Number of connections (fewer is better)
        num_connections = len(route.get('connections', []))
        connection_penalty = num_connections * 0.15
        
        # Base reliability score
        scores['reliability'] = max(0, 1.0 - connection_penalty)
        
        # Speed score (based on total travel time)
        total_time = route.get('total_duration_minutes', 300)
        scores['speed'] = max(0, 1.0 - (total_time - 120) / 600)  # Normalize around 2-12 hours
        
        # Weather impact on route
        weather_risk = 0
        for segment in route.get('segments', []):
            # Mock weather check - in production, check each airport
            weather_risk += 0.1  # placeholder
        
        scores['weather'] = max(0, 1.0 - weather_risk)
        
        # Identify risks
        if num_connections >= 2:
            scores['risks'].append('Multiple connections increase delay risk')
        
        if total_time > 600:  # More than 10 hours
            scores['risks'].append('Long travel time')
        
        # Calculate overall score (weighted average)
        scores['overall'] = (
            scores['reliability'] * 0.4 +
            scores['speed'] * 0.3 +
            scores['weather'] * 0.3
        )
        
        return scores
    
    def _generate_route_recommendation(self, score: Dict[str, Any]) -> str:
        """Generate human-readable recommendation"""
        
        if score['overall'] > 0.8:
            return "Highly recommended - Best combination of reliability and speed"
        elif score['overall'] > 0.65:
            return "Good option - Reliable with reasonable travel time"
        elif score['overall'] > 0.5:
            return "Acceptable - Consider if other options unavailable"
        else:
            return "Not recommended - High risk of delays or long travel time"