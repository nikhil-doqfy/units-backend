from django.urls import path
from . import views

urlpatterns = [
    path("charges", views.charges),
]
