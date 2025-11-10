
import json
import uuid
from django.contrib.auth.hashers import make_password ,check_password
from utilities import status, constants
from utilities.helper_functions import prepare_response , validate_email, send_email, validate_password,send_ses_email
from user_service.models import UserProfile  ,UserVerification
from user_service.utils import request_otp_sent
from utilities.decorator import is_request_authenticated
from utilities.jwt_token import create_jwt_token , get_jwt_token, decode_jwt_token
from utilities.oauth_utils import login_with_outlook ,login_with_google
from django.utils import timezone
from datetime import datetime, timedelta
from django.template.loader import render_to_string

def user_login(request):
    if request.method != "POST":
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        data = json.loads(request.body)
        email = data.get("email")
        password = data.get("password")
        otp = data.get("otp")
    except json.JSONDecodeError:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_400_BAD_REQUEST
        )

   
    if email and password:
        user = UserProfile.objects.filter(email=email).first()
        if not user:
            return prepare_response(
                message=constants.USER_NOT_ONBOARDED,
                status=status.HTTP_400_BAD_REQUEST
            )

        if not check_password(password, user.hashed_password):
            return prepare_response(
                message=constants.INVALID_CREDENTIALS,
                status=status.HTTP_400_BAD_REQUEST
            )

        if not user.is_login_allowed:
            return prepare_response(
                message=constants.LOGIN_NOT_ALLOWED,
                status=status.HTTP_403_FORBIDDEN
            )

        token = create_jwt_token(user)
        return prepare_response(
            content={
                "id": user.id,
                "email": user.email,
                "user_type": user.user_type,
                "is_verified": user.is_verified,
                "is_detail_updated": user.is_detail_updated,
                "is_document_uploaded": user.is_document_uploaded,
                "access_token": token,
                "token_type": "Bearer"
            },
            message=constants.LOGIN_SUCCESSFUL,
            status=status.HTTP_200_OK
        )

    elif email and otp:
        try:
            user = UserProfile.objects.get(email=email)
        except UserProfile.DoesNotExist:
            return prepare_response(
                message=constants.USER_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        record = UserVerification.objects.filter(
            email=email, otp=otp
        ).order_by('-created').first()

        if not record:
            return prepare_response(
                message=constants.INCORRECT_OTP,
                status=status.HTTP_400_BAD_REQUEST
            )


        if record.is_verified:
            token = create_jwt_token(user)
            record.verified_time = timezone.now()
           
            token = create_jwt_token(user)
            record.is_verified = False
            record.save()
            return prepare_response(
                content={ 
                "id": user.id,
                "email": user.email,
                "user_type": user.user_type,
                "is_verified": user.is_verified,
                "access_token": token,
                "token_type": "Bearer"
              },
            message=constants.LOGIN_SUCCESSFUL_WITH_OTP,
            status=status.HTTP_200_OK
               )
        else:
            return prepare_response(       
            message=constants. OTP_NOT_VERIFIED,
            status=status.HTTP_400_BAD_REQUEST
        )



    else:
        return prepare_response(
            message=constants.FIELD_REQUIRED,
            status=status.HTTP_400_BAD_REQUEST
        )





def google_login(request):
    if request.method != "POST":
        return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    try:
        data = json.loads(request.body)
        oauth_token = data.get("token")
     

    except json.JSONDecodeError:
        return prepare_response(message=constants.INVALID_JSON_BODY, status=status.HTTP_400_BAD_REQUEST)

    if not oauth_token:
        return prepare_response(message=constants.OAUTH_TOKEN_REQUIRED, status=status.HTTP_400_BAD_REQUEST)

    user = login_with_google(oauth_token)
    if not user:
        return prepare_response(message=constants.INVALID_CREDENTIALS, status=status.HTTP_401_UNAUTHORIZED)

    token = create_jwt_token(user)

    return prepare_response(
        content={
            "id": user.id,
            "email": user.email,
            "user_type": user.user_type,
            "is_verified": user.is_verified,
            "is_detail_updated": user.is_detail_updated,
            "is_document_uploaded": user.is_document_uploaded,
            "access_token": token,
            "token_type": "Bearer"
        },
        message=constants.LOGIN_SUCCESSFUL,
        status=status.HTTP_200_OK
    )


def outlook_login(request):
    if request.method != "POST":
        return prepare_response(
            message=constants.INVALID_REQUEST,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    try:
        data = json.loads(request.body)
        oauth_token = data.get("token")
    except json.JSONDecodeError:
        return prepare_response(
            message=constants.INVALID_JSON_BODY,
            status=status.HTTP_400_BAD_REQUEST
        )
    if not oauth_token:
        return prepare_response(
            message=constants.OAUTH_TOKEN_REQUIRED,
            status=status.HTTP_400_BAD_REQUEST
        )
    user = login_with_outlook(oauth_token)
    if not user:
        return prepare_response(
            message=constants.INVALID_CREDENTIALS,
            status=status.HTTP_401_UNAUTHORIZED
        )
    token = create_jwt_token(user)
    return prepare_response(
        content={
            "id": user.id,
            "email": user.email,
            "user_type": user.user_type,
            "is_verified": user.is_verified,
            "is_detail_updated": user.is_detail_updated,
            "is_document_uploaded": user.is_document_uploaded,
            "access_token": token,
            "token_type": "Bearer"
        },
        message=constants.LOGIN_SUCCESSFUL,
        status=status.HTTP_200_OK
    )



@is_request_authenticated
def logout(request):
    user = getattr(request, 'user', None)
    if not user:
        return prepare_response(message=constants.AUTHENTICATION_FAILED, status=401)
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return prepare_response(message=constants.AUTH_HEADER_MISSING, status=401)
    token = get_jwt_token(auth_header)
    if user.token != token:
        return prepare_response(message=constants.INVALID_TOKEN, status=401)
    user.token = None
    user.save(update_fields=['token'])

    return prepare_response(message=constants.LOGOUT_SUCCESSFULL, status=200)

def verify_password_otp(request):
    if request.method != "POST":
        return prepare_response(
            message=constants.INVALID_REQUEST,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    try:
        data = json.loads(request.body)
        email = data.get("email")
        otp = data.get("otp")

        if not email or not otp:
            return prepare_response(
                message=constants.EMAIL_AND_OTP_REQUIRED,
                status=status.HTTP_400_BAD_REQUEST
            )
        record = UserVerification.objects.filter(
            email=email, otp=otp, is_verified=False
        ).order_by('-created').first()
        if not record:
            return prepare_response(
                message=constants.INCORRECT_OTP,
                status=status.HTTP_400_BAD_REQUEST
            )
        expiry_time = record.created + timezone.timedelta(minutes=10)

        if timezone.now() > expiry_time:
            return prepare_response(
                message=constants.OTP_EXPIRED,
                status=status.HTTP_400_BAD_REQUEST
            )
        record.is_verified = True
        record.verified_time = timezone.now()
        record.save()
        return prepare_response(
            message=constants.OTP_VERIFIED_SUCCESS,
            content={"email": email},
            status=status.HTTP_200_OK
        )
    except Exception as e:
        print("Error:", e)
        return prepare_response(
            message=constants.INTERNAL_SERVER_ERROR,
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def reset_password(request):
    if request.method != "POST":
        return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)
    try:
        data = json.loads(request.body)
        email = data.get("email")
        otp = data.get("otp")  
        password = data.get("password")  
        confirm_password = data.get("confirm_password")
        if not all([email, otp, password, confirm_password]):
            return prepare_response(
                message=constants.EMAIL_OTP_PASSWORD_REQUIRED,
                status=status.HTTP_400_BAD_REQUEST
            )
        if password != confirm_password:
            return prepare_response(
                message=constants.PASSWORDS_DO_NOT_MATCH,
                status=status.HTTP_400_BAD_REQUEST
            )
        if not validate_password(password):
            return prepare_response(
                message=constants.WEAK_PASSWORD ,
                status=status.HTTP_400_BAD_REQUEST
            )

        verified_record = UserVerification.objects.filter(
            email=email, otp=otp, is_verified=True
        ).order_by('-verified_time').first()

        if not verified_record:
            return prepare_response(message=constants.INCORRECT_OTP, status=status.HTTP_400_BAD_REQUEST)
        expiry_time = verified_record.verified_time + timezone.timedelta(minutes=10)
        if timezone.now() > expiry_time:
            return prepare_response(message=constants.OTP_EXPIRED, status=status.HTTP_400_BAD_REQUEST)
        user = UserProfile.objects.filter(email=email).first()
        if not user:
            return prepare_response(message=constants.USER_NOT_FOUND, status=status.HTTP_400_BAD_REQUEST)
        user.hashed_password = make_password(password)
        user.save(update_fields=['hashed_password'])
        return prepare_response(message=constants.PASSWORD_RESET_SUCCESS, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        print("Error:", e)
        return prepare_response(message=constants.INTERNAL_SERVER_ERROR, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    


def send_password_otp(request): 
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            email = data.get("email")

            if not email:
                return prepare_response(
                    message=constants.INVALID_REQUEST_METHOD,
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                user = UserProfile.objects.get(email=email)
            except UserProfile.DoesNotExist:
                return prepare_response(
                    message=constants.USER_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )

            otp = request_otp_sent()

            UserVerification.objects.create(
                user=user,
                email=email,
                otp=otp,
                verification_type="PASSWORD_RESET",
                is_verified=False
            )

        
            body_html = render_to_string(
                "email_templates/send_password_otp.html",
                {"otp": otp, "expiry_minutes": constants.OTP_EXPIRY_MINUTES}
            )

            subject = "Password Reset OTP - DOQFY"
            body_text = f"Your OTP for password reset is: {otp}. It will expire in {constants.OTP_EXPIRY_MINUTES} minutes."

            success = send_ses_email(email, subject, body_text, body_html)

            if success:
                return prepare_response(message=constants.OTP_SEND_SUCCESS)
            else:
                return prepare_response(
                    message=constants.OTP_SEND_FAILED,
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        except Exception as e:
            print(f"Error sending OTP via SES: {e}")
            return prepare_response(
                message=f"Unexpected error: {str(e)}",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    else:
        return prepare_response(
            message=constants.METHOD_NOT_ALLOWED,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
