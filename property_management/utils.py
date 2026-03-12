from user_service.models import (
    UserProfile,
    OwnerDocumentsMapping,
    StaffDocumentsMapping,
    CompanyUserDocumentsMapping,
    TenantDocumentsMapping,
    UnitDetails,
    Company,
    PropertyImages,
    CompanyStaff,
)
from property_management.models import UserInvitation, AuditLog
from utilities.helper_functions import send_ses_email, fetch_s3_presigned_url, datetime_to_epoch_millis
from utilities import status ,  constants
from django.contrib.auth.models import User
import uuid
import re
from django.template.loader import render_to_string
from datetime import timedelta
from django.utils import timezone


def get_location_kv(city):
    if not city:
        return None, None, None

    state = city.state
    country = state.country if state else None
    city_kv = {
        "key": city.id,
        "value": city.name
    } if city else None

    state_kv = {
        "key": state.id,
        "value": state.name
    } if state else None

    country_kv = {
        "key": country.id,
        "value": country.name
    } if country else None

    return city_kv, state_kv, country_kv


def get_full_property_data(unit_id):
    try:
        prop = UnitDetails.objects.filter(id=unit_id).first()
        if not prop:
            return None, "UnitDetails not found"

        parent_property = None
        if prop.property:
            property_type_choices = dict(constants.PROPERTY_TYPE_CHOICES)
            parent_property = {
                "id": prop.property.id,
                "property_name": prop.property.property_name,
                "property_type": {
                    "key": prop.property.property_type,
                    "value": property_type_choices.get(prop.property.property_type)
                },
                "address_line_1": prop.property.address_line_1,
                "address_line_2": prop.property.address_line_2,
                "landmark": prop.property.landmark,
                "pincode": prop.property.pincode,
                "latitude": prop.property.latitude,
                "longitude": prop.property.longitude,
                "map_address": prop.property.map_address,
            }

        property_unit_data = {
            "unit_id": prop.id,
            "unit_name": prop.unit_name,
            "property_type": prop.property_type,
            "land_area": prop.land_area,
            "land_area_unit": prop.land_area_unit,
            "land_dm_no": prop.land_dm_no,
            "no_of_bedrooms": prop.no_of_bedrooms,
            "area_of_property": prop.area_of_property,
            "area_of_property_unit": prop.area_of_property_unit,
            "floor_no": prop.floor_no,
            "parking_no": prop.parking_no,
            "no_of_balcony": prop.no_of_balcony,
            "plot_no": prop.plot_no,
            "makani_no": prop.makani_no,
            "dewa_no": prop.dewa_no,
            "property_code": prop.property_code,
            "step_status": prop.step_status,
            "owner_id": prop.owner.id if prop.owner else None,
            "company_id": prop.company.id if prop.company else None,
            "is_occupied": prop.is_occupied,
            "status": "Not Available" if prop.is_occupied else "Available",
            "commercial_details": {
                "rent": prop.rent,
                "security_deposit": prop.security_deposit,
                "booking_amount": prop.booking_amount,
                "maintenance_charges": prop.maintenance_charges,
                "cycle": prop.cycle,
                "notice_period": prop.notice_period,
                "commission_percent": prop.commission_percent,
            }
        }

        images = [
            {
                "id": img.id,
                "file_name": img.file_name,
                "url": fetch_s3_presigned_url(img.image_path, file_name=img.file_name),
                "type": img.image_type
            }
            for img in prop.property_images.all().order_by("-id")
        ]

        document_type_choices = dict(constants.PROPERTY_DOCUMENT_CHOICES)
        documents_list = [
            {
                "id": mapping.id,
                "file_name": mapping.document.file_name,
                "url": fetch_s3_presigned_url(
                    mapping.document.file_path,
                    file_name=mapping.document.file_name
                ),
                "type": mapping.document_choice
            }
            for mapping in prop.property_documents.select_related("document").order_by("-id")
        ]
        documents = documents_list

        owner_data = None
        if prop.owner:
            city = prop.owner.city
            city_kv, state_kv, country_kv = get_location_kv(city)
            owner_data = {
                "id": prop.owner.id,
                "email": prop.owner.user.email,
                "first_name": prop.owner.user.first_name,
                "last_name": prop.owner.user.last_name,
                "address": prop.owner.address,
                "additional_address": prop.owner.additional_address,
                "city": city_kv,
                "state": state_kv,
                "country": country_kv,
                "postal_code": prop.owner.pin_code,
                "contact_number": prop.owner.contact_number,
                "locality": prop.owner.locality,
                "uae_residence_visa": prop.owner.uae_residence_visa,
                "emirate_id": prop.owner.emirate_id,
                "trade_license_number": prop.owner.trade_license_number,
                "owner_code": prop.owner.user_code,
            }

        tenant_data = None
        lease = prop.lease_details.first()
        if lease and lease.tenant:
            city = lease.tenant.city
            city_kv, state_kv, country_kv = get_location_kv(city)
            tenant_data = {
                "id": lease.tenant.id,
                "email": lease.tenant.user.email,
                "first_name": lease.tenant.user.first_name,
                "last_name": lease.tenant.user.last_name,
                "address": lease.tenant.address,
                "additional_address": lease.tenant.additional_address,
                "city": city_kv,
                "state": state_kv,
                "country": country_kv,
                "postal_code": lease.tenant.pin_code,
                "contact_number": lease.tenant.contact_number,
                "locality": lease.tenant.locality,
                "uae_residence_visa": lease.tenant.uae_residence_visa,
                "emirate_id": lease.tenant.emirate_id,
                "tenant_code": lease.tenant.user_code,
            }

        final_data = {
            "property_unit": property_unit_data,
            "parent_property": parent_property,
            "images": images,
            "documents": documents,
            "owner": owner_data,
            "tenant": tenant_data,
        }

        return final_data, None

    except Exception as e:
        return None, str(e)



