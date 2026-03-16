from django.urls import path
from lead import views

urlpatterns = [
    path('lead', views.lead_view, name='lead_view'),
    path('lead/bulk-import', views.lead_bulk_import, name='lead_bulk_import'),
    path('lead/activity-log', views.activity_log_view, name='activity_log_view'),
]
