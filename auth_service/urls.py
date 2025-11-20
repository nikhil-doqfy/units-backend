from . import views
from django.urls import path

urlpatterns = [
    path('login/', views.user_login, name='auth_login'),
    path('login/google/', views.google_login, name='google_login'),
    path('login/outlook/', views.outlook_login, name='google_login'),
    path('logout/', views.logout, name='logout'),        
    path("password/otp/send/", views.send_password_otp, name="send_password_otp"),
    path("password/otp/verify/", views.verify_password_otp, name="verify_password_otp"),
    path("password/reset/", views.reset_password, name="reset_password"),

    # path("uaepass/authorize", views.uaepass_authorize),
    # path("uaepass/callback", views.uaepass_callback),
    # path("uaepass/token", views.uaepass_token),
    # path("uaepass/userinfo", views.uaepass_userinfo),
    # path("uaepass/login", views.uaepass_final_login),
    
        
]

