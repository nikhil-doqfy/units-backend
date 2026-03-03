from django.urls import path
from . import views

urlpatterns = [
    path('', views.terms_api, name='terms-api'),
]