def get_full_user_data(user_profile_id):
    """
    Returns a dictionary with complete user data including:
    - Basic user info
    - Company info (if COMPANY_USER)
    - Documents related to the user
    """

    try:
        user_profile = UserProfile.objects.select_related('user').filter(id=user_profile_id).first()
        if not user_profile:
            return None, "UserProfile not found"

        user = user_profile.user
        city_kv, state_kv, country_kv = get_location_kv(user_profile.city)
        user_data = {
            "id": user_profile.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "profile_image": user_profile.profile_image,
            "last_login": user.last_login,
            "user_role": user_profile.user_role,
            "contact_number": user_profile.contact_number,
            "address": user_profile.address,
            "additional_address": user_profile.additional_address,
            "city": city_kv,
            "state":state_kv,
            "country": country_kv,
            "time_zone": user_profile.time_zone,
            "pin_code": user_profile.pin_code,
            "locality":user_profile.locality,
            "user_code":user_profile.user_code,
            "emirate_id":user_profile.emirate_id,
            

            # "emirates"
        }


        company_data = None
        if user_profile.user_role == constants.COMPANY_USER:
            company = Company.objects.filter(company_user=user_profile).first()
            if company:
                company_data = {
                    "id": company.id,
                    "company_name": company.company_name,
                    "company_code": company.company_code,
                    "company_address": company.company_address
                }

        documents = []

        if user_profile.user_role == constants.OWNER:
            docs_qs = OwnerDocumentsMapping.objects.filter(owner=user_profile).select_related('document')
        elif user_profile.user_role == constants.TENANT:
            docs_qs = TenantDocumentsMapping.objects.filter(tenant=user_profile).select_related('document')
        elif user_profile.user_role == constants.COMPANY_USER:
            docs_qs = CompanyUserDocumentsMapping.objects.filter(company_user=user_profile).select_related('document')
        elif user_profile.user_role == constants.STAFF:
            docs_qs = StaffDocumentsMapping.objects.filter(staff=user_profile).select_related('document')
        else:
            docs_qs = []

        for mapping in docs_qs:
            doc = mapping.document
            documents.append({
                "id": mapping.id,
                "file_name": doc.file_name,
                "url": fetch_s3_presigned_url(doc.file_path, file_name=doc.file_name)
            })

        final_data = {
            "user": user_data,
            "company": company_data,
            "documents": documents
        }

        return final_data, None

    except Exception as e:
        return None, str(e)



