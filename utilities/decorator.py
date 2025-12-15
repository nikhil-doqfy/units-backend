from functools import wraps
from user_service.models import UserProfile
from utilities import constants, status
from utilities.helper_functions import prepare_response
from utilities.jwt_token import get_jwt_token, decode_jwt_token
from jwt import ExpiredSignatureError


def is_request_authenticated(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        try:
            # --------------------
            # 1. Get Authorization Token
            # --------------------
            auth_header = request.headers.get("Authorization")
            if not auth_header:
                return prepare_response(
                    message=constants.AUTH_HEADER_MISSING,
                    status=status.HTTP_401_UNAUTHORIZED
                )

            token = get_jwt_token(auth_header)
            if isinstance(token, dict) and token.get("message"):
                return prepare_response(
                    message=token["message"],
                    status=status.HTTP_401_UNAUTHORIZED
                )

            # --------------------
            # 2. Decode Token
            # --------------------
            try:
                decoded_token = decode_jwt_token(token)
            except ExpiredSignatureError:
                return prepare_response(
                    message=constants.TOKEN_EXPIRED,
                    status=status.HTTP_401_UNAUTHORIZED
                )

            if isinstance(decoded_token, dict) and decoded_token.get("error"):
                return prepare_response(
                    message=decoded_token["error"],
                    status=status.HTTP_401_UNAUTHORIZED
                )

            # --------------------
            # 3. Validate Payload
            # --------------------
            user_email = decoded_token.get("email")
            if not user_email:
                return prepare_response(
                    message=constants.INVALID_TOKEN_PAYLOAD,
                    status=status.HTTP_401_UNAUTHORIZED
                )

            # --------------------
            # 4. Fetch UserProfile
            # --------------------
            user_profile = UserProfile.objects.filter(user__email=user_email).first()
            if not user_profile:
                return prepare_response(
                    message=constants.AUTH_USER_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )

            # --------------------
            # 5. Validate Token Match
            # --------------------
            if user_profile.token != token:
                return prepare_response(
                    message=constants.TOKEN_INVALID_OR_EXPIRED,
                    status=status.HTTP_401_UNAUTHORIZED
                )

            # --------------------
            # 6. Attach user to request
            # --------------------
            request.user = user_profile   # same logic preserved

        except Exception as e:
            print("Auth Error:", e)
            return prepare_response(
                message=constants.AUTHENTICATION_FAILED,
                status=status.HTTP_401_UNAUTHORIZED
            )

        return view_func(request, *args, **kwargs)

    return wrapper
