from django.urls import path
from payment import views as payment_views

urlpatterns = [
    path("access_rental_account/", payment_views.access_rental_account),

    path("owner_rent_amounts/", payment_views.owner_rent_amounts),

    path("rental_payments/",payment_views.rental_payments),

    
]