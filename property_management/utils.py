from user_service.models import UserProfile,Documents,OwnerDocumentsMapping,StaffDocumentsMapping,CompanyUserDocumentsMapping,TenantDocumentsMapping,PropertyUnitDetails,Property,Company,PMStaffCompanyMapping,PropertyImages ,PropertyDocumentsMapping
from property_management.models import LeasePropertyDetails,UserInvitation
from utilities.helper_functions import upload_file_to_s3_base64,fetch_s3_file_as_base64, prepare_response, logger,send_ses_email,safe_decimal ,safe_epoch_to_datetime ,replace_placeholders ,fetch_s3_presigned_url ,export_to_csv ,datetime_to_epoch_millis,get_pdfkit_config,generate_property_code ,fetch_s3_presigned_url_for_download
from utilities import status ,  constants
from django.contrib.auth.models import User
import uuid
import re
from django.template.loader import render_to_string
from datetime import datetime, timedelta
from django.utils import timezone

def get_full_property_data(property_unit_id):
    """
    Returns complete property data including:
    - PropertyUnitDetails
    - Parent Property
    - Property Images
    - Property Documents
    - Owner Details
    - Tenant Details (from LeasePropertyDetails if exists)
    """
    try:
     
        prop = PropertyUnitDetails.objects.filter(id=property_unit_id).first()
        if not prop:
            return None, "PropertyUnitDetails not found"
        parent_property = None
        if prop.property:
            parent_property = {
                "id": prop.property.id,
                "property_name": prop.property.property_name,
                "property_code": prop.property.Property_code,
                "property_address":prop.property.address,
            }

        property_type_options = dict(constants.PROPERTY_TYPE_CHOICES)
        property_type_data = {
            "key": prop.property_type_options,
            "value": property_type_options.get(prop.property_type_options)
        }
        property_unit_data = {
            "id": prop.id,
            "property_unit_name": prop.property_unit_name,
            "land_dm_no": prop.land_dm_no,
            "area_of_property": prop.area_of_property,
            "no_of_parking": prop.no_of_parking,
            "bedrooms": prop.bedrooms,
            "balcony": prop.balcony,
            "plot_no": prop.plot_no,
            "area_unit": prop.area_unit,
            "land_area": prop.land_area,
            "apartment_no": prop.apartment_no,
            "apartment_floor_no": prop.apartment_floor_no,
            "no_of_floors": prop.no_of_floors,
            "makani_no": prop.makani_no,
            "dewa_no": prop.dewa_no,
            "property_code": prop.property_code,
            "property_type": property_type_data,
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
        images_qs = prop.property_images.all().order_by("-id")
        images = [
            {
                "id": img.id,
                "file_name": img.file_name,
                "url": fetch_s3_presigned_url(img.image_path, file_name=img.file_name),
                "type": img.image_type
            }
            for img in images_qs
        ]

        docs_qs = prop.property_documents.select_related('document').order_by("-id")
        documents = [
            {
                "id": mapping.id,
                "file_name": mapping.document.file_name,
                "url": fetch_s3_presigned_url(mapping.document.file_path, file_name=mapping.document.file_name),
                "type": mapping.document_choice
            }
            for mapping in docs_qs
        ]
        owner_data = None
        if prop.owner:
            owner_user = prop.owner.user
            city = prop.owner.city
            state = city.state if city else None
            country = state.country if state else None
            owner_data = {
                "id": prop.owner.id,
                "email": owner_user.email,
                "first_name": owner_user.first_name,
                "last_name": owner_user.last_name,
                "address": prop.owner.address,
                "additional_address": prop.owner.additional_address,
                 "city": city.name if city else None,
              "state": state.name if state else None,
            "country": country.name if country else None,
                "pin_code": prop.owner.pin_code,
                "contact_number": prop.owner.contact_number,
            }
        tenant_data = None
        lease = prop.lease_details.first()  
        if lease and lease.tenant:
            tenant_user = lease.tenant.user
            city = lease.tenant.city
            state = city.state if city else None
            country = state.country if state else None
            tenant_data = {
                "id": lease.tenant.id,
                "email": tenant_user.email,
                "first_name": tenant_user.first_name,
                "last_name": tenant_user.last_name,
                "address": lease.tenant.address,
                "additional_address": lease.tenant.additional_address,
               "city": city.name if city else None,
                      "state": state.name if state else None,
        "country": country.name if country else None,
                "pin_code": lease.tenant.pin_code,
                "contact_number": lease.tenant.contact_number,
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
            "city": user_profile.city,
            "state": user_profile.state,
            "country": user_profile.country,
            "time_zone": user_profile.time_zone,
            "pin_code": user_profile.pin_code,
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



def create_and_send_invitation(invited_by_profile, email, invitation_type, template_name):
    """
    invited_by_profile → UserProfile instance
    email → email to send invitation
    invitation_type → string (OWNER_TO_PMC / PMC_TO_OWNER / PMC_TO_TENANT)
    template_name → HTML template file
    """
    if UserInvitation.objects.filter(
        email=email,
        invitation_type=invitation_type,
        invited_by=invited_by_profile
    ).exists():
        return None, "Invitation already sent to this email"
    token = str(uuid.uuid4())

    invitation = UserInvitation.objects.create(
        email=email,
        invited_by=invited_by_profile,
        created_by=invited_by_profile.user, 
        invitation_type=invitation_type,
        token=token,
        status=constants.PENDING
    )
    invite_link = f"https://frontend.com/invite/accept?token={token}"
    subject = "Invitation to Join Property Management Portal"

    body_text = (
        f"You are invited by {invited_by_profile.user.email}. "
        f"Use this link: {invite_link}"
    )

    body_html = render_to_string(template_name, {
        "inviter_email": invited_by_profile.user.email,
        "invite_link": invite_link,
    })

    try:
        send_ses_email(email, subject, body_text, body_html)
    except Exception:
        return None, "Invitation created but email sending failed"

    return invitation, None




def serialize_lease(lease):
    return {
        "id": lease.id,
        "property": {
            "key": lease.lease_property.id,
            "value": lease.lease_property.property.property_name if hasattr(lease.lease_property, "property") else ""
        },
        "tenant": {
            "key": lease.tenant.id,
            "value": lease.tenant.full_name
        },
        "owner_id": lease.owner.id if lease.owner else None,
        "owner_name": lease.owner.full_name if lease.owner else None,
        "created_by_id": lease.created_by.id if lease.created_by else None,
        "lease_start_date": datetime_to_epoch_millis(lease.lease_start_date),
        "lease_end_date": datetime_to_epoch_millis(lease.lease_end_date),
        "lease_grace_start_date": datetime_to_epoch_millis(lease.lease_grace_start_date),
        "lease_grace_end_date": datetime_to_epoch_millis(lease.lease_grace_end_date),

        "lease_remarks": lease.lease_remarks,
        "step_status": lease.step_status,

        "commercial_details": {
            "annual_amount": lease.annual_amount,
            "actual_annual_amount": lease.actual_annual_amount,
            "rent": lease.rent,
            "booking_amount": lease.booking_amount,
            "security_deposit": lease.security_deposit,
            "maintenance_charges": lease.maintenance_charges,
            "commission_percentage": lease.commission_percentage,
            "notice_period": lease.notice_period,
            "discount": lease.discount,
        }
    }





def get_property_images(property_id, single=False):
    """
    get single or list of property images 
    """
    try:
        property_obj = PropertyUnitDetails.objects.get(id=property_id)
    except PropertyUnitDetails.DoesNotExist:
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
