import json
import uuid
from django.contrib.auth.hashers import make_password
from utilities import status, constants
from utilities.helper_functions import prepare_response 
from user_service.models import UserProfile ,StaffDetails , PropertyManagerCompanyDetails , StaffRole
from property_management.models import OwnerDetails , TenantDetails
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



@is_request_authenticated
def user_profile_view(request):
    try:
        current_user = request.user  

        if request.method == "GET":
            user_data = {
                "id": current_user.id,
                "full_name": "",
                "email": current_user.email,
                "contact": None,
                "role": current_user.user_type,
                "profile_image": current_user.profile_image,
                "country": getattr(current_user, "country", ""),
                "time_zone": getattr(current_user, "time_zone", "UTC"),
                "utc": getattr(current_user, "utc", ""),
                "address": "",
                "state": "",
                "postal_code": ""
            }

   
            if current_user.user_type == constants.OWNER:
                owner = OwnerDetails.objects.filter(user=current_user).first()
                if owner:
                    user_data.update({
                        "full_name": owner.full_name,
                        "contact": owner.mobile_number,
                        "address": getattr(owner, "address", ""),
                        "state": getattr(owner, "state", ""),
                        "postal_code": getattr(owner, "postal_code", "")
                    })


            elif current_user.user_type == constants.PROPERTY_MANAGER:
                pmc = PropertyManagerCompanyDetails.objects.filter(user=current_user).first()
                if pmc:
                    user_data.update({
                        "full_name": pmc.company_name,
                        "contact": pmc.phone_number,
                        "address": getattr(pmc, "company_address", ""),
                        "state": getattr(pmc, "state", ""),
                        "postal_code": getattr(pmc, "postal_code", "")
                    })


            elif current_user.user_type == constants.TENANT:
                tenant = TenantDetails.objects.filter(user=current_user).first()
                if tenant:
                    user_data.update({
                        "full_name": tenant.full_name,
                        "contact": tenant.mobile_number,
                        "address": getattr(tenant, "address", ""),
                        "state": getattr(tenant, "state", ""),
                        "postal_code": getattr(tenant, "postal_code", "")
                    })

            return prepare_response(
                content=user_data,
                message=constants.PROFILE_FETCHED_SUCCESS,
                status=status.HTTP_200_OK
            )


        elif request.method == "PUT":
            data = json.loads(request.body)

         
            new_contact = data.get("contact")
            new_full_name = data.get("full_name")
            new_profile_image = data.get("profile_image")
            new_country = data.get("country")
            new_time_zone = data.get("time_zone")
            new_utc = data.get("utc")
            new_address = data.get("address")
            new_state = data.get("state")
            new_postal_code = data.get("postal_code")
            new_role = data.get("role")

       
            if new_profile_image:
                current_user.profile_image = new_profile_image
            if new_country:
                current_user.country = new_country
            if new_time_zone:
                current_user.time_zone = new_time_zone
            if new_utc:
                current_user.utc = new_utc
            if new_role:
                current_user.user_type = new_role

            current_user.save()

     
            if current_user.user_type == constants.OWNER:
                OwnerDetails.objects.filter(user=current_user).update(
                    mobile_number=new_contact,
                    full_name=new_full_name,
                    address=new_address,
                    state=new_state,
                    postal_code=new_postal_code
                )

            elif current_user.user_type == constants.PROPERTY_MANAGER:
                PropertyManagerCompanyDetails.objects.filter(user=current_user).update(
                    phone_number=new_contact,
                    company_name=new_full_name,
                    company_address=new_address,
                    state=new_state,
                    postal_code=new_postal_code
                )   

            elif current_user.user_type == constants.TENANT:
                TenantDetails.objects.filter(user=current_user).update(
                    mobile_number=new_contact,
                    full_name=new_full_name,
                    address=new_address,
                    state=new_state,
                    postal_code=new_postal_code
                )

            return prepare_response(
                message=constants.PROFILE_UPDATED_SUCCESS,
                status=status.HTTP_200_OK
            )


        else:
            return prepare_response(
                message=constants.INVALID_REQUEST_METHOD,
                status=status.HTTP_405_METHOD_NOT_ALLOWED
            )

    except Exception as e:
        print("Error in user_profile_view:", e)
        return prepare_response(
            message=f"Error: {str(e)}",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



def user_management_view(request):
    if request.method == "GET":
        try:
            users = UserProfile.objects.filter(is_deleted=False)
            data = []

            for user in users:
                name = None
                contact_number = None
                details = None

                if user.user_type == constants.TENANT:
                    tenant = TenantDetails.objects.filter(user=user).first()
                    if tenant:
                        name = tenant.full_name
                        contact_number = tenant.mobile_number
                        details = {
                            "address": tenant.address,
                            "property_id": tenant.property.id if tenant.property else None,
                            "state": tenant.state,
                            "postal_code": tenant.postal_code,
                        }

                elif user.user_type == constants.OWNER:
                    owner = OwnerDetails.objects.filter(user=user).first()
                    if owner:
                        name = owner.full_name
                        contact_number = owner.mobile_number
                        details = {
                            "address": owner.address,
                            "trade_license_number": owner.trade_license_number,
                            "state": owner.state,
                            "postal_code": owner.postal_code,
                        }

                elif user.user_type == constants.PROPERTY_MANAGER:
                    pmc = PropertyManagerCompanyDetails.objects.filter(user=user).first()
                    if pmc:
                        name = pmc.company_name
                        contact_number = pmc.phone_number
                        details = {
                            "email_address": pmc.email_address,
                            "trade_license_number": pmc.trade_license_number,
                            "company_id": pmc.company_id,
                            "state": pmc.state,
                            "postal_code": pmc.postal_code,
                        }

    
                data.append({
                    "id": user.id,
                    "name": name,
                    "contact_number": contact_number,
                    "email": user.email,
                    "role": user.user_type,
                    "created_on": user.created.strftime("%d %b %Y") if user.created else None,
                    "is_verified": user.is_verified,
                    "is_deleted": user.is_deleted,
                    "is_login_allowed": user.is_login_allowed,
                    "details": details
                })

            return prepare_response(
                message=constants.USER_FETCHED_SUCCESS,
                content=data,
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return prepare_response(
                message=f"Error fetching users: {str(e)}",
                status=status.HTTP_400_BAD_REQUEST
            )

 
    elif request.method == "PUT":
        try:
            body = json.loads(request.body)
            user_id = body.get("user_id")

            user = UserProfile.objects.filter(id=user_id, is_deleted=False).first()
            if not user:
                return prepare_response(
                    message=constants.USER_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )

            user.is_verified = body.get("is_verified", user.is_verified)
            user.email = body.get("email", user.email)
            user.is_login_allowed = body.get("is_login_allowed", user.is_login_allowed)
            user.is_deleted = body.get("is_deleted", user.is_deleted)
            if "email" in body:
                user.email = body["email"]
            if "is_verified" in body:
                user.is_verified = body["is_verified"]
            if "is_login_allowed" in body:
                user.is_login_allowed = body["is_login_allowed"]
  
            user.save()

            return prepare_response(
                message=constants.USER_UPDATED_SUCCESS,
                content={"id": user.id, "email": user.email},
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return prepare_response(
                message=f"Error updating user: {str(e)}",
                status=status.HTTP_400_BAD_REQUEST
            )

 
    elif request.method == "DELETE":
        try:
            body = json.loads(request.body)
            user_id = body.get("user_id")

            user = UserProfile.objects.filter(id=user_id).first()
            if not user:
                return prepare_response(
                    message=constants.USER_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )

            user.is_deleted = True
            user.save()

            return prepare_response(
                message=constants.USER_SOFT_DELETED,
                content={"id": user.id, "is_deleted": user.is_deleted},
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return prepare_response(
                message=f"Error deleting user: {str(e)}",
                status=status.HTTP_400_BAD_REQUEST
            )

    else:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    


def user_management_deleted_view(request):
    if request.method == "GET":
        try:
            users = UserProfile.objects.filter(is_deleted=True)
            data = []

            for user in users:
                name = None
                contact_number = None
                details = None

                if user.user_type == constants.TENANT:
                    tenant = TenantDetails.objects.filter(user=user).first()
                    if tenant:
                        name = tenant.full_name
                        contact_number = tenant.mobile_number
                        details = {
                            "address": tenant.address,
                            "property_id": tenant.property.id if tenant.property else None,
                            "state": tenant.state,
                            "postal_code": tenant.postal_code,
                        }

                elif user.user_type == constants.OWNER:
                    owner = OwnerDetails.objects.filter(user=user).first()
                    if owner:
                        name = owner.full_name
                        contact_number = owner.mobile_number
                        details = {
                            "address": owner.address,
                            "trade_license_number": owner.trade_license_number,
                            "state": owner.state,
                            "postal_code": owner.postal_code,
                        }

                elif user.user_type == constants.PROPERTY_MANAGER:
                    pmc = PropertyManagerCompanyDetails.objects.filter(user=user).first()
                    if pmc:
                        name = pmc.company_name
                        contact_number = pmc.phone_number
                        details = {
                            "email_address": pmc.email_address,
                            "trade_license_number": pmc.trade_license_number,
                            "company_id": pmc.company_id,
                            "state": pmc.state,
                            "postal_code": pmc.postal_code,
                        }

    
                data.append({
                    "id": user.id,
                    "name": name,
                    "contact_number": contact_number,
                    "email": user.email,
                    "role": user.user_type,
                    "created_on": user.created.strftime("%d %b %Y") if user.created else None,
                    "is_verified": user.is_verified,
                    "is_deleted": user.is_deleted,
                    "is_login_allowed": user.is_login_allowed,
                    "details": details
                })

            return prepare_response(
                message=constants.USER_FETCHED_SUCCESS,
                content=data,
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return prepare_response(
                message=f"Error fetching users: {str(e)}",
                status=status.HTTP_400_BAD_REQUEST
            )

 
    elif request.method == "PUT":
        try:
            body = json.loads(request.body)
            user_id = body.get("user_id")

            user = UserProfile.objects.filter(id=user_id, is_deleted=True).first()
            if not user:
                return prepare_response(
                    message=constants.USER_DOES_NOT_EXIST,
                    status=status.HTTP_404_NOT_FOUND
                )

            user.is_verified = body.get("is_verified", user.is_verified)
            user.email = body.get("email", user.email)
            user.is_login_allowed = body.get("is_login_allowed", user.is_login_allowed)
            user.is_deleted = body.get("is_deleted", user.is_deleted)
            if "email" in body:
                user.email = body["email"]
            if "is_verified" in body:
                user.is_verified = body["is_verified"]
            if "is_login_allowed" in body:
                user.is_login_allowed = body["is_login_allowed"]



  
            user.save()

            return prepare_response(
                message=constants.USER_UPDATED_SUCCESS,
                content={"id": user.id, "email": user.email},
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return prepare_response(
                message=f"Error updating user: {str(e)}",
                status=status.HTTP_400_BAD_REQUEST
            )

 
    elif request.method == "DELETE":
        try:
            body = json.loads(request.body)
            user_id = body.get("user_id")

            user = UserProfile.objects.filter(id=user_id).first()
            if not user:
                return prepare_response(
                    message=constants.USER_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )

            
            user.delete()

            return prepare_response(
                message=constants.USER_PERMANENTLY_DELETED,
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return prepare_response(
                message=f"Error deleting user: {str(e)}",
                status=status.HTTP_400_BAD_REQUEST
            )

    else:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )