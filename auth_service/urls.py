from . import views
from django.urls import path

urlpatterns = [
    path('login', views.user_login, name='auth_login'),
    path('logout', views.logout, name='logout'),        
    path("otp/send", views.send_otp, name="send_otp"),
    path("otp/verify", views.verify_otp, name="verify_otp"),
    path("password/reset", views.reset_password, name="reset_password"),
    path("change/password", views.change_password, name="change_password"), 

    
        
]

