from django.urls import path
from public_api import views as public_api_views

urlpatterns = [
    path("generate_keys/", public_api_views.generate_keys),
]