def create_and_send_invitation(invited_by_profile, email, invitation_type, template_name, property_unit=None):
    """
    invited_by_profile → UserProfile instance
    email → email to send invitation
    invitation_type → string (OWNER_TO_PMC / PMC_TO_OWNER / PMC_TO_TENANT)
    template_name → HTML template file
    """
    if UserInvitation.objects.filter(
        email=email,
        invitation_type=invitation_type,
        invited_by=invited_by_profile,
        property_unit=property_unit
    ).exists():
        return None, "Invitation already sent to this email"
    token = str(uuid.uuid4())
    invitation = UserInvitation.objects.create(
        email=email,
        invited_by=invited_by_profile,
        created_by=invited_by_profile.user,
        invitation_type=invitation_type,
        token=token,
        status=constants.PENDING,
        property_unit=property_unit
    )
    user_exists = User.objects.filter(email=email).exists()
    if user_exists:
        base_url = "https://units.doqfy.in/auth/login"
    else:
        base_url = "https://units.doqfy.in/auth/new-user"
    invite_link = base_url 
    subject = "Invitation to Join Property Management Portal"
    property_context = {}
    if property_unit:
        property_context = {
            "property_name": getattr(property_unit.property, "property_name", ""),
            "property_unit_name": getattr(property_unit, "property_unit_name", ""),
            "apartment_no": getattr(property_unit, "apartment_no", ""),
            "address": getattr(property_unit.property, "address", "") if property_unit.property else "",
        }
    body_text = (
        f"You are invited by {invited_by_profile.user.email}\n"
        f"Property: {property_context.get('property_name', '')}\n"
        f"Unit: {property_context.get('property_unit_name', '')}\n"
        f"Apartment No: {property_context.get('apartment_no', '')}\n"
        f"Address: {property_context.get('address', '')}\n\n"
        f"Use this link: {invite_link}"
    )
    body_html = render_to_string(template_name, {
        "inviter_email": invited_by_profile.user.email,
        "invite_link": invite_link,
        "property": property_context,
    })
    try:
        send_ses_email(email, subject, body_text, body_html)
    except Exception:
        return None, "Invitation created but email sending failed"
    return invitation, None





def serialize_lease(lease):
    return {
         "id": lease.id,
        "parent_property": {
    "key": lease.lease_property.property.id if lease.lease_property and lease.lease_property.property else None,
    "value": lease.lease_property.property.property_name if lease.lease_property and lease.lease_property.property else ""
},
"property_unit_name": {
    "key": lease.lease_property.id if lease.lease_property else None,
    "value": lease.lease_property.property_unit_name if lease.lease_property else ""
},

        "tenant": {
            "key": lease.tenant.id if lease.tenant else None,
            "value": (
                lease.tenant.user.get_full_name()
                if lease.tenant and lease.tenant.user.get_full_name()
                else lease.tenant.user.username
                if lease.tenant else None
            )
        },
        "owner": {
            "key": lease.owner.id if lease.owner else None,
            "value": (
                lease.owner.user.get_full_name()
                if lease.owner and lease.owner.user.get_full_name()
                else lease.owner.user.username
                if lease.owner else None
            )
        },


        "created_by_id": lease.created_by.id if lease.created_by else None,

        "lease_number": lease.lease_number,
        "lease_start_date": datetime_to_epoch_millis(lease.lease_start_date),
        "lease_end_date": datetime_to_epoch_millis(lease.lease_end_date),
        "lease_grace_start_date": datetime_to_epoch_millis(lease.lease_grace_start_date),
        "lease_grace_end_date": datetime_to_epoch_millis(lease.lease_grace_end_date),
        "lease_remarks": lease.lease_remarks,
        "step_status": lease.step_status,
        "lease_status": lease.lease_status,
        "pdf_path": lease.pdf_path,

        "annual_amount": lease.annual_amount,
        "actual_annual_amount": lease.actual_annual_amount,
        "rent": lease.rent,
        "booking_amount": lease.booking_amount,
        "security_deposit": lease.security_deposit,
        "maintenance_charges": lease.maintenance_charges,
        "commission_percentage": lease.commission_percentage,
        "notice_period": lease.notice_period,
        "discount": lease.discount,
        "contract_amount": lease.contract_amount,
        "payment_count": lease.payment_count,
        "shell": lease.shell,
        "core": lease.core,
    }


