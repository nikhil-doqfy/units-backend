from django.urls import path
from user_service import views as user_serviceviews
from lead import views

urlpatterns = [
    path('create_lead', views.create_lead, name='create_lead'),
    path('convert_lead', views.convert_lead_to_tenant, name='convert_lead_to_tenant'),
] 
