from django.urls import path
from . import views

app_name = 'home'

urlpatterns = [
    path('', views.index, name='index'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('add-flight/', views.add_flight, name='add_flight'),
    path('remove-flight/<int:tracked_flight_id>/', views.remove_flight, name='remove_flight'),
    path('flight/<int:tracked_flight_id>/', views.flight_detail, name='flight_detail'),
]