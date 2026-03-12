from django.urls import path
from user_service import views as user_serviceviews
from . import views

urlpatterns = [
    path("signup", user_serviceviews.user_sign_up),
    path("profile", views.userprofile_view, name='userprofile_view'), 
    path("management", views.user_management, name='user_management'),
    path('add_role', views.create_role, name='create_role'), 
    path('staff_view', views.staff_view, name='staff_view'),
    path('role_table', views.role_table_view, name='role_table_view'),
    path('users_csv', views.export_users_csv, name='export_users_csv'),
    path('staff_csv', views.export_staff_csv, name='export_staff_csv'),
    path("search_details", views.contact_list_view, name="contact_list"),
    path('create_lead', views.create_lead, name='create_lead'),
    path('convert_lead', views.convert_lead_to_tenant, name='convert_lead_to_tenant'),
    ] 
