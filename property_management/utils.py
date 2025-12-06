from property_management.models import OwnerDetails ,TenantDetails , LeasePropertyDetails ,LeaseCommercials,LeaseEjariUpload,OwnerPMCInvitation,PMCOwnerInvitation , PMCTenantInvitation ,Template, TemplateFields ,TemplateValues 
from user_service.models import PropertyManagerCompanyDetails ,PropertyDetails ,UserProfile,StaffDetails  ,PropertyCommercial ,PropertyImages ,PropertyDocuments 
from utilities.helper_functions import upload_file_to_s3_base64,fetch_s3_file_as_base64, prepare_response, logger,send_ses_email,safe_decimal ,safe_epoch_to_datetime ,replace_placeholders ,fetch_s3_presigned_url ,export_to_csv ,datetime_to_epoch_millis,get_pdfkit_config,generate_property_code 
from utilities import status ,  constants

def get_property_images(property_id):
    """
    Returns all images for a given property ID
    """
    images_qs = PropertyImages.objects.filter(property_id=property_id)
    images_list = []

    for img in images_qs:
        presigned_url = fetch_s3_presigned_url(
            img.image_path,
            file_name=img.file_name
        )
        images_list.append({
            "image_url": presigned_url,
            "image_type": img.image_type,
            "file_name": img.file_name
        })
    return images_list






def get_owner_full_details(owner_id):
    """
    Get full details of an owner by owner_id.
    
    Returns dict with all user and owner fields or None if not found.
    """
    owner = OwnerDetails.objects.filter(id=owner_id).select_related('user').first()
    if not owner:
        return None
    user = owner.user
    owner_data = {
        "owner_id": owner.id,
        "owner_name": owner.full_name,
        "email": user.email if user else None,
        "user_type": user.user_type if user else None,
        "first_name": user.first_name if user else None,
        "last_name": user.last_name if user else None,
        "emirates_id": owner.emirate_id,
        "uae_residence_visa": owner.uae_residence_visa,
        "trade_license_number": owner.trade_license_number,
        "owner_number": owner.owner_number,
        "mobile_number": owner.mobile_number,
        "manage_manually": owner.manage_manually,
        "manage_through_pmc": owner.manage_through_pmc,
        "manage_through": owner.manage_through,
        "profile_image": user.profile_image if user else None,
        "profile_image_type": user.profile_image_type if user else None,
        "country": user.country if user else None,
        "time_zone": user.time_zone if user else None,
        "utc": user.utc if user else None,
        "last_login": user.last_login if user else None,
        "address": owner.address,
        "state": owner.state,
        "postal_code": owner.postal_code,
        "emirates_id_file": owner.emirates_id_file,
        "residence_visa_file": owner.residence_visa_file,
        "dld_certificate_file": owner.dld_certificate_file,
        "dewa_registration_file": owner.dewa_registration_file,
        "owner_documents": owner.owner_documents or {},
    }

    return owner_data





def get_property_documents(property_id):
    """
    Fetch all documents for a given property_id.
    Returns dict with documents list and step_status.
    """
    try:
        property_obj = PropertyDetails.objects.get(id=property_id)
    except PropertyDetails.DoesNotExist:
        return None

    docs_qs = PropertyDocuments.objects.filter(property_id=property_id).order_by("-id")
    final_docs = []

    for doc in docs_qs:
        url = doc.file_path
        file_name = doc.file_name
        doc_type = doc.document_type
        base64_data = fetch_s3_presigned_url(url, file_name=file_name)

        final_docs.append({
            "file_name": file_name,
            "data": base64_data,
            "type": doc_type,
            "id": doc.id,
        })

    return  final_docs




def get_tenant_data(tenant_id):
    """
    Fetch full tenant data by tenant_id.
    Returns a dictionary with all tenant info and documents.
    """
    try:
        tenant = TenantDetails.objects.select_related("user").get(id=tenant_id)
    except TenantDetails.DoesNotExist:
        return None

    tenant_user = tenant.user
    documents = {}
    doc_fields = [
        "emirates_id_file",
        "passport_self_file",
        "passport_family_file",
        "visa_self_file",
        "visa_family_file",
        "employment_proof_file",
        "bank_statement_file"
    ]
    for field in doc_fields:
        file_path = getattr(tenant, field, None)
        if file_path:
            documents[field] = fetch_s3_presigned_url(file_path, file_name=file_path.split("/")[-1])

   
    tenant_data = {
        "tenant_id": tenant.id,
        "full_name": tenant.full_name,
        "email": tenant_user.email if tenant_user else None,
        "mobile_number": tenant.mobile_number,
        "tenant_number": tenant.tenant_number,
        "nationality": tenant.nationality,
        "address": tenant.address,
        "city": tenant.city,
        "state": tenant.state,
        "postal_code": tenant.postal_code,
        "emirates_id": tenant.emirate_id,
        "uae_residence_visa": tenant.uae_residence_visa,
        "trade_license_number": tenant.trade_license_number,
        "passport_self": tenant.passport_self,
        "passport_family_member": tenant.passport_family_member,
        "passport_expiry": tenant.passport_expiry,
        "visa_self": tenant.visa_self,
        "visa_family_member": tenant.visa_family_member,
        "visa_expiry": tenant.visa_expiry,
        "employment_proof": tenant.employment_proof,
        "manage_through": tenant.manage_through,
        "tenant_documents": documents,
        "profile_image": tenant_user.profile_image if tenant_user else None,
    }
    return tenant_data




def get_lease_ejari_documents(lease_id):
    """
    Fetch all Ejari documents for a given lease_id.
    Returns documents list or None if lease doesn't exist.
    """

    if not lease_id:
        return None

    lease_obj = LeasePropertyDetails.objects.filter(id=lease_id).first()
    if not lease_obj:
        return None

    docs_qs = LeaseEjariUpload.objects.filter(lease_id=lease_id).order_by("-id")
    final_docs = []

    for doc in docs_qs:
        url = doc.file_path
        file_name = doc.file_name
        doc_type = doc.document_type
        base64_data = fetch_s3_presigned_url(url, file_name=file_name)

        final_docs.append({
            "file_name": file_name,
            "data": base64_data,
            "type": doc_type,
            "id": doc.id,
        })

    return final_docs


def get_owner_documents(owner_id):
    owner = OwnerDetails.objects.filter(id=owner_id).first()
    if not owner:
        return None
    return owner.owner_documents or {}


def get_tenant_documents(tenant_id):
    tenant = TenantDetails.objects.filter(id=tenant_id).first()
    if not tenant:
        return None
    return tenant.tenant_documents or {}




def get_pmc_documents(pmc_id):
    pmc = PropertyManagerCompanyDetails.objects.filter(id=pmc_id).first()
    if not pmc:
        return None
    return pmc.pmc_documents or {}
