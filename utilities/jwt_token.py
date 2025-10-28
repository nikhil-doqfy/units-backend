import jwt
from utilities.config import JWT_SECRET_KEY, JWT_ALGORITHM
from datetime import datetime, timedelta
from utilities import constants

DEFAULT_EXPIRY_MINUTES = 60
def create_jwt_token(user_profile):
    expiry_time = datetime.utcnow() + timedelta(minutes=constants.JWT_TOKEN_EXPIRY_MINUTES)
    payload = {
        'user_id': user_profile.id,
        'email': user_profile.email,
        'exp': expiry_time
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    user_profile.token = token
    user_profile.save(update_fields=['token'])
    return token


def get_jwt_token(auth_header: str):
    parts = auth_header.split(' ')
    if len(parts) != 2 or parts[0] != 'Bearer':
        return {'message': constants.INVALID_TOKEN}
    return parts[1]


def decode_jwt_token(token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return {'error': constants.TOKEN_EXPIRED}
    except jwt.DecodeError:
        return {'error': constants.INVALID_TOKEN}
