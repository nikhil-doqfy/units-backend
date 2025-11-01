import json
import uuid
from django.contrib.auth.hashers import make_password
from utilities import status, constants
from utilities.helper_functions import prepare_response 
from user_service.models import UserProfile ,StaffDetails , PropertyManagerCompanyDetails , StaffRole
from user_service.utils import request_otp_sent
from django.db import transaction
from utilities.decorator import is_request_authenticated

def user_sign_up(request):
    if request.method == "POST":
        data = json.loads(request.body)
        email = data.get("email")
        password = data.get("password")
        confirm_password = data.get("confirm_password")
        user_type = data.get("user_type")

        if not all([email, password, confirm_password, user_type]):
            return prepare_response(
                message=constants.FIELD_REQUIRED,
                status=status.HTTP_400_BAD_REQUEST
            )
        if password != confirm_password:
            return prepare_response(
                message=constants.PASSWORD_MISMATCH,
                status=status.HTTP_400_BAD_REQUEST
            )
        if UserProfile.objects.filter(email=email).exists():
            return prepare_response(
                message=constants.EMAIL_ALREADY_REGISTERED,
                status=status.HTTP_400_BAD_REQUEST
            )
        user = UserProfile.objects.create(
            email=email,
            hashed_password=make_password(password),
            user_type=user_type,
            is_login_allowed=True
        )
        return prepare_response(
            content={
                "id": user.id,
                "email": user.email,
                "user_type": user.user_type
            },
            message=constants.USER_REGISTERED_SUCCESSFULLY,
            status=status.HTTP_201_CREATED
        )
    else:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )


def send_otp(request):
    if request.method == "POST":
        data = json.loads(request.body)
        email = data.get("email")
        user_profile = UserProfile.objects.filter(email=email).first()
        if not user_profile:
            return prepare_response(
                message=constants.USER_NOT_ONBOARDED,
                status=status.HTTP_400_BAD_REQUEST
            )
        otp = request_otp_sent()
        user_profile.otp = otp
        user_profile.save(update_fields=['otp'])
        return prepare_response(
            content={"otp": otp},
            message=constants.OTP_GENERATED_SUCCESSFULLY,
            status=status.HTTP_200_OK
        )
    
    else:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )


@is_request_authenticated
def staff_signup(request):
    if request.method != 'POST':
        return prepare_response(message=constants.ONLY_POST_METHOD_ALLOWED,  status=status.HTTP_405_METHOD_NOT_ALLOWED)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return prepare_response(message=constants.INVALID_JSON_BODY, status=status.HTTP_400_BAD_REQUEST)
    user_profile = request.user  
    if user_profile.user_type not in [constants.PROPERTY_MANAGER, constants.STAFF]:
        return prepare_response(
            message=constants.ACCESS_DENIED_FOR_STAFF,
            status=status.HTTP_400_BAD_REQUEST
        )
    property_manager_details = None
    if user_profile.user_type == constants.STAFF:
        staff_details = StaffDetails.objects.filter(user=user_profile).first() 
        if not staff_details:
            return prepare_response(
                message=constants.STAFF_DETAILS_NOT_FOUND,
                status=status.HTTP_400_BAD_REQUEST
            )
        staff_role = staff_details.staff_role
        if not staff_role:
            return prepare_response(
                message=constants.STAFF_ROLE_NOT_FOUND,
                status=status.HTTP_400_BAD_REQUEST
            )
        if not staff_role.permissions.get("Staff Management", {}).get("Add Staff", False):
            return prepare_response(
                message=constants.ACCESS_DENIED_FOR_STAFF,
                status=status.HTTP_400_BAD_REQUEST
            )
        property_manager_details = staff_details.property_manager
        if not property_manager_details:
            return prepare_response(
                message=constants.STAFF_USER_NOT_PROPERTY_MANAGER,
                status=status.HTTP_400_BAD_REQUEST
            )
    elif user_profile.user_type == constants.PROPERTY_MANAGER:
        property_manager_details = PropertyManagerCompanyDetails.objects.filter(
            user=user_profile
        ).first()
        if not property_manager_details:
            return prepare_response(
                message=constants.PROPERTY_MANAGER_DETAILS_NOT_FOUND,
                status=status.HTTP_400_BAD_REQUEST
            )
        staff_role = StaffRole.objects.filter(
            id=data.get("staff_role_id"),
            property_manager=property_manager_details
        ).first()
        if not staff_role:
            return prepare_response(
                message=constants.STAFF_ROLE_NOT_FOUND,
                status=status.HTTP_400_BAD_REQUEST
            )
    try:
        with transaction.atomic():
            user = UserProfile.objects.update_or_create(
                email=data.get("email"),
                hashed_password=make_password(data.get("hashed_password")),
                user_type=data.get("user_type"),
                is_login_allowed=True
            )
            staff_id = data.get("staff_id") or str(uuid.uuid4())
            staff_details = StaffDetails.objects.create(
                staff_name=data.get("staff_name"),
                phone_number=data.get("phone_number"),
                staff_id=staff_id,
                assign_property=data.get("assign_property"),
                staff_role=staff_role,
                property_manager=property_manager_details,
                user=user,  
            )
    except Exception as e:
        return prepare_response(
            message=constants.STAFF_CREATION_FAILED,
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    return prepare_response(
        content={
            "user_id": user.id,
            "email_id": user.email,
            "type": user.user_type,
            "otp_verified": user.is_verified,
            "is_detail_updated": user.is_detail_updated,
            "is_document_uploaded": user.is_document_uploaded,
            "staff_role_id": staff_details.staff_role.id,
        },
        message=constants.STAFF_USER_CREATED_SUCCESS,
        status=status.HTTP_201_CREATED
    )



