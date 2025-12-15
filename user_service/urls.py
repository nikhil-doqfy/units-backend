from django.urls import path
from user_service import views as user_serviceviews
from . import views

urlpatterns = [
    path("signup", user_serviceviews.user_sign_up),
    
    path("profile", views.userprofile_view, name='userprofile_view'),
    # path('staff/signup/', views.staff_signup, name='staff_signup'), 
    # path('profile/view/', views.user_profile_view, name='user_profile_view'), 
    # path('user/management', views.user_management_view, name='user_management_view'), 
    # path('toggle/user/active', views.toggle_user_active, name='toggle_user_active'),
]