from django.urls import path
from .views import charges_api

urlpatterns = [
    path("", charges_api),   
]