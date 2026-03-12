import os
from pathlib import Path
from dotenv import load_dotenv
from django.conf import settings

# Load environment-specific .env file based on APP_ENV (default: dev)
# Looks for: .env.dev / .env.uat / .env.prod in the units-architecture directory
# If the file doesn't exist, load_dotenv silently skips it — no crash
_env_dir = Path(__file__).resolve().parents[3]
_app_env = os.getenv("APP_ENV", "dev")
_env_file = _env_dir / f".env.{_app_env}"
load_dotenv(dotenv_path=_env_file)

HOST = os.getenv("HOST", "http://localhost:8000")
DEFAULT_HOST = os.getenv("DEFAULT_HOST", "http://localhost:8000")
PASSWORD_EXPIRY_TIME = 180
JWT_SECRET_KEY = settings.SECRET_KEY
JWT_ALGORITHM = "HS256"

GOOGLE_OAUTH_TOKENINFO_URL = os.getenv("GOOGLE_OAUTH_TOKENINFO_URL")
OUTLOOK_GRAPH_ME_URL = os.getenv("OUTLOOK_GRAPH_ME_URL")

EMAIL_CHANNEL_SES = "SES"
EMAIL_CHANNEL_SMTP = "SMTP"
EMAIL_CHANNEL_PREFERENCE = os.getenv("EMAIL_CHANNEL_PREFERENCE", EMAIL_CHANNEL_SES)
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_CHARSET = os.getenv("EMAIL_CHARSET", "UTF-8")

AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
AWS_REGION = os.getenv("AWS_REGION")
AWS_PRESIGNED_EXPIRATION = int(os.getenv("AWS_PRESIGNED_EXPIRATION", 3600))
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

OTP_VALID_TIME = int(os.getenv("OTP_VALID_TIME", 300))  # Default to 5 minutes (300 seconds)
