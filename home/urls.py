from . import views
from django.urls import path
from .views import api_usage_readout

app_name = 'home'

from .ai_views import (
    predict_delay, recommend_routes,
    delay_prediction_page, route_optimizer_page
)

urlpatterns = [
    path('', views.index, name='index'),
    path('flight/<int:flight_id>/', views.flight_detail, name='flight_detail'),
    path("admin/api-usage/", api_usage_readout, name="api_usage_readout"),
    path('weather/', views.weather_insights, name='weather_insights'),
       path('debug-config/', views.debug_config, name='debug_config'),
]
