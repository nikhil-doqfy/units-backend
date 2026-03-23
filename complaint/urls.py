from django.urls import path
from complaint import views

urlpatterns = [
    path('complaint/', views.complaint_api, name='complaint_api'),
    path('complaint/images/', views.upload_complaint_images, name='upload_complaint_images'),
    path('complaint/<str:complaint_id>/', views.complaint_detail_api, name='complaint_detail_api'),
]