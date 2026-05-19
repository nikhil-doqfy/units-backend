
import json
import uuid
from django.contrib.auth.hashers import make_password
from utilities import status, constants
from utilities.helper_functions import prepare_response, validate_password, send_ses_email
from user_service.models import UserProfile, UserVerification, Owner, Tenant, PropertyManager


def _build_permissions(profile):
    """Return permission map for a PropertyManager, empty dict otherwise."""
    if not isinstance(profile, PropertyManager):
        return {}
    pm = PropertyManager.objects.filter(pk=profile.pk).prefetch_related("roles__permissions").first()
    if not pm:
        return {}
    permissions = {}
    for role in pm.roles.all():
        for perm in role.permissions.all():
            existing = permissions.get(perm.module_name, {"create": False, "edit": False, "delete": False, "view": False})
            permissions[perm.module_name] = {
                "create": existing["create"] or perm.create,
                "edit":   existing["edit"]   or perm.edit,
                "delete": existing["delete"] or perm.delete,
                "view":   existing["view"]   or perm.view,
            }
    return permissions
from user_service.utils import request_otp_sent
from utilities.decorator import is_request_authenticated
from utilities.jwt_token import create_jwt_token, get_jwt_token
from django.utils import timezone
from django.template.loader import render_to_string
from django.core.cache import cache


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

        user_obj = None

        if purpose_text == "login":
            try:
                user_obj = UserProfile.objects.get(user__email=email)
            except UserProfile.DoesNotExist:
                return prepare_response(
                    message=constants.USER_DOES_NOT_EXIST,
                    status=status.HTTP_404_NOT_FOUND
                )

        elif purpose_text == "signup":
            existing = UserProfile.objects.select_related("user").filter(user__email=email).first()
            if existing:
                return prepare_response(
                    message="User already registered. Please log in to continue.",
                    content={
                        "already_registered": True,
                        "id":         existing.id,
                        "email":      existing.user.email,
                        "first_name": existing.user.first_name,
                        "last_name":  existing.user.last_name,
                        "name":       f"{existing.user.first_name} {existing.user.last_name}".strip(),
                    },
                    status=status.HTTP_200_OK
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

        if purpose_text == "signup":
            # No UserProfile exists yet — store OTP in cache until signup completes
            cache.set(f"otp_signup_{email}", otp, timeout=constants.OTP_EXPIRY_MINUTES * 60)
        else:
            UserVerification.objects.update_or_create(
                user_profile=user_obj,
                purpose=purpose_text,
                defaults={
                    "otp": otp,
                    "is_verified": False,
                }
            )

        body_html = render_to_string(
            "email_templates/send_password_otp.html",
            {"otp": otp, "purpose": purpose_text, "expiry_minutes": constants.OTP_EXPIRY_MINUTES}
        )

        subject = f"{purpose_text.capitalize()} OTP - UNITS"
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
        purpose = (data.get("purpose") or "login").lower()

        if not (email and otp):
            return prepare_response(
                message=constants.EMAIL_OTP_REQUIRED,
                status=status.HTTP_400_BAD_REQUEST
            )

        if purpose == "signup":
            stored_otp = cache.get(f"otp_signup_{email}")
            if not stored_otp or str(stored_otp) != str(otp):
                return prepare_response(
                    message=constants.INCORRECT_OTP,
                    status=status.HTTP_400_BAD_REQUEST
                )
            cache.delete(f"otp_signup_{email}")
            return prepare_response(
                message=constants.OTP_VERIFIED_SUCCESS,
                content={"email": email},
                status=status.HTTP_200_OK
            )

        user_profile = UserProfile.objects.filter(user__email=email).first()
        if not user_profile:
            return prepare_response(
                message=constants.USER_DOES_NOT_EXIST,
                status=status.HTTP_404_NOT_FOUND
            )

        record = UserVerification.objects.filter(
            user_profile=user_profile,
            is_verified=False
        ).order_by('-id').first()

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
            user_profile__user__email=email,
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
    try:
        UserProfile.objects.filter(pk=request.user.pk).update(token=None)
        return prepare_response(
            message=constants.LOGOUT_SUCCESSFULL,
            status=status.HTTP_200_OK
        )
    except Exception as e:
        print("LOGOUT ERROR:", e)
        return prepare_response(
            message=constants.INTERNAL_SERVER_ERROR,
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
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

    role_model_map = {
        constants.OWNER: Owner,
        constants.TENANT: Tenant,
        constants.COMPANY_USER: PropertyManager,
        constants.STAFF: PropertyManager,
    }
    profile_model = role_model_map.get(user_role, UserProfile)

    if email and password:
        profile = profile_model.objects.select_related("user").filter(user__email=email).first()
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

        company_name = None
        if isinstance(profile, PropertyManager) and profile.company_id:
            company_name = profile.company.name

        token = create_jwt_token(profile)

        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])

        return prepare_response(
            content={
                "id": profile.id,
                "email": user.email,
                "user_role": user_role,
                "access_token": token,
                "token_type": "Bearer",
                "first_name": user.first_name,
                "last_name": user.last_name,
                "profile_image": profile.profile_image,
                "company_name": company_name,
                "permissions": _build_permissions(profile),
            },
            message=constants.LOGIN_SUCCESSFUL,
            status=status.HTTP_200_OK
        )
    elif email and otp:
        profile = profile_model.objects.select_related("user").filter(user__email=email).first()
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

        record = UserVerification.objects.filter(
            user_profile=profile,
            otp=otp,
            purpose="login"
        ).order_by("-id").first()

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

        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])

        company_name = None
        if isinstance(profile, PropertyManager) and profile.company_id:
            company_name = profile.company.name

        return prepare_response(
            content={
                "id": profile.id,
                "email": user.email,
                "user_role": user_role,
                "access_token": token,
                "token_type": "Bearer",
                "first_name": user.first_name,
                "last_name": user.last_name,
                "profile_image": profile.profile_image,
                "company_name": company_name,
                "permissions": _build_permissions(profile),
            },
            message=constants.LOGIN_SUCCESSFUL_WITH_OTP,
            status=status.HTTP_200_OK
        )

    else:
        return prepare_response(
            message=constants.FIELD_REQUIRED,
            status=status.HTTP_400_BAD_REQUEST
        )
