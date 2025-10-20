from django.urls import path
from . import views

app_name = 'home'

urlpatterns = [
    path('', views.index, name='index'),
    path('flight/<int:flight_id>/', views.flight_detail, name='flight_detail'),
]