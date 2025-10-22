# views.py
from django.shortcuts import get_object_or_404, redirect
from django.http import JsonResponse, HttpResponseBadRequest
from django.db import IntegrityError, transaction
from user_service.models import UserProfile
from property_management.models import OwnerDetails ,PropertyDocuments
from utilities.decorator import is_request_authenticated
import json
import os
from django.http import HttpResponseBadRequest
from django.conf import settings
from utilities.helper_functions import  prepare_response, logger
from utilities import config as aws_constants
 
from utilities.decorator import is_request_authenticated
import base64
from utilities.helper_functions import upload_file_to_s3_base64, prepare_response, logger
from utilities import status
from django.utils import timezone

@is_request_authenticated
def submit_owner_details(request):
    if request.method != "POST":
        return prepare_response(message="Only POST requests are allowed", status=status.HTTP_405_METHOD_NOT_ALLOWED)

    try:
        current_user = request.user  # Assuming user is authenticated via request.user
        data = request.POST  # or request.body for JSON

        # Check if owner details already exist
        if OwnerDetails.objects.filter(user=current_user).exists():
            return prepare_response( message="Owner details already exist for this user.",status=status.HTTP_400_BAD_REQUEST)

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

            # Update user's detail updated status
            current_user.is_detail_updated = True
            current_user.save()

        return prepare_response( content={"owner_details_id": owner_details.id, "is_detail_updated": current_user.is_detail_updated},message="Owner details saved successfully.",status=status.HTTP_201_CREATED)
 

    except IntegrityError:
        return prepare_response(
            message="Documents are already uploaded for this user.",
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
            message="Only POST requests are allowed.",
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    current_user = request.user  # Set by your decorator

    if current_user.user_type != "OWNER":
        return prepare_response(
            message="Access denied. Only owners can access this resource.",
            status=status.HTTP_403_FORBIDDEN
        )

    # Parse JSON or form data
    import json
    try:
        data = json.loads(request.body)
        option = data.get("option", "").lower()
    except Exception:
        option = request.POST.get("option", "").lower()

    try:
        # Fetch owner details
        owner_details = get_object_or_404(OwnerDetails, user=current_user)

        # Validate and update management option
        if option == "manual":
            owner_details.manage_manually = True
            owner_details.manage_through_pmc = False
        elif option == "pmc":
            owner_details.manage_manually = False
            owner_details.manage_through_pmc = True
        else:
            return prepare_response(
                message="Invalid option. Choose either 'manual' or 'pmc'.",
                status=status.HTTP_400_BAD_REQUEST
            )

        owner_details.save()

        return prepare_response(
            content={"chosen_option": option},
            message="Management option updated successfully.",
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return prepare_response(
            message=f"An error occurred: {str(e)}",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ----------------@router.post("/owner/upload-documents")--------------------------------------------------------------------------------------------------







@is_request_authenticated
def upload_owner_documents(request):
    if request.method != "POST":
        return prepare_response(
            message="Only POST requests are allowed.",
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        data = json.loads(request.body)
    except Exception:
        return prepare_response(
            message="Invalid JSON body.",
            status=status.HTTP_400_BAD_REQUEST
        )

    documents = data.get("documents", [])

    if len(documents) != 4:
        return prepare_response(
            message="All 4 documents are required.",
            status=status.HTTP_400_BAD_REQUEST
        )

    current_user = request.user
    try:
        owner_details = OwnerDetails.objects.get(user=current_user)
    except OwnerDetails.DoesNotExist:
        return prepare_response(
            message="Owner details not found for this user.",
            status=status.HTTP_404_NOT_FOUND
        )
    
        # Prepare dict to save in PropertyDocuments
    prop_docs_dict = {}

    for doc in documents:
        base64_data = doc.get("document")
        file_name = doc.get("file_name")
        doc_type = doc.get("type")  # e.g., 'emirates_id', 'residence_visa'

        if not base64_data or not file_name or not doc_type:
            return prepare_response(
                message=f"Missing fields in document: {doc}",
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Upload to S3
            s3_url = upload_file_to_s3_base64(
                base64_data, 
                f"owner_documents/{current_user.id}/{file_name}"
            )
            # Update DB fields dynamically
            setattr(owner_details, f"{doc_type}_file", s3_url)
        except Exception as e:
            return prepare_response(
                message=f"Failed to upload document '{file_name}': {str(e)}",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    # Save owner details and update user's document upload status
    owner_details.save()
    current_user.is_document_uploaded = True
    current_user.save()

     # ✅ Save or update PropertyDocuments
    prop_doc_instance, created = PropertyDocuments.objects.get_or_create(
        document_title=f"Owner {current_user.id} Documents",
        defaults={"property_documents": prop_docs_dict}
    )
    if not created:
        prop_doc_instance.property_documents = prop_docs_dict
        prop_doc_instance.updated_at = timezone.now()
        prop_doc_instance.save()

    return prepare_response(
        message="Documents uploaded successfully.",
        status=status.HTTP_200_OK
    )





# [
#   {"type": "emirates_id", "file_name": "emirates_id.pdf", "document": "..."},
#   {"type": "residence_visa", "file_name": "residence_visa.pdf", "document": "..."},
#   {"type": "dld_certificate", "file_name": "dld_certificate.pdf", "document": "..."},
#   {"type": "dewa_registration", "file_name": "dewa_registration.pdf", "document": "..."}
# ]


