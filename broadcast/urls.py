from django.urls import path
from broadcast import views

urlpatterns = [
    path("announcement/",views.announcement,name="announcement"),
    path("send/",views.announcement_send,name="announcement_send"),
    path("banner/",views.announcement_banner,name="announcement_banner"),
    path("recipients/", views.announcement_recipients, name="announcement_recipients"),
]