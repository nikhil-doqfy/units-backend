import os
import logging
from logging.handlers import TimedRotatingFileHandler

BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

PROJECT_ROOT = os.path.dirname(BASE_DIR)
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "application.log")

def get_logger(name):

    logger = logging.getLogger(name)
    if not logger.handlers:

        file_handler = TimedRotatingFileHandler(
            filename=LOG_FILE,
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8"
        )

        formatter = logging.Formatter(
            "%(asctime)s - %(name)25s - %(funcName)25s() - %(levelname)10s - %(lineno)s - %(message)s"
        )

        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    logger.setLevel(logging.INFO)
    logger.propagate = False

    return logger
