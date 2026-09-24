# property_management/celery_config.py

import os

from celery.schedules import crontab

# "redis" (not 127.0.0.1) matches the docker-compose service name -- inside
# a container, 127.0.0.1 refers to the container itself, not the redis
# service. DB index 0 stays isolated from units-finance's own queue, which
# uses DB index 1 (FINANCE_REDIS_URL).
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
broker_url = REDIS_URL
result_backend = REDIS_URL

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
    "send-lease-expiry-reminders-daily": {
        "task": "lease.tasks.send_lease_expiry_reminders",
        "schedule": crontab(hour=9, minute=15),  # daily at 9:15 AM
    },
    "release-expired-holds-hourly": {
        "task": "lead.tasks.release_expired_holds",
        "schedule": crontab(minute=0),  # hourly
    },
}