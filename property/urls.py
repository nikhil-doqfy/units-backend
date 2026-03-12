from django.urls import path
from . import views

urlpatterns = [
    path('property', views.property, name='property'),
    path('property/blocks', views.property_blocks, name='property_blocks'),
    path('property/images', views.property_images, name='property_images'),
    path('property/document-types', views.property_document_types, name='property_document_types'),
    path('property/documents', views.property_documents, name='property_documents'),
]
