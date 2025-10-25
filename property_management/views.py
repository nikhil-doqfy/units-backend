# views.py
from django.shortcuts import get_object_or_404
from django.db import IntegrityError, transaction
from property_management.models import OwnerDetails ,PropertyDocuments
from utilities.decorator import is_request_authenticated
import json
from utilities.helper_functions import  prepare_response, logger
from utilities import config as aws_constants
from utilities.decorator import is_request_authenticated
from utilities.helper_functions import upload_file_to_s3_base64, prepare_response, logger
from utilities import status ,  constants
from django.utils import timezone
from utilities import config
from utilities.helper_functions import fetch_s3_file_as_base64



@is_request_authenticated
def submit_owner_details(request):
    if request.method != "POST":
        return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    try:
        current_user = request.user  
        data = request.POST  

       
        if OwnerDetails.objects.filter(user=current_user).exists():
            return prepare_response( message=constants.OWNER_DETAILS_ALREADY_EXISTS,status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            owner_details = OwnerDetails.objects.create(
                user=current_user,
                full_name=data.get("full_name"),
                emirate_id=data.get("emirate_id"),
                uae_residence_visa=data.get("uae_residence_visa"),
                trade_license_number=data.get("trade_license_number"),
                owner_number=data.get("owner_number"),
                mobile_number=data.get("mobile_number"),
                manage_manually=data.get("manage_manually", False),
                manage_through_pmc=data.get("manage_through_pmc", False),
                emirates_id_file=data.get("emirates_id_file"),
                residence_visa_file=data.get("residence_visa_file"),
                dld_certificate_file=data.get("dld_certificate_file"),
                dewa_registration_file=data.get("dewa_registration_file"),
            )

            
            current_user.is_detail_updated = True
            current_user.save()

        return prepare_response( content={"owner_details_id": owner_details.id, "is_detail_updated": current_user.is_detail_updated},message=constants.OWNER_DETAILS_SAVED_SUCCESS,status=status.HTTP_201_CREATED)
 

    except IntegrityError:
        return prepare_response(
            message=constants.DOCUMENTS_ALREADY_UPLOADED,
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return prepare_response(
            message=f"Failed to save owner details: {str(e)}",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )









@is_request_authenticated
def choose_manage_option(request):
    """
    Allows the authenticated owner to choose their management option.
    """
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
    """
    Fetch all uploaded owner documents from S3 and return as Base64 strings.
    """
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





