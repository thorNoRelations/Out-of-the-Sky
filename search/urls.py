from django.urls import path
from . import views

app_name = 'search'

urlpatterns = [
    path('', views.search, name='search'),
    path('api/flights/', views.search_flights, name='search_flights'),

    # Interactive Map URLs
    path('map/', views.interactive_map, name='interactive_map'),
    path('api/live-flights/', views.get_live_flights, name='get_live_flights'),
    path('api/flight/<str:icao24>/', views.get_flight_details, name='get_flight_details'),
]