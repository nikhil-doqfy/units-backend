# config.py
import os
from dotenv import load_dotenv
from django.conf import settings

# Load .env file
load_dotenv()

# ------------------- General -------------------
HOST = os.getenv("HOST", "http://localhost:8000")
DEFAULT_HOST = os.getenv("DEFAULT_HOST", "http://localhost:8000")
PASSWORD_EXPIRY_TIME = 180

# ------------------- JWT -------------------
JWT_SECRET_KEY = settings.SECRET_KEY
JWT_ALGORITHM = "HS256"

# ------------------- Google OAuth -------------------
GOOGLE_OAUTH_TOKENINFO_URL = os.getenv(
    "GOOGLE_OAUTH_TOKENINFO_URL",
    "https://www.googleapis.com/oauth2/v3/tokeninfo?id_token={token}"
)

# ------------------- Microsoft OAuth -------------------
OUTLOOK_GRAPH_ME_URL = os.getenv(
    "OUTLOOK_GRAPH_ME_URL",
    "https://graph.microsoft.com/v1.0/me"
)

# ------------------- AWS / SES -------------------
EMAIL_CHANNEL_SES = "SES"
EMAIL_CHANNEL_SMTP = "SMTP"
EMAIL_CHANNEL_PREFERENCE = EMAIL_CHANNEL_SES
EMAIL_SENDER = "DOQFY - We Simplify <sarthak@doqfy.in>"
EMAIL_CHARSET = "UTF-8"

AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
AWS_PRESIGNED_EXPIRATION = int(os.getenv("AWS_PRESIGNED_EXPIRATION", 3600))
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
