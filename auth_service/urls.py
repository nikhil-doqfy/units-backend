from . import views
from django.urls import path

urlpatterns = [
    # path('login/', views.user_login, name='auth_login'),
    # path('login/google/', views.google_login, name='google_login'),
    # path('login/outlook/', views.outlook_login, name='google_login'),
    # path('logout/', views.logout, name='logout'),        
    path("otp/send", views.send_otp, name="send_otp"),
    path("otp/verify", views.verify_otp, name="verify_otp"),
    path("password/reset/", views.reset_password, name="reset_password"),
    # path("change/password", views.change_password, name="change_password"), 
    # path("uaepass/authorize", views.uaepass_authorize),
    # path("uaepass/callback", views.uaepass_callback),
    # path("uaepass/token", views.uaepass_token),
    # path("uaepass/userinfo", views.uaepass_userinfo),
    # path("uaepass/login", views.uaepass_final_login),
    
        
]

