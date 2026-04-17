# property_management/celery_config.py

from celery.schedules import crontab

broker_url = "redis://127.0.0.1:6379/0"
result_backend = "redis://127.0.0.1:6379/0"

accept_content = ["json"]
task_serializer = "json"
result_serializer = "json"

timezone = "Asia/Kolkata"

beat_scheduler = "django_celery_beat.schedulers:DatabaseScheduler"

# Optional: define periodic tasks here (if not using DB scheduler)
beat_schedule = {
    "send-expiry-reminders-daily": {
        "task": "user_service.tasks.send_agreement_expiry_reminders",
        "schedule": crontab(hour=9, minute=0),  # daily at 9 AM
    },
}