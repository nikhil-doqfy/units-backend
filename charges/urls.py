from django.urls import path
from charges import views as charge_views
from . import views

urlpatterns = [
    path("manage_charges/", charge_views.charges_api),  
    path("toggle_charge_editable/", views.toggle_charge_editable), 
]