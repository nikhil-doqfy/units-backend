
from django.shortcuts import get_object_or_404
from django.db import IntegrityError, transaction
from property_management.models import OwnerDetails ,TenantDetails , LeasePropertyDetails ,LeaseCommercials,LeaseEjariUpload,OwnerPMCInvitation,PMCOwnerInvitation , PMCTenantInvitation ,Template, TemplateFields ,TemplateValues 
from user_service.models import PropertyManagerCompanyDetails ,PropertyDetails ,UserProfile,StaffDetails  ,PropertyCommercial ,PropertyImages ,PropertyDocuments 
from utilities.decorator import is_request_authenticated
import json
from utilities.helper_functions import upload_file_to_s3_base64,fetch_s3_file_as_base64, prepare_response, logger,send_ses_email,safe_decimal ,safe_epoch_to_datetime ,replace_placeholders ,fetch_s3_presigned_url ,export_to_csv ,datetime_to_epoch_millis,get_pdfkit_config,generate_property_code 
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
from django.core.paginator import Paginator, EmptyPage
from django.conf import settings
import os
from datetime import datetime
import datetime
import re
import pdfkit
import platform
from django.http import FileResponse, Http404
from property_management.utils import get_property_images


@is_request_authenticated
def serve_media(request, path):

    file_path = os.path.join(settings.MEDIA_ROOT, path)

    if os.path.exists(file_path):
        return FileResponse(open(file_path, 'rb'))
    else:
        raise Http404("File not found or unable to access requested media file")


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
                    {"key": prop.id, "value": prop.property_name} for prop in properties
                ]
        
        elif option_type == "PROPERTY_TYPES":
            content["property_types"] = [{"key": choice[0], "value": choice[1]}for choice in constants.PROPERTY_TYPE_CHOICES]
        elif option_type == "PMC_LIST":
            pmcs = PropertyManagerCompanyDetails.objects.all()
            content["pmc_list"] = [
                 {"key": pmc.id, "value": pmc.company_name} for pmc in pmcs
                  ]
        elif option_type == "USER_TYPES":
            content["user_types"] = [
                 {"key": constants.OWNER, "value": "Owner"},
                {"key": constants.PROPERTY_MANAGER, "value": "Property Manager"},
                {"key": constants.TENANT, "value": "Tenant"},
                {"key": constants.STAFF, "value": "Staff"},
            ]
        elif option_type == "TENANTS_LIST":
            tenants = TenantDetails.objects.all()
            content["tenants_list"] = [{
                "key": tenant.id,
            "value": tenant.full_name   }
            for tenant in tenants]
        
        elif option_type == "PMC_PROPERTIES":
            pmc = PropertyManagerCompanyDetails.objects.filter(user=user).first()
            if not pmc:
                content["pmc_properties"] = []
            else:
                properties = PropertyDetails.objects.filter(property_manager=pmc)
                content["pmc_properties"] = [
                    {"key": prop.id, "value": prop.property_name} for prop in properties
                ]

        elif option_type == "PREDEFINED_TEMPLATES":
            templates = Template.objects.filter(is_predefined=True, is_active=True)
            content["predefined_templates"] = [
                {
            "key": template.id,
            "value": template.name,
            "description": template.description
           }
            for template in templates
              ]
            
        elif option_type == "ALL_PMC":
            pmcs = PropertyManagerCompanyDetails.objects.all()
            content["all_pmc"] = [
                {"key": pmc.id, "value": pmc.company_name}
                for pmc in pmcs
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
            owner_id = request.GET.get("owner_id")
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

            if owner_id:
                owner = owners_qs.filter(id=owner_id).first()
                if not owner:
                    return prepare_response(
                        message=constants.OWNER_NOT_FOUND,
                        status=status.HTTP_404_NOT_FOUND
                    )
                user = owner.user
                properties = PropertyDetails.objects.filter(owner=user)
                property_with_tenant_data = []
                for property_obj in properties:
                    tenant = TenantDetails.objects.filter(property=property_obj).first()
                    lease = LeasePropertyDetails.objects.filter(
                        lease_property=property_obj
                    ).first()
                    images_qs = PropertyImages.objects.filter(property=property_obj)
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
                    tenant_profile_image = None
                    if tenant and tenant.user and tenant.user.profile_image:
                        tenant_profile_image = tenant.user.profile_image
     
                    property_with_tenant_data.append({
                        "property_code": property_obj.property_code if property_obj.property_code else None,
                         "property_name": property_obj.property_name if property_obj.property_name else None,
                        "tenancy_status": property_obj.rental_status if property_obj.rental_status else None,
                         "agreement": {
                          "lease_id": lease.id,
                                         } if lease else None,
                        "images": images_list if images_list else None,
                         "tenant":{
                             "name": tenant.full_name if tenant else None,
                             "profile_image": tenant_profile_image if tenant_profile_image else None,

                         }
                        })


                properties = PropertyDetails.objects.filter(owner=owner.user).values(
                    "id",
                    "property_name",  
                    "address",
                    "rental_status",
                    "property_code"
                )
                owner_data = {
                    "id": owner.id,
                    "user_id": user.id if user else None,
                    "full_name": owner.full_name,
                    "emirate_id": owner.emirate_id,
                    "uae_residence_visa": owner.uae_residence_visa,
                    "trade_license_number": owner.trade_license_number,
                    "owner_number": owner.owner_number,
                    "mobile_number": owner.mobile_number,
                    "user_type": user.user_type,
                    "manage_manually": owner.manage_manually,
                    "manage_through_pmc": owner.manage_through_pmc,
                    "created_at": owner.created_at.strftime("%Y-%m-%d %H:%M:%S")
                                    if hasattr(owner, "created_at") else None,
                    
                    "property_count": len(properties),
                    "email": user.email if user else None,
                    "profile_image": user.profile_image if user else None,
                    "properties": property_with_tenant_data,
                    "property_count": len(property_with_tenant_data),
                }
                return prepare_response(
                    content=owner_data,
                    message=constants.OWNER_DETAILS_FETCHED_SUCCESS,
                    status=status.HTTP_200_OK
                )

            paginator = Paginator(owners_qs, limit)
            try:
                owners_page = paginator.page(page)
            except EmptyPage:
                owners_page = paginator.page(paginator.num_pages)
            owners_data = []


            for owner in owners_page:
                user = owner.user
                properties = PropertyDetails.objects.filter(owner=owner.user)
                property_list = []
                for property_obj in properties:
                    images_list = get_property_images(property_obj.id)
                    property_list.append({
                        "property_code": property_obj.property_code,
                        "property_name": property_obj.property_name,
                        "rental_status": property_obj.rental_status,
                       "images": images_list if images_list else None  
                                     })
 

                owners_data.append({
                    "id": owner.id,
                    "user_id": owner.user.id if owner.user else None,
                    "full_name": owner.full_name,
                    "owner_number": owner.owner_number,
                    "mobile_number": owner.mobile_number,
                    "property_count": len(properties),
                    "email": user.email if user else None,
                    "profile_image": user.profile_image if user else None,
                    "properties": property_list
                })
            pagination_meta = {
                "current_page": owners_page.number,
                "limit": limit,
                "total_records": paginator.count,
                "total_pages": paginator.num_pages
            }

            
            return prepare_response(
                content= owners_data,
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
    # prop_doc_instance, created = PropertyDocuments.objects.get_or_create(
    #     document_title=f"Owner {current_user.id} Documents",
    #     defaults={"property_documents": prop_docs_dict}
    # )
    # if not created:
    #     prop_doc_instance.property_documents = prop_docs_dict
    #     prop_doc_instance.updated_at = timezone.now()
    #     prop_doc_instance.save()

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
    tenant_id = request.GET.get("tenant_id")

    def get_tenant():
        """Helper to fetch tenant by query param or current user"""
        if tenant_id:
            return TenantDetails.objects.select_related("property", "user").filter(id=tenant_id).first()
        return TenantDetails.objects.select_related("property", "user").filter(user=user).first()

 
    if request.method == "GET":
        try:
            tenant = get_tenant()
            if not tenant:
                return prepare_response(
                    message=constants.TENANT_DETAILS_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )

            user_profile = tenant.user
            property_name = tenant.property.property_name if tenant.property else None

            tenant_data = {
                "tenant_id": tenant.id,
                "profile_image_type":user_profile.profile_image_type if user_profile else None,
                "type": user_profile.user_type if user_profile else None,
                "email": user_profile.email if user_profile else None,
                "first_name": user_profile.first_name if user_profile else None,
                "last_name": user_profile.last_name if user_profile else None,
                "country": user_profile.country if user_profile else None,
                "profile_image": user_profile.profile_image if user_profile else None,
                "emirate_id": tenant.emirate_id,
                "contact_number": tenant.mobile_number,
                "nationality": tenant.nationality,
                "country":user_profile.country if user_profile else None ,
                "address": tenant.address,
                "linked_property": property_name,
                "postal_code":tenant.postal_code,
                "city":tenant.city,
                

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
                    message=constants.EMAIL_REQUIRED,
                    status=status.HTTP_400_BAD_REQUEST
                )

            if UserProfile.objects.filter(email=email).exists():
                return prepare_response(
                    message=constants.EMAIL_ALREADY_REGISTERED,
                    status=status.HTTP_400_BAD_REQUEST
                )

            property_id = data.get("property_id")
            first_name = (data.get("first_name") or "").strip()
            last_name = (data.get("last_name") or "").strip()
            full_name = f"{first_name} {last_name}".strip()
            tenant_number = str(uuid.uuid4())

            user = UserProfile.objects.create(
                email=email,
                user_type=constants.TENANT,
                is_verified=True,
                is_login_allowed=True,
                is_detail_updated=True,
                profile_image=data.get("profile_image"),
                first_name=first_name,
                last_name=last_name
            )

            tenant_details = TenantDetails.objects.create(
                user=user,
                full_name=full_name,
                emirate_id=data.get("emirate_id"),
                mobile_number=data.get("contact_number"),
                tenant_number=tenant_number,
                property=PropertyDetails.objects.get(id=property_id) if property_id else None,
            )

            user.is_detail_updated = True
            user.save()

            return prepare_response(
                content={"id": tenant_details.id},
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
            data = json.loads(request.body.decode('utf-8'))
        except Exception:
            return prepare_response(
                message=constants.INVALID_JSON_BODY,
                status=status.HTTP_400_BAD_REQUEST
            )

        tenant_details = get_tenant()
        if not tenant_details:
            return prepare_response(
                message=constants.TENANT_DETAILS_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        user_profile = tenant_details.user

        try:
     
            for field in ["first_name", "last_name", "email", "country", "profile_image"]:
                if field in data:
                    setattr(user_profile, field, data[field])
            user_profile.save()


            for field_map in [("emirate_id", "emirate_id"),
                              ("contact_number", "mobile_number"),
                              ("nationality", "nationality"),
                              ("address", "address")]:
                if field_map[0] in data:
                    setattr(tenant_details, field_map[1], data[field_map[0]])

       
            tenant_details.full_name = f"{user_profile.first_name} {user_profile.last_name}".strip()
            tenant_details.save()

            return prepare_response(
                content={"email": user_profile.email},
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

                images_base64 = get_property_images(prop.id)

                # images_base64 = []
                # if prop.images:
                #     for img_url in prop.images:
                #         img_b64 = fetch_s3_file_as_base64(img_url) 
                #         if img_b64:
                #             images_base64.append(img_b64)

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


    if request.method == "GET":
        try:
            property_id = request.GET.get("property_id")

            if not property_id:
                return prepare_response(message=constants.PROPERTY_ID_REQUIRED, status=status.HTTP_400_BAD_REQUEST)

            prop = PropertyDetails.objects.filter(id=property_id).first()
            if not prop:
                return prepare_response(message=constants.PROPERTY_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
            property_type_options = dict(constants.PROPERTY_TYPE_CHOICES)
            property_data = {
                                
                                "key": prop.property_type,            
                                "value":property_type_options[prop.property_type]
                             
                                    }

            content = {
                "id": prop.id,
                "property_name": prop.property_name,
                "address": prop.address,
                "area_of_property": prop.area_of_property,
                "no_of_parking": prop.no_of_parking,
                "bedrooms": prop.bedrooms,
                "balcony": prop.balcony,
                "plot_no": prop.plot_no,
                "area_unit": prop.area_unit,
                "property_code": prop.property_code,
                "property_type": property_data,
                "land_area":prop.land_area,
                "land_dm_no":prop.land_dm_no,
                "apartment_no":prop.apartment_no,
                "no_of_floors":prop.no_of_floors,
                 "makani_no" :prop.makani_no,
                 "dewa_no":prop.dewa_no,
                "step_choice": prop.step_status if prop else None
                
               
            }

            return prepare_response(content=content, status=status.HTTP_200_OK)

        except Exception as e:
            return prepare_response(message={"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    elif request.method == "PUT":
        try:
            data = json.loads(request.body)
            property_id = data.get("property_id")

            if not property_id:
                return prepare_response(message=constants.PROPERTY_ID_REQUIRED, status=status.HTTP_400_BAD_REQUEST)

            prop = PropertyDetails.objects.filter(id=property_id).first()
            if not prop:
                return prepare_response(message=constants.PROPERTY_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)

        
            updatable_fields = [
                "property_name", "land_dm_no", "address", "area_of_property",
                "no_of_parking", "makani_no", "dewa_no", "property_type",
                "land_area", "apartment_no", "bedrooms", "balcony",
                "plot_no", "area_unit", "land_area_unit", "no_of_floors",
                "property_code", "invited_email_id"
            ]

            for field in updatable_fields:
                if field in data:
                    setattr(prop, field, data[field])

            prop.save()

            return prepare_response(
                message=constants.PROPERTY_UPDATE_SUCCESS,
                content={"property_id": prop.id},
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return prepare_response(message={"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    elif request.method == "POST":
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
            balcony = data.get("balcony")
            plot_no = data.get("plot_no")
            area_unit = data.get("area_unit")
            land_area_unit = data.get("land_area_unit")
            no_of_floors = data.get("no_of_floors")
            # property_code = data.get("property_code")
            invited_email_id = data.get("invited_email_id")
            property_code=generate_property_code()

            if user.user_type == "OWNER":
                owner = user
                property_manager = None

            elif  user.user_type == "PROPERTY_MANAGER":
                pmc_obj = PropertyManagerCompanyDetails.objects.filter(user=user).first()
                if not pmc_obj:
                    return prepare_response(message=constants.PROPERTY_MANAGER_Details_NOT_FOUND, status=status.HTTP_400_BAD_REQUEST)
                property_manager = pmc_obj
                owner = None
   

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
                balcony=balcony,
                plot_no=plot_no,
                area_unit=area_unit,
                land_area_unit=land_area_unit,
                no_of_floors=no_of_floors,
                property_code=property_code,
                invited_email_id=invited_email_id,
                owner=owner,
                property_manager=property_manager,
                step_status="BASIC_DETAILS",
                
            )

            return prepare_response(
                message=constants.PROPERTY_ADDED,
                content={"id": new_property.id},
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            return prepare_response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    else:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
           status= status.HTTP_405_METHOD_NOT_ALLOWED
        )









@is_request_authenticated
def add_commercial_details(request):
    user = request.user
    try:

        if request.method == "GET":
            property_id = request.GET.get("property_id")
            if not property_id:
                return prepare_response(message=constants.PROPERTY_ID_REQUIRED, status=status.HTTP_400_BAD_REQUEST)

            commercial_obj = PropertyCommercial.objects.filter(property_id=property_id).first()
            if not commercial_obj:
                return prepare_response(message=constants.COMMERCIAL_DETAILS_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
            property_obj = PropertyDetails.objects.filter(id=property_id).first()

         
            data = {
                "property_id":property_id,
                "rent": commercial_obj.rent,
                "security_deposit": commercial_obj.security_deposit,
                "booking_amount": commercial_obj.booking_amount,
                "maintenance_charges": commercial_obj.maintenance_charges,
                "cycle": commercial_obj.cycle,
                "notice_period": commercial_obj.notice_period,
                "commission_percent": commercial_obj.commission_percent,
                              "pmc": {
                        "key": property_obj.property_manager.id,
                        "value": property_obj.property_manager.company_name
                        } if property_obj.property_manager else None   
                       ,
                "step_choice": property_obj.step_status if property_obj else None 
            }

            return prepare_response(content=data, message=constants.COMMERCIAL_DETAILS_FETCHED, status=status.HTTP_200_OK)

        if request.method in ["POST", "PUT"]:
            data = json.loads(request.body)
            property_id = data.get("property_id")

            if not property_id:
                return prepare_response(message=constants.PROPERTY_ID_REQUIRED, status=status.HTTP_400_BAD_REQUEST)

            property_obj = PropertyDetails.objects.filter(id=property_id).first()
            if not property_obj:
                return prepare_response(message=constants.PROPERTY_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
            

            
            if user.user_type == "OWNER":
                pmc_id = data.get("pmc_id")
                if pmc_id:
                    pmc_obj = PropertyManagerCompanyDetails.objects.filter(id=pmc_id).first()
                    if not pmc_obj:
                        return prepare_response(message=constants.PMC_NOT_FOUND, status=status.HTTP_400_BAD_REQUEST)
                    property_obj.property_manager = pmc_obj
                    property_obj.save()

                        
        if request.method == "POST":
            PropertyCommercial.objects.update_or_create(
                property=property_obj,
                defaults={
                        "rent": safe_decimal(data.get("rent")),
                         "security_deposit": safe_decimal(data.get("security_deposit")),
                         "booking_amount": safe_decimal(data.get("booking_amount")),
                        "maintenance_charges": safe_decimal(data.get("maintenance_charges")),
                         "commission_percent": safe_decimal(data.get("commission_percent")),
                         "cycle": data.get("cycle"),
                        "notice_period": data.get("notice_period"),
                        

                       
                       
                }
            )
            property_obj.step_status = "COMMERCIALS_DETAILS"
            property_obj.save()
            return prepare_response(
                
                message=constants.COMMERCIAL_DETAILS_CREATED,
                status=status.HTTP_201_CREATED
            )


        if request.method == "PUT":
            commercial_obj = PropertyCommercial.objects.filter(property=property_obj).first()
            if not commercial_obj:
                return prepare_response("Commercial details not found", status=status.HTTP_404_NOT_FOUND)
            decimal_fields = ["rent", "security_deposit", "booking_amount", "maintenance_charges", "commission_percent"]
            other_fields = ["cycle", "notice_period"]
            updatable_fields = [
                "rent", "security_deposit", "booking_amount",
                "maintenance_charges", "cycle", "notice_period",
                "commission_percent"
            ]

            for field in decimal_fields:
                if field in data:
                    setattr(commercial_obj, field, safe_decimal(data[field])
                            )
            for field in other_fields:
                if field in data:
                    setattr(commercial_obj, field, data[field])

            commercial_obj.save()

            return prepare_response(
                message=constants.COMMERCIAL_DETAILS_UPDATED,
                status=status.HTTP_200_OK
            )

        return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    except Exception as e:
        return prepare_response(f"Error: {str(e)}", status=status.HTTP_500_INTERNAL_SERVER_ERROR)





def property_images_view(request):
    try:


        if request.method == "GET":
            property_id = request.GET.get("property_id")

            if not property_id:
                return prepare_response(message=constants.PROPERTY_ID_REQUIRED , status=status.HTTP_400_BAD_REQUEST)

            try:
                property_obj = PropertyDetails.objects.get(id=property_id)
            except PropertyDetails.DoesNotExist:
                return prepare_response(message=constants.INVALID_PROPERTY_ID, status=status.HTTP_404_NOT_FOUND)

            images_qs = PropertyImages.objects.filter(property_id=property_id).order_by("-id")
         
            final_images = []

            for img in images_qs:
                url = img.image_path
                file_name = img.file_name
                img_type = img.image_type

                base64_data = fetch_s3_presigned_url(url,file_name=file_name)

                final_images.append({
                    "file_name": file_name,
                    "data": base64_data,
                    "type": img_type,
                    "id":img.id,
                })

            return prepare_response(
                message="Fetched successfully",
                content={
                    "images": final_images,
                    "property_id": property_id,
                    "step_choice": property_obj.step_status
                },
                status=status.HTTP_200_OK
            )


        if request.method == "POST":
            body = json.loads(request.body)
            property_id = body.get("property_id")
            images = body.get("images", [])

            if not property_id:
                return prepare_response(message=constants.PROPERTY_ID_REQUIRED , status=status.HTTP_400_BAD_REQUEST)

            if not isinstance(images, list) or not images:
                return prepare_response(message="Images must be a list", status=status.HTTP_400_BAD_REQUEST)

            try:
                property_obj = PropertyDetails.objects.get(id=property_id)
            except PropertyDetails.DoesNotExist:
                return prepare_response(message=constants.PROPERTY_NOT_FOUND,status=status.HTTP_404_NOT_FOUND)

            uploaded_files = []

            for img in images:
                file_name = img.get("file_name")
                base64_data = img.get("data")
                img_type = img.get("type", "INTERIOR").upper()

                if not file_name or not base64_data:
                    return prepare_response(message=constants.MISSING_FILE_OR_DATA , status=status.HTTP_400_BAD_REQUEST)

                object_name = f"property_images/{property_id}/{file_name}"

                image_url = upload_file_to_s3_base64(base64_data, object_name)

                PropertyImages.objects.create(
                    property=property_obj,
                    file_name=file_name,
                    image_path=image_url,
                    image_type=img_type
                )

                uploaded_files.append({
                    "file_name": file_name,
                    "image_url": image_url,
                    "image_type": img_type
                })
                property_obj.step_status = "PROPERTY_IMAGES_DETAILS"
                property_obj.save()
                 
                         
                
                

            return prepare_response(
                message=constants.IMAGE_UPLOADED_SUCCESS,
                content={"uploaded": uploaded_files},
                status=status.HTTP_201_CREATED
            )

    
        if request.method == "PUT":
            body = json.loads(request.body)

            property_id = body.get("property_id")
            images = body.get("images", [])

            if not property_id:
                return prepare_response(message=constants.PROPERTY_ID_REQUIRED , status=status.HTTP_400_BAD_REQUEST)

            if not isinstance(images, list):
                return prepare_response(message="Images must be a list", status=status.HTTP_400_BAD_REQUEST)

            try:
                property_obj = PropertyDetails.objects.get(id=property_id)
            except PropertyDetails.DoesNotExist:
                return prepare_response(message=constants.PROPERTY_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)

            updated_files = []

            for img in images:
                file_name = img.get("file_name")
                base64_data = img.get("data")
                img_type = img.get("type", "INTERIOR").upper()

                if not file_name or not base64_data:
                    return prepare_response(message=constants.MISSING_FILE_OR_DATA , status=status.HTTP_400_BAD_REQUEST)

             
                img_obj, created = PropertyImages.objects.update_or_create(
                    property=property_obj,
                    file_name=file_name,
                    defaults={
                        "image_type": img_type
                    }
                )

              
                object_name = f"property_images/{property_id}/{file_name}"
                image_url = upload_file_to_s3_base64(base64_data, object_name)

                img_obj.image_path = image_url
                img_obj.image_type = img_type
                img_obj.save()

                updated_files.append({
                    "file_name": file_name,
                    "image_url": image_url,
                    "image_type": img_type,
                    "status": "updated" if not created else "created"
                })

            return prepare_response(
                message=constants.IMAGE_UPLOADED_SUCCESS,
                content={"updated": updated_files},
                status=status.HTTP_200_OK
            )

        return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    except Exception as e:
        return prepare_response(message=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)






def property_documents_view(request):
    try:

        if request.method == "GET":
            property_id = request.GET.get("property_id")

            if not property_id:
                return prepare_response(message=constants.PROPERTY_ID_REQUIRED , status=status.HTTP_400_BAD_REQUEST)

            try:
                property_obj = PropertyDetails.objects.get(id=property_id)
            except PropertyDetails.DoesNotExist:
                return prepare_response(message=constants.INVALID_PROPERTY_ID, status=status.HTTP_404_NOT_FOUND)

            docs_qs = PropertyDocuments.objects.filter(property_id=property_id).order_by("-id")
            final_docs = []

            for doc in docs_qs:
                url = doc.file_path
                file_name = doc.file_name
                doc_type = doc.document_type

                # base64_data = fetch_s3_file_as_base64(url)
                base64_data = fetch_s3_presigned_url(url,file_name=file_name)

                final_docs.append({
                    "file_name": file_name,
                    "data": base64_data,
                    "type": doc_type,
                    "id":doc.id,
                })
            

            return prepare_response(
                message="Fetched successfully",
                content={
                    "documents": final_docs,
                    "property_id": property_id,
                    "step_choice": property_obj.step_status
                },
                status=status.HTTP_200_OK
            )



        if request.method == "POST":
            body = json.loads(request.body)
            property_id = body.get("property_id")
            documents = body.get("documents", [])

            if not property_id:
                return prepare_response(message=constants.PROPERTY_ID_REQUIRED , status=status.HTTP_400_BAD_REQUEST)

            if not isinstance(documents, list) or not documents:
                return prepare_response(message="Documents must be a list", status=status.HTTP_400_BAD_REQUEST)

            try:
                property_obj = PropertyDetails.objects.get(id=property_id)
            except PropertyDetails.DoesNotExist:
                return prepare_response(message=constants.PROPERTY_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)

            uploaded_files = []

            for doc in documents:
                file_name = doc.get("file_name")
                base64_data = doc.get("data")
                doc_type = doc.get("type", "RENTAL_DOCUMENT").upper()

                if not file_name or not base64_data:
                    return prepare_response(message=constants.MISSING_FILE_OR_DATA , status=status.HTTP_400_BAD_REQUEST)

                object_name = f"property_documents/{property_id}/{file_name}"

                file_url = upload_file_to_s3_base64(base64_data, object_name)

                PropertyDocuments.objects.create(
                    property=property_obj,
                    file_name=file_name,
                    file_path=file_url,
                    document_type=doc_type
                )

                uploaded_files.append({
                    "file_name": file_name,
                    "file_url": file_url,
                    "type": doc_type
                })
                property_obj.step_status = "DOCUMENTS_DETAILS"
                property_obj.save()

            return prepare_response(
                message="Documents uploaded successfully",
                content={"uploaded": uploaded_files},
                status=status.HTTP_201_CREATED
            )


    
        if request.method == "PUT":
            body = json.loads(request.body)
            property_id = body.get("property_id")
            documents = body.get("documents", [])

            if not property_id:
                return prepare_response(message=constants.PROPERTY_ID_REQUIRED , status=status.HTTP_400_BAD_REQUEST)

            if not isinstance(documents, list):
                return prepare_response(message="Documents must be a list",status= status.HTTP_400_BAD_REQUEST)

            try:
                property_obj = PropertyDetails.objects.get(id=property_id)
            except PropertyDetails.DoesNotExist:
                return prepare_response(message=constants.PROPERTY_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)

            updated_files = []

            for doc in documents:
                file_name = doc.get("file_name")
                base64_data = doc.get("data")
                doc_type = doc.get("type", "RENTAL_DOCUMENT").upper()

                if not file_name or not base64_data:
                    return prepare_response(message=constants.MISSING_FILE_OR_DATA ,status= status.HTTP_400_BAD_REQUEST)

                doc_obj, created = PropertyDocuments.objects.get_or_create(
                    property=property_obj,
                    file_name=file_name,
                    defaults={"document_type": doc_type}
                )

                object_name = f"property_documents/{property_id}/{file_name}"
                file_url = upload_file_to_s3_base64(base64_data, object_name)

                doc_obj.file_path = file_url
                doc_obj.document_type = doc_type
                doc_obj.save()

                updated_files.append({
                    "file_name": file_name,
                    "file_url": file_url,
                    "type": doc_type,
                    "status": "updated" if not created else "created"
                })

            return prepare_response(
                message="Documents updated successfully",
                content={"updated": updated_files},
                status=status.HTTP_200_OK
            )

        return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    except Exception as e:
        return prepare_response(message=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)








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
                    assigned_properties_data = []
                    for prop in assigned_props:
                        owner_data = None
                        if prop.owner:
                            owner_data = {
                        "id": prop.owner.id,
                        "name": getattr(prop.owner, "full_name", None),
                        
                    }
                        tenant_data = None
                   
                        tenant_obj = TenantDetails.objects.filter(property=prop).select_related("user").first()
                        tenant_data = None
                        if tenant_obj:
                            tenant_data = {
                                "id": tenant_obj.id,
                                 "name": tenant_obj.full_name,
                            }

                        # documents = []
                        # for doc in prop.property_docs_relationship.all():
                        #     documents.append({
                        #     "id": doc.id,
                        #   "file_name": doc.file_name,
                        #  "document_type": doc.document_type,
                        #     "file_path": doc.file_path
                        #      })
                        
                        images = []
                        for img in prop.property_images.all():
                            presigned_url = None
                            if img.image_path:
                                presigned_url = fetch_s3_presigned_url(
                                    img.image_path,
                                    file_name=f"{img.file_name}")
                                
                            images.append({
                                     "id": img.id,
                                     "image_type": img.image_type,
                                     "file_name": img.file_name,
                                    "image_path": presigned_url
                                         })
                        assigned_properties_data.append({
                         "property_name": prop.property_name,
                        "property_code": prop.property_code,
                         "owner": owner_data,
                         "tenant": tenant_data,
                        #  "documents": documents,
                         "images": images
                            })

                        
 


                    data = {
                        "id": staff.id,
                        "staff_name": staff.staff_name, 
                        "staff_id": staff.staff_id,
                        "phone_number": staff.phone_number,
                        "email": staff.user.email if staff.user else None,
                        "country": staff.user.country if staff.user else None,
                        "profile_image_type": staff.user.profile_image_type if staff.user else None,
                        "profile_image":staff.user.profile_image if staff.user else None,


                         "emirate_id": staff.emirate_id,
                        "city": staff.city,
                        "locality": staff.locality,
                        "postal_code": staff.postal_code,
                        "address_line_1": staff.address_line_1,
                        "address_line_2": staff.address_line_2,

                        "assign_property": staff.assign_property,
                        "staff_role": {
                            "id": staff.staff_role.id,
                            "name": staff.staff_role.name,
                        } if staff.staff_role else None,
                        


                        "total_assigned_properties": total_assigned,
                        "assigned_properties": assigned_properties_data

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
            try:
                page_obj = paginator.page(page)
            except EmptyPage:
                page_obj = paginator.page(paginator.num_pages)
            

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
            pagination_meta = {
                "current_page": page_obj.number,
                "limit": limit,
                "total_records": paginator.count,
                "total_pages": paginator.num_pages
            }
            return prepare_response(
                content=data,
                message=constants.STAFF_LIST_FETCHED_SUCCESS,
                status=status.HTTP_200_OK,
                pagination=pagination_meta,
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
            # document = PropertyDocuments.objects.filter(property=prop).first() if "PropertyDocuments" in globals() else None
            # document_title = document.document_title if document else "-"

            property_list.append({
                "code": prop.property_code or "-",
                "property_name": prop.property_name,
                "tenant_name": tenant_name,
                "tenancy_status": tenancy_status,
                "dimension": dimension,
               
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







@is_request_authenticated
def pmc_owner_view_list(request):
    try:
        user = request.user 
        if request.method == "PUT":
            body = json.loads(request.body)
            property_id = body.get("property_id")
            pmc_id = body.get("pmc_id")

            if not property_id or not pmc_id:
                return prepare_response(
                    message="property_id & pmc_id required",
                    status=status.HTTP_400_BAD_REQUEST
                )

            property_obj = PropertyDetails.objects.filter(id=property_id, owner=user).first()
            if not property_obj:
                return prepare_response(
                    message="You are not owner of this property!",
                    status=status.HTTP_403_FORBIDDEN
                )

            pmc_obj = PropertyManagerCompanyDetails.objects.filter(id=pmc_id).first()
            if not pmc_obj:
                return prepare_response(
                    message="PMC not found",
                    status=status.HTTP_404_NOT_FOUND
                )

            property_obj.property_manager = pmc_obj
            property_obj.save()

            return prepare_response(
                message="Property assigned successfully!",
                status=status.HTTP_200_OK
            )

      
        elif request.method == "GET":
            pmc_id = request.GET.get("pmc_id")

            
            if pmc_id:
                pmc_obj = PropertyManagerCompanyDetails.objects.filter(
                    id=pmc_id,
                    properties_managed__owner=user
                ).select_related("user").first()

                if not pmc_obj:
                    return prepare_response(
                        message="PMC not found or not linked to your properties",
                        status=status.HTTP_404_NOT_FOUND
                    )

                user_profile = pmc_obj.user
                pmc_docs_json = pmc_obj.pmc_documents or {}
                final_docs = []
                for key, url in pmc_docs_json.items():
                    base64_data = fetch_s3_presigned_url(url, file_name=key)
                    final_docs.append({
                        "file_name": key,
                        "data": base64_data,
                        "type": key,
                    })
                properties = PropertyDetails.objects.filter(
                     property_manager=pmc_obj,
                     owner=user
                    )
                properties_assigned = []
                for property_obj in properties:
                    tenant = TenantDetails.objects.filter(
                             property=property_obj
                              ).select_related("user").first()
                    tenant_name = tenant.full_name if tenant else None
                    tenant_profile_image = (
                    tenant.user.profile_image if tenant and tenant.user and tenant.user.profile_image else None)
                    images_qs = PropertyImages.objects.filter(property_id=property_obj.id)
                    images_list = [{
                    "file_name": img.file_name,
                    "data": img.image_path,
                    "type": img.image_type,
                    "id": img.id,
                                 }
                        for img in images_qs
                
                                    ]
                    properties_assigned.append({
                                "property_code": property_obj.property_code or None,
                                "property_name": property_obj.property_name or None,
        
                                 "tenancy_status": property_obj.rental_status or None,
                                  "dimension": property_obj.bedrooms or None,
        
                                         "tennat":{
                                              "name":tenant_name,
                                             "profile_image":tenant_profile_image,
            

                                             },
                               "property_images": images_list,
                                 })                      
                

                  

                data = {
                    "id": pmc_obj.id,
                    "company_code": pmc_obj.company_code,
                    "company_name": pmc_obj.company_name,
                    "company_id": pmc_obj.company_id,
                    "company_address": pmc_obj.company_address,
                    "city": pmc_obj.city,
                    "locality": pmc_obj.locality,
                    "postal_code": pmc_obj.postal_code,
                    "address_line_1": pmc_obj.address_line_1,
                    "address_line_2": pmc_obj.address_line_2,
                    "company_emirate_id": pmc_obj.company_emirate_id,
                    "uae_residence_visa": pmc_obj.uae_residence_visa,
                    "emirate_id": pmc_obj.emirate_id,
                    "trade_license_number": pmc_obj.trade_license_number,
                    "rera_license": pmc_obj.rera_license,
                    "phone_number": pmc_obj.phone_number,
                    "email": user_profile.email,
                    "first_name": user_profile.first_name,
                    "last_name": user_profile.last_name,
                    "profile_image": user_profile.profile_image,
                    "user_type": user_profile.user_type,
                    "documents": final_docs,
                    "properties_assigned":properties_assigned

                }

                return prepare_response(
                    content=[data],
                    message="PMC Full Details",
                    status=status.HTTP_200_OK
                )

      
            search = request.GET.get("search", "").strip()
            page = int(request.GET.get("page", 1))
            limit = int(request.GET.get("limit", 10))

            pmc_qs = PropertyManagerCompanyDetails.objects.filter(
                properties_managed__owner=user
            ).distinct()

            if search:
                pmc_qs = pmc_qs.filter(
                    Q(company_name__icontains=search)
                    | Q(company_code__icontains=search)
                    | Q(company_address__icontains=search)
                )

            paginator = Paginator(pmc_qs, limit)
            try:
                pmc_page = paginator.page(page)
            except EmptyPage:
                pmc_page = paginator.page(paginator.num_pages)

            data = []
            for p in pmc_page:
                properties = PropertyDetails.objects.filter(property_manager=p, owner=user)
                total_properties = properties.count()
                occupied = properties.filter(is_occupied=True).count()
                vacant = total_properties - occupied

                data.append({
                    "id": p.id,
                    "code": p.company_code,
                    "pmc_name": p.company_name,
                    "property_handling": f"{total_properties} Property",
                    "tenancy_ratio": f"{occupied}:{vacant}",
                    "address": p.company_address,
                })

            return prepare_response(
                content=data,
                message=constants.PROPERTY_MANAGER_DETAILS_FETCHED,
                status=status.HTTP_200_OK,
                pagination={
                    "current_page": pmc_page.number,
                    "limit": limit,
                    "total_records": paginator.count,
                    "total_pages": paginator.num_pages,
                }
            )

        else:
            return prepare_response(
                message=constants.INVALID_REQUEST_METHOD,
                status=status.HTTP_405_METHOD_NOT_ALLOWED
            )

    except Exception as e:
        print("Error:", e)
        return prepare_response(
            message=constants.SOMETHING_WENT_WRONG,
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )





@is_request_authenticated
def property_details_list_view(request):
    if request.method == "GET":
        try:
            user=request.user 

            property_id = request.GET.get("property_id")
            search = request.GET.get("search", "").strip()
            page = int(request.GET.get("page", 1))
            limit = int(request.GET.get("limit", 10))

            properties = PropertyDetails.objects.select_related(
                "owner",
                "property_manager",
                "staff",
                "commercial"   
            ).prefetch_related(
                Prefetch("tenant_details", queryset=TenantDetails.objects.select_related("user"))
            ).order_by("-id") 

            if property_id:
                properties = properties.filter(id=property_id)
                if not properties.exists():
                    return prepare_response(
                        message="Property Not Found",
                        status=status.HTTP_404_NOT_FOUND
                    )
            if not property_id:
                all_properties = request.GET.get("all", "").lower() == "true"

                if not all_properties:
                    if user.user_type == constants.OWNER:
                        properties = properties.filter(owner=user)
                    elif user.user_type == constants.TENANT:
                        properties = properties.filter(tenant_details__user=user).distinct()
                    elif user.user_type == constants.PROPERTY_MANAGER:
                        properties = properties.filter(property_manager__user=user).distinct()


            if search:
                properties = properties.filter(
                    Q(property_name__icontains=search) |
                    Q(owner__owner_details__full_name__icontains=search) |
                    Q(tenant_details__full_name__icontains=search)
                ).distinct()

            if not property_id:
                paginator = Paginator(properties, limit)
                try:
                    properties_page = paginator.page(page)
                except EmptyPage:
                    properties_page = paginator.page(paginator.num_pages)
            else:
                properties_page = properties  

            data = []

            for prop in properties_page:

                tenants = prop.tenant_details.all()
                tenant_data = []
                for tenant in tenants:
                    tenant_user = tenant.user
                    tenant_data.append({
                        "tenant_name": tenant.full_name,
                        "contact_number": tenant.mobile_number,
                        "tenant_number": tenant.tenant_number,
                        "nationality": tenant.nationality,
                        "email": tenant_user.email if tenant_user else None,
                        "profile_image": tenant_user.profile_image if tenant_user else None,
                        "emirate_id":tenant.emirate_id,
                        "country":tenant_user.country if tenant_user else None, 
                        "address": tenant.address

                    })

                owner_details = OwnerDetails.objects.filter(user=prop.owner).first()
                owner_user = prop.owner

                owner_info = {
                    "owner_name": owner_details.full_name if owner_details else "N/A",
                    "contact_number": owner_details.mobile_number if owner_details else "N/A",
                    "trade_license": owner_details.trade_license_number if owner_details else "N/A",
                    "email": owner_user.email if owner_user else None,
                    "profile_image": owner_user.profile_image if owner_user else None,

                    "emirate_id": owner_details.emirate_id if owner_details else "N/A",
                    "uae_residence_visa": owner_details.uae_residence_visa if owner_details else "N/A",
                    
                    "owner_code":owner_details.owner_number if owner_details else "N/A",
                   

                }


                pmc = prop.property_manager
                pmc_info = {
                    "company_name": pmc.company_name if pmc else "N/A",
                    "company_code": pmc.company_code if pmc else "N/A",
                    "rera_license": pmc.rera_license if pmc else "N/A",
                    "contact_number": pmc.phone_number if pmc else "N/A",
                    "email": pmc.user.email if pmc and pmc.user else None,
                    "profile_image": pmc.user.profile_image if pmc and pmc.user else None,
                }

     
                commercial = getattr(prop, "commercial", None)

                commercial_info = {
                    "rent": commercial.rent if commercial else None,
                    "security_deposit": commercial.security_deposit if commercial else None,
                    "booking_amount": commercial.booking_amount if commercial else None,
                    "maintenance_charges": commercial.maintenance_charges if commercial else None,
                    "cycle": commercial.cycle if commercial else None,
                    "notice_period": commercial.notice_period if commercial else None,
                    "commission_percent": commercial.commission_percent if commercial else None,
                }

        
                rental_status_display = (
                    constants.RENTAL_NOT_AVAILABLE
                    if prop.is_occupied
                    else constants.RENTAL_AVAILABLE
                )
                images_qs = PropertyImages.objects.filter(property=prop).order_by("-id")
                images_data = []
                for img in images_qs:
                    url = img.image_path
                    file_name = img.file_name
                    img_type = img.image_type
                    base64_data = fetch_s3_presigned_url(url, file_name=file_name)
                    images_data.append({
                                         "file_name": file_name,
                                         "image_url": url,
                                         "data": base64_data,
                                          "type": img_type,
                         "id": img.id,})

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
                    "commercial_info": commercial_info,
                    "images": images_data
                })

            if property_id:
                pagination_meta = None
            else:
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
                message=constants.TENANT_DETAILS_NOT_FOUND,
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



@is_request_authenticated
def lease_property_view(request):

    user = request.user
    try:

        if request.method == "POST":
            body = json.loads(request.body)
            lease_property_id = body.get("lease_property_id")
            lease_tenant_id = body.get("lease_tenant_id")
            

        
            if not lease_property_id or not lease_tenant_id:
                return prepare_response(
                    message=constants.LEASE_PROPERTY_TENANT_REQUIRED,
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            lease_property = PropertyDetails.objects.get(id=lease_property_id)
            tenant = TenantDetails.objects.get(id=lease_tenant_id)
            # created_by = PropertyManagerCompanyDetails.objects.get(id=created_by_id)

           
            if not lease_property.owner:
                return prepare_response(message=constants.PROPERTY_NO_OWNER_ASSIGNED, status=status.HTTP_400_BAD_REQUEST)
            owner = OwnerDetails.objects.get(user=lease_property.owner) 

         
            lease_start_date = safe_epoch_to_datetime(body.get("lease_start_date"))
            lease_end_date = safe_epoch_to_datetime(body.get("lease_end_date"))
            if not lease_start_date or not lease_end_date:
                return prepare_response(message="Invalid lease start or end date", status=status.HTTP_400_BAD_REQUEST)

            lease_grace_start_date = safe_epoch_to_datetime(body.get("lease_grace_start_date")) if body.get("lease_grace_start_date") else None
            lease_grace_end_date = safe_epoch_to_datetime(body.get("lease_grace_end_date")) if body.get("lease_grace_end_date") else None

            lease_remarks = body.get("lease_remarks", "")
            lease_status = body.get("lease_status", "DRAFT")

            created_by = PropertyManagerCompanyDetails.objects.filter(user=request.user).first()
            if not created_by:
                return prepare_response(
                    message=constants.LOGGED_IN_USER_NOT_PM,
                    status=status.HTTP_400_BAD_REQUEST
                    )
             

           
            lease = LeasePropertyDetails.objects.create(
                lease_property=lease_property,
                lease_tenant=tenant,
                owner=owner,
                created_by=created_by,
                lease_start_date=lease_start_date,
                lease_end_date=lease_end_date,
                lease_grace_start_date=lease_grace_start_date,
                lease_grace_end_date=lease_grace_end_date,
                lease_remarks=lease_remarks,
                lease_status=lease_status,
                step_status="LEASE_DETAILS"
            )

            return prepare_response(
                content={"id": lease.id},
                message=constants.LEASE_CREATED,
                status=status.HTTP_201_CREATED
            )

        elif request.method == "PUT":
            body = json.loads(request.body)
            lease_id = body.get("lease_id")
            if not lease_id:
                return prepare_response(message=constants.LEASE_ID_REQUIRED, status=status.HTTP_400_BAD_REQUEST)

            lease = LeasePropertyDetails.objects.get(id=lease_id)

          
            lease_property_id = body.get("lease_property_id")
            lease_tenant_id = body.get("lease_tenant_id")
            # lease_tenant_id = body.get("lease_tenant_id")
            # created_by_id = body.get("created_by_id")

            if lease_property_id:
                lease_property = PropertyDetails.objects.get(id=lease_property_id)
                lease.lease_property = lease_property

                if not lease_property.owner:
                    return prepare_response(message=constants.PROPERTY_NO_OWNER_ASSIGNED, status=status.HTTP_400_BAD_REQUEST)
                lease.owner = OwnerDetails.objects.get(user=lease_property.owner)

            if lease_tenant_id:
                 lease.lease_tenant = TenantDetails.objects.get(id=lease_tenant_id)
                           
            created_by = PropertyManagerCompanyDetails.objects.filter(user=request.user).first()
            if not created_by:
                return prepare_response(
                    message=constants.LOGGED_IN_USER_NOT_PM,
                    status=status.HTTP_400_BAD_REQUEST
                    )
       
            lease_start_date = safe_epoch_to_datetime(body.get("lease_start_date"))
            lease_end_date = safe_epoch_to_datetime(body.get("lease_end_date"))
            lease_grace_start_date = safe_epoch_to_datetime(body.get("lease_grace_start_date"))
            lease_grace_end_date = safe_epoch_to_datetime(body.get("lease_grace_end_date"))

            if lease_start_date: lease.lease_start_date = lease_start_date
            if lease_end_date: lease.lease_end_date = lease_end_date
            if lease_grace_start_date: lease.lease_grace_start_date = lease_grace_start_date
            if lease_grace_end_date: lease.lease_grace_end_date = lease_grace_end_date


            lease.lease_remarks = body.get("lease_remarks", lease.lease_remarks)
            lease.lease_status = body.get("lease_status", lease.lease_status)
            lease.save()

            return prepare_response(
                content={"lease_id": lease.id},
                message=constants.LEASE_UPDATED,
                status=status.HTTP_200_OK
            )

        elif request.method == "GET":
            
            lease_id = request.GET.get("lease_id")
            search = request.GET.get("search", "")
            page = int(request.GET.get("page", 1))
            limit = int(request.GET.get("limit", 10))

            if  lease_id:
                lease = LeasePropertyDetails.objects.get(id=lease_id)
                lease_data={
                    "id": lease.id,
                "lease_property":{"key":lease.lease_property.id , "value":lease.lease_property.property_name} ,
                "lease_tenant":{"key":lease.lease_tenant.id , "value":lease.lease_tenant.full_name} , 
                "owner_id": lease.owner.id if lease.owner else None,
                "owner_name": f"{lease.owner.full_name}" if lease.owner else None,
                "created_by_id": lease.created_by.id if lease.created_by else None,
                "lease_start_date": int(lease.lease_start_date.timestamp() * 1000) if lease.lease_start_date else None,
                "lease_end_date": int(lease.lease_end_date.timestamp() * 1000) if lease.lease_end_date else None,
                "lease_grace_start_date": int(lease.lease_grace_start_date.timestamp() * 1000) if lease.lease_grace_start_date else None,
                "lease_grace_end_date": int(lease.lease_grace_end_date.timestamp() * 1000) if lease.lease_grace_end_date else None,
                "lease_remarks": lease.lease_remarks,
                # "lease_status": lease.lease_status,
                "step_choice":lease.step_status

                }
                return prepare_response(content=lease_data , message=constants.LEASE_FETCHED, status=status.HTTP_200_OK)
            else:

                pagination_meta = None

                pmc = user.property_manager_details.first()

                if user.user_type == "OWNER":
                    owner = OwnerDetails.objects.filter(user=user).first()
                    if not owner:
                        return prepare_response(message=constants.OWNER_NOT_FOUND, status=status.HTTP_400_BAD_REQUEST)
                    leases = LeasePropertyDetails.objects.filter(owner=owner)

                else:
                    pmc = user.property_manager_details.first()
                    if not pmc:
                        return prepare_response(message=constants.PMC_NOT_FOUND, status=status.HTTP_400_BAD_REQUEST)
                    leases = LeasePropertyDetails.objects.filter(created_by=pmc)

   


                if search:
                    leases = leases.filter(
                    Q(lease_property__property_name__icontains=search) |
                     Q(lease_tenant__full_name__icontains=search)
                                          )
                leases = leases.order_by("-id")
                total_count = leases.count()
                start = (page - 1) * limit
                end = start + limit
                leases = leases[start:end]

                response_data = []
                for lease in leases:
                        pdf_url = None
                        response_data.append({
                              "id": lease.id,
                              "property_name": lease.lease_property.property_name,
                              "Property_code":lease.lease_property.property_code,
                              "lease_status": lease.lease_status,
                              "lease_start_date": int(lease.lease_start_date.timestamp()*1000),
                              "lease_end_date": int(lease.lease_end_date.timestamp()*1000),
                              "lease_pdf_url": pdf_url,

                                "tenant": {
                                "name": f"{lease.lease_tenant.user.first_name} {lease.lease_tenant.user.last_name}".strip(),
                                "profile_image": lease.lease_tenant.user.profile_image,
                                 "profile_image_type": lease.lease_tenant.user.profile_image_type,
                                             }
                                             })
                pagination_meta = {
                         "current_page": page,
                         "limit": limit,
                         "total_records": total_count,
                         "total_pages": (total_count + limit - 1) // limit,
                     }
                
                return prepare_response(
                        content=response_data,
                        message=constants.LEASE_LIST_FETCHED,
                        status=status.HTTP_200_OK,
                        pagination=pagination_meta,
                    )


        else:
            return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    except PropertyDetails.DoesNotExist:
        return prepare_response(message=constants.PROPERTY_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
    except TenantDetails.DoesNotExist:
        return prepare_response(message=constants.TENANT_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
    except PropertyManagerCompanyDetails.DoesNotExist:
        return prepare_response(message=constants.CREATED_BY_USER_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
    except OwnerDetails.DoesNotExist:
        return prepare_response(message=constants.OWNER_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
    except LeasePropertyDetails.DoesNotExist:
        return prepare_response(message=constants.LEASE_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return prepare_response(message=str(e), status=status.HTTP_400_BAD_REQUEST)



    



@is_request_authenticated
def lease_commercials_view(request):
    try:
        if request.method == "POST":
            
            body = json.loads(request.body)
            lease_id = body.get("lease_id")
            if not lease_id:
                return prepare_response(message=constants.LEASE_ID_REQUIRED, status=status.HTTP_400_BAD_REQUEST)

            lease = LeasePropertyDetails.objects.get(id=lease_id)

            annual_amount = body.get("annual_amount")
            rent = body.get("rent")
            if annual_amount is None or rent is None:
                return prepare_response(message=constants.ANNUAL_AMOUNT_RENT_REQUIRED, status=status.HTTP_400_BAD_REQUEST)

            commercial = LeaseCommercials.objects.create(
                lease=lease,
                annual_amount=annual_amount,
                rent=rent,
                actual_annual_amount= safe_decimal(body.get("actual_annual_amount")),
                booking_amount= safe_decimal(body.get("booking_amount")),
                security_deposit= safe_decimal(body.get("security_deposit")),
                maintenance_charges= safe_decimal (body.get("maintenance_charges")),
                commission_percentage= safe_decimal(body.get("commission_percentage")),
                notice_period=body.get("notice_period"),
                discount=safe_decimal(body.get("discount"))
            )
            lease.step_status="LEASE_COMMERCIALS"
            lease.save()

            return prepare_response(
                message=constants.LEASE_COMMERCIALS_CREATED,
                content={"commercial_id": commercial.id},
                status=status.HTTP_201_CREATED
            )

        elif request.method == "PUT":
        
            body = json.loads(request.body)
            lease_id = body.get("lease_id")
            if not lease_id:
                return prepare_response(message=constants.LEASE_ID_REQUIRED, status=status.HTTP_400_BAD_REQUEST)
            try:
                commercial = LeaseCommercials.objects.get(lease_id=lease_id)
            except LeaseCommercials.DoesNotExist:
                return prepare_response(
                    message=constants.NO_LEASE_COMMERCIALS_FOR_LEASE,
                    status=status.HTTP_404_NOT_FOUND
                                 )

         
            for field in ["annual_amount", "rent", "actual_annual_amount", "booking_amount",
                          "security_deposit", "maintenance_charges", "commission_percentage",
                          "notice_period", "discount"]:
                if field in body:
                    setattr(commercial, field, body[field])


            commercial.save()

            return prepare_response(
                message=constants.LEASE_COMMERCIALS_UPDATED,
                content={"lease_id": lease_id},
                status=status.HTTP_200_OK
            )

        elif request.method == "GET":
      
            commercial_id = request.GET.get("commercial_id")
            lease_id = request.GET.get("lease_id")

            if commercial_id:
                commercial = LeaseCommercials.objects.get(id=commercial_id)
                data = {
                    "commercial_id": commercial.id,
                    "id": commercial.lease.id,
                    "annual_amount": commercial.annual_amount,
                    "rent": commercial.rent,
                    "actual_annual_amount": commercial.actual_annual_amount,
                    "booking_amount": commercial.booking_amount,
                    "security_deposit": commercial.security_deposit,
                    "maintenance_charges": commercial.maintenance_charges,
                    "commission_percentage": commercial.commission_percentage,
                    "notice_period": commercial.notice_period,
                    "discount": commercial.discount
                }
                return prepare_response(content=data, message=constants.LEASE_COMMERCIALS_FETCHED, status=status.HTTP_200_OK)

            elif lease_id:
                commercials = LeaseCommercials.objects.filter(lease_id=lease_id).first()
                lease = commercials.lease
                data = {
                    "commercial_id": commercials.id,
                    "id": commercials.lease.id,
                    "annual_amount": commercials.annual_amount,
                    "rent": commercials.rent,
                    "actual_annual_amount": commercials.actual_annual_amount,
                    "booking_amount": commercials.booking_amount,
                    "security_deposit": commercials.security_deposit,
                    "maintenance_charges": commercials.maintenance_charges,
                    "commission_percentage": commercials.commission_percentage,
                    "notice_period": commercials.notice_period,
                    "discount": commercials.discount,
                    "step_choice": lease.step_status

                } 
                return prepare_response(content= data, message=constants.LEASE_COMMERCIALS_LIST_FETCHED, status=status.HTTP_200_OK)
            else:
                return prepare_response(message=constants.COMMERCIAL_OR_LEASE_ID_REQUIRED, status=status.HTTP_400_BAD_REQUEST)

        else:
            return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    except LeasePropertyDetails.DoesNotExist:
        return prepare_response(message=constants.LEASE_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
    except LeaseCommercials.DoesNotExist:
        return prepare_response(message=constants.LEASE_COMMERCIALS_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return prepare_response(message=str(e), status=status.HTTP_400_BAD_REQUEST)




def lease_ejari_documents_view(request):
    try:
        if request.method == "GET":
            lease_id = request.GET.get("lease_id")

            if not lease_id:
                return prepare_response(message=constants.LEASE_ID_REQUIRED,status=status.HTTP_400_BAD_REQUEST)

            try:
                lease_obj = LeasePropertyDetails.objects.get(id=lease_id)
            except LeasePropertyDetails.DoesNotExist:
                return prepare_response(message=constants.INVALID_LEASE_ID, status=status.HTTP_404_NOT_FOUND)

            docs_qs = LeaseEjariUpload.objects.filter(lease_id=lease_id).order_by("-id")
            final_docs = []

            for doc in docs_qs:
                url = doc.file_path
                file_name = doc.file_name
                doc_type = doc.document_type

                base64_data = fetch_s3_presigned_url(url,file_name=file_name)

                final_docs.append({
                    "file_name": file_name,
                    "data": base64_data,
                    "type": doc_type,
                    "id": doc.id,
                })

            return prepare_response(
                message=constants.LEASE_EJARI_DOCS_FETCHED,
                content={
                    "documents": final_docs,
                    "lease_id": lease_id,
                    "step_choice": lease_obj.step_status
                },
                status=status.HTTP_200_OK
            )

        if request.method == "POST":
            body = json.loads(request.body)
            lease_id = body.get("lease_id")
            documents = body.get("documents", [])

            if not lease_id:
                return prepare_response(message=constants.LEASE_ID_REQUIRED, status=status.HTTP_400_BAD_REQUEST)

            if not isinstance(documents, list) or not documents:
                return prepare_response(message="Documents must be a list", status=status.HTTP_400_BAD_REQUEST)

            try:
                lease_obj = LeasePropertyDetails.objects.get(id=lease_id)
            except LeasePropertyDetails.DoesNotExist:
                return prepare_response(message=constants.LEASE_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)

            uploaded_files = []

            for doc in documents:
                file_name = doc.get("file_name")
                base64_data = doc.get("data")
                doc_type = doc.get("type", "").upper()

                if not file_name or not base64_data:
                    return prepare_response(message=constants.MISSING_FILE_OR_DATA ,status=status.HTTP_400_BAD_REQUEST)

                object_name = f"lease_documents/{lease_id}/{file_name}"

                file_url = upload_file_to_s3_base64(base64_data, object_name)

                LeaseEjariUpload.objects.create(
                    lease=lease_obj,
                    file_name=file_name,
                    file_path=file_url,
                    document_type=doc_type
                )

                uploaded_files.append({
                    "file_name": file_name,
                    "file_url": file_url,
                    "type": doc_type,
                })

                lease_obj.step_status = "ATTACH_DOCUMENTS"
                lease_obj.save()

            return prepare_response(
                message=constants.LEASE_EJARI_DOCS_UPLOADED,
                content={"uploaded": uploaded_files},
                status=status.HTTP_200_OK
            )

        if request.method == "PUT":
            body = json.loads(request.body)
            lease_id = body.get("lease_id")
            documents = body.get("documents", [])

            if not lease_id:
                return prepare_response(message=constants.LEASE_ID_REQUIRED, status=status.HTTP_400_BAD_REQUEST)

            if not isinstance(documents, list):
                return prepare_response(message="Documents must be a list", status=status.HTTP_400_BAD_REQUEST)

            try:
                lease_obj = LeasePropertyDetails.objects.get(id=lease_id)
            except LeasePropertyDetails.DoesNotExist:
                return prepare_response(message=constants.LEASE_NOT_FOUND,status=status.HTTP_404_NOT_FOUND)

            updated_files = []

            for doc in documents:
                file_name = doc.get("file_name")
                base64_data = doc.get("data")
                doc_type = doc.get("type", "").upper()

                if not file_name or not base64_data:
                    return prepare_response(message=constants.MISSING_FILE_OR_DATA,status=status.HTTP_400_BAD_REQUEST)

                doc_obj, created = LeaseEjariUpload.objects.get_or_create(
                    lease=lease_obj,
                    file_name=file_name,
                    defaults={"document_type": doc_type}
                )

                object_name = f"lease_documents/{lease_id}/{file_name}"
                file_url = upload_file_to_s3_base64(base64_data, object_name)

                doc_obj.file_path = file_url
                doc_obj.document_type = doc_type
                doc_obj.save()

                updated_files.append({
                    "file_name": file_name,
                    "file_url": file_url,
                    "type": doc_type,
                    "status": "created" if created else "updated",
                })

            return prepare_response(
                message=constants.LEASE_EJARI_DOCS_UPDATED,
                content={"updated": updated_files},
                status=status.HTTP_200_OK
            )

        return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    except Exception as e:
        return prepare_response(message=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)





def generate_contract(request):
    if request.method != "POST":    
        return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    try:
        body = json.loads(request.body)

        template_id = body.get("template_id")
        lease_id = body.get("lease_id")
        values_dict = body.get("values")

        if not template_id or not lease_id or not values_dict:
            return prepare_response(
                message=constants.TEMPLATE_LEASE_VALUES_REQUIRED,
                status=status.HTTP_400_BAD_REQUEST
            )

        template = Template.objects.get(id=template_id)
        lease = LeasePropertyDetails.objects.get(id=lease_id)

        TemplateValues.objects.create(
            document_template=template,
            lease=lease,
            value=values_dict
        )

        template_path = template.template_path

        if os.path.isdir(template_path):
            return prepare_response(
                message=f"Template path is a folder, not a file: {template_path}",  
                status=status.HTTP_400_BAD_REQUEST
            )

        if not os.path.exists(template_path):
            return prepare_response(
                message=f"Template not found: {template_path}",
                status=status.HTTP_404_NOT_FOUND
            )

        with open(template_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        mapping = {}
        fields = TemplateFields.objects.filter(document_template=template)
        for field in fields:
            key = field.id_attribute or field.name_attribute  
            if key and key in values_dict:
                mapping[key] = values_dict[key]

        html_content = replace_placeholders(html_content, mapping)

        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"lease_{timestamp}.html"

        save_dir = os.path.join(settings.MEDIA_ROOT, "generated_templates")
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, filename)

        with open(save_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        pdf_filename = f"lease_{timestamp}.pdf"
        pdf_save_path = os.path.join(save_dir, pdf_filename)
        config = get_pdfkit_config()
        


        pdfkit.from_file(save_path, pdf_save_path, configuration=config)
        pdf_bytes = pdfkit.from_string(html_content, False, configuration=config)
        pdf_filename = f"lease_{timestamp}.pdf"
        s3_object_name = f"generated_templates/{pdf_filename}"
        pdf_s3_url = upload_file_to_s3_base64(pdf_bytes, s3_object_name)

     
        # pdf_relative_path = os.path.relpath(pdf_save_path, settings.MEDIA_ROOT).replace(os.sep, '/')
        # pdf_db_path = f"media/{pdf_relative_path}"

       
        relative_path = os.path.relpath(save_path, settings.MEDIA_ROOT).replace(os.sep, '/')
        db_path = f"/media/{relative_path}"

        file_url = f"{settings.MEDIA_URL}generated_templates/{filename}"
        new_template = Template.objects.create(
            name=f"User Lease Template {timestamp}",
            template_path=db_path,
            # pdf_path=pdf_s3_url,
            is_active=True,
            is_predefined=False
        )
        lease.pdf_path = pdf_s3_url
        lease.save()
        return prepare_response(
            message=constants.CONTRACT_GENERATED_SUCCESS,
            content={"file_url": file_url, "pdf_url": pdf_s3_url},
            status=status.HTTP_200_OK
        )
    except Exception as e:
        return prepare_response(message=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)



def get_template_fields(request):
    try:
        template_id = request.GET.get("template_id")
        if not template_id:
            return prepare_response(
                message=constants.TEMPLATE_ID_REQUIRED,
                status=status.HTTP_400_BAD_REQUEST
            )

        template = Template.objects.get(id=template_id)
        fields = TemplateFields.objects.filter(document_template=template)

        field_list = []
        for field in fields:
            field_list.append({
                "id_attribute": field.id_attribute,
                "name_attribute": field.name_attribute,
                "label": field.label_attribute,
                "html_tag": field.html_tag,
                "required": field.required,
                "min_value": field.min_value,
                "max_value": field.max_value,
                "min_length": field.min_length,
                "max_length": field.max_length,
                "pattern": field.pattern,
                "predefined_value": field.predefined_value,
            })

        return prepare_response(
            content={
                "template_id": template.id,
                "template_name": template.name,
                "template_path": template.template_path,
                "fields": field_list
            },
            message=constants.TEMPLATE_FIELDS_FETCHED,
            status=status.HTTP_200_OK
        )

    except Template.DoesNotExist:
        return prepare_response(
            message=constants.INVALID_TEMPLATE_ID,
            status=status.HTTP_404_NOT_FOUND
        )

    except Exception as e:
        return prepare_response(
            message=str(e),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



@is_request_authenticated
def get_lease_pdf(request):
    lease_id = request.GET.get("lease_id")
    if not lease_id:
        return prepare_response(
            message=constants.LEASE_ID_REQUIRED,
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        lease = LeasePropertyDetails.objects.get(id=lease_id)

        if not lease.pdf_path:
            return prepare_response(
                message=constants.PDF_NOT_AVAILABLE_FOR_LEASE,
                status=status.HTTP_404_NOT_FOUND
            )

        presigned_url = fetch_s3_presigned_url(
            lease.pdf_path,
            file_name=f"lease_{lease_id}.pdf"
        )
        if not presigned_url:
            return prepare_response(
                message=constants.FAILED_TO_GENERATE_PRESIGNED_URL,
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return prepare_response(
            message=constants.PDF_URL_FETCHED_SUCCESSFULLY ,
            content={"pdf_url": presigned_url},
            status=status.HTTP_200_OK
        )

    except LeasePropertyDetails.DoesNotExist:
        return prepare_response(
            message=constants.LEASE_NOT_FOUND,
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return prepare_response(
            message=str(e),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# -----------------------------------------------------Export All CSV APIs-------------------------------------------------------- 

# property/details/list/view/
@is_request_authenticated
def export_property_csv(request):
    if request.method != "GET":
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        user = request.user
        property_id = request.GET.get("property_id")

        properties = PropertyDetails.objects.select_related(
            "owner",
            "property_manager",
            "commercial"
        ).prefetch_related(
            Prefetch("tenant_details", queryset=TenantDetails.objects.select_related("user"))
        ).distinct()

        if user.user_type == constants.OWNER:
            properties = properties.filter(owner=user)

        elif user.user_type == constants.TENANT:
            properties = properties.filter(tenant_details__user=user)

        elif user.user_type == constants.PROPERTY_MANAGER:
            properties = properties.filter(property_manager__user=user)

        if property_id:
            properties = properties.filter(id=property_id)

        export_data = []

        if user.user_type == constants.TENANT:
            field_names = ["Property Name", "Owner Name", "Tenancy Status", "Bedrooms", "PMC Name"]

        elif user.user_type == constants.OWNER:
            field_names = ["Property Name", "Tenant Name", "Agreement Expiry", "Dimension", "PMC Name"]

        else:  # PMC
            field_names = ["Property ID", "Tenant Name", "Owner Name", "Tenancy Status"]

        for prop in properties:
            owner_details = OwnerDetails.objects.filter(user=prop.owner).first()
            owner_name = owner_details.full_name if owner_details else "N/A"

            pmc = prop.property_manager
            pmc_name = pmc.company_name if pmc else "N/A"

            tenants = prop.tenant_details.all()
            tenancy_status = "Occupied" if prop.is_occupied else "Vacant"

            if user.user_type == constants.TENANT:
                export_data.append({
                    "Property Name": prop.property_name,
                    "Owner Name": owner_name,
                    "Tenancy Status": tenancy_status,
                    "Bedrooms": prop.bedrooms or "N/A",
                    "PMC Name": pmc_name
                })

            elif user.user_type == constants.OWNER:
                if tenants.exists():
                    for tenant in tenants:
                        commercial = prop.commercial
                        export_data.append({
                            "Property Name": prop.property_name,
                            "Tenant Name": tenant.full_name,
                            "Agreement Expiry": commercial.notice_period if commercial else "N/A",
                            "Dimension": prop.area_of_property or "N/A",
                            "PMC Name": pmc_name
                        })
                else:
                    export_data.append({
                        "Property Name": prop.property_name,
                        "Tenant Name": "N/A",
                        "Agreement Expiry": "N/A",
                        "Dimension": prop.area_of_property or "N/A",
                        "PMC Name": pmc_name
                    })

            else:  
                if tenants.exists():
                    for tenant in tenants:
                        export_data.append({
                            "Property ID": prop.id,
                            "Tenant Name": tenant.full_name,
                            "Owner Name": owner_name,
                            "Tenancy Status": tenancy_status
                        })
                else:
                    export_data.append({
                        "Property ID": prop.id,
                        "Tenant Name": "N/A",
                        "Owner Name": owner_name,
                        "Tenancy Status": tenancy_status
                    })

        return export_to_csv("property_export", field_names, export_data)

    except Exception as e:
        return prepare_response(
            message=f"Error exporting CSV: {str(e)}",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )




# staff/view/
@is_request_authenticated
def export_staff_csv(request):
    if request.method != "GET":
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        search = request.GET.get("search", "")

    
        staff_qs = StaffDetails.objects.select_related("staff_role", "user") \
            .prefetch_related("assigned_properties").all()

  
        if search:
            staff_qs = staff_qs.filter(
                Q(staff_name__icontains=search) |
                Q(staff_id__icontains=search) |
                Q(phone_number__icontains=search)
            )


        field_names = [
            "Staff ID",
            "Staff Name",
            "Phone Number",
            "Staff Role",
            "User Email",
            "Total Assigned Properties"
        ]

        export_data = []

        for staff in staff_qs:
            export_data.append({
                "Staff ID": staff.staff_id,
                "Staff Name": staff.staff_name,
                "Phone Number": staff.phone_number,
                "Staff Role": staff.staff_role.name if staff.staff_role else "N/A",
                "User Email": staff.user.email if staff.user else "N/A",
                "Total Assigned Properties": staff.assigned_properties.count()
            })

        return export_to_csv("staff_data_export", field_names, export_data)

    except Exception as e:
        return prepare_response(
            message=f"Error exporting CSV: {str(e)}",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



# /tenant/list/view
# @is_request_authenticated
def export_tenant_csv(request):
    if request.method != "GET":
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        search = request.GET.get("search", "")
      
        tenants_qs = TenantDetails.objects.select_related("property", "lease_property_details").all()
        if search:
            tenants_qs = tenants_qs.filter(full_name__icontains=search)

    
        field_names = [
            "Tenant ID",
            "Full Name",
            "Tenant Number",
            "Mobile Number",
            "Property Assigned",
            "Rental Agreement"
        ]

        export_data = []

        for tenant in tenants_qs:
            export_data.append({
                "Tenant ID": tenant.id,
                "Full Name": tenant.full_name,
                "Tenant Number": tenant.tenant_number,
                "Mobile Number": tenant.mobile_number,
                "Property Assigned": tenant.property.property_name if tenant.property else "N/A",
                "Rental Agreement": "N/A",
            })

        return export_to_csv("tenant_data_export", field_names, export_data)

    except Exception as e:
        return prepare_response(
            message=f"Error exporting CSV: {str(e)}",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )





# /owner/details/list/view/
@is_request_authenticated
def export_owner_csv(request):
    if request.method != "GET":
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    try:
        owners_qs = OwnerDetails.objects.all().select_related("user")
        field_names = [
            "Owner Name",
            "Code",
            "Contact Number",
            "Properties",
            "Email Address"
        ]
        export_data = []
        for owner in owners_qs:
            user = owner.user
            properties = PropertyDetails.objects.filter(owner=user).values_list("property_name", flat=True) if user else []
            properties_str = ", ".join(properties)  

            export_data.append({
                "Owner Name": owner.full_name,
                "Code": owner.owner_number,
                "Contact Number": owner.mobile_number,
                "Properties": f"{properties_str} ({len(properties)})" if properties else "None",
                "Email Address": user.email if user else "N/A"
            })
        return export_to_csv("owners_data", field_names, export_data)

    except Exception as e:
        return prepare_response(
            message=f"Error exporting CSV: {str(e)}",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



# pmc/owner/view/list/
@is_request_authenticated
def export_pmc_csv(request):
    if request.method != "GET":
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    try:
        user = request.user
        search = request.GET.get("search", "").strip()

        pmc_qs = PropertyManagerCompanyDetails.objects.filter(
            properties_managed__owner=user
        ).distinct()

        if search:
            pmc_qs = pmc_qs.filter(
                Q(company_name__icontains=search)
                | Q(company_code__icontains=search)
                | Q(company_address__icontains=search)
            )

        field_names = [
            "PMC Name",
            "PMC Code",
            "Properties Handled",
            "Tenancy Ratio",
            "Address"
        ]

        export_data = []
        for p in pmc_qs:
            properties = PropertyDetails.objects.filter(property_manager=p, owner=user)
            total_properties = properties.count()
            occupied = properties.filter(is_occupied=True).count()
            vacant = total_properties - occupied

            export_data.append({
                "PMC Name": p.company_name,
                "PMC Code": p.company_code,
                "Properties Handled": f"{total_properties} Property",
                "Tenancy Ratio": f"{occupied}:{vacant}",
                "Address": p.company_address,
            })

        return export_to_csv("pmc_data", field_names, export_data)

    except Exception as e:
        return prepare_response(
            message=f"Error exporting CSV: {str(e)}",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



# /lease/export/csv/
@is_request_authenticated
def export_lease_tenecy_csv(request):
    if request.method != "GET":
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        user = request.user
        search = request.GET.get("search", "").strip()


        if user.user_type == "OWNER":
            owner = OwnerDetails.objects.filter(user=user).first()
            if not owner:
                return prepare_response(message=constants.OWNER_NOT_FOUND, status=status.HTTP_400_BAD_REQUEST)
            leases = LeasePropertyDetails.objects.filter(owner=owner)

        else: 
            pmc = user.property_manager_details.first()
            if not pmc:
                return prepare_response(message=constants.PMC_NOT_FOUND, status=status.HTTP_400_BAD_REQUEST)
            leases = LeasePropertyDetails.objects.filter(created_by=pmc)

        
        if search:
            leases = leases.filter(
                Q(lease_property__property_name__icontains=search) |
                Q(lease_tenant__full_name__icontains=search)
            )

        field_names = [
            "Property Code",
            "Property Name",
            "Tenant Name",
            "Lease Status",
            "Lease Start Date",
            "Lease End Date"
        ]

        export_data = []
        for l in leases:
            tenant_name = f"{l.lease_tenant.user.first_name} {l.lease_tenant.user.last_name}".strip()

            export_data.append({
                "Property Code": l.lease_property.property_code,
                "Property Name": l.lease_property.property_name,
                "Tenant Name": tenant_name,
                "Lease Status": l.lease_status,
                "Lease Start Date": l.lease_start_date.strftime("%d-%m-%Y"),
                "Lease End Date": l.lease_end_date.strftime("%d-%m-%Y"),
            })

        return export_to_csv("lease_data", field_names, export_data)

    except Exception as e:
        return prepare_response(
            message=f"Error exporting CSV: {str(e)}",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