def get_property_images(property_id, single=False):
    """
    get single or list of property images 
    """
    try:
        property_obj = property.objects.get(id=property_id)
    except property.DoesNotExist:
        return {
            "error": True,
            "message": "Invalid property id"
        }

    images_qs = PropertyImages.objects.filter(
        property=property_obj
    ).order_by("-id")

    if not images_qs.exists():
        return {
            "error": False,
            "property": property_obj,
            "images": []  
        }

    final_images = []

 
    if single:
        images_qs = images_qs[:1]  

    for img in images_qs:
        final_images.append({
            "id": img.id,
            "file_name": img.file_name,
            "type": img.image_type,
            "data": fetch_s3_presigned_url(
                img.image_path,
                file_name=img.file_name
            )
        })

    return {
        "error": False,
        "property": property_obj,
        "images": final_images 
    }


def get_lease_status(lease_obj):
    """
    Args:
        lease_obj: LeasePropertyDetails instance
    Returns:
        str: 'ongoing', 'about_to_expire', 'expired' or None if lease_obj is None
    """
    if not lease_obj:
        return None
    
    now = timezone.now()
    lease_end = lease_obj.lease_end_date

    if lease_end < now:
        return "Expired"
    elif now + timedelta(days=30) >= lease_end: 
        return "About to Expire"
    else:
        return "Ongoing"





def get_staff_details(company_staff: CompanyStaff, include_password=False):
 
    staff_profile = company_staff.staff
    django_user = staff_profile.user
    total_properties = company_staff.assigned_properties.count()
    occupied_properties = company_staff.assigned_properties.filter(is_occupied=True).count()
    tenancy_ratio = f"{occupied_properties}:{total_properties}" if total_properties else "0:0"
    data = {
        "staff_id": company_staff.id,
        "staff_name": django_user.first_name,
        "email": django_user.email,
        "contact_number": staff_profile.contact_number,
        "emirate_id": staff_profile.emirate_id,
        "city": staff_profile.city.name if staff_profile.city else None,
        "locality": staff_profile.locality,
        "address": staff_profile.address,
        "additional_address": staff_profile.additional_address,
        "postal_code": staff_profile.pin_code,
        "property_count": total_properties,
        "tenancy_ratio": tenancy_ratio,
        "roles": [role.name for role in company_staff.roles.all()],
    }

    if include_password:
        data["password_hash"] = django_user.password
    return data





def get_tenant_detail_by_id(tenant_id):
    tenant_profile = UserProfile.objects.select_related(
        "user", "city"
    ).filter(
        id=tenant_id,
        user_role=constants.TENANT
    ).first()

    if not tenant_profile:
        return None

    user = tenant_profile.user

    return {
        "tenant_id": tenant_profile.id,
        "full_name": user.get_full_name(),
        "email": user.email,

        "user_code": tenant_profile.user_code,

        "contact_number": tenant_profile.contact_number,

        "telephone_number": tenant_profile.telephone_number,
        "fax_number": tenant_profile.fax_number,

        "passport_number": tenant_profile.passport_number,
        "passport_expiry_datetime": tenant_profile.passport_expiry_datetime,
        "visa_number": tenant_profile.visa_number,
        "visa_expiry_datetime": tenant_profile.visa_expiry_datetime,

        "emirate_id": tenant_profile.emirate_id,
        "uae_residence_visa": tenant_profile.uae_residence_visa,

        "address": tenant_profile.address,
        "additional_address": tenant_profile.additional_address,
        "locality": tenant_profile.locality,
        "pin_code": tenant_profile.pin_code,

        "city": {
            "key": tenant_profile.city.id if tenant_profile.city else None,
            "value": tenant_profile.city.name if tenant_profile.city else None,
        },
        "natioanlity":tenant_profile.city.state.country.name if tenant_profile.city else None ,
    
    }

def audit_logs(request, message, action_type):
    user_profile = request.user

    AuditLog.objects.create(
        userprofile=user_profile,
        created_by=user_profile.user,
        message=message,
        action_type=action_type
    )