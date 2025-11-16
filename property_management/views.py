
from django.shortcuts import get_object_or_404
from django.db import IntegrityError, transaction
from property_management.models import OwnerDetails ,PropertyDocuments,TenantDetails , LeasePropertyDetails ,LeaseCommercials,LeaseEjariUpload,LeaseDocumentLayout,OwnerPMCInvitation,PMCOwnerInvitation , PMCTenantInvitation 
from user_service.models import PropertyManagerCompanyDetails ,PropertyDetails ,UserProfile,StaffDetails  ,PropertyCommercial
from utilities.decorator import is_request_authenticated
import json
from utilities.helper_functions import upload_file_to_s3_base64,fetch_s3_file_as_base64, prepare_response, logger,send_ses_email
from utilities import status ,  constants
from django.utils import timezone
from utilities import config
from django.core.paginator import Paginator
from django.db.models import Q
import datetime
from django.forms.models import model_to_dict 
from django.db.models import Count
import uuid
from django.db.models import Prefetch
from django.template.loader import render_to_string
from datetime import timedelta
from django.contrib.auth.hashers import make_password


@is_request_authenticated
def options(request):
    if request.method != "GET":
        return prepare_response(
            content={},
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    option_types = request.GET.get("option_type")
    if not option_types:
        return prepare_response(
            message=constants.QUERY_PARAMETER,
            status=status.HTTP_400_BAD_REQUEST
        )

    option_types = [t.strip() for t in option_types.split(",")]
    content = {}
    user = request.user

    for option_type in option_types:
       
        if option_type == "OWNER_PROPERTIES":

                properties = PropertyDetails.objects.filter(owner=user)
                content["owner_properties"] = [
                    {"id": prop.id, "property_name": prop.property_name} for prop in properties
                ]
        
        elif option_type == "PROPERTY_TYPES":
            content["property_types"] = [{"value": choice[0], "label": choice[1]}for choice in constants.PROPERTY_TYPE_CHOICES]
        elif option_type == "PMC_LIST":
            pmcs = PropertyManagerCompanyDetails.objects.all()
            content["pmc_list"] = [
                 {"id": pmc.id, "company_name": pmc.company_name} for pmc in pmcs
                  ]
        else:
            content[option_type] = [] 

    return prepare_response(
        content=content,
        message=constants.DROPDOWN_DATA_FETCHED_SUCEESS,
        status=status.HTTP_200_OK
    )


@is_request_authenticated
def owner_details_view(request):


    try:
        current_user = request.user

        if current_user.user_type != constants.OWNER:
            return prepare_response(
                message=constants.ACCESS_DENIED_OWNER_ONLY,
                status=status.HTTP_403_FORBIDDEN
            )
        if request.method == "GET":
            owner = OwnerDetails.objects.filter(user=current_user).first()
            if not owner:
                return prepare_response(
                    message=constants.OWNER_DETAILS_NOT_FOUND,
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
                message=constants.OWNER_DETAILS_FETCHED_SUCCESS,
                content=owner_data,
                status=status.HTTP_200_OK
            )

        elif request.method == "POST":
            data = json.loads(request.body)

            if OwnerDetails.objects.filter(user=current_user).exists():
                return prepare_response(
                    message=constants.OWNER_DETAILS_ALREADY_EXISTS,
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
                message=constants.OWNER_DETAILS_SAVE_SUCCESS,
                content={"id": owner.id},
                status=status.HTTP_201_CREATED
            )
        elif request.method == "PUT":
            data = json.loads(request.body)
            owner = OwnerDetails.objects.filter(user=current_user).first()

            if not owner:
                return prepare_response(
                    message=constants.OWNER_DETAILS_NOT_FOUND,
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
                message=constants.OWNER_DETAILs_UPDATE_SUCCESS,
                status=status.HTTP_200_OK
            )
        elif request.method == "DELETE":
            owner = OwnerDetails.objects.filter(user=current_user).first()
            if not owner:
                return prepare_response(
                    message=constants.OWNER_DETAILS_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )

            owner.delete()
            return prepare_response(
                message=constants.OWNER_DELETE_SUCCESS,
                status=status.HTTP_200_OK
            )
        else:
            return prepare_response(
                message=constants.INVALID_REQUEST_METHOD,
                status=status.HTTP_405_METHOD_NOT_ALLOWED
            )

    except Exception as e:
        logger.error(f"Error in owner_details_view: {str(e)}")
        return prepare_response(
            message=f"Something went wrong: {str(e)}",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )




@is_request_authenticated
def owner_details_list_view(request):
    try:    
        current_user = request.user
        if request.method == "GET":
            search = request.GET.get("search")
            owners_qs = OwnerDetails.objects.all().select_related("user")
            page = int(request.GET.get("page", 1))
            limit = int(request.GET.get("limit", 10))

            if search:
                owners_qs = owners_qs.filter(
                    Q(full_name__icontains=search)
                    | Q(mobile_number__icontains=search)
                    | Q(owner_number__icontains=search)
                )

            
            paginator = Paginator(owners_qs, limit)
            try:
                owners_page = paginator.page(page)
            except EmptyPage:
                owners_page = paginator.page(paginator.num_pages)
            owners_data = []

            for owner in owners_page:
                user = owner.user
                properties = PropertyDetails.objects.filter(owner=owner.user).values(
                    "id",
                    "property_name",
                    "address",
                    "rental_status",
                    "property_code"
                )

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
                    "properties": list(properties),
                    "property_count": len(properties),
                    
                    "email": user.email if user else None,
                    "profile_image": user.profile_image if user else None,
                })
            pagination_meta = {
                "current_page": owners_page.number,
                "limit": limit,
                "total_records": paginator.count,
                "total_pages": paginator.num_pages
            }

            
            return prepare_response(
                content={"total": len(owners_data), "owners": owners_data},
                pagination=pagination_meta,
                message=constants.OWNER_DETAILS_FETCHED_SUCCESS,
                status=status.HTTP_200_OK
            )


        elif request.method == "POST":
            try:
                data = json.loads(request.body)
            except:
                return prepare_response(
                    message=constants.INVALID_REQUEST_METHOD,
                    status=status.HTTP_400_BAD_REQUEST
                )

            user_id = data.get("user_id")
            full_name = data.get("full_name")

            if not user_id or not full_name:
                return prepare_response(
                    message=constants.USER_ID_FULL_NAME_REQUIRED,
                    status=status.HTTP_400_BAD_REQUEST
                )

            user = UserProfile.objects.filter(id=user_id).first()
            if not user:
                return prepare_response(
                    message=constants.USER_DOES_NOT_EXIST,
                    status=status.HTTP_404_NOT_FOUND
                )

            owner = OwnerDetails.objects.create(
                user=user,
                full_name=full_name,
                emirate_id=data.get("emirate_id"),
                uae_residence_visa=data.get("uae_residence_visa"),
                trade_license_number=data.get("trade_license_number"),
                owner_number=data.get("owner_number"),
                mobile_number=data.get("mobile_number"),
                manage_manually=data.get("manage_manually", False),
                manage_through_pmc=data.get("manage_through_pmc", False),
            )

            return prepare_response(
                content={"id": owner.id},
                message=constants.OWNER_DETAILS_SAVE_SUCCESS,
                status=status.HTTP_201_CREATED
            )


        elif request.method == "PUT":
            try:
                data = json.loads(request.body)
            except:
                return prepare_response(
                    message=constants.INVALID_REQUEST_METHOD,
                    status=status.HTTP_400_BAD_REQUEST
                )

            owner_id = data.get("id")
            if not owner_id:
                return prepare_response(
                    message=constants.OWNER_ID_IS_REQUIRE,
                    status=status.HTTP_400_BAD_REQUEST
                )

            owner = OwnerDetails.objects.filter(id=owner_id).first()
            if not owner:
                return prepare_response(
                    message=constants.OWNER_DETAILS_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )

            owner.full_name = data.get("full_name", owner.full_name)
            owner.emirate_id = data.get("emirate_id", owner.emirate_id)
            owner.uae_residence_visa = data.get("uae_residence_visa", owner.uae_residence_visa)
            owner.trade_license_number = data.get("trade_license_number", owner.trade_license_number)
            owner.owner_number = data.get("owner_number", owner.owner_number)
            owner.mobile_number = data.get("mobile_number", owner.mobile_number)
            owner.manage_manually = data.get("manage_manually", owner.manage_manually)
            owner.manage_through_pmc = data.get("manage_through_pmc", owner.manage_through_pmc)
            owner.save()

            return prepare_response(
                message=constants.OWNER_DETAILS_SAVE_SUCCESS,
                status=status.HTTP_200_OK
            )


        elif request.method == "DELETE":
            try:
                data = json.loads(request.body)
            except:
                return prepare_response(
                    message=constants.INVALID_REQUEST_METHOD,
                    status=status.HTTP_400_BAD_REQUEST
                )

            owner_id = data.get("id")
            if not owner_id:
                return prepare_response(
                    message=constants.OWNER_ID_IS_REQUIRE,
                    status=status.HTTP_400_BAD_REQUEST
                )

            owner = OwnerDetails.objects.filter(id=owner_id).first()
            if not owner:
                return prepare_response(
                    message=constants.OWNER_DETAILS_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )

      
            PropertyDetails.objects.filter(owner=owner.user).delete()
            owner.delete()

            return prepare_response(
                message=constants.OWNER_DELETE,
                status=status.HTTP_200_OK
            )


        else:
            return prepare_response(
                message=constants.INVALID_REQUEST_METHOD,
                status=status.HTTP_405_METHOD_NOT_ALLOWED
            )

    except Exception as e:
        return prepare_response(
            message=f"Error: {str(e)}",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )











