from django.urls import path
from home.ai_views import predict_delay, recommend_routes

urlpatterns = [
    path('predict-delay/', predict_delay, name='predict_delay'),
    path('recommend-routes/', recommend_routes, name='recommend_routes'),
]