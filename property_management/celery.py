import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'property_management.settings')

app = Celery('property_management')

# 🔥 THIS LINE IS IMPORTANT
app.config_from_object('property_management.celery_config')

app.autodiscover_tasks()