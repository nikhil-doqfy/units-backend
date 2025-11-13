import random
from user_service.models import UserProfile

def request_otp_sent():
    otp = random.randint(100000, 999999)
    return otp
