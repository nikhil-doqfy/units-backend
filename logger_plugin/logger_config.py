import os
import logging.handlers
BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

PROJECT_ROOT = os.path.dirname(BASE_DIR)
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
os.makedirs(LOG_DIR, exist_ok=True) 
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,

    "formatters": {
        "standard": {
            "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        }
    },

    "handlers": {
        "application_file": {
            "level": "INFO",
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": os.path.join(LOG_DIR, "application.log"),
            "when": "midnight",
            "interval": 1,
            "backupCount": 30,
            "formatter": "standard",
            "encoding": "utf-8",
            "delay": True,
        }
    },

    "root": {
        "handlers": ["application_file"],
        "level": "INFO",
    },
    "loggers": {
        "django.request": {
            "handlers": ["application_file"],
            "level": "ERROR",
            "propagate": False,
    },
    "django.utils.autoreload": {
            "handlers": ["application_file"],
            "level": "ERROR",
            "propagate": False,
        }
    }
}

