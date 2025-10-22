from django.conf import settings
import os
from dotenv import load_dotenv

HOST="http://localhost:8000"   #config.py
PASSWORD_EXPIRY_TIME = 180 
DEFAULT_HOST = "http://localhost:8000"



# JWT
JWT_SECRET_KEY = settings.SECRET_KEY
JWT_ALGORITHM = "HS256"
# Google OAuth config
GOOGLE_OAUTH_TOKENINFO_URL = "https://www.googleapis.com/oauth2/v3/tokeninfo?id_token={token}"
#Microsoft OAuth config
OUTLOOK_GRAPH_ME_URL = "https://graph.microsoft.com/v1.0/me"
# ----------------------------------------SES_AWS----------------------------------------------------------------------
# utilities/config.py

load_dotenv()
EMAIL_CHANNEL_SES = 'SES'
EMAIL_CHANNEL_SMTP = 'SMTP'
EMAIL_CHANNEL_PREFERENCE = EMAIL_CHANNEL_SES
EMAIL_SENDER = "DOQFY - We Simplify <admin@doqfy.in>"
EMAIL_CHARSET = "UTF-8"
# EMAIL_SENDER = "DOQFY - We Simplify <admin@doqfy.in>"





AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")
AWS_PRESIGNED_EXPIRATION = int(os.getenv("AWS_PRESIGNED_EXPIRATION", 3600))
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")