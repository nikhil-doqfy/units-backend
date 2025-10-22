from django.urls import path
from user_service import views as user_serviceviews
from . import views

urlpatterns = [
    path("signup/", user_serviceviews.user_sign_up),
    path("otp/send/", user_serviceviews.send_otp),
    path('staff/signup/', views.staff_signup, name='staff_signup'),

]