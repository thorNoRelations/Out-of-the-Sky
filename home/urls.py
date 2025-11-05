from . import views
from django.urls import path
from .views import api_usage_readout

app_name = 'home'

urlpatterns = [
    path('', views.index, name='index'),
    path('flight/<int:flight_id>/', views.flight_detail, name='flight_detail'),
    path("admin/api-usage/", api_usage_readout, name="api_usage_readout"),
]