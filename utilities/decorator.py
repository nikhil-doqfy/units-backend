from functools import wraps
from user_service.models import UserProfile
from utilities import constants, status
from utilities.helper_functions import prepare_response, is_password_expire
from utilities.jwt_token import get_jwt_token, decode_jwt_token
# from property_management.models import Role, ApiPermissions, RolePermission
from utilities import constants

def is_request_authenticated(function):
    def wrap(request, *args, **kwargs):

        # ── Allow OPTIONS for Swagger ──────────────────
        if request.method == "OPTIONS":
            from django.http import HttpResponse
            response = HttpResponse()
            response["Allow"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            response["Access-Control-Allow-Origin"] = "*"
            response["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
            response["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            return response

        token = request.headers.get('Authorization')
        if token:
            token = get_jwt_token(token) 
            if not token: 
                return prepare_response(
                    message=constants.INVALID_TOKEN_PAYLOAD, 
                    status=status.HTTP_401_UNAUTHORIZED
                )   

            decoded_token = decode_jwt_token(token)
            if 'error' in decoded_token:
                return prepare_response(
                    message=decoded_token.get('error'), 
                    status=status.HTTP_401_UNAUTHORIZED
                ) 

            user_email = decoded_token.get("email")
            user_profile = UserProfile.objects.filter(user__email=user_email).first()

            if not user_profile:
                return prepare_response(
                    message=constants.AUTH_USER_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )

            if not user_profile.user.is_active:
                return prepare_response(
                    message=constants.USER_ACCOUNT_DISABLED,
                    status=status.HTTP_403_FORBIDDEN
                )

            if user_profile.token != token:
                return prepare_response(
                    message=constants.TOKEN_INVALID_OR_EXPIRED,
                    status=status.HTTP_401_UNAUTHORIZED
                )

            request.user = user_profile  

            if is_password_expire(user_profile):
                return prepare_response(
                    message=constants.PASSWORD_EXPIRED,
                    status=status.HTTP_401_UNAUTHORIZED
                )

            return function(request, *args, **kwargs)

        else:
            return prepare_response(
                message=constants.INVALID_LOGIN_DETAILS,
                status=status.HTTP_401_UNAUTHORIZED
            )
            
    wrap.__doc__ = function.__doc__
    wrap.__name__ = function.__name__
    return wrap