from django.urls import path
from user_service import views as user_serviceviews

urlpatterns = [
    path("signup/", user_serviceviews.user_sign_up),
    path("otp/send/", user_serviceviews.send_otp),

]