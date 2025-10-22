from django.shortcuts import render
import json
import uuid
from django.contrib.auth.hashers import make_password
from utilities import status, constants
from utilities.helper_functions import prepare_response , validate_email, send_email, validate_password
from user_service.models import UserProfile  ,UserVerification
from user_service.utils import request_otp_sent
from utilities.decorator import is_request_authenticated
from django.contrib.auth.hashers import check_password
from utilities.jwt_token import create_jwt_token  # JWT helper
from django.views.decorators.http import require_POST
from utilities.oauth_utils import login_with_google
from utilities.oauth_utils import login_with_outlook
from django.utils import timezone
from utilities.helper_functions import send_ses_email
from datetime import datetime, timedelta

# Create your views here.


# POST /login – User login with email/password.
# POST /login/google – Login using Google OAuth.
# POST /login/outlook – Login using Outlook OAuth.
# POST /auth/logout – Logout the authenticated user.
# POST /password/reset – Reset user password.


# ------------------------------/user/login/ ------------------------------------------------------------------------------------
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
    except json.JSONDecodeError:
        return prepare_response(
            message="Invalid JSON",
            status=status.HTTP_400_BAD_REQUEST
        )

    # ---------- Validate Required Fields ----------
    if not all([email, password]):
        return prepare_response(
            message=constants.FIELD_REQUIRED,
            status=status.HTTP_400_BAD_REQUEST
        )

    # ---------- Check if user exists ----------
    user = UserProfile.objects.filter(email=email).first()
    if not user:
        return prepare_response(
            message=constants.USER_NOT_ONBOARDED,
            status=status.HTTP_400_BAD_REQUEST
        )

    # ---------- Check Password ----------
    if not check_password(password, user.hashed_password):
        print("DB hashed password:", user.hashed_password)
        return prepare_response(
            
            message=constants.INVALID_CREDENTIALS,
            status=status.HTTP_400_BAD_REQUEST
        )

    # ---------- Check if login allowed ----------
    if not user.is_login_allowed:
        return prepare_response(
            message=constants.LOGIN_NOT_ALLOWED,
            status=status.HTTP_403_FORBIDDEN
        )

    # ---------- Create JWT Token ----------
    token = create_jwt_token(user)

    # ---------- Return JWT Token in response ----------
    return prepare_response(
        content={
            "id": user.id,
            "email": user.email,
            "user_type": user.user_type,
            "is_verified": user.is_verified,
            "is_detail_updated": user.is_detail_updated,
            "is_document_uploaded": user.is_document_uploaded,
            "access_token": token,      # <-- JWT token here
            "token_type": "Bearer"      # <-- for frontend usage
        },
        message=constants.LOGIN_SUCCESSFUL,
        status=status.HTTP_200_OK
    )


#------------------------------/user/google_login/ ------------------------------------------------------------------------------------








def google_login(request):
    if request.method != "POST":
        return prepare_response(message="Only POST method allowed", status=status.HTTP_405_METHOD_NOT_ALLOWED)

    try:
        data = json.loads(request.body)
        oauth_token = data.get("token")
        print("🔹 Received token from request:", oauth_token)

    except json.JSONDecodeError:
        return prepare_response(message="Invalid JSON", status=status.HTTP_400_BAD_REQUEST)

    if not oauth_token:
        return prepare_response(message="OAuth token is required", status=status.HTTP_400_BAD_REQUEST)

    user = login_with_google(oauth_token)
    if not user:
        return prepare_response(message="Invalid credentials", status=status.HTTP_401_UNAUTHORIZED)

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
        message="Login successful",
        status=status.HTTP_200_OK
    )



#------------------------------/user/outlook_login/ -----------------------------------------------------------------------------------

def outlook_login(request):
    """
    Outlook OAuth login view.
    """
    # ---------- Only POST allowed ----------
    if request.method != "POST":
        return prepare_response(
            message="Only POST method allowed",
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    # ---------- Parse JSON body ----------
    try:
        data = json.loads(request.body)
        oauth_token = data.get("token")
    except json.JSONDecodeError:
        return prepare_response(
            message="Invalid JSON",
            status=status.HTTP_400_BAD_REQUEST
        )

    if not oauth_token:
        return prepare_response(
            message="OAuth token is required",
            status=status.HTTP_400_BAD_REQUEST
        )

    # ---------- Authenticate user ----------
    user = login_with_outlook(oauth_token)
    if not user:
        return prepare_response(
            message=constants.INVALID_CREDENTIALS,
            status=status.HTTP_401_UNAUTHORIZED
        )

    # ---------- Create JWT token ----------
    token = create_jwt_token(user)

    # ---------- Return response ----------
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
        message="Login successful",
        status=status.HTTP_200_OK
    )

#------------------------------/auth/logout -----------------------------------------------------------------------------------
from utilities.decorator import is_request_authenticated
from utilities import status
from utilities.helper_functions import prepare_response

