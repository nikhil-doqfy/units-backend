
import json
import uuid
from django.contrib.auth.hashers import make_password ,check_password
from utilities import status, constants
from utilities.helper_functions import prepare_response , validate_email, send_email, validate_password, send_ses_email
from user_service.models import UserProfile,Documents,OwnerDocumentsMapping,StaffDocumentsMapping,CompanyUserDocumentsMapping,TenantDocumentsMapping,UserVerification ,Company
from user_service.utils import request_otp_sent
from utilities.decorator import is_request_authenticated
from utilities.jwt_token import create_jwt_token , get_jwt_token, decode_jwt_token
from utilities.oauth_utils import login_with_outlook ,login_with_google
from django.utils import timezone
from datetime import datetime, timedelta
from django.template.loader import render_to_string


def send_otp(request):
    if request.method != "POST":
        return prepare_response(
            message=constants.METHOD_NOT_ALLOWED,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        data = json.loads(request.body)
        email = data.get("email")
        purpose = data.get("purpose")  

        if not email:
            return prepare_response(
                message=constants.EMAIL_REQUIRED,
                status=status.HTTP_400_BAD_REQUEST
            )

        if purpose is None:
            purpose_text = "login"
        else:
            purpose_text = purpose.lower()

        if purpose_text == "login":
            try:
                user_obj = UserProfile.objects.get(user__email=email)
            except UserProfile.DoesNotExist:
                return prepare_response(
                    message=constants.USER_DOES_NOT_EXIST,
                    status=status.HTTP_404_NOT_FOUND
                )

        elif purpose_text == "signup":
            if UserProfile.objects.filter(user__email=email).exists():
                return prepare_response(
                    message=constants.EMAIL_ALREADY_REGISTERED,
                    status=status.HTTP_400_BAD_REQUEST
                )

        elif purpose_text in ["forget_password", "reset_password"]:
            try:
                user_obj = UserProfile.objects.get(user__email=email)
            except UserProfile.DoesNotExist:
                return prepare_response(
                    message=constants.USER_DOES_NOT_EXIST,
                    status=status.HTTP_404_NOT_FOUND
                )

        else:
            return prepare_response(
                message=constants.INVALID_PURPOSE,
                status=status.HTTP_400_BAD_REQUEST
            )

        otp = request_otp_sent()

        UserVerification.objects.update_or_create(
            email=email,
            defaults={
                "otp": otp,
                "is_verified": False,
                "created": timezone.now(),
                "purpose": purpose_text
            }
        )

        body_html = render_to_string(
            "email_templates/send_password_otp.html",
            {"otp": otp, "purpose": purpose_text, "expiry_minutes": constants.OTP_EXPIRY_MINUTES}
        )

        subject = f"{purpose_text.capitalize()} OTP - DOQFY"
        body_text = f"Your OTP is: {otp}"
        print(f"Generated OTP for {email} is {otp}")  # Debug log

        success = send_ses_email(email, subject, body_text, body_html)

        if success:
            return prepare_response(message=constants.OTP_SENT_SUCCESS)
        else:
            return prepare_response(
                message=constants.OTP_SEND_FAILED,
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    except Exception as e:
        print("SEND OTP ERROR:", e)
        return prepare_response(
            message=f"Unexpected error: {str(e)}",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )




def verify_otp(request):
    if request.method != "POST":
        return prepare_response(
            message=constants.INVALID_REQUEST,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        data = json.loads(request.body)
        email = data.get("email")
        otp = data.get("otp")
        purpose = data.get("purpose")  

        if not (email and otp):
            return prepare_response(
                message=constants.EMAIL_OTP_REQUIRED,
                status=status.HTTP_400_BAD_REQUEST
            )

        record = UserVerification.objects.filter(
            email=email,
            is_verified=False
        ).order_by('-created').first()

        if not record:
            return prepare_response(
                message=constants.INCORRECT_OTP,
                status=status.HTTP_400_BAD_REQUEST
            )

        if str(record.otp) != str(otp):
            return prepare_response(
                message=constants.INCORRECT_OTP,
                status=status.HTTP_400_BAD_REQUEST
            )

  
        expiry_time = record.created + timezone.timedelta(minutes=constants.OTP_EXPIRY_MINUTES)
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
        print("VERIFY OTP ERROR:", e)
        return prepare_response(
            message=constants.INTERNAL_SERVER_ERROR,
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



def reset_password(request):
    if request.method != "POST":
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
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
                message=constants.WEAK_PASSWORD,
                status=status.HTTP_400_BAD_REQUEST
            )
        verified_record = UserVerification.objects.filter(
            email=email,
            otp=otp,
            is_verified=True
        ).order_by('-verified_time').first()

        if not verified_record:
            return prepare_response(
                message=constants.INCORRECT_OTP,
                status=status.HTTP_400_BAD_REQUEST
            )

        expiry_time = verified_record.verified_time + timezone.timedelta(minutes=10)
        if timezone.now() > expiry_time:
            return prepare_response(
                message=constants.OTP_EXPIRED,
                status=status.HTTP_400_BAD_REQUEST
            )

        user_profile = UserProfile.objects.filter(user__email=email).first()
        if not user_profile:
            return prepare_response(
                message=constants.USER_NOT_FOUND,
                status=status.HTTP_400_BAD_REQUEST
            )

        user_profile.user.password = make_password(password)
        user_profile.user.save(update_fields=['password'])

        return prepare_response(
            message=constants.PASSWORD_RESET_SUCCESS,
            status=status.HTTP_200_OK
        )

    except Exception as e:
        print("RESET PASSWORD ERROR:", e)
        return prepare_response(
            message=constants.INTERNAL_SERVER_ERROR,
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@is_request_authenticated
def logout(request):
    user = getattr(request, 'user', None) 
    if not user:
        return prepare_response(
            message=constants.AUTHENTICATION_FAILED,
            status=status.HTTP_401_UNAUTHORIZED
        )


    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return prepare_response(
            message=constants.AUTH_HEADER_MISSING,
            status=status.HTTP_401_UNAUTHORIZED
        )

    token = get_jwt_token(auth_header)

    if user.token != token:
        return prepare_response(
            message=constants.INVALID_TOKEN,
            status=status.HTTP_401_UNAUTHORIZED
        )


    user.token = None
    user.save(update_fields=['token'])

    return prepare_response(
        message=constants.LOGOUT_SUCCESSFULL,
        status=status.HTTP_200_OK
    )



@is_request_authenticated
def change_password(request):
    if request.method != "POST":
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        data = json.loads(request.body)

        old_password = data.get("current_password")
        new_password = data.get("new_password")
        confirm_password = data.get("new_confirm_password")

   
        if not all([old_password, new_password, confirm_password]):
            return prepare_response(
                message=constants.OLD_NEW_CONFIRM_PASSWORD_REQUIRED,
                status=status.HTTP_400_BAD_REQUEST
            )

        if new_password != confirm_password:
            return prepare_response(
                message=constants.PASSWORDS_DO_NOT_MATCH,
                status=status.HTTP_400_BAD_REQUEST
            )

        if not validate_password(new_password):
            return prepare_response(
                message=constants.WEAK_PASSWORD,
                status=status.HTTP_400_BAD_REQUEST
            )

        user_profile = request.user             
        user = user_profile.user                    

  
        if not user.check_password(old_password):
            return prepare_response(
                message=constants.PASSWORD_MISMATCH,
                status=status.HTTP_400_BAD_REQUEST
            )

      
        user.set_password(new_password)
        user.save(update_fields=["password"])

        return prepare_response(
            message=constants.PASSWORD_UPDATED,
            status=status.HTTP_200_OK
        )

    except Exception as e:
        print("CHANGE PASSWORD ERROR:", e)
        return prepare_response(
            message=constants.INTERNAL_SERVER_ERROR,
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

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
        user_role = data.get("user_role")
    except json.JSONDecodeError:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_400_BAD_REQUEST
        )

    if email and password:
        profile = UserProfile.objects.select_related("user").filter(user__email=email).first()
        if not profile:
            return prepare_response(
                message=constants.USER_NOT_ONBOARDED,
                status=status.HTTP_400_BAD_REQUEST
            )

        user = profile.user

        if not user.is_active:
            return prepare_response(
                message=constants.USER_ACCOUNT_DISABLED,
                status=status.HTTP_403_FORBIDDEN
            )

        if not user.check_password(password):
            return prepare_response(
                message=constants.INVALID_CREDENTIALS,
                status=status.HTTP_400_BAD_REQUEST
            )

        if profile.user_role != user_role:
            return prepare_response(
                message=f"This user does not belong to {user_role.title()}",
                status=status.HTTP_400_BAD_REQUEST
            )

        company_name = None
        if profile.user_role in [constants.COMPANY_USER, constants.STAFF]:
            company_instance = Company.objects.filter(company_user=profile).first()
            if company_instance:
                company_name = company_instance.company_name

        token = create_jwt_token(profile)

      
        profile.token = token
        profile.save(update_fields=["token"])

        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])

        return prepare_response(
            content={
                "id": profile.id,
                "email": user.email,
                "user_role": profile.user_role,
                "access_token": token,
                "token_type": "Bearer",
                "first_name": user.first_name,
                "last_name": user.last_name,
                "profile_image": profile.profile_image,
                "company_name": company_name,
            },
            message=constants.LOGIN_SUCCESSFUL,
            status=status.HTTP_200_OK
        )


    elif email and otp:
        profile = UserProfile.objects.select_related("user").filter(user__email=email).first()
        if not profile:
            return prepare_response(
                message=constants.AUTH_USER_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        user = profile.user

        if not user.is_active:
            return prepare_response(
                message=constants.USER_ACCOUNT_DISABLED,
                status=status.HTTP_403_FORBIDDEN
            )

        if profile.user_role != user_role:
            return prepare_response(
                message=constants.USER_TYPE_MISMATCH,
                status=status.HTTP_400_BAD_REQUEST
            )

        record = UserVerification.objects.filter(
            email=email,
            otp=otp,
            purpose="login"
        ).order_by("-created").first()

        if not record:
            return prepare_response(
                message=constants.INCORRECT_OTP,
                status=status.HTTP_400_BAD_REQUEST
            )

        if not record.is_verified:
            return prepare_response(
                message=constants.OTP_NOT_VERIFIED,
                status=status.HTTP_400_BAD_REQUEST
            )

        record.is_verified = False
        record.verified_time = timezone.now()
        record.save(update_fields=["is_verified", "verified_time"])

        token = create_jwt_token(profile)

  
        profile.token = token
        profile.save(update_fields=["token"])

        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])

        company_name = None
        if profile.user_role in [constants.COMPANY_USER, constants.STAFF]:
            company_instance = Company.objects.filter(company_user=profile).first()
            if company_instance:
                company_name = company_instance.company_name

        return prepare_response(
            content={
                "id": profile.id,
                "email": user.email,
                "user_role": profile.user_role,
                "access_token": token,
                "token_type": "Bearer",
                "first_name": user.first_name,
                "last_name": user.last_name,
                "profile_image": profile.profile_image,
                "company_name": company_name,
            },
            message=constants.LOGIN_SUCCESSFUL_WITH_OTP,
            status=status.HTTP_200_OK
        )

    else:
        return prepare_response(
            message=constants.FIELD_REQUIRED,
            status=status.HTTP_400_BAD_REQUEST
        )





