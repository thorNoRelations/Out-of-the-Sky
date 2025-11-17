from django.urls import path
from . import views
from home import views as home_views  # Import from home

app_name = 'search'

urlpatterns = [
    path('', views.search, name='search'),
    path('api/flights/', views.search_flights, name='search_flights'),
    # Interactive Map URLs - import from home.views
    path('map/', home_views.interactive_map, name='interactive_map'),
    path('api/live-flights/', home_views.get_live_flights, name='get_live_flights'),
    path('api/flight/<str:icao24>/', home_views.get_flight_details, name='get_flight_details'),
]