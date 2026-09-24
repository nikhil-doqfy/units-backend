"""
Real DRF authentication, wrapping the same JWT/token logic as
utilities/decorator.py::is_request_authenticated so both can coexist while
the API migrates to DRF endpoint-by-endpoint (see lease/lead's DRF pass).

Unlike the decorator (which returns 401/403/404 depending on failure type
via prepare_response), DRF's authentication contract only supports raising
AuthenticationFailed (401) or returning None (unauthenticated). All auth-
stage failures below surface as 401 -- this is a deliberate, standard DRF
convention, not an attempt to preserve the decorator's exact status codes.
"""
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from user_service.models import UserProfile
from utilities import constants
from utilities.helper_functions import is_password_expire
from utilities.jwt_token import get_jwt_token, decode_jwt_token


class JWTAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return None

        token = get_jwt_token(auth_header)
        if not token:
            raise AuthenticationFailed(constants.INVALID_TOKEN_PAYLOAD)

        decoded_token = decode_jwt_token(token)
        if "error" in decoded_token:
            raise AuthenticationFailed(decoded_token.get("error"))

        user_email = decoded_token.get("email")
        user_profile = UserProfile.objects.filter(user__email=user_email).first()
        if not user_profile:
            raise AuthenticationFailed(constants.AUTH_USER_NOT_FOUND)

        if not user_profile.user.is_active:
            raise AuthenticationFailed(constants.USER_ACCOUNT_DISABLED)

        if user_profile.token != token:
            raise AuthenticationFailed(constants.TOKEN_INVALID_OR_EXPIRED)

        if is_password_expire(user_profile):
            raise AuthenticationFailed(constants.PASSWORD_EXPIRED)

        # UserProfile isn't a Django auth user (no AbstractBaseUser), but
        # DRF's IsAuthenticated permission duck-types request.user.is_authenticated.
        # An instance-level attribute (not persisted, doesn't touch the model
        # class) is the standard way to satisfy that check for a custom user
        # object -- same pattern used wherever DRF is bolted onto a
        # non-Django-auth user model.
        user_profile.is_authenticated = True
        return (user_profile, token)

    def authenticate_header(self, request):
        # Without this, DRF's permission_denied() has no authenticate_header
        # to fall back on and returns 403 for a request with no credentials
        # at all -- returning a WWW-Authenticate scheme here makes DRF raise
        # NotAuthenticated (401) instead, matching this app's convention
        # (is_request_authenticated always returned 401 for a missing token).
        return "Bearer"