def all_owner_details(request):

    try:

        if request.method == "GET":
            owner_id = request.GET.get("id", None)
            search = request.GET.get("search", "").strip()

            owners = OwnerDetails.objects.select_related("user").all()

       
            if search:
                owners = owners.filter(
                    Q(full_name__icontains=search)
                    | Q(mobile_number__icontains=search)
                    | Q(user__email__icontains=search)
                )

      
            if owner_id:
                owner = owners.filter(id=owner_id).first()
                if not owner:
                    return prepare_response(
                        message=constants.OWNER_DETAILS_NOT_FOUND,
                        status=status.HTTP_404_NOT_FOUND
                    )

                owner_data = model_to_dict(owner)
                owner_data["email"] = owner.user.email if owner.user else None
                owner_data["total_properties"] = PropertyDetails.objects.filter(owner=owner.user).count()
                return prepare_response(
                    content=owner_data,
                    message=constants.OWNER_DETAILS_FETCHED_SUCCESS,
                    status=status.HTTP_200_OK
                )


            data = []
            for o in owners:
                total_properties = PropertyDetails.objects.filter(owner=o.user).count()
                email = o.user.email if o.user else None

                data.append({
                    "id": o.id,
                    "owner_name": o.full_name,
                    "code": f"VC{o.id}21",
                    "contact_number": o.mobile_number,
                    "properties": total_properties,
                    "email": email,
                })

            return prepare_response(
                content=data,
                message=constants.OWNER_DETAILS_FETCHED_SUCCESS,
                status=status.HTTP_200_OK
            )


        elif request.method == "PUT":
            try:
                body = json.loads(request.body)
            except json.JSONDecodeError:
                return prepare_response(
                    message=constants.INVALID_REQUEST_METHOD,
                    status=status.HTTP_400_BAD_REQUEST
                )

            owner_id = body.get("id")
            if not owner_id:
                return prepare_response(
                    message=constants.OWNER_ID_IS_REQUIRE,
                    status=status.HTTP_400_BAD_REQUEST
                )

            owner = OwnerDetails.objects.filter(id=owner_id).first()
            if not owner:
                return prepare_response(
                    message=constants.OWNER_DETAILS_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )

    
            updatable_fields = [
                "full_name",
                "mobile_number",
                "emirate_id",
                "uae_residence_visa",
                "trade_license_number",
                "manage_manually",
                "manage_through_pmc"
            ]
            for field in updatable_fields:
                if field in body:
                    setattr(owner, field, body[field])

            owner.save()
            return prepare_response(
                message=constants.OWNER_DETAILS_SAVE_SUCCESS,
                status=status.HTTP_200_OK
            )


        elif request.method == "DELETE":
            try:
                body = json.loads(request.body)
            except json.JSONDecodeError:
                return prepare_response(
                    message=constants.INVALID_REQUEST_METHOD,
                    status=status.HTTP_400_BAD_REQUEST
                )

            owner_id = body.get("id")
            if not owner_id:
                return prepare_response(
                    message=constants.OWNER_ID_IS_REQUIRE,
                    status=status.HTTP_400_BAD_REQUEST
                )

            owner = OwnerDetails.objects.filter(id=owner_id).first()
            if not owner:
                return prepare_response(
                    message=constants.OWNER_DETAILS_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )

            owner.delete()
            return prepare_response(
                message=constants.OWNER_DELETE_SUCCESS,
                status=status.HTTP_200_OK
            )

        else:
            return prepare_response(
                message=constants.INVALID_REQUEST_METHOD,
                status=status.HTTP_405_METHOD_NOT_ALLOWED
            )

    except Exception as e:
        return prepare_response(
            message=f"Internal Server Error: {str(e)}",
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
    tenant_id = request.GET.get("id")

    def get_tenant():
        """Helper to fetch tenant by query param or current user"""
        if tenant_id:
            return TenantDetails.objects.select_related("property").filter(id=tenant_id).first()
        return TenantDetails.objects.select_related("property").filter(user=user).first()

   
    if request.method == "GET":
        try:
            tenant = get_tenant()
            if not tenant:
                return prepare_response(
                    message=constants.TENANT_DETAILS_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )

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
                "type": tenant.user.user_type if hasattr(tenant, "user") else None,
                "email": tenant.user.email if hasattr(tenant, "user") else None,
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
                "profile_picture": tenant.user.profile_image if hasattr(tenant, "user") else None,
                "documents": filtered_documents,
            }

            return prepare_response(
                content={"tenant_details": tenant_data},
                message=constants.TENANT_DETAILS_FETCHED_SUCCESS,
                status=status.HTTP_200_OK
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

        try:
            email = data.get("email")
            if not email:
                return prepare_response(
                    message="Email is required.",
                    status=status.HTTP_400_BAD_REQUEST
                )
            property_id = data.get("property_id")
            
            user, created = UserProfile.objects.get_or_create(
                email=email,
                defaults={
                    "user_type": constants.TENANT,
                    "is_verified": True,
                    "is_login_allowed": True,
                    "is_detail_updated": True,
                    "profile_image": data.get("profile_image")
                }
            )

            
            existing_tenant = TenantDetails.objects.filter(user=user).first()
            if existing_tenant:
                return prepare_response(
                    message=constants.TENANT_DETAILS_ALREADY_EXISTS,
                    status=status.HTTP_400_BAD_REQUEST
                )

           
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
                emirates_id_file=data.get("emirates_id_file"),
                passport_self_file=data.get("passport_self_file"),
                passport_family_file=data.get("passport_family_file"),
                visa_self_file=data.get("visa_self_file"),
                visa_family_file=data.get("visa_family_file"),
                employment_proof_file=data.get("employment_proof_file"),
                bank_statement_file=data.get("bank_statement_file"),
                address=data.get("address"),
                state=data.get("state"),
                postal_code=data.get("postal_code"),
                property=PropertyDetails.objects.get(id=property_id) if property_id else None,
                
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
                    "user": {
                        "id": user.id,
                        "email": user.email,
                        "profile_image": user.profile_image,
                        "user_type": user.user_type,
                        "is_detail_updated": user.is_detail_updated,
                    },
                },
                message=constants.TENANT_DETAILS_SAVED_SUCCESS,
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            print("Error in POST tenant creation:", e)
            return prepare_response(
                message=f"Failed to save tenant details: {str(e)}",
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

        tenant_details = get_tenant()
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
        except Exception as e:
            return prepare_response(
                message=f"Failed to update tenant details: {str(e)}",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

   
    elif request.method == "DELETE":
        tenant_details = get_tenant()
        if not tenant_details:
            return prepare_response(
                message=constants.TENANT_DETAILS_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            with transaction.atomic():
                tenant_details.delete()
            return prepare_response(
                message=constants.TENANT_DETAILS_DELETED_SUCCESS,
                status=status.HTTP_200_OK
            )
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
                    content={"page": page, "total_pages": 0, "total_properties": 0, "data": []},
                    status=status.HTTP_404_NOT_FOUND,
                )

            paginator = Paginator(properties, limit)
            page_obj = paginator.get_page(page)

            data = []
            for prop in page_obj:

                
                commercial_data = None
                if hasattr(prop, "commercial"):
                    commercial_data = {
                        "rent": prop.commercial.rent,
                        "security_deposit": prop.commercial.security_deposit,
                        "booking_amount": prop.commercial.booking_amount,
                        "maintenance_charges": prop.commercial.maintenance_charges,
                        "cycle": prop.commercial.cycle,
                        "notice_period": prop.commercial.notice_period,
                        "commission_percent": prop.commercial.commission_percent,
                    }

       
                tenants_list = []
                for tenant in prop.tenant_details.all():
                    tenants_list.append({
                        "full_name": tenant.full_name,
                        "email": tenant.user.email if tenant.user else None,
                        "mobile_number": tenant.mobile_number,
                        "emirate_id": tenant.emirate_id,
                        "tenant_number": tenant.tenant_number,
                        "address": tenant.address,
                        "state": tenant.state,
                        "postal_code": tenant.postal_code,
                        "nationality": tenant.nationality,
                        "passport_self": tenant.passport_self,
                        "passport_family_member": tenant.passport_family_member,
                        "passport_expiry": tenant.passport_expiry,
                        "visa_self": tenant.visa_self,
                        "visa_family_member": tenant.visa_family_member,
                        "visa_expiry": tenant.visa_expiry,
                        "employment_proof": tenant.employment_proof,
                        "emirates_id_file": tenant.emirates_id_file,
                        "passport_self_file": tenant.passport_self_file,
                        "passport_family_file": tenant.passport_family_file,
                        "visa_self_file": tenant.visa_self_file,
                        "visa_family_file": tenant.visa_family_file,
                        "employment_proof_file": tenant.employment_proof_file,
                        "bank_statement_file": tenant.bank_statement_file,
                        "lease_property_details_id": tenant.lease_property_details.id if tenant.lease_property_details else None,
                        "city":tenant.city
                    })

            
                owner_data = None
                if prop.owner:
                    if prop.owner.user_type == constants.OWNER:
                        owner_detail_obj = OwnerDetails.objects.filter(user=prop.owner).first()
                        if owner_detail_obj:
                            owner_data = {
                                "id": prop.owner.id,
                                "full_name": owner_detail_obj.full_name,
                                "email": prop.owner.email,
                                "user_type": prop.owner.user_type,
                                "mobile_number": owner_detail_obj.mobile_number,
                                "emirate_id": owner_detail_obj.emirate_id,
                                "trade_license_number": owner_detail_obj.trade_license_number,
                                "address": owner_detail_obj.address,
                                "state": owner_detail_obj.state,
                                "postal_code": owner_detail_obj.postal_code,
                            }
                        else:
                            owner_data = {
                                "id": prop.owner.id,
                                "email": prop.owner.email,
                                "user_type": prop.owner.user_type,
                            }
                        
                    elif prop.owner.user_type == constants.PROPERTY_MANAGER:
                        pmc_obj = PropertyManagerCompanyDetails.objects.filter(user=prop.owner).first()
                        if pmc_obj:
                            owner_data = {
                                "id": prop.owner.id,
                                "company_name": pmc_obj.company_name,
                                "company_code": pmc_obj.company_code,
                                "email": pmc_obj.email_address,
                                "user_type": prop.owner.user_type,
                                "phone_number": pmc_obj.phone_number,
                                "address": pmc_obj.company_address,
                                "city": pmc_obj.city,
                                "locality": pmc_obj.locality,
                                "postal_code": pmc_obj.postal_code,
                                "trade_license_number": pmc_obj.trade_license_number,
                            }
                        else:
                            owner_data = {
                                "id": prop.owner.id,
                                "email": prop.owner.email,
                                "user_type": prop.owner.user_type,
                            }

                
                images_base64 = []
                if prop.images:
                    for img_url in prop.images:
                        img_b64 = fetch_s3_file_as_base64(img_url)
                        if img_b64:
                            images_base64.append(img_b64)

                data.append({
                    "id": prop.id,
                    "property_code": prop.property_code,
                    "property_name": prop.property_name,
                    "address": prop.address,
                    "area_of_property": prop.area_of_property,
                    "no_of_parking": prop.no_of_parking,
                    "property_type": prop.property_type,
                    "rental_status": prop.rental_status,
                    "commercial": commercial_data,
                    "tenants": tenants_list,
                    "owner": owner_data,
                    "images": images_base64,
                })

            return prepare_response(
                message=constants.PROPERTY_LIST_FETCHED,
                content={
                    "page": page,
                    "total_pages": paginator.num_pages,
                    "total_properties": paginator.count,
                    "data": data,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return prepare_response(
                message=f"Error fetching property list: {str(e)}",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )



    elif request.method == "PUT":
        try:
            property_id = request.GET.get("id")
            if not property_id:
                return prepare_response(
                    message=constants.PROPERTY_ID_REQUIRED,
                    status=status.HTTP_400_BAD_REQUEST,
                )

            property_obj = PropertyDetails.objects.filter(id=property_id).first()
            if not property_obj:
                return prepare_response(
                    message=constants.PROPERTY_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND,
                )

            data = json.loads(request.body)

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
                    setattr(property_obj, field, value)

            property_obj.save()

            if data.get("property_type") == "Commercial":
                if hasattr(property_obj, "commercial"):
                    commercial = property_obj.commercial

                    commercial.rent = data.get("rent", commercial.rent)
                    commercial.security_deposit = data.get("security_deposit", commercial.security_deposit)
                    commercial.booking_amount = data.get("booking_amount", commercial.booking_amount)
                    commercial.maintenance_charges = data.get("maintenance_charges", commercial.maintenance_charges)
                    commercial.cycle = data.get("cycle", commercial.cycle)
                    commercial.notice_period = data.get("notice_period", commercial.notice_period)
                    commercial.commission_percent = data.get("commission_percent", commercial.commission_percent)

                    commercial.save()

                else:
                    PropertyCommercial.objects.create(
                        property=property_obj,
                        rent=data.get("rent"),
                        security_deposit=data.get("security_deposit"),
                        booking_amount=data.get("booking_amount"),
                        maintenance_charges=data.get("maintenance_charges"),
                        cycle=data.get("cycle"),
                        notice_period=data.get("notice_period"),
                        commission_percent=data.get("commission_percent"),
                    )

            return prepare_response(
                message=constants.PROPERTY_UPDATE_SUCCESS,
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return prepare_response(
                message=f"Error updating property: {str(e)}",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    elif request.method == "DELETE":
        try:
            property_id = request.GET.get("id")
            if not property_id:
                return prepare_response(
                    message=constants.PROPERTY_ID_REQUIRED,
                    status=status.HTTP_400_BAD_REQUEST,
                )

            property_obj = PropertyDetails.objects.filter(id=property_id).first()
            if not property_obj:
                return prepare_response(
                    message=constants.PROPERTY_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND,
                )

            property_obj.delete()

            return prepare_response(
                message=constants.PROPERTY_DELETED,
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return prepare_response(
                message=f"Error deleting property: {str(e)}",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    else:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )



@is_request_authenticated
def create_property_basic(request):
    if request.method != "POST":
        return prepare_response(message=constants.INVALID_REQUEST, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    try:
        data = json.loads(request.body)
        user = request.user   

  
        property_name = data.get("property_name")
        land_dm_no = data.get("land_dm_no")
        address = data.get("address")
        area_of_property = data.get("area_of_property")
        no_of_parking = data.get("no_of_parking")
        makani_no = data.get("makani_no")
        dewa_no = data.get("dewa_no")
        property_type = data.get("property_type")
        land_area = data.get("land_area")
        apartment_no = data.get("apartment_no")
        bedrooms = data.get("bedrooms")
        apartment_floor_no = data.get("apartment_floor_no")
        balcony = data.get("balcony")
        plot_no = data.get("plot_no")
        area_unit = data.get("area_unit")
        land_area_unit = data.get("land_area_unit")
        no_of_floors = data.get("no_of_floors")
        property_code = data.get("property_code")
        invited_email_id = data.get("invited_email_id")
      

        if user.user_type == "PROPERTY_MANAGER":
            owner = user

 
            property_manager = PropertyManagerCompanyDetails.objects.filter(user=user).first()
            if not property_manager:
                return prepare_response(message= constants.PROPERTY_MANAGER_DETAILS_NOT_FOUND, status=status.HTTP_400_BAD_REQUEST)

        elif user.user_type == "OWNER":
            owner = user 


            pmc_id = data.get("property_manager_id")
            if pmc_id:
                property_manager = PropertyManagerCompanyDetails.objects.filter(id=pmc_id).first()
            else:
                property_manager = None

        else:
            return prepare_response( message=constants.ONLY_OWNER_AND_PMC, status=status.HTTP_403_FORBIDDEN)

      

        new_property = PropertyDetails.objects.create(
            property_name=property_name,
            land_dm_no=land_dm_no,
            address=address,
            area_of_property=area_of_property,
            no_of_parking=no_of_parking,
            makani_no=makani_no,
            dewa_no=dewa_no,
            property_type=property_type,
            land_area=land_area,
            apartment_no=apartment_no,
            bedrooms=bedrooms,
            apartment_floor_no=apartment_floor_no,
            balcony=balcony,
            plot_no=plot_no,
            area_unit=area_unit,
            land_area_unit=land_area_unit,
            no_of_floors=no_of_floors,
            property_code=property_code,
            invited_email_id=invited_email_id,
            owner=owner,
            property_manager=property_manager,

        )

        return prepare_response(
            message=constants.PROPERTY_ADDED,
            content= {"property_id":new_property.id},
         status=status.HTTP_201_CREATED  ) 

    except Exception as e:
        return prepare_response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)









@is_request_authenticated
def add_commercial_details(request):
    if request.method != "POST":
        return prepare_response(message=constants.INVALID_REQUEST, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    try:
        data = json.loads(request.body)
        property_id = data.get("property_id")

        if not property_id:
            return prepare_response(message=constants.PROPERTY_ID_REQUIRED, status=status.HTTP_400_BAD_REQUEST)

        property_obj = PropertyDetails.objects.filter(id=property_id).first()
        if not property_obj:
            return prepare_response(constants.PROPERTY_MANAGER_Details_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)

        commercial_obj, created = PropertyCommercial.objects.update_or_create(
            property=property_obj,
            defaults={
                "rent": data.get("rent"),
                "security_deposit": data.get("security_deposit"),
                "booking_amount": data.get("booking_amount"),
                "maintenance_charges": data.get("maintenance_charges"),
                "cycle": data.get("cycle"),
                "notice_period": data.get("notice_period"),
                "commission_percent": data.get("commission_percent"),
            }
        )

        return prepare_response(
            message=constants.COMMERCIAL_DETAILS_SAVE,
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return prepare_response(
            message=f"Error: {str(e)}",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



@is_request_authenticated
def upload_property_images(request):
    if request.method != "POST":
        return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    try:
        data = json.loads(request.body)
        property_id = data.get("property_id")
        images = data.get("images", [])

        if not property_id:
            return prepare_response(message=constants.PROPERTY_ID_REQUIRED, status=status.HTTP_400_BAD_REQUEST)

        property_obj = PropertyDetails.objects.filter(id=property_id).first()
        if not property_obj:
            return prepare_response(message=constants.PROPERTY_MANAGER_Details_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)

        uploaded_urls = []
        for idx, img in enumerate(images):
            base64_data = img.get("data")
            file_name = img.get("file_name", f"property_{property_id}_{idx}.jpg")

            if base64_data:
                url = upload_file_to_s3_base64(base64_data, f"property_images/{property_id}/{file_name}")
                uploaded_urls.append(url)

        
        property_obj.images = (property_obj.images or []) + uploaded_urls
        property_obj.save()

        return prepare_response(
            message=constants.IMAGE_UPLOADED_SUCCESS,
            content={"images": uploaded_urls},
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return prepare_response(
            message=f"Error: {str(e)}",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )








@is_request_authenticated
def owner_property_tenants_view(request):
  
    if request.method != "GET":
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    user = request.user

    # if user.user_type != constants.OWNER:
    #     return prepare_response(
    #         message=constants.ACCESS_DENIED_OWNER_ONLY,
    #         status=status.HTTP_403_FORBIDDEN
    #     )

    try:
     
        page = int(request.GET.get("page", 1))
        limit = int(request.GET.get("limit", 10))
        search = request.GET.get("search", "").strip()

       
        properties_qs = PropertyDetails.objects.select_related(
            "owner", "property_manager", "staff"
        ).filter(owner=user)

        
        if search:
            properties_qs = properties_qs.filter(
                Q(property_name__icontains=search) |
                Q(property_code__icontains=search) |
                Q(address__icontains=search)
            )

     
        if not properties_qs.exists():
            return prepare_response(
                message="No properties found for this owner.",
                content={"data": [], "page": page, "total_pages": 0, "total_records": 0},
                status=status.HTTP_404_NOT_FOUND
            )

        
        paginator = Paginator(properties_qs, limit)
        page_obj = paginator.get_page(page)

        response_data = []
        for prop in page_obj:
            tenant = TenantDetails.objects.filter(property=prop).first()

            response_data.append({
                "property_id": prop.id,
                "property_code": prop.property_code,
                "property_name": prop.property_name,
                "tenant_name": tenant.full_name if tenant else "N/A",
                "tenant_id": tenant.id if tenant else None,
                "tenancy_status": "Occupied" if prop.is_occupied else "Vacant",
                "agreement_status": True if tenant and tenant.lease_property_details else False,
                "owner_id": prop.owner.id if prop.owner else None,
                "property_manager_name": prop.property_manager.company_name if prop.property_manager else None,
                # "staff_assigned": prop.staff.user.full_name if prop.staff else None,
            })
        content = {
            "page": page,
            "total_pages": paginator.num_pages,
            "total_records": paginator.count,
            "data": response_data
        }

        return prepare_response(
            message=constants.OWNER_PROPERTIES_WITH_TENANTS,
            content=content,
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return prepare_response(
            message=f"Error fetching owner property tenant list: {str(e)}",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


    



@is_request_authenticated
def tenant_list_view(request):
    
    current_user = request.user


    if request.method == "GET":
        try:
            search_query = request.GET.get("search", "").strip()
            page = int(request.GET.get("page", 1))
            limit = int(request.GET.get("limit", 10))
            tenants = TenantDetails.objects.all().select_related("property", "lease_property_details")
            if search_query:
                tenants = tenants.filter(full_name__icontains=search_query)
            total_count = tenants.count()
            start = (page - 1) * limit
            end = start + limit
            tenants = tenants[start:end]

            

            tenant_list = []
            for tenant in tenants:
                tenant_list.append({
                    "id": tenant.id,
                    "full_name": tenant.full_name,
                    "tenant_number": tenant.tenant_number,
                    "mobile_number": tenant.mobile_number,
                    "property_assigned": tenant.property.property_name if tenant.property else None,
                    "rental_agreement":"None"
                    # "rental_agreement": (
                    #     tenant.lease_property_details.lease_file
                    #     if tenant.lease_property_details else None
                    # ),
                })
            
            pagination_info = {
                "current_page": page,
                "limit": limit,
                "total_records": total_count,
                "total_pages": (total_count + limit - 1) // limit,  
            }

            return prepare_response(
                content={"tenants": tenant_list},
                pagination=pagination_info,
                message=constants.TENANT_DETAILS_FETCHED_SUCCESS,
                status=status.HTTP_200_OK,
                
            )

        except Exception as e:
            print("GET Error:", e)
            return prepare_response(
                message=constants.TENANT_DETAILS_NOT_FOUND,
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


    elif request.method == "DELETE":
        try:
            tenant_id = request.GET.get("id")
            if not tenant_id:
                return prepare_response(
                    message=constants.TENANT_ID_REQUIRE,
                    status=status.HTTP_400_BAD_REQUEST
                )

            tenant = TenantDetails.objects.filter(id=tenant_id).first()
            if not tenant:
                return prepare_response(
                    message=constants.TENANT_DETAILS_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )

            if current_user.user_type not in ["OWNER", "PROPERTY_MANAGER"]:
                return prepare_response(
                    message=constants.PERMISSSION_DENIED,
                    status=status.HTTP_403_FORBIDDEN
                )

            tenant.delete()

            return prepare_response(
                message=constants.TENANT_DELETED_SUCCESS,
                status=status.HTTP_200_OK
            )

        except Exception as e:
            print("DELETE Error:", e)
            return prepare_response(
                message=constants.ERROR_DELETING_SUCCESS,
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
 
    else:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
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
            id = data.get("id") 

            if not id:
                return prepare_response(
                    message=constants.PROPERTY_MANAGER_ID_REQUIRE,
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
            property_count = PropertyDetails.objects.filter(
                property_manager=manager
            ).count()
            total_properties = PropertyDetails.objects.filter(property_manager=manager).count()
            occupied = PropertyDetails.objects.filter(property_manager=manager, is_occupied=True).count()
            vacant = total_properties - occupied
            tenancy_ratio = f"{occupied}:{vacant}"
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
                "property_handling": property_count,  
                "tenancy_ratio":tenancy_ratio
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



@is_request_authenticated
def staff_view(request):
    try:
      
        if request.method == "POST":
            body = json.loads(request.body)

            staff_name = body.get("staff_name")
            email = body.get("email")
            phone_number = body.get("phone_number")
            staff_role_id = body.get("staff_role_id")
            password = body.get("password")
            confirm_password = body.get("confirm_password")
            assign_property = body.get("assign_property")
            assigned_property_ids = body.get("assigned_property_ids", [])

         
            if not all([staff_name, email, phone_number, staff_role_id, password, confirm_password]):
                return prepare_response(
                    message=constants.ALL_FIELD_REQUIRED,
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

            
            with transaction.atomic():
                user = UserProfile.objects.create(
                    email=email,
                    hashed_password=make_password(password),
                    user_type=constants.STAFF,
                    is_verified=True,
                    is_login_allowed=True
                )

                
                staff_id = f"STF-{user.id:04d}"

                staff = StaffDetails.objects.create(
                    staff_name=staff_name,
                    phone_number=phone_number,
                    staff_id=staff_id,
                    assign_property=assign_property,
                    user=user,
                    staff_role_id=staff_role_id,
                )

                if assigned_property_ids:
                    staff.assigned_properties.set(assigned_property_ids)

            
            data = {
                "id": staff.id,
                "staff_name": staff.staff_name,
                "staff_id": staff.staff_id,
                "phone_number": staff.phone_number,
                "user_email": user.email,
                "staff_role": {
                    "id": staff.staff_role.id,
                    "name": staff.staff_role.name,
                },
            }

            return prepare_response(
                content=data,
                message=constants.STAFF_CREATION_SUCCESS,
                status=status.HTTP_201_CREATED
            )

      
        elif request.method == "GET":
            staff_id = request.GET.get("id")
            search = request.GET.get("search", "")
            page = int(request.GET.get("page", 1))
            limit = int(request.GET.get("limit", 10))

            if staff_id:
                try:
                    staff = StaffDetails.objects.select_related("staff_role", "user").prefetch_related("assigned_properties").get(id=staff_id)
                    assigned_props = staff.assigned_properties.all()
                    total_assigned = assigned_props.count()

                    data = {
                        "id": staff.id,
                        "staff_name": staff.staff_name,
                        "staff_id": staff.staff_id,
                        "phone_number": staff.phone_number,
                        "assign_property": staff.assign_property,
                        "staff_role": {
                            "id": staff.staff_role.id,
                            "name": staff.staff_role.name,
                        } if staff.staff_role else None,
                        "user_email": staff.user.email if staff.user else None,
                        "total_assigned_properties": total_assigned,
                        "assigned_properties": [
                            {
                                "id": prop.id,
                                "property_name": prop.property_name,
                                "property_code": prop.property_code
                            }
                            for prop in assigned_props
                        ]
                    }

                    return prepare_response(
                        content=data,
                        message=constants.STAFF_LIST_FETCHED_SUCCESS,
                        status=status.HTTP_200_OK
                    )
                except StaffDetails.DoesNotExist:
                    return prepare_response(
                        message="Staff not found",
                        status=status.HTTP_404_NOT_FOUND
                    )

            staff_qs = StaffDetails.objects.select_related("staff_role", "user").prefetch_related("assigned_properties").all()

            if search:
                staff_qs = staff_qs.filter(
                    Q(staff_name__icontains=search)
                    | Q(staff_id__icontains=search)
                    | Q(phone_number__icontains=search)
                )

            paginator = Paginator(staff_qs, limit)
            page_obj = paginator.get_page(page)

            data = []
            for staff in page_obj:
                total_assigned = staff.assigned_properties.count()
                data.append({
                    "id": staff.id,
                    "staff_name": staff.staff_name,
                    "staff_id": staff.staff_id,
                    "phone_number": staff.phone_number,
                    "assign_property": staff.assign_property,
                    "staff_role": {
                        "id": staff.staff_role.id,
                        "name": staff.staff_role.name,
                    } if staff.staff_role else None,
                    "user_email": staff.user.email if staff.user else None,
                    "total_assigned_properties": total_assigned,
                })

            return prepare_response(
                content=data,
                message=constants.STAFF_LIST_FETCHED_SUCCESS,
                status=status.HTTP_200_OK,
                paginator=page_obj,
                total_records=paginator.count
            )

       
        elif request.method == "PUT":
            staff_id = request.GET.get("id")
            if not staff_id:
                return prepare_response(message="Staff ID is required in query params", status=status.HTTP_400_BAD_REQUEST)

            try:
                staff = StaffDetails.objects.get(id=staff_id)
            except StaffDetails.DoesNotExist:
                return prepare_response(message="Staff not found", status=status.HTTP_404_NOT_FOUND)

            body = json.loads(request.body)

            staff.staff_name = body.get("staff_name", staff.staff_name)
            staff.phone_number = body.get("phone_number", staff.phone_number)
            staff.assign_property = body.get("assign_property", staff.assign_property)

            if "staff_role_id" in body:
                staff.staff_role_id = body["staff_role_id"]

            staff.save()

            return prepare_response(
                message=constants.STAFF_DETAILS_UPDATED_SUCCESS,
                status=status.HTTP_200_OK
            )

       
        elif request.method == "DELETE":
            staff_id = request.GET.get("id")
            if not staff_id:
                return prepare_response(message="Staff ID is required in query params", status=status.HTTP_400_BAD_REQUEST)

            try:
                staff = StaffDetails.objects.get(id=staff_id)
                staff.delete()
                return prepare_response(
                    message=constants.STAFF_DELETED_SUCCESS,
                    status=status.HTTP_200_OK
                )
            except StaffDetails.DoesNotExist:
                return prepare_response(
                    message="Staff not found",
                    status=status.HTTP_404_NOT_FOUND
                )

    except Exception as e:
        return prepare_response(
            message=str(e),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



    



 
@is_request_authenticated
def pmc_dashboard_view(request):
    current_user = request.user

    
    if current_user.user_type != constants.PROPERTY_MANAGER:
        return prepare_response(
            message=constants.ONLY_PROPERTY_MANAGER_CAN_VIEW,
            status=status.HTTP_403_FORBIDDEN
        )

    try:

        pmc = PropertyManagerCompanyDetails.objects.filter(user=current_user).first()
        if not pmc:
            return prepare_response(
                message=constants.PROPERTY_MANAGER_Details_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        pmc_data = {
            "company_name": pmc.company_name,
            "company_code": pmc.company_code,
            "company_id": pmc.company_id,
            "phone_number": pmc.phone_number,
            "email_address": pmc.email_address,
            "city": pmc.city or "-",
            "locality": pmc.locality or "-",
            "postal_code": pmc.postal_code or "-",
            "address_line_1": pmc.address_line_1 or "-",
            "address_line_2": pmc.address_line_2 or "-",
            "documents": [
                {"title": k, "file": v} for k, v in (pmc.pmc_documents or {}).items()
            ],
        }

        properties = PropertyDetails.objects.filter(property_manager=pmc)
        property_list = []

        for prop in properties:
            tenant = TenantDetails.objects.filter(property=prop).first()
            tenant_name = tenant.full_name if tenant else "N/A"
            tenancy_status = "Occupied" if prop.is_occupied else "Vacant"
            dimension = prop.bedrooms or "-" 
            document = PropertyDocuments.objects.filter(property=prop).first() if "PropertyDocuments" in globals() else None
            document_title = document.document_title if document else "-"

            property_list.append({
                "code": prop.property_code or "-",
                "property_name": prop.property_name,
                "tenant_name": tenant_name,
                "tenancy_status": tenancy_status,
                "dimension": dimension,
                "document": document_title,
            })


        response_data = {
            "pmc_details": pmc_data,
            "properties_assigned": property_list,
            "total_properties": len(property_list),
        }

        return prepare_response(response_data, status=status.HTTP_200_OK)

    except Exception as e:
        return prepare_response(
            message=f"Error fetching PMC dashboard data: {str(e)}",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )








def pmc_owner_view_list(request):
    try:
 
        if request.method == "GET":
            pmc_id = request.GET.get("id", None)
            search = request.GET.get("search", "").strip()

            pmc_qs = PropertyManagerCompanyDetails.objects.all()

       
            if search:
                pmc_qs = pmc_qs.filter(
                    Q(company_name__icontains=search)
                    | Q(company_code__icontains=search)
                    | Q(company_address__icontains=search)
                )

          
            if pmc_id:
                pmc = pmc_qs.filter(id=pmc_id).first()
                if not pmc:
                    return prepare_response(
                        message=constants.PROPERTY_MANAGER_DETAILS_NOT_FOUND,
                        status=status.HTTP_404_NOT_FOUND
                    )

                pmc_data = model_to_dict(pmc)
                pmc_data["property_handling"] = PropertyDetails.objects.filter(property_manager=pmc).count()
                return prepare_response(
                    content=pmc_data,
                    message=constants.PROPERTY_MANAGER_DETAILS_FETCHED,
                    status=status.HTTP_200_OK
                )

            
            data = []
            for p in pmc_qs:
                total_properties = PropertyDetails.objects.filter(property_manager=p).count()
                total_properties = PropertyDetails.objects.filter(property_manager=p).count()
                occupied = PropertyDetails.objects.filter(property_manager=p, is_occupied=True).count()
                vacant = total_properties - occupied
                tenancy_ratio = f"{occupied}:{vacant}"
                data.append({
                    "id": p.id,
                    "code": p.company_code,
                    "pmc_name": p.company_name,
                    "property_handling": f"{total_properties} Property",
                    "tenancy_ratio": tenancy_ratio,
                    "address": p.company_address,
                })

            return prepare_response(
                content=data,
                message=constants.PROPERTY_MANAGER_DETAILS_FETCHED,
                status=status.HTTP_200_OK
            )


        elif request.method == "PUT":
            try:
                body = json.loads(request.body)
            except json.JSONDecodeError:
                return prepare_response(
                    message=constants.INVALID_JSON_BODY,
                    status=status.HTTP_400_BAD_REQUEST
                )

            pmc_id = request.GET.get("id")

            if not pmc_id:
                return prepare_response(
                    message=constants.PROPERTY_MANAGER_ID_REQUIRE,
                    status=status.HTTP_400_BAD_REQUEST
                )

            pmc = PropertyManagerCompanyDetails.objects.filter(id=pmc_id).first()
            if not pmc:
                return prepare_response(
                    message=constants.PROPERTY_MANAGER_DETAILS_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )


            updatable_fields = [
                "company_name",
                "company_address",
                "phone_number",
                "email_address",
                "trade_license_number",
                "rera_license",
            ]
            for field in updatable_fields:
                if field in body:
                    setattr(pmc, field, body[field])

            pmc.save()
            return prepare_response(
                message=constants.PROPERTY_MANAGER_DETAILS_SAVED,
                status=status.HTTP_200_OK
            )

        elif request.method == "DELETE":


            pmc_id = request.GET.get("id")

            if not pmc_id:
                return prepare_response(
                    message=constants.PROPERTY_MANAGER_ID_REQUIRE,
                    status=status.HTTP_400_BAD_REQUEST
                )

            pmc = PropertyManagerCompanyDetails.objects.filter(id=pmc_id).first()
            if not pmc:
                return prepare_response(
                    message=constants.PROPERTY_MANAGER_DETAILS_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )

            pmc.delete()
            return prepare_response(
                message=constants.PROPERTY_MANAGER_DETAILS_DELETE_SUCCESS,
                status=status.HTTP_200_OK
            )

        else:
            return prepare_response(
                message=constants.INVALID_REQUEST_METHOD,
                status=status.HTTP_405_METHOD_NOT_ALLOWED
            )

    except Exception as e:
        return prepare_response(
            message=f"Internal Server Error: {str(e)}",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


from django.core.paginator import Paginator, EmptyPage

@is_request_authenticated
def property_details_list_view(request):
    if request.method == "GET":
        try:
            search = request.GET.get("search", "").strip()

            page = int(request.GET.get("page", 1))       
            limit = int(request.GET.get("limit", 10))     

            
            properties = PropertyDetails.objects.select_related(
                "owner",
                "property_manager",
                "staff"
            ).prefetch_related(
                Prefetch("tenant_details", queryset=TenantDetails.objects.all())
            )

           
            if search:
                properties = properties.filter(
                    Q(property_name__icontains=search) |
                    Q(owner__owner_details__full_name__icontains=search) |
                    Q(tenant_details__full_name__icontains=search)
                ).distinct()

   
            paginator = Paginator(properties, limit)
            try:
                properties_page = paginator.page(page)
            except EmptyPage:
                properties_page = paginator.page(paginator.num_pages)

            data = []

      
            for prop in properties_page:
                tenants = prop.tenant_details.all()
                tenant_data = [
                    {
                        "tenant_name": tenant.full_name,
                        "mobile_number": tenant.mobile_number,
                        "tenant_number": tenant.tenant_number,
                        "nationality": tenant.nationality,
                    }
                    for tenant in tenants
                ] if tenants.exists() else []

                owner_details = OwnerDetails.objects.filter(user=prop.owner).first()
                owner_info = {
                    "owner_name": owner_details.full_name if owner_details else "N/A",
                    "owner_mobile": owner_details.mobile_number if owner_details else "N/A",
                    "trade_license": owner_details.trade_license_number if owner_details else "N/A",
                }

                pmc = prop.property_manager
                pmc_info = {
                    "company_name": pmc.company_name if pmc else "N/A",
                    "company_code": pmc.company_code if pmc else "N/A",
                    "rera_license": pmc.rera_license if pmc else "N/A",
                    "phone_number": pmc.phone_number if pmc else "N/A",
                }

                rental_status_display = (
                    "Not Available" if prop.is_occupied else prop.rental_status
                )

                data.append({
                    "id": prop.id,
                    "property_name": prop.property_name,
                    "address": prop.address,
                    "property_code": prop.property_code,
                    "property_type": prop.property_type,
                    "area_of_property": prop.area_of_property,
                    "no_of_parking": prop.no_of_parking,
                    "bedrooms": prop.bedrooms,
                    "balcony": prop.balcony,
                    "plot_no": prop.plot_no,
                    "is_occupied": prop.is_occupied,
                    "area_unit": prop.area_unit,
                    "rental_status": rental_status_display,
                    "tenants": tenant_data,
                    "owner_info": owner_info,
                    "pmc_info": pmc_info,
                })


            pagination_meta = {
              
                "current_page": properties_page.number,
                "limit": limit,
                "total_records": paginator.count,
                "total_pages": paginator.num_pages
                
            }

            return prepare_response(
                content=data,
                message=constants.PROPERTY_LIST_FETCHED,
                pagination=pagination_meta,
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return prepare_response(
                message=f"Error fetching properties: {str(e)}",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    else:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )





@is_request_authenticated
def invite_owner_pmc(request):
    if request.method == "POST":
        try:
            current_user = request.user

           
            if current_user.user_type != constants.OWNER:
                return prepare_response(
                    message=constants.ACCESS_DENIED_OWNER,
                    status=status.HTTP_403_FORBIDDEN
                )

            data = json.loads(request.body)
            email = data.get("email")

            if not email:
                return prepare_response(
                    message=constants.EMAIL_REQUIRED,
                    status=status.HTTP_400_BAD_REQUEST
                )

        
            if OwnerPMCInvitation.objects.filter(email=email, invited_by=current_user).exists():
                return prepare_response(
                    message=constants.PMC_ALREADY_INVITED,
                    status=status.HTTP_400_BAD_REQUEST
                )

      
            token = str(uuid.uuid4())
            invitation = OwnerPMCInvitation.objects.create(
                email=email,
                invited_by=current_user,
                token=token,
                status=constants.PENDING if hasattr(constants, 'PENDING') else "pending",
            )

         
            invite_link = f"https://yourfrontend.com/pmc/invite/accept?token={token}"
            subject = "Invitation to Join Property Management Portal"
            body_text = f"You have been invited to join as a PMC by {current_user.email}. Use this link: {invite_link}"

   
            body_html = render_to_string(
                "email_templates/invite_owner_pmc.html",
                {
                    "inviter_email": current_user.email,
                    "invite_link": invite_link,
                }
            )

            try:
                send_ses_email(email, subject, body_text, body_html)
            except Exception as e:
                print(f"SES Email Error: {e}")
                return prepare_response(
                    message=constants.INVITATION_CREATED_EMAIL_FAILED,
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            return prepare_response(
                content={
                    "email": invitation.email,
                    "token": invitation.token,
                    "status": invitation.status,
                },
                message=constants.PMC_INVITATION_SENT_SUCCESS,
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            print(f"Error in invite_owner_pmc: {e}")
            return prepare_response(
                message=f"Error sending invitation: {str(e)}",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    else:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )



@is_request_authenticated
def invite_pmc_to_owner(request):
    if request.method == "POST":
        try:
            current_user = request.user

            if current_user.user_type != constants.PROPERTY_MANAGER:
                return prepare_response(
                    message=constants.ACCESS_DENIED_PMC,
                    status=status.HTTP_403_FORBIDDEN
                )

            data = json.loads(request.body)
            email = data.get("email")

            if not email:
                return prepare_response(
                    message=constants.EMAIL_REQUIRED,
                    status=status.HTTP_400_BAD_REQUEST
                )

            
            if PMCOwnerInvitation.objects.filter(email=email, invited_by=current_user).exists():
                return prepare_response(
                    message=constants.OWNER_ALREADY_INVITED,
                    status=status.HTTP_400_BAD_REQUEST
                )

          
            token = str(uuid.uuid4())
            invitation = PMCOwnerInvitation.objects.create(
                email=email,
                invited_by=current_user,
                token=token,
                status=constants.PENDING if hasattr(constants, "PENDING") else "pending",
            )

            invite_link = f"https://yourfrontend.com/owner/invite/accept?token={token}"
            subject = "Invitation to Join Property Management Portal"
            body_text = f"You have been invited by {current_user.email} to join as an Owner. Use this link: {invite_link}"

          
            body_html = render_to_string(
                "email_templates/invite_pmc_to_owner.html",
                {
                    "inviter_email": current_user.email,
                    "invite_link": invite_link,
                }
            )

 
            try:
                send_ses_email(email, subject, body_text, body_html)
            except Exception as e:
                print(f"SES Email Error: {e}")
                return prepare_response(
                    message=constants.INVITATION_CREATED_EMAIL_FAILED,
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            return prepare_response(
                content={
                    "email": invitation.email,
                    "token": invitation.token,
                    "status": invitation.status,
                },
                message=constants.OWNER_INVITATION_SENT_SUCCESS,
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            print(f"Error in invite_pmc_to_owner_view: {e}")
            return prepare_response(
                message=f"Error sending invitation: {str(e)}",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    else:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )



@is_request_authenticated
def invite_tenant_by_pmc(request):
    if request.method == "POST":
        try:
            current_user = request.user
            if current_user.user_type != constants.PROPERTY_MANAGER:
                return prepare_response(
                    message=constants.ACCESS_DENIED_TENANT_PMC,
                    status=status.HTTP_403_FORBIDDEN
                )
            data = json.loads(request.body)
            email = data.get("email")

            if not email:
                return prepare_response(
                    message=constants.EMAIL_REQUIRED,
                    status=status.HTTP_400_BAD_REQUEST
                )
            if PMCTenantInvitation.objects.filter(email=email, invited_by=current_user).exists():
                return prepare_response(
                    message=constants.TENANT_ALREADY_INVITED,
                    status=status.HTTP_400_BAD_REQUEST
                )
            token = str(uuid.uuid4())
            invitation = PMCTenantInvitation.objects.create(
                email=email,
                invited_by=current_user,
                token=token,
                status=constants.PENDING if hasattr(constants, "PENDING") else "pending",
            )
            invite_link = f"https://yourfrontend.com/tenant/invite/accept?token={token}"
            subject = "Invitation to Join Property Management Portal"
            body_text = (
                f"You have been invited by {current_user.email} to join as a Tenant. "
                f"Use this link to accept: {invite_link}"
            )
           
            body_html = render_to_string(
                "email_templates/invite_tenant_by_pmc.html",
                {
                    "inviter_email": current_user.email,
                    "invite_link": invite_link,
                }
            )
            try:
                send_ses_email(email, subject, body_text, body_html)
            except Exception as e:
                print(f"SES Email Error: {e}")
                return prepare_response(
                    message=constants.INVITATION_CREATED_EMAIL_FAILED,
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            return prepare_response(
                content={
                    "email": invitation.email,
                    "token": invitation.token,
                    "status": invitation.status,
                },
                message=constants.TENANT_INVITATION_SENT_SUCCESS,
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            print(f"Error in invite_tenant_by_pmc: {e}")
            return prepare_response(
                message=f"Error sending invitation: {str(e)}",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    else:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )



@is_request_authenticated
def assign_property_by_owner(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            property_id = data.get('property_id')
            pmc_id = data.get('pmc_id')
        except (ValueError, KeyError):
            return prepare_response(message=constants.INVALID_INPUT_FORMAT, status=status.HTTP_400_BAD_REQUEST)
        current_user = request.user
        if current_user.user_type != constants.OWNER:
            return prepare_response(message=constants.FORBIDDEN_ASSIGN_PROPERTY , status=status.HTTP_403_FORBIDDEN)

        property_to_assign = PropertyDetails.objects.filter(
            id=property_id,
            owner=current_user  
        ).first()
        if not property_to_assign:
            return prepare_response(message=constants.PROPERTY_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        property_to_assign.property_manager_id = pmc_id
        property_to_assign.save()
        return prepare_response(message=constants.PROPERTY_ASSIGNED_SUCCESS, status=status.HTTP_200_OK)
    return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)



@is_request_authenticated
def property_statistics(request):
    if request.method != "GET":
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        user = request.user
        user_type = user.user_type
        now = timezone.now()
        properties = PropertyDetails.objects.filter(owner=user)
        renewal_window = now + timedelta(days=30)
        lease_queryset = LeasePropertyDetails.objects.filter( 
            lease_property__in=properties
            )
        active_count = lease_queryset.filter(
            lease_start_date__lte=now,
            lease_end_date__gte=now
            ).count()
        upcoming_renewals_count = lease_queryset.filter(
            lease_end_date__gt=now,
            lease_end_date__lte=renewal_window
             ).count()
        negotiations_count = lease_queryset.filter(
            lease_end_date__lt=now
            ).count()

        total_properties = properties.count()
        occupied_properties = properties.filter(is_occupied=True).count()
        vacant_properties = total_properties - occupied_properties

        data = {
            "user_email": user.email,
            "user_type": user_type,
            "total_properties": total_properties,
            "occupied_properties": occupied_properties,
            "vacant_properties": vacant_properties,
            "total_leases": lease_queryset.count(),
            "active_leases": active_count,
            "upcoming_renewals": upcoming_renewals_count,
            "negotiations": negotiations_count
        }

        return prepare_response(
            content=data,
            message=constants.PROPERTY_STATSTICS_FETCHED,
            status=status.HTTP_200_OK
        )

    except Exception as e:
        print("Error in property_summary:", e)
        return prepare_response(
            message=constants.SOMTHING_WENT_WRONG,
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )




@is_request_authenticated
def tenant_my_property(request):
    try:
        user = request.user

        
        if user.user_type != "TENANT":
            return prepare_response(
                message=constants.ACCESS_DENIED_TENANTS_ONLY,
                status=status.HTTP_403_FORBIDDEN
            )

    
        tenant = (
            TenantDetails.objects
            .select_related("property", "property__owner")
            .filter(user=user)
            .first()
        )

        if not tenant:
            return prepare_response(
                message="Tenant details not found.",
                status=status.HTTP_404_NOT_FOUND
            )

       
        tenant_info = {
            "full_name": tenant.full_name,
            "email": user.email,
            "mobile_number": tenant.mobile_number,
            "nationality": tenant.nationality,
            "emirate_id": tenant.emirate_id,
            "tenant_number": tenant.tenant_number,
        }

        
        property_list = []
        tenant_properties = (
            TenantDetails.objects
            .select_related("property", "property__owner")
            .filter(user=user)
        )

        for tenant_entry in tenant_properties:
            property_obj = tenant_entry.property
            if not property_obj:
                continue

            property_data = {
                "property_name": property_obj.property_name,
                "address": property_obj.address,
                "property_code": property_obj.property_code,
                "bedrooms": property_obj.bedrooms,
                "balcony": property_obj.balcony,
                "rental_status": property_obj.rental_status,
                "is_occupied": property_obj.is_occupied,
                "tenancy_start_date": property_obj.tenancy_start_date,
                "tenancy_end_date": property_obj.tenancy_end_date,
                "owner": {
                    "email": property_obj.owner.email if property_obj.owner else None,
                    "user_id": property_obj.owner.id if property_obj.owner else None,
                }
            }

            property_list.append(property_data)

       
        response_content = {
            "tenant": tenant_info,
            "properties": property_list
        }

        return prepare_response(
            content=response_content,
            message=constants.TENANT_DETAILS_FETCHED_SUCCESS,
            status=status.HTTP_200_OK
        )

    except Exception as e:
        print("Tenant Dashboard Error:", e)
        return prepare_response(
            message=constants.SOMTHING_WENT_WRONG,
            content={"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    




@is_request_authenticated
def property_tenant_list_view(request):
    if request.method != "GET":
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    user = request.user

    try:
        page = int(request.GET.get("page", 1))
        limit = int(request.GET.get("limit", 10))
        search = request.GET.get("search", "").strip()
        property_id = request.GET.get("property_id")

     
        if user.user_type == constants.OWNER:
            properties_qs = PropertyDetails.objects.select_related(
                "owner", "property_manager"
            ).filter(owner=user)
        elif user.user_type == constants.TENANT:
            properties_qs = PropertyDetails.objects.select_related(
                "owner", "property_manager"
            ).all()
        else:
            return prepare_response(
                message=constants.ACCESS_DENIED,
                status=status.HTTP_403_FORBIDDEN
            )

      
        if property_id:
            properties_qs = properties_qs.filter(id=property_id)

      
        if search:
            properties_qs = properties_qs.filter(
                Q(property_name__icontains=search) |
                Q(owner__owner_details__full_name__icontains=search)
            )

        if not properties_qs.exists():
            return prepare_response(
                message="No properties found.",
                content={"data": [], "page": page, "total_pages": 0, "total_records": 0},
                status=status.HTTP_404_NOT_FOUND
            )

    
        paginator = Paginator(properties_qs, limit)
        page_obj = paginator.get_page(page)

        response_data = []
        for prop in page_obj:
            tenant = TenantDetails.objects.filter(property=prop).first()
            commercial = getattr(prop, "commercial", None)

            response_data.append({
                "property_id": prop.id,
                "property_code": prop.property_code,
                "property_name": prop.property_name,
                "address": prop.address,
                "bedrooms": prop.bedrooms,

                "rental_status": prop.rental_status,
                "is_occupied": prop.is_occupied,
                "rental_status": "Available" if prop.is_occupied else "Not Available",
       
                "owner": {
                    "id": prop.owner.id if prop.owner else None,
                    "name": prop.owner.owner_details.first().full_name if prop.owner and prop.owner.owner_details.exists() else None,
                    "email": prop.owner.email if prop.owner else None
                },
                "property_manager_name": prop.property_manager.company_name if prop.property_manager else None,
                "tenant_name": tenant.full_name if tenant else None,
                "tenant_id": tenant.id if tenant else None,
                "agreement_status": True if tenant and tenant.lease_property_details else False,
                "commercial_details": {
                    "rent": commercial.rent if commercial else None,
                    "security_deposit": commercial.security_deposit if commercial else None,
                    "booking_amount": commercial.booking_amount if commercial else None,
                    "maintenance_charges": commercial.maintenance_charges if commercial else None,
                    "cycle": commercial.cycle if commercial else None,
                    "notice_period": commercial.notice_period if commercial else None,
                    "commission_percent": commercial.commission_percent if commercial else None,
                } if commercial else None
            })

        content = {
            "page": page,
            "total_pages": paginator.num_pages,
            "total_records": paginator.count,
            "data": response_data
        }

        return prepare_response(
            message="Properties fetched successfully.",
            content=content,
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return prepare_response(
            message=f"Error fetching properties: {str(e)}",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
