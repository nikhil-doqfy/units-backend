from django.urls import path
from payment import views as payment_views

urlpatterns = [
    path("access_rental_account/", payment_views.access_rental_account)
]