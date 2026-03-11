from django.urls import path
from terms import views

urlpatterns = [
    path('', views.terms_api, name='terms-api'),
]