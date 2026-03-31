from django.urls import path
from complaint import views

urlpatterns = [
    path('complaint', views.complaint_api, name='complaint_api'),
    path('complaint/images', views.upload_complaint_images, name='upload_complaint_images'),
    path('complaint/accept/<str:code>', views.accept_complaint, name='accept_complaint'),
    path('complaint/decline/<str:code>', views.decline_complaint, name='decline_complaint'),
    path('complaint/start/<str:code>', views.start_work, name='start_work'),
    path('complaint/complete/<str:code>', views.complete_work, name='complete_work'),
    path('complaint/verify/<str:code>', views.verify_complaint, name='verify_complaint'),
]