from django.test import TestCase, Client
from django.urls import reverse
import json


class SearchViewsTestCase(TestCase):
    """Test cases for search functionality"""

    def setUp(self):
        self.client = Client()

    def test_search_page_loads(self):
        """Test that the search page loads successfully"""
        response = self.client.get(reverse('search:search'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'search/search.html')

    def test_search_by_flight_number(self):
        """Test searching flights by flight number"""
        response = self.client.get(
            reverse('search:search_flights'),
            {'flight_number': 'AA101'}
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertIn('flights', data)
        self.assertIn('count', data)

    def test_search_by_airline(self):
        """Test searching flights by airline"""
        response = self.client.get(
            reverse('search:search_flights'),
            {'airline': 'American'}
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])

    def test_search_by_origin(self):
        """Test searching flights by origin airport"""
        response = self.client.get(
            reverse('search:search_flights'),
            {'origin': 'JFK'}
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])

    def test_search_by_destination(self):
        """Test searching flights by destination airport"""
        response = self.client.get(
            reverse('search:search_flights'),
            {'destination': 'LAX'}
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])

    def test_search_by_status(self):
        """Test filtering flights by status"""
        response = self.client.get(
            reverse('search:search_flights'),
            {'status': 'airborne'}
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])

    def test_combined_search(self):
        """Test searching with multiple parameters"""
        response = self.client.get(
            reverse('search:search_flights'),
            {
                'airline': 'American',
                'status': 'airborne',
                'origin': 'JFK'
            }
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])

    def test_empty_search(self):
        """Test search with no parameters returns all flights"""
        response = self.client.get(reverse('search:search_flights'))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertGreater(data['count'], 0)

    def test_no_results_search(self):
        """Test search that returns no results"""
        response = self.client.get(
            reverse('search:search_flights'),
            {'flight_number': 'NONEXISTENT999'}
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['count'], 0)
