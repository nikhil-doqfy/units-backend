import random
from user_service.models import UserProfile



def request_otp_sent():
    otp = random.randint(1000, 9999)
    return otp
