import jwt
from utilities.config import JWT_SECRET_KEY,JWT_ALGORITHM
from django.utils import timezone
from datetime import timedelta
from utilities import constants

def create_jwt_token(user_profile):
    token = jwt.encode({'user_id':user_profile.id},JWT_SECRET_KEY,algorithm=JWT_ALGORITHM)
    if user_profile.token_expiry:
        token = jwt.encode({'user_id':user_profile.id, 'exp': timezone.now() + timedelta(minutes=user_profile.token_expiry)},JWT_SECRET_KEY,algorithm=JWT_ALGORITHM)
    user_profile.token = token
    user_profile.save()
    return token      

def get_jwt_token(token):
    token = token.split(' ')  
    if len(token) != 2 and token[0] != 'Bearer':
        return { 'message': constants.INVALID_TOKEN }
    return token[1]

def decode_jwt_token(token):
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return {'error': constants.TOKEN_EXPIRED }
    except jwt.DecodeError:
        return {'error': constants.INVALID_TOKEN}