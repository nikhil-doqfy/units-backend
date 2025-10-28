import requests
from user_service.models import UserProfile
from utilities.config import GOOGLE_OAUTH_TOKENINFO_URL, OUTLOOK_GRAPH_ME_URL
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

def verify_google_token(token: str) -> dict:
    url = GOOGLE_OAUTH_TOKENINFO_URL.format(token=token)
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    return None

def login_with_google(oauth_token: str):
    payload = verify_google_token(oauth_token)
    print("🔹 Payload from Google:", payload)
    if not payload:
        return None
    email = payload.get("email")
    if not email:
        return None
    user = UserProfile.objects.filter(email=email).first()
    return user


def verify_outlook_token(token: str) -> dict: 
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(OUTLOOK_GRAPH_ME_URL, headers=headers)
    if response.status_code == 200:
        return response.json()
    return None

def login_with_outlook(oauth_token: str):
    payload = verify_outlook_token(oauth_token)
    if not payload:
        return None
    email = payload.get("mail") or payload.get("userPrincipalName")
    if not email:
        return None
    return UserProfile.objects.filter(email=email).first()