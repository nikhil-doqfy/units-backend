from django.urls import path
from user_service import views as user_serviceviews
from . import views

urlpatterns = [
    path("signup", user_serviceviews.user_sign_up),
    
    path("profile", views.userprofile_view, name='userprofile_view'),

]