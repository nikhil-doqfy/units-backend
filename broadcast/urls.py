from django.urls import path

from broadcast import views

app_name = "broadcast"

urlpatterns = [
    # List / create / edit / delete announcements
    path("announcement/",views.announcement,name="announcement"),

    # Manually send a draft or scheduled announcement
    path("send/",views.announcement_send,name="announcement_send"),

    # Upload / replace the banner image
    path("banner/",views.announcement_banner,name="announcement_banner"),

    # Per-announcement recipient list (with status filter & pagination)
    path("recipients/", views.announcement_recipients, name="announcement_recipients"),
]