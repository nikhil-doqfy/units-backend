
from django.shortcuts import get_object_or_404
from django.db import IntegrityError, transaction
from property_management.models import OwnerDetails ,PropertyDocuments,TenantDetails , LeasePropertyDetails ,LeaseCommercials,LeaseEjariUpload,LeaseDocumentLayout
from user_service.models import PropertyManagerCompanyDetails ,PropertyDetails 
from utilities.decorator import is_request_authenticated
import json
from utilities.helper_functions import upload_file_to_s3_base64,fetch_s3_file_as_base64, prepare_response, logger
from utilities import status ,  constants
from django.utils import timezone
from utilities import config
from django.core.paginator import Paginator
from django.db.models import Q


@is_request_authenticated
def owner_details_view(request):
    """
    CRUD API for OwnerDetails
    """

    try:
        current_user = request.user

        if current_user.user_type != constants.OWNER:
            return prepare_response(
                message="Access denied. Only owners can manage owner details.",
                status=status.HTTP_403_FORBIDDEN
            )
        if request.method == "GET":
            owner = OwnerDetails.objects.filter(user=current_user).first()
            if not owner:
                return prepare_response(
                    message="Owner details not found.",
                    status=status.HTTP_404_NOT_FOUND
                )

            owner_data = {
                "full_name":owner.full_name,
                "id": owner.id,
                "user_email": owner.user.email,
                "emirate_id": owner.emirate_id,
                "uae_residence_visa": owner.uae_residence_visa,
                "trade_license_number": owner.trade_license_number,
                "owner_number": owner.owner_number,
                "mobile_number": owner.mobile_number,
                "manage_manually": owner.manage_manually,
                "manage_through_pmc": owner.manage_through_pmc,
                "emirates_id_file": owner.emirates_id_file,
                "residence_visa_file": owner.residence_visa_file,
                "dld_certificate_file": owner.dld_certificate_file,
                "dewa_registration_file": owner.dewa_registration_file,
            }

            return prepare_response(
                message="Owner details fetched successfully.",
                content=owner_data,
                status=status.HTTP_200_OK
            )

        elif request.method == "POST":
            data = json.loads(request.body)

            if OwnerDetails.objects.filter(user=current_user).exists():
                return prepare_response(
                    message="Owner details already exist.",
                    status=status.HTTP_400_BAD_REQUEST
                )
            emirates_id_file = upload_file_to_s3_base64(data["emirates_id_file"], f"owner/{current_user.id}/emirates_id.png") if data.get("emirates_id_file") else None
            residence_visa_file = upload_file_to_s3_base64(data["residence_visa_file"], f"owner/{current_user.id}/residence_visa.png") if data.get("residence_visa_file") else None
            dld_certificate_file = upload_file_to_s3_base64(data["dld_certificate_file"], f"owner/{current_user.id}/dld_certificate.png") if data.get("dld_certificate_file") else None
            dewa_registration_file = upload_file_to_s3_base64(data["dewa_registration_file"], f"owner/{current_user.id}/dewa_registration.png") if data.get("dewa_registration_file") else None

            owner = OwnerDetails.objects.create(
                user=current_user,
                full_name=data.get("full_name", ""),
                emirate_id=data.get("emirate_id", ""),
                uae_residence_visa=data.get("uae_residence_visa", ""),
                trade_license_number=data.get("trade_license_number", ""),
                owner_number=data.get("owner_number", ""),
                mobile_number=data.get("mobile_number", ""),
                manage_manually=data.get("manage_manually", False),
                manage_through_pmc=data.get("manage_through_pmc", False),
                emirates_id_file=emirates_id_file,
                residence_visa_file=residence_visa_file,
                dld_certificate_file=dld_certificate_file,
                dewa_registration_file=dewa_registration_file,
            )

            return prepare_response(
                message="Owner details created successfully.",
                content={"id": owner.id},
                status=status.HTTP_201_CREATED
            )
        elif request.method == "PUT":
            data = json.loads(request.body)
            owner = OwnerDetails.objects.filter(user=current_user).first()

            if not owner:
                return prepare_response(
                    message="Owner details not found.",
                    status=status.HTTP_404_NOT_FOUND
                )

            owner.emirate_id = data.get("emirate_id", owner.emirate_id)
            owner.uae_residence_visa = data.get("uae_residence_visa", owner.uae_residence_visa)
            owner.trade_license_number = data.get("trade_license_number", owner.trade_license_number)
            owner.owner_number = data.get("owner_number", owner.owner_number)
            owner.mobile_number = data.get("mobile_number", owner.mobile_number)
            owner.manage_manually = data.get("manage_manually", owner.manage_manually)
            owner.manage_through_pmc = data.get("manage_through_pmc", owner.manage_through_pmc)

           
            if data.get("emirates_id_file"):
                owner.emirates_id_file = upload_file_to_s3_base64(data["emirates_id_file"], f"owner/{current_user.id}/emirates_id.png")

            if data.get("residence_visa_file"):
                owner.residence_visa_file = upload_file_to_s3_base64(data["residence_visa_file"], f"owner/{current_user.id}/residence_visa.png")

            if data.get("dld_certificate_file"):
                owner.dld_certificate_file = upload_file_to_s3_base64(data["dld_certificate_file"], f"owner/{current_user.id}/dld_certificate.png")

            if data.get("dewa_registration_file"):
                owner.dewa_registration_file = upload_file_to_s3_base64(data["dewa_registration_file"], f"owner/{current_user.id}/dewa_registration.png")

            owner.save()

            return prepare_response(
                message="Owner details updated successfully.",
                status=status.HTTP_200_OK
            )
        elif request.method == "DELETE":
            owner = OwnerDetails.objects.filter(user=current_user).first()
            if not owner:
                return prepare_response(
                    message="Owner details not found.",
                    status=status.HTTP_404_NOT_FOUND
                )

            owner.delete()
            return prepare_response(
                message="Owner details deleted successfully.",
                status=status.HTTP_200_OK
            )
        else:
            return prepare_response(
                message="Invalid request method.",
                status=status.HTTP_405_METHOD_NOT_ALLOWED
            )

    except Exception as e:
        logger.error(f"Error in owner_details_view: {str(e)}")
        return prepare_response(
            message=f"Something went wrong: {str(e)}",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@is_request_authenticated
def list_all_owners(request):
    try:
        if request.method != "GET":
            return prepare_response(
                message=constants.INVALID_REQUEST_METHOD,
                status=status.HTTP_405_METHOD_NOT_ALLOWED
            )
        search = request.GET.get("search")  
        owners_qs = OwnerDetails.objects.all().select_related("user")
        if search:
            owners_qs = owners_qs.filter(
                Q(full_name__icontains=search)
                | Q(mobile_number__icontains=search)
                | Q(owner_number__icontains=search)
            )
        owners_data = []
        for owner in owners_qs:
            owners_data.append({
                "id": owner.id,
                "user_id": owner.user.id if owner.user else None,
                "full_name": owner.full_name,
                "emirate_id": owner.emirate_id,
                "uae_residence_visa": owner.uae_residence_visa,
                "trade_license_number": owner.trade_license_number,
                "owner_number": owner.owner_number,
                "mobile_number": owner.mobile_number,
                "manage_manually": owner.manage_manually,
                "manage_through_pmc": owner.manage_through_pmc,
                "created_at": owner.created_at.strftime("%Y-%m-%d %H:%M:%S") if hasattr(owner, "created_at") else None,
            })

        return prepare_response(
            content={"total": len(owners_data), "owners": owners_data},
            message=constants.OWNER_LIST_FETCHED_SUCCESS,
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return prepare_response(
            message=f"Failed to fetch owner list: {str(e)}",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



@is_request_authenticated
def choose_manage_option(request):
    if request.method != "POST":
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    current_user = request.user 
    if current_user.user_type != "OWNER":
        return prepare_response(
            message=constants.ACCESS_DENIED_OWNER_ONLY,
            status=status.HTTP_403_FORBIDDEN
        )
    import json
    try:
        data = json.loads(request.body)
        option = data.get("option", "").lower()
    except Exception:
        option = request.POST.get("option", "").lower()

    try:
       
        owner_details = get_object_or_404(OwnerDetails, user=current_user)
        if option == "manual":
            owner_details.manage_manually = True
            owner_details.manage_through_pmc = False
        elif option == "pmc":
            owner_details.manage_manually = False
            owner_details.manage_through_pmc = True
        else:
            return prepare_response(
                message=constants.INVALID_OPTION,
                status=status.HTTP_400_BAD_REQUEST
            )
        owner_details.save()
        return prepare_response(
            content={"chosen_option": option},
            message=constants.MANAGEMENT_OPTION_UPDATED_SUCCESS,
            status=status.HTTP_200_OK
        )
    except Exception as e:
        return prepare_response(
            message=f"An error occurred: {str(e)}",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



@is_request_authenticated
def upload_owner_documents(request):
    if request.method != "POST":
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    try:
        data = json.loads(request.body)
    except Exception:
        return prepare_response(
            message=constants.INVALID_JSON_BODY,
            status=status.HTTP_400_BAD_REQUEST
        )
    documents = data.get("documents", [])
    if len(documents) != 4:
        return prepare_response(
            message=constants.ALL_DOCUMENTS_REQUIRED,
            status=status.HTTP_400_BAD_REQUEST
        )

    current_user = request.user
    try:
        owner_details = OwnerDetails.objects.get(user=current_user)
    except OwnerDetails.DoesNotExist:
        return prepare_response(
            message=constants.OWNER_DETAILS_NOT_FOUND,
            status=status.HTTP_404_NOT_FOUND
        )  
    prop_docs_dict = {}
    for doc in documents:
        base64_data = doc.get("document")
        file_name = doc.get("file_name")
        doc_type = doc.get("type") 
        if not base64_data or not file_name or not doc_type:
            return prepare_response(
                message=f"Missing fields in document: {doc}",
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            s3_url = upload_file_to_s3_base64(
                base64_data, 
                f"owner_documents/{current_user.id}/{file_name}"
            )
            setattr(owner_details, f"{doc_type}_file", s3_url)
        except Exception as e:
            return prepare_response(
                message=f"Failed to upload document '{file_name}': {str(e)}",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    owner_details.save()
    current_user.is_document_uploaded = True
    current_user.save()
    prop_doc_instance, created = PropertyDocuments.objects.get_or_create(
        document_title=f"Owner {current_user.id} Documents",
        defaults={"property_documents": prop_docs_dict}
    )
    if not created:
        prop_doc_instance.property_documents = prop_docs_dict
        prop_doc_instance.updated_at = timezone.now()
        prop_doc_instance.save()

    return prepare_response(
        message=constants.DOCUMENTS_UPLOAD_SUCCESS,
        status=status.HTTP_200_OK
    )

@is_request_authenticated
def get_owner_documents(request):
    if request.method != "GET":
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    current_user = request.user
    try:
        owner_details = OwnerDetails.objects.filter(user=current_user).first()
        if not owner_details:
            return prepare_response(
                message=constants.OWNER_DETAILS_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )
        documents = {
            "emirates_id_file": owner_details.emirates_id_file,
            "residence_visa_file": owner_details.residence_visa_file,
            "dld_certificate_file": owner_details.dld_certificate_file,
            "dewa_registration_file": owner_details.dewa_registration_file,
        }
        base64_docs = {}
        for doc_type, file_url in documents.items():
            base64_docs[doc_type] = fetch_s3_file_as_base64(file_url) if file_url else None
        return prepare_response(
            content={"documents": base64_docs},
            message=constants.DOCUMENTS_FETCH_SUCCESS,
            status=status.HTTP_200_OK
        )
    except Exception as e:
        logger.error(f" Failed to fetch documents: {str(e)}")
        return prepare_response(
            message=f"Failed to fetch documents: {str(e)}",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    

@is_request_authenticated
def upload_tenant_documents(request):
    if request.method != "POST":
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    current_user = request.user
    if current_user.user_type != constants.TENANT:
        return prepare_response(
            message=constants.ACCESS_DENIED_TENANTS_ONLY_UPLOAD_DOC,
            status=status.HTTP_403_FORBIDDEN
        )
    try:
        data = json.loads(request.body)
    except Exception:
        return prepare_response(
            message=constants.INVALID_JSON_BODY,
            status=status.HTTP_400_BAD_REQUEST
        )
    required_docs = ["emirates_id", "passport_self", "visa_self", "employment_proof", "bank_statement"]
    optional_docs = ["passport_family", "visa_family"]

    document_data = data.get("documents", {})
    for doc in required_docs:
        if doc not in document_data:
            return prepare_response(
                message=f"Missing required document: {doc}",
                status=status.HTTP_400_BAD_REQUEST
            )
    try:
        tenant_details = TenantDetails.objects.filter(user=current_user).first()
        if not tenant_details:
            return prepare_response(
                message=constants.TENANT_DETAILS_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        document_urls = {}
        for doc_type in required_docs + optional_docs:
            base64_data = document_data.get(doc_type)
            if base64_data:
                file_name = f"{doc_type}_{timezone.now().strftime('%Y%m%d%H%M%S')}.pdf"
                s3_url = upload_file_to_s3_base64(
                    base64_data,
                    f"tenant_documents/{current_user.id}/{file_name}"
                )
                document_urls[doc_type] = s3_url
        tenant_details.emirates_id_file = document_urls.get("emirates_id")
        tenant_details.passport_self_file = document_urls.get("passport_self")
        tenant_details.visa_self_file = document_urls.get("visa_self")
        tenant_details.employment_proof_file = document_urls.get("employment_proof")
        tenant_details.bank_statement_file = document_urls.get("bank_statement")
        tenant_details.passport_family_file = document_urls.get("passport_family")
        tenant_details.visa_family_file = document_urls.get("visa_family")
        tenant_details.save()
        current_user.is_document_uploaded = True
        current_user.save(update_fields=["is_document_uploaded"])
        return prepare_response(
            content={"document_urls": document_urls},
            message=constants.DOCUMENTS_UPLOAD_SUCCESS,
            status=status.HTTP_200_OK
        )
    except Exception as e:
        return prepare_response(
            message=f"Failed to upload tenant documents: {str(e)}",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    

@is_request_authenticated
def update_tenant_documents(request):
    if request.method != "PUT":
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    try:
        data = json.loads(request.body)
    except Exception:
        return prepare_response(
            message=constants.INVALID_JSON_BODY,
            status=status.HTTP_400_BAD_REQUEST
        )
    current_user = request.user
    if current_user.user_type != constants.TENANT:
        return prepare_response(
            message=constants.ACCESS_DENIED_TENANTS_ONLY,
            status=status.HTTP_403_FORBIDDEN
        )
    try:
        tenant_details = TenantDetails.objects.get(user=current_user)
    except TenantDetails.DoesNotExist:
        return prepare_response(
            message=constants.TENANT_DETAILS_NOT_FOUND,
            status=status.HTTP_400_BAD_REQUEST
        )
    document_fields = [
        "emirates_id",
        "passport_self",
        "visa_self",
        "employment_proof",
        "bank_statement",
        "passport_family",
        "visa_family",
    ]
    updated_docs = {}

    for field in document_fields:
        doc_data = data.get(field)
        if not doc_data or doc_data == "":
            continue
        try:
            s3_url = upload_file_to_s3_base64(
                doc_data,
                f"tenant_documents/{current_user.id}/{field}"
            )
            setattr(tenant_details, f"{field}_file", s3_url)
            updated_docs[field] = s3_url
        except Exception as e:
            return prepare_response(
                message=f"Failed to upload {field}: {str(e)}",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    if not updated_docs:
        return prepare_response(
            message=constants.NO_NEW_DOC_PROVIDED,
            status=status.HTTP_400_BAD_REQUEST
        )
    tenant_details.save()
    current_user.is_document_uploaded = True
    current_user.save()
    return prepare_response(
        message=constants.DOCUMENTS_UPLOAD_SUCCESS,
        status=status.HTTP_200_OK
    )


  
@is_request_authenticated
def tenant_details_view(request):
    user = request.user  


    if user.user_type != constants.TENANT:
        return prepare_response(
            message=constants.ACCESS_DENIED_TENANTS_ONLY,
            status=status.HTTP_403_FORBIDDEN
        )
    if request.method == "GET":
        try:
            tenant = TenantDetails.objects.select_related("property").get(user=user)
            property_details = tenant.property.property_name if tenant.property else None

            documents = [
                {"file_url": tenant.emirates_id_file, "document_name": "Emirates ID"},
                {"file_url": tenant.passport_self_file, "document_name": "Passport Self"},
                {"file_url": tenant.passport_family_file, "document_name": "Passport Family Member"},
                {"file_url": tenant.visa_self_file, "document_name": "Visa Self"},
                {"file_url": tenant.visa_family_file, "document_name": "Visa Family Member"},
                {"file_url": tenant.employment_proof_file, "document_name": "Employment Proof"},
                {"file_url": tenant.bank_statement_file, "document_name": "Bank Statement"},
            ]

            filtered_documents = [doc for doc in documents if doc["file_url"]]

            tenant_data = {
                "tenant_id": tenant.id,
                "full_name": tenant.full_name,
                "type": user.user_type,
                "email": user.email,
                "phone": tenant.mobile_number,
                "tenant_number": tenant.tenant_number,
                "emirate_id": tenant.emirate_id,
                "nationality": tenant.nationality,
                "passport_self": tenant.passport_self,
                "passport_family_member": tenant.passport_family_member,
                "passport_expiry": tenant.passport_expiry,
                "visa_self": tenant.visa_self,
                "visa_family_member": tenant.visa_family_member,
                "visa_expiry": tenant.visa_expiry,
                "employment_proof": tenant.employment_proof,
                "linked_property": property_details,
                "profile_picture": user.profile_image,
                "documents": filtered_documents,
            }

            return prepare_response(
                content={"tenant_details": tenant_data},
                message=constants.TENANT_DETAILS_FETCHED_SUCCESS,
                status=status.HTTP_200_OK
            )

        except TenantDetails.DoesNotExist:
            return prepare_response(
                message=constants.TENANT_DETAILS_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return prepare_response(
                message=f"An unexpected error occurred: {str(e)}",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    elif request.method == "POST":
        try:
            data = json.loads(request.body.decode('utf-8'))
        except Exception:
            return prepare_response(
                message=constants.INVALID_JSON_BODY,
                status=status.HTTP_400_BAD_REQUEST
            )

        if TenantDetails.objects.filter(user=user).exists():
            return prepare_response(
                message=constants.TENANT_DETAILS_ALREADY_EXISTS,
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            tenant_details = TenantDetails.objects.create(
                user=user,
                full_name=data.get("full_name"),
                emirate_id=data.get("emirate_id"),
                mobile_number=data.get("mobile_number"),
                tenant_number=data.get("tenant_number"),
                nationality=data.get("nationality"),
                passport_self=data.get("passport_self"),
                passport_family_member=data.get("passport_family_member"),
                passport_expiry=data.get("passport_expiry"),
                visa_self=data.get("visa_self"),
                visa_family_member=data.get("visa_family_member"),
                visa_expiry=data.get("visa_expiry"),
                employment_proof=data.get("employment_proof"),
            )
            user.is_detail_updated = True
            user.save()

            return prepare_response(
                content={
                    "tenant_details": {
                        "id": tenant_details.id,
                        "full_name": tenant_details.full_name,
                        "mobile_number": tenant_details.mobile_number,
                        "nationality": tenant_details.nationality,
                    },
                    "is_detail_updated": user.is_detail_updated,
                },
                message=constants.TENANT_DETAILS_SAVED_SUCCESS,
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            return prepare_response(
                message=f"Failed to save tenant details: {str(e)}",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    elif request.method == "PUT":
        try:
            data = json.loads(request.body.decode("utf-8"))
        except Exception:
            return prepare_response(
                message=constants.INVALID_JSON_BODY,
                status=status.HTTP_400_BAD_REQUEST
            )

        tenant_details = TenantDetails.objects.filter(user=user).first()
        if not tenant_details:
            return prepare_response(
                message=constants.TENANT_DETAILS_NOT_FOUND,
                status=404
            )

        try:
            for key, value in data.items():
                if hasattr(tenant_details, key):
                    setattr(tenant_details, key, value)

            with transaction.atomic():
                tenant_details.save()

            return prepare_response(
                content={
                    "tenant_details": {
                        "id": tenant_details.id,
                        "full_name": tenant_details.full_name,
                        "mobile_number": tenant_details.mobile_number,
                        "nationality": tenant_details.nationality,
                    },
                    "is_detail_updated": getattr(user, "is_detail_updated", None),
                },
                message=constants.TENANT_DETAILS_UPDATED_SUCCESSFULLY,
                status=status.HTTP_200_OK
            )

        except IntegrityError as ie:
            return prepare_response(
                message=f"Database error: {str(ie)}",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            print("Error updating tenant details:", e)
            return prepare_response(
                message=f"Failed to update tenant details: {str(e)}",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


    elif request.method == "DELETE":
        tenant_id = request.GET.get("id")
        if not tenant_id:
            return prepare_response(
                message="Tenant ID is required in query parameters.",
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            tenant = TenantDetails.objects.filter(id=tenant_id, user=user).first()
            if not tenant:
                return prepare_response(
                     message=constants.TENANT_DETAILS_NOT_FOUND,
                     status=status.HTTP_404_NOT_FOUND
                )
            with transaction.atomic():
                tenant.delete()
            return prepare_response(
                message=constants.TENANT_DETAILS_DELETED_SUCCESS,
                status=status.HTTP_200_OK)

        except Exception as e:
            return prepare_response(
                message=f"Failed to delete tenant details: {str(e)}",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
    else:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )





@is_request_authenticated
def upload_pmc_documents(request):
    if request.method != "POST":
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    try:
        data = json.loads(request.body)
    except Exception:
        return prepare_response(
            message=constants.INVALID_JSON_BODY,
            status=status.HTTP_400_BAD_REQUEST
        )
    documents = data.get("documents", [])
    if len(documents) != 3:
        return prepare_response(
            message=constants.ALL_THREE_DOCUMENTS_REQUIRED,
            status=status.HTTP_400_BAD_REQUEST
        )
    current_user = request.user
    if current_user.user_type != constants.PROPERTY_MANAGER:
        return prepare_response(
            message=constants.ACCESS_DENIED_PROPERTY_MANAGER,
            status=status.HTTP_403_FORBIDDEN
        )
    try:
        pm_details = PropertyManagerCompanyDetails.objects.get(user=current_user)
    except PropertyManagerCompanyDetails.DoesNotExist:
        return prepare_response(
            message=constants.PROPERTY_MANAGER_Details_NOT_FOUND,
            status=status.HTTP_404_NOT_FOUND
        )
    pmc_docs_dict = {}
    for doc in documents:
        base64_data = doc.get("document")
        file_name = doc.get("file_name")
        doc_type = doc.get("type")
        if not base64_data or not file_name or not doc_type:
            return prepare_response(
                message=f"Missing fields in document: {doc}",
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            s3_url = upload_file_to_s3_base64(
                base64_data,
                f"pmc_documents/{current_user.id}/{file_name}"
            ) 
            pmc_docs_dict[doc_type] = s3_url
        except Exception as e:
            return prepare_response(
                message=f"Failed to upload document '{file_name}': {str(e)}",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    pm_details.pmc_documents = pmc_docs_dict
    pm_details.save()
    current_user.is_document_uploaded = True
    current_user.save()
    return prepare_response(
        message=constants.DOCUMENTS_UPLOAD_SUCCESS,
        content={"documents": pmc_docs_dict},
        status=status.HTTP_200_OK
    )





@is_request_authenticated
def property_details_view(request):
    if request.method == "GET":
        try:
            page = int(request.GET.get("page", 1))
            limit = int(request.GET.get("limit", 10))
            search = request.GET.get("search", "").strip()
            property_id = request.GET.get("property_id", "").strip() 

            properties = PropertyDetails.objects.all()

            if property_id:
                properties = properties.filter(id=property_id)
            elif search:
                filters = (
                    Q(property_name__icontains=search)
                    | Q(property_code__icontains=search)
                    | Q(address__icontains=search)
                )
                if search.isdigit():
                    filters |= Q(id__iexact=search)
                properties = properties.filter(filters)

            if not properties.exists():
                return prepare_response(
                    message=constants.DATA_NOT_FOUND,
                    content={
                        "page": page,
                        "total_pages": 0,
                        "total_properties": 0,
                        "data": []
                    },
                    status=status.HTTP_404_NOT_FOUND
                )

            paginator = Paginator(properties, limit)
            page_obj = paginator.get_page(page)

            data = [{
                "id": prop.id,
                "property_code": prop.property_code,
                "property_name": prop.property_name,
                "address": prop.address,
                "area_of_property": prop.area_of_property,
                "no_of_parking": prop.no_of_parking,
                "property_type": prop.property_type,
                "rental_status": prop.rental_status,
            } for prop in page_obj]

            response_data = {
                "page": page,
                "total_pages": paginator.num_pages,
                "total_properties": paginator.count,
                "data": data
            }

            return prepare_response(
                message=constants.PROPERTY_LIST_FETCHED,
                content=response_data,
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return prepare_response(
                message=f"Error fetching property list: {str(e)}",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    elif request.method == "POST":
        try:
            data = json.loads(request.body)
        except Exception:
            return prepare_response(
                message=constants.INVALID_JSON_BODY,
                status=status.HTTP_400_BAD_REQUEST
            )

        current_user = request.user

        if current_user.user_type != constants.OWNER:
            return prepare_response(
                message=constants.ACCESS_DENIED_OWNER_ONLY,
                status=status.HTTP_403_FORBIDDEN
            )
        manager_id = data.get("property_manager_id")
        if not manager_id:
            return prepare_response(
                message="Property Manager ID is required.",
                status=status.HTTP_400_BAD_REQUEST
                  )
        
      

        try:
            manager_details = PropertyManagerCompanyDetails.objects.get(id=manager_id)
            if not manager_details:
                return prepare_response(
                    message=constants.PROPERTY_MANAGER_Details_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )

            with transaction.atomic():
                PropertyDetails.objects.create(
                    property_name=data.get("property_name"),
                    land_dm_no=data.get("land_dm_no"),
                    address=data.get("address"),
                    area_of_property=data.get("area_of_property"),
                    no_of_parking=data.get("no_of_parking"),
                    makani_no=data.get("makani_no"),
                    dewa_no=data.get("dewa_no"),
                    property_type=data.get("property_type", "Apartment"),
                    land_area=data.get("land_area", "1048"),
                    apartment_no=data.get("apartment_no", "48"),
                    bedrooms=data.get("bedrooms", "Select bedroom"),
                    apartment_floor_no=data.get("apartment_floor_no", "3"),
                    balcony=data.get("balcony", "1"),
                    plot_no=data.get("plot_no", "128"),
                    area_unit=data.get("area_unit", "Sq-ft"),
                    land_area_unit=data.get("land_area_unit", "Sq-ft"),
                    property_code=data.get("property_code"),
                    invited_email_id=data.get("invited_email_id"),
                    property_manager=manager_details,
                    is_occupied=data.get("is_occupied", False),
                    rental_status=data.get("rental_status", "Available"),
                    tenancy_start_date=data.get("tenancy_start_date"),
                    tenancy_end_date=data.get("tenancy_end_date"),
                    owner=current_user
                )

            return prepare_response(
                message=constants.PROPERTY_ADDED,
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return prepare_response(
                message=f"Failed to create property: {str(e)}",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    elif request.method == "PUT":
        try:
            property_id = request.GET.get("id")
            if not property_id:
                return prepare_response(
                    message=constants.PROPERTY_ID_REQUIRED,
                    status=status.HTTP_400_BAD_REQUEST
                )

            property_instance = PropertyDetails.objects.filter(id=property_id).first()
            if not property_instance:
                return prepare_response(
                    message=constants.PROPERTY_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )

            try:
                data = json.loads(request.body)
            except json.JSONDecodeError:
                return prepare_response(
                    message=constants.INVALID_JSON_BODY,
                    status=status.HTTP_400_BAD_REQUEST
                )

            allowed_fields = [
                "property_name",
                "address",
                "area_of_property",
                "no_of_parking",
                "property_type",
                "rental_status",
            ]

            for field, value in data.items():
                if field in allowed_fields:
                    setattr(property_instance, field, value)

            property_instance.save()

            updated_data = {
                "id": property_instance.id,
                "property_name": property_instance.property_name,
                "address": property_instance.address,
                "area_of_property": property_instance.area_of_property,
                "no_of_parking": property_instance.no_of_parking,
                "property_type": property_instance.property_type,
                "rental_status": property_instance.rental_status,
            }

            return prepare_response(
                message=constants.PROPERTY_UPDATE_SUCCESS,
                content=updated_data,
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return prepare_response(
                message=f"Error updating property: {str(e)}",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    elif request.method == "DELETE":
        try:
            property_id = request.GET.get("id")
            if not property_id:
                return prepare_response(
                    message=constants.PROPERTY_ID_REQUIRED,
                    status=status.HTTP_400_BAD_REQUEST
                )

            property_instance = PropertyDetails.objects.filter(id=property_id).first()
            if not property_instance:
                return prepare_response(
                    message=constants.PROPERTY_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )

            property_instance.delete()
            return prepare_response(
                message=constants.PROPERTY_DELETED,
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return prepare_response(
                message=f"Error deleting property: {str(e)}",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    else:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )


@is_request_authenticated
def owner_tenants_list(request):
    if request.method != "GET":
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    user = request.user

    if user.user_type != constants.OWNER:
        return prepare_response(
            message=constants.ACCESS_DENIED_OWNER_ONLY, 
            status=status.HTTP_403_FORBIDDEN
        )

    try:
      
        page = int(request.GET.get("page", 1))
        limit = int(request.GET.get("limit", 10))
        search = request.GET.get("search", "").strip()
        tenants_qs = TenantDetails.objects.select_related("property", "user").filter(
            property__owner=user
        )
        if search:
            tenants_qs = tenants_qs.filter(
                Q(full_name__icontains=search) |
                Q(mobile_number__icontains=search) |
                Q(emirate_id__icontains=search)|Q(property__property_name__icontains=search)|Q(property__id__icontains=search)
            )

        if not tenants_qs.exists():
            return prepare_response(
                message="Data not found",
                content={
                    "page": page,
                    "total_pages": 0,
                    "total_tenants": 0,
                    "data": []
                },
                status=status.HTTP_404_NOT_FOUND
            )
        paginator = Paginator(tenants_qs, limit)
        page_obj = paginator.get_page(page)

        data = []
        for t in page_obj:
            data.append({
                "tenant_id": t.id,
                "full_name": t.full_name,
                "mobile_number": t.mobile_number,
                "emirate_id": t.emirate_id,
                "nationality": t.nationality,
                "linked_property_id": t.property.id if t.property else None,
                "linked_property_name": t.property.property_name if t.property else None,
            })

        response_data = {
            "page": page,
            "total_pages": paginator.num_pages,
            "total_tenants": paginator.count,
            "data": data
        }

        return prepare_response(
            message=constants.TENANT_LIST_FETCHED_SUCCES,
            content=response_data,
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return prepare_response(
            message=f"Error fetching tenant list: {str(e)}",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
   


@is_request_authenticated
def property_manager_details_view(request):
 
    if request.method == "GET":
        current_user = request.user
        if current_user.user_type != constants.PROPERTY_MANAGER:
            return prepare_response(
                message=constants.ACCESS_DENIED_PROPERTY_MANAGER,
                status=status.HTTP_403_FORBIDDEN
            )
        try:
            manager = PropertyManagerCompanyDetails.objects.filter(user=current_user).first()
            if not manager:
                return prepare_response(
                    message=constants.PROPERTY_MANAGER_DETAILS_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )

            company_address = ", ".join(filter(None, [
                manager.address_line_1,
                manager.address_line_2,
                manager.city,
                manager.postal_code
            ]))

            pmc_documents = []
            if isinstance(manager.pmc_documents, dict) and manager.pmc_documents:
                for index, (doc_type, doc_url) in enumerate(manager.pmc_documents.items(), start=1):
                    pmc_documents.append({
                        "id": index,
                        "doc_name": doc_type.replace("_", " ").title(),
                        "doc_number": doc_url
                    })

            properties_assigned = []
            if hasattr(manager, 'properties_managed'):
                for property_rec in manager.properties_managed.all():
                    properties_assigned.append({
                        "code": property_rec.property_code or "-",
                        "property_name": property_rec.property_name,
                        "tenant_name": "Tenant Name" if property_rec.is_occupied else "Not Occupied",
                        "agreement_status": "Ongoing" if property_rec.is_occupied else "Available",
                        "dimensions": f"{property_rec.bedrooms} BHK",
                        "documents": f"File.{property_rec.id}"
                    })

            content = {
                "company_code": manager.company_code,
                "company_name": manager.company_name,
                "email": manager.email_address,
                "phone_number": manager.phone_number,
                "company_id": manager.company_id,
                "city": manager.city,
                "locality": manager.locality,
                "postal_code": manager.postal_code,
                "address_line_1": manager.address_line_1,
                "address_line_2": manager.address_line_2,
                "company_address": company_address,
                "pmc_documents": pmc_documents,
                "properties_assigned": properties_assigned
            }
            return prepare_response(
                message=constants.PROPERTY_MANAGER_DETAILS_FETCHED,
                content=content,
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return prepare_response(
                message=f"An error occurred while fetching Property Manager details: {str(e)}",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    elif request.method == "POST":
        try:
            data = json.loads(request.body)
        except Exception:
            return prepare_response(
                message=constants.INVALID_JSON_BODY,
                status=status.HTTP_400_BAD_REQUEST
            )

        current_user = request.user
        if current_user.user_type != constants.PROPERTY_MANAGER:
            return prepare_response(
                message=constants.ACCESS_DENIED_PROPERTY_MANAGER,
                status=status.HTTP_403_FORBIDDEN
            )

        if PropertyManagerCompanyDetails.objects.filter(user=current_user).exists():
            return prepare_response(
                message=constants.PROPERTY_MANAGER_DETAILS_EXISTS,
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with transaction.atomic():
                property_manager_details = PropertyManagerCompanyDetails.objects.create(
                    user=current_user,
                    company_code=data.get("company_code"),
                    company_name=data.get("company_name"),
                    company_id=data.get("company_id"),
                    company_address=data.get("company_address"),
                    city=data.get("city"),
                    locality=data.get("locality"),
                    postal_code=data.get("postal_code"),
                    address_line_1=data.get("address_line_1"),
                    address_line_2=data.get("address_line_2"),
                    company_emirate_id=data.get("company_emirate_id"),
                    trade_license_number=data.get("trade_license_number"),
                    license_issuer=data.get("license_issuer"),
                    rera_license=data.get("rera_license"),
                    phone_number=data.get("phone_number"),
                    email_address=data.get("email_address"),
                    pmc_documents={}
                )
                current_user.is_detail_updated = True
                current_user.save()

            return prepare_response(
                message=constants.PROPERTY_MANAGER_DETAILS_SAVED,
                content={
                    "property_manager_details": {
                        "id": property_manager_details.id,
                        "company_name": property_manager_details.company_name,
                        "company_code": property_manager_details.company_code,
                        "company_id": property_manager_details.company_id,
                        "email_address": property_manager_details.email_address,
                    },
                    "is_detail_updated": current_user.is_detail_updated
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return prepare_response(
                message=f"Failed to save property manager details: {str(e)}",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    elif request.method == "PUT":
        try:
            data = json.loads(request.body)
        except Exception:
            return prepare_response(
                message=constants.INVALID_JSON_BODY,
                status=status.HTTP_400_BAD_REQUEST
            )

        current_user = request.user
        if current_user.user_type != constants.PROPERTY_MANAGER:
            return prepare_response(
                message=constants.ACCESS_DENIED_PROPERTY_MANAGER,
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            pm_details = PropertyManagerCompanyDetails.objects.filter(user=current_user).first()
            if not pm_details:
                return prepare_response(
                    message=constants.PROPERTY_MANAGER_DETAILS_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )

            updatable_fields = [
                "company_code", "company_name", "company_id", "company_address",
                "city", "locality", "postal_code", "address_line_1", "address_line_2",
                "company_emirate_id", "trade_license_number", "license_issuer",
                "rera_license", "phone_number", "email_address"
            ]
            for field in updatable_fields:
                if field in data:
                    setattr(pm_details, field, data.get(field))

            with transaction.atomic():
                pm_details.save()
                current_user.is_detail_updated = True
                current_user.save()

            return prepare_response(
                message=constants.PROPERTY_MANAGER_DETAILS_UPDATED,
                content={
                    "property_manager_details": {
                        "id": pm_details.id,
                        "company_name": pm_details.company_name,
                        "company_code": pm_details.company_code,
                        "company_id": pm_details.company_id,
                        "email_address": pm_details.email_address,
                    },
                    "is_detail_updated": current_user.is_detail_updated
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return prepare_response(
                message=f"Failed to update property manager details: {str(e)}",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    elif request.method == "DELETE":
        try:
            data = json.loads(request.body)
            id = data.get("id")  #  id = request.GET.get("id")

            if not id:
                return prepare_response(
                    message="Property Manager ID is required.",
                    status=status.HTTP_400_BAD_REQUEST
                )

            pm_details = PropertyManagerCompanyDetails.objects.filter(id=id).first()
            if not pm_details:
                return prepare_response(
                    message=constants.PROPERTY_MANAGER_DETAILS_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )

            pm_details.delete()
            return prepare_response(
                message=constants.PROPERTY_MANAGER_DETAILS_DELETED,
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return prepare_response(
                message=f"Error deleting property manager details: {str(e)}",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


    else:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )




# --------------------------------------Property_MAnager_LISt---------------------------------------------/

@is_request_authenticated
def property_manager_list(request):
    try:
        if request.method != "GET":
            return prepare_response(
                message=constants.INVALID_REQUEST_METHOD,
                status=status.HTTP_405_METHOD_NOT_ALLOWED
            )
        page = int(request.GET.get("page", 1))
        limit = int(request.GET.get("limit", 10))
        search = request.GET.get("search", "").strip()
        managers = PropertyManagerCompanyDetails.objects.all().order_by("id")
        if search:
            managers = managers.filter(
                Q(company_code__icontains=search) |
                Q(company_name__icontains=search) |
                Q(company_id__icontains=search)
            )
        paginator = Paginator(managers, limit)
        page_obj = paginator.get_page(page)
        data = []
        for manager in page_obj:
            data.append({
                "id": manager.id,
                "company_code": manager.company_code,
                "company_name": manager.company_name,
                "company_id": manager.company_id,
                "email": manager.email_address,
                "phone_number": manager.phone_number,
                "city": manager.city,
                "locality": manager.locality,
                "postal_code": manager.postal_code,
            })

        response_content = {
            "page": page,
            "total_pages": paginator.num_pages,
            "total_property_managers": paginator.count,
            "data": data
        }
        return prepare_response(
            message=constants.PROPERTY_MANAGER_LIST_FETCHED,
            content=response_content,
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return prepare_response(
            message=f"Error fetching property manager list: {str(e)}",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )












