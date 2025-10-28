from functools import wraps
from user_service.models import UserProfile
from utilities import constants, status
from utilities.helper_functions import prepare_response
from utilities.jwt_token import get_jwt_token, decode_jwt_token  

def is_request_authenticated(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        try:
            auth_header = request.headers.get("Authorization")
            if not auth_header:
                return prepare_response(
                    message="Authorization header missing",
                    status=401
                )
            token = get_jwt_token(auth_header)
            if isinstance(token, dict) and "message" in token:
                return prepare_response(
                    message=token["message"],
                    status=401
                )
            decoded_token = decode_jwt_token(token)
            if isinstance(decoded_token, dict) and "error" in decoded_token:
                return prepare_response(
                    message=decoded_token["error"],
                    status=401
                )
            user_email = decoded_token.get("email")
            if not user_email:
                return prepare_response(
                    message="Invalid token payload",
                    status=401
                )
            user = UserProfile.objects.filter(email=user_email).first()
            if not user:
                return prepare_response(
                    message="User not found",
                    status=404
                )
            if user.token != token:
                return prepare_response(
                    message="Token invalid or expired",
                    status=401
                )
            request.user = user
        except Exception as e:
            print("Auth Error:", e)
            return prepare_response(
                message="Authentication failed",
                status=500
            )
        return view_func(request, *args, **kwargs)
    return wrapper
