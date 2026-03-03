from django.urls import path
from .views import terms_api

urlpatterns = [
    path('terms/', terms_api, name='terms_api'),
]