@is_request_authenticated
def logout(request):
    """
    Logout the currently authenticated user.
    This only logs out the person whose JWT token was sent in the Authorization header.
    """
    user = getattr(request, 'user', None)

    if not user:
        return prepare_response(
            message="User not authenticated",
            status=status.HTTP_401_UNAUTHORIZED
        )

    # Invalidate only this user's token
    user.token = None
    user.save(update_fields=['token'])

    return prepare_response(
        message="Logout successful",
        status=status.HTTP_200_OK
    )


def verify_password_otp(request):
    # Allow only POST method
    if request.method != "POST":
        return prepare_response(
            message="Only POST method allowed",
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        data = json.loads(request.body)
        email = data.get("email")
        otp = data.get("otp")

        if not email or not otp:
            return prepare_response(
                message="Email and OTP required",
                status=status.HTTP_400_BAD_REQUEST
            )

        record = UserVerification.objects.filter(
            email=email, otp=otp, is_verified=False
        ).order_by('-created_at').first()

        if not record:
            return prepare_response(
                message="Invalid OTP",
                status=status.HTTP_400_BAD_REQUEST
            )

        # --- Check OTP expiry (10 minutes validity) ---
        expiry_time = record.created_at + timezone.timedelta(minutes=10)
        if timezone.now() > expiry_time:
            return prepare_response(
                message="OTP expired",
                status=status.HTTP_400_BAD_REQUEST
            )

        # --- Mark verified ---
        record.is_verified = True
        record.verified_time = timezone.now()
        record.save()

        return prepare_response(
            message="OTP verified successfully.",
            content={"email": email},
            status=status.HTTP_200_OK
        )

    except Exception as e:
        print("Error:", e)
        return prepare_response(
            message="Internal Server Error",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )






# reset password via SMTP
def reset_password(request):
    if request.method != "POST":
        return prepare_response(message="Only POST method allowed", status=405)

    try:
        data = json.loads(request.body)
        email = data.get("email")
        otp = data.get("otp")  # use 'otp'
        password = data.get("password")  # use 'password'
        confirm_password = data.get("confirm_password")

        # Check required fields
        if not all([email, otp, password, confirm_password]):
            return prepare_response(
                message="Email, otp, password, and confirm_password are required",
                status=400
            )

        # Password match check
        if password != confirm_password:
            return prepare_response(
                message="Password and confirm password do not match",
                status=400
            )

        # Optional: Validate password strength
        if not validate_password(password):
            return prepare_response(
                message="Weak password. Must contain upper, lower, number, and special char.",
                status=400
            )

        # Check OTP record
        verified_record = UserVerification.objects.filter(
            email=email, otp=otp, is_verified=True
        ).order_by('-verified_time').first()

        if not verified_record:
            return prepare_response(message="Invalid OTP", status=400)

        # Check OTP expiry (10 min)
        expiry_time = verified_record.verified_time + timezone.timedelta(minutes=10)
        if timezone.now() > expiry_time:
            return prepare_response(message="OTP expired", status=400)

        # Update password
        user = UserProfile.objects.filter(email=email).first()
        if not user:
            return prepare_response(message="User not found", status=404)

        user.hashed_password = make_password(password)
        user.save(update_fields=['hashed_password'])

        return prepare_response(message="Password reset successfully", status=201)

    except Exception as e:
        print("Error:", e)
        return prepare_response(message="Internal Server Error", status=500)



# ---------------------------------------------reset_password END VIA SMTP--------------------------


# -----------------------------------------------view SES----------------------------------------
# user_service/views.py
# sending otp via SES

OTP_EXPIRY_MINUTES = 5  # OTP valid for 5 minutes

@require_POST
def send_password_otp(request):
    """
    Send OTP email for password reset via SES.
    """
    try:
        # Parse request body
        data = json.loads(request.body)
        email = data.get("email")
        if not email:
            return prepare_response(
                message="Email is required",
                status=400
            )
        # Check if user exists
        try:
            user = UserProfile.objects.get(email=email)
        except UserProfile.DoesNotExist:
            return prepare_response(
                message="User with this email does not exist",
                status=404
            )
        # Generate OTP
        otp = request_otp_sent()
        # Store OTP record
        UserVerification.objects.create(
            user=user,
            email=email,
            otp=otp,
            verification_type="PASSWORD_RESET",  # Changed verification type
            is_verified=False
        )
        # Prepare email content
        subject = "Password Reset OTP - DOQFY"
        body_text = f"Your OTP for password reset is: {otp}. It will expire in {OTP_EXPIRY_MINUTES} minutes."
        body_html = f"""
        <html>
            <body>
                <p>Your OTP for password reset is: <b>{otp}</b>.</p>
                <p>It will expire in {OTP_EXPIRY_MINUTES} minutes.</p>
            </body>
        </html>
        """
        # Send email
        success = send_ses_email(email, subject, body_text, body_html)
        if success:
            return prepare_response(
                message="✅ OTP sent successfully"
            )
        else:
            return prepare_response(
                message="Failed to send OTP email",
                status=500
            )
    except Exception as e:
        print(f"Error sending OTP via SES: {e}")
        return prepare_response(
            message=f"Unexpected error: {str(e)}",
            status=500
        )
