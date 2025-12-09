
from . import views
from django.urls import path
from .views import api_usage_readout

app_name = 'home'


urlpatterns = [
    path('', views.index, name='index'),
    path('flight/<int:flight_id>/', views.flight_detail_view, name='flight_detail'),
    path('track/<str:flight_number>/', views.track_flight, name='flight_tracker'),
    path('flight/<int:flight_id>/assess-risk/', views.assess_delay_risk_view, name='assess_delay_risk'),
    path('account/', views.account_view, name='account'),
    path("admin/api-usage/", api_usage_readout, name="api_usage_readout"),
    path('weather/', views.weather_insights, name='weather_insights'),
    path('debug-config/', views.debug_config, name='debug_config'),
]
