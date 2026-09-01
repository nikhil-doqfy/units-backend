from django.urls import path
from support import views
from property_management.models import Base

urlpatterns = [
    path("support-ticket", views.support_ticket_api, name="support_ticket_api"),
    path("support-ticket/reply", views.support_ticket_reply_api, name="support_ticket_reply_api"),
]