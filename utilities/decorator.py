from functools import wraps
from django.http import JsonResponse
from user_service.models import UserProfile
from utilities import constants, status
from utilities.helper_functions import prepare_response
from utilities.jwt_token import get_jwt_token, decode_jwt_token  # ✅ centralized functions
# from utilities.config import JWT_SECRET_KEY, JWT_ALGORITHM  # ✅ centralized config

def is_request_authenticated(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        try:
            # ---------- Get Token from Header ----------
            auth_header = request.headers.get("Authorization")
            if not auth_header:
                return prepare_response(
                    message="Authorization header missing",
                    status=status.HTTP_401_UNAUTHORIZED
                )

            token = get_jwt_token(auth_header)
            if isinstance(token, dict) and "message" in token:
                return prepare_response(
                    message=token["message"],
                    status=status.HTTP_401_UNAUTHORIZED
                )

            # ---------- Decode Token ----------
            decoded_token = decode_jwt_token(token)
            if isinstance(decoded_token, dict) and "error" in decoded_token:
                return prepare_response(
                    message=decoded_token["error"],
                    status=status.HTTP_401_UNAUTHORIZED
                )

            # ---------- Extract email ----------
            user_email = decoded_token.get("email")
            if not user_email:
                return prepare_response(
                    message="Invalid token payload",
                    status=status.HTTP_401_UNAUTHORIZED
                )

            # ---------- Fetch user from DB ----------
            user = UserProfile.objects.filter(email=user_email).first()
            if not user:
                return prepare_response(
                    message="User not found",
                    status=status.HTTP_404_NOT_FOUND
                )

            # ---------- Attach user ----------
            request.user = user

        except Exception as e:
            print("Auth Error:", e)
            return prepare_response(
                message="Authentication failed",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # ---------- Proceed ----------
        return view_func(request, *args, **kwargs)

    return wrapper
