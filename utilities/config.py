import os
from pathlib import Path
from dotenv import load_dotenv
from django.conf import settings

# Load environment-specific .env file based on APP_ENV (default: dev)
# Looks for: .env.dev / .env.uat / .env.prod in the units-architecture directory
# If the file doesn't exist, load_dotenv silently skips it — no crash
_env_dir = Path(__file__).resolve().parents[3]
print(_env_dir)
_app_env = os.getenv("APP_ENV", "dev")
_env_file = _env_dir / f".env.{_app_env}"
load_dotenv(dotenv_path=_env_file)

HOST = os.getenv("HOST", "http://localhost:8000")
DEFAULT_HOST = os.getenv("DEFAULT_HOST", "http://localhost:8000")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:4200")
PASSWORD_EXPIRY_TIME = 180
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = "HS256"

GOOGLE_OAUTH_TOKENINFO_URL = os.getenv("GOOGLE_OAUTH_TOKENINFO_URL")
OUTLOOK_GRAPH_ME_URL = os.getenv("OUTLOOK_GRAPH_ME_URL")

FINANCE_SERVICE_URL = os.getenv("FINANCE_SERVICE_URL", "http://units-finance:8001")
FINANCE_INTERNAL_TOKEN = os.getenv("FINANCE_INTERNAL_TOKEN")

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

SES_AWS_ACCESS_KEY = os.getenv("SES_AWS_ACCESS_KEY", AWS_ACCESS_KEY)
SES_AWS_SECRET_KEY = os.getenv("SES_AWS_SECRET_KEY", AWS_SECRET_KEY)
SES_AWS_REGION = os.getenv("SES_AWS_REGION", AWS_REGION)

OTP_VALID_TIME = int(os.getenv("OTP_VALID_TIME", 300))  # Default to 5 minutes (300 seconds)

# E-signature -- pluggable provider (see lease/esign/). SIGNATURE_PROVIDER
# picks which one lease/esign/factory.py hands back; adding a second
# provider later (DocuSign, Adobe Sign, ...) means implementing
# lease/esign/base.py's SignatureProvider and registering it in
# factory.py's _PROVIDERS -- no changes needed in lease/views.py.
SIGNATURE_PROVIDER = os.getenv("SIGNATURE_PROVIDER", "uaepass")

# UAE PASS eSignSP -- a real PAdES digital signature applied to the
# document (not just a login event). CLIENT_ID/SECRET here are for the
# signature service specifically, issued separately from a plain UAE PASS
# OAuth login app -- see the "prerequisites" note in the docs. Not set in
# dev; until they are, starting a signature will fail with a clear
# "not configured" error rather than silently sending a broken request.
# Docs: https://docs.uaepass.ae/feature-guides/signature-integration-guide/digital-signature-single-document
UAE_PASS_ENV = os.getenv("UAE_PASS_ENV", "staging")  # "staging" | "production"
UAE_PASS_HOST = "id.uaepass.ae" if UAE_PASS_ENV == "production" else "stg-id.uaepass.ae"
UAE_PASS_SIGN_TOKEN_URL = f"https://{UAE_PASS_HOST}/trustedx-authserver/oauth/main-as/token"
UAE_PASS_SIGN_RESOURCE_URL = f"https://{UAE_PASS_HOST}/trustedx-resources/esignsp/v2"
# UAE PASS's own docs illustrate the Authorization header with a
# "docsign:demodemo" credential, but it's just a redacted example, not a
# live shared sandbox account -- confirmed by testing it directly against
# staging (401 Unauthorized). A real client_id/secret issued by the UAE
# PASS team is required even for staging.
UAE_PASS_SIGN_CLIENT_ID = os.getenv("UAE_PASS_SIGN_CLIENT_ID")
UAE_PASS_SIGN_CLIENT_SECRET = os.getenv("UAE_PASS_SIGN_CLIENT_SECRET")
UAE_PASS_SIGN_SCOPE = os.getenv("UAE_PASS_SIGN_SCOPE", "urn:safelayer:eidas:sign:process:document")
# Issued by the UAE PASS team alongside the client credentials -- identifies
# which signature policy (PAdES profile, certificate authority, etc.) to sign under.
UAE_PASS_SIGN_POLICY_ID = os.getenv("UAE_PASS_SIGN_POLICY_ID", "")
UAE_PASS_SIGN_CALLBACK_URL = os.getenv("UAE_PASS_SIGN_CALLBACK_URL", f"{HOST}/api/lease/esign/callback")

print("AWS REGION:", os.getenv("AWS_REGION"))
