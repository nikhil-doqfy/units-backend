
from django.shortcuts import get_object_or_404
from django.db import IntegrityError, transaction
from user_service.models import UserProfile,Documents,OwnerDocumentsMapping,StaffDocumentsMapping,CompanyUserDocumentsMapping,TenantDocumentsMapping,PropertyUnitDetails,Property,Company,PMStaffCompanyMapping,PropertyImages ,PropertyDocumentsMapping,Country, State, City
from property_management.models import LeasePropertyDetails 
from utilities.decorator import is_request_authenticated
import json
from utilities.helper_functions import upload_file_to_s3_base64,fetch_s3_file_as_base64, prepare_response, logger,send_ses_email,safe_decimal ,safe_epoch_to_datetime ,replace_placeholders ,fetch_s3_presigned_url ,export_to_csv ,datetime_to_epoch_millis,get_pdfkit_config,generate_property_code ,fetch_s3_presigned_url_for_download
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
from property_management import settings
import os
from datetime import datetime
import datetime
import re
import pdfkit
import platform
from django.http import FileResponse, Http404
from property_management.utils import get_full_property_data,get_full_user_data,create_and_send_invitation,serialize_lease
import math



@is_request_authenticated
def serve_media(request, path):
    file_path = os.path.join(settings.MEDIA_ROOT, path)
    response = FileResponse(open(file_path, 'rb'))
    return response


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

     
        if option_type == "COUNTRY":
            countries = Country.objects.all()
            content["country"] = [{"key": c.id, "value": c.name} for c in countries]

        elif option_type == "STATE":
            country_id = request.GET.get("country_id")
            if not country_id:
                content["state"] = []
            else:
                states = State.objects.filter(country_id=country_id)
                content["state"] = [{"key": s.id, "value": s.name} for s in states]
        elif option_type == "CITY":
            state_id = request.GET.get("state_id")
            if not state_id:
                content["city"] = []
            else:
                cities = City.objects.filter(state_id=state_id)
                content["city"] = [{"key": c.id, "value": c.name} for c in cities]

        else:
            content[option_type] = []

    return prepare_response(
        content=content,
        message=constants.DROPDOWN_DATA_FETCHED_SUCEESS,
        status=status.HTTP_200_OK
    )




@is_request_authenticated
def property_table_view(request):
    user = request.user 
    search = request.GET.get("search", "").strip()
    page = int(request.GET.get("page", 1))
    limit = int(request.GET.get("limit", 10))
    property_id = request.GET.get("property_id")

    if property_id:
        full_data, error = get_full_property_data(property_id)
        if error:
            return prepare_response(message=error, status=404)
        return prepare_response(content=full_data, message="Property details fetched successfully", status=200)


    if user.user_role == constants.OWNER:
        properties_qs = PropertyUnitDetails.objects.filter(owner=user)

        properties_qs = properties_qs.prefetch_related(
            Prefetch("lease_details", queryset=LeasePropertyDetails.objects.select_related("tenant"))
        )


    elif user.user_role == constants.COMPANY_USER:
        company = Company.objects.filter(company_user=user).first()
        if not company:
            return prepare_response(
                message="Company not found for this user",
                status=400
            )
        properties_qs = PropertyUnitDetails.objects.filter(company=company).select_related("owner").prefetch_related(
            Prefetch("lease_details", queryset=LeasePropertyDetails.objects.select_related("tenant"))
        )


    elif user.user_role == constants.TENANT:
        lease_qs = LeasePropertyDetails.objects.filter(tenant=user).select_related(
            "lease_property__owner",
            "lease_property__company",
            "lease_property__property"
        )

        properties_data = []
        for lease in lease_qs:
            prop_unit = lease.lease_property
            properties_data.append({
                "property_id": prop_unit.id,
                "property_name": prop_unit.property.property_name if prop_unit.property else None,
                "owner_name": prop_unit.owner.user.email if prop_unit.owner else None,
                "tenancy_status": "Occupied" if prop_unit.is_occupied else "Available",
                "dimension": prop_unit.area_of_property,
                "company_name": prop_unit.company.company_name if prop_unit.company else None,
            })
        return prepare_response(
            content=properties_data,
            message="Tenant properties fetched successfully",
            status=200
        )

    else:
        return prepare_response(
            message="Unauthorized user role",
            status=403
        )

    if search:
        properties_qs = properties_qs.filter(
            Q(property_unit_name__icontains=search) |
            Q(property__property_name__icontains=search) |
            Q(owner__user__email__icontains=search) |
            Q(company__company_name__icontains=search) |
            Q(lease_details__tenant__user__email__icontains=search)
        ).distinct()


    paginator = Paginator(properties_qs, limit)
    try:
        properties_page = paginator.page(page)
    except EmptyPage:
        properties_page = paginator.page(paginator.num_pages)


    data = []
    for prop in properties_page:
        tenants = [lease.tenant.user.email for lease in prop.lease_details.all()]
        data.append({
            "property_id": prop.id,
            "property_name": prop.property.property_name if prop.property else None,
            "owner_name": prop.owner.user.email if prop.owner else None,
            "company_name": prop.company.company_name if prop.company else None,
            "tenants": tenants,
            "tenancy_status": "Occupied" if prop.is_occupied else "Available",
            "dimension": prop.area_of_property
        })

    pagination_meta = {
        "current_page": properties_page.number,
        "limit": limit,
        "total_records": paginator.count,
        "total_pages": paginator.num_pages
    }

    return prepare_response(
        content=data,
        message="Properties fetched successfully",
        pagination=pagination_meta,
        status=200
    )



@is_request_authenticated
def save_property(request):
    user_profile = request.user
    if request.method == "GET":
        try:
            property_id = request.GET.get("property_id")
            if not property_id:
                return prepare_response(
                    message=constants.PROPERTY_ID_REQUIRED,
                    status=status.HTTP_400_BAD_REQUEST
                )

            prop = PropertyUnitDetails.objects.filter(id=property_id).first()
            if not prop:
                return prepare_response(
                    message=constants.PROPERTY_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )

            property_type_options = dict(constants.PROPERTY_TYPE_CHOICES)
            property_type_data = {
                "key": prop.property_type_options,
                "value": property_type_options.get(prop.property_type_options)
            }

            content = {
                "id": prop.id,
                "property_unit_name": prop.property_unit_name,
                "land_dm_no": prop.land_dm_no,
                "area_of_property": prop.area_of_property,
                "no_of_parking": prop.no_of_parking,
                "bedrooms": prop.bedrooms,
                "balcony": prop.balcony,
                "plot_no": prop.plot_no,
                "area_unit": prop.area_unit,
                "property_code": prop.property_code,
                "property_type": property_type_data,
                "land_area": prop.land_area,
                "makani_no": prop.makani_no,
                "dewa_no": prop.dewa_no,
                "apartment_no": prop.apartment_no,
                "apartment_floor_no": prop.apartment_floor_no,
                "no_of_floors": prop.no_of_floors,
                "step_status": prop.step_status,
                "commercial_details": {
                    "rent": prop.rent,
                    "security_deposit": prop.security_deposit,
                    "booking_amount": prop.booking_amount,
                    "maintenance_charges": prop.maintenance_charges,
                    "cycle": prop.cycle,
                    "notice_period": prop.notice_period,
                    "commission_percent": prop.commission_percent,
                },
                "owner_id": prop.owner.id if prop.owner else None
            }

            return prepare_response(content=content, status=status.HTTP_200_OK)

        except Exception as e:
            return prepare_response(
                message={"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    elif request.method == "PUT":
        try:
            current_user = request.user
            data = json.loads(request.body)
            property_id = data.get("property_id")
            if not property_id:
                return prepare_response(
                    message=constants.PROPERTY_ID_REQUIRED,
                    status=status.HTTP_400_BAD_REQUEST
                )

            prop = PropertyUnitDetails.objects.filter(id=property_id).first()
            if not prop:
                return prepare_response(
                    message=constants.PROPERTY_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )

            basic_fields = [
            "property_unit_name", "land_dm_no", "area_of_property",
            "no_of_parking", "makani_no", "dewa_no",
            "land_area", "apartment_no", "bedrooms", "balcony",
            "plot_no", "area_unit", "land_area_unit",
            "apartment_floor_no", "no_of_floors", "property_type_options"
             ]

            for field in basic_fields:
                if field in data:
                    value = data.get(field)
                    if value is not None:
                        setattr(prop, field, value)
                    
            if "property_type" in data and data["property_type"]:
                prop.property_type = data["property_type"]
                  
            commercial_fields = [
                "rent", "security_deposit", "booking_amount",
                "maintenance_charges", "cycle", "notice_period", "commission_percent"
            ]
            for field in commercial_fields:
                if field in data:
                    setattr(prop, field, data[field])

            
            if current_user.user_role == constants.COMPANY_USER:
                owner_id = data.get("owner_id")
                if owner_id:
                    owner_obj = UserProfile.objects.filter(
                    id=owner_id, user_role=constants.OWNER
                ).first()
                    if owner_obj:
                        prop.owner = owner_obj

                if hasattr(current_user, "company"):
                    prop.company = current_user.company
            
            elif current_user.user_role == constants.OWNER:
                 company_id = data.get("company_id")
                 if company_id:
                     company_obj = Company.objects.filter(id=company_id).first()
                     if company_obj:
                         prop.company = company_obj
                 prop.owner = current_user
            prop.save()
            return prepare_response(
                message=constants.PROPERTY_UPDATE_SUCCESS,
                content={"property_id": prop.id},
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return prepare_response(
                message={"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    elif request.method == "POST":
        try:
            data = json.loads(request.body)
            property_unit_name = data.get("property_unit_name")
            land_dm_no = data.get("land_dm_no")
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
            apartment_floor_no = data.get("apartment_floor_no")
            no_of_floors = data.get("no_of_floors")
            property_code = generate_property_code()
            if user_profile.user_role == constants.OWNER:
                owner = user_profile
                company = None
            elif user_profile.user_role == constants.COMPANY_USER:
                company = Company.objects.filter(company_user=user_profile).first()
                if not company:
                    return prepare_response(
                        message=constants.COMPANY_NOT_FOUND,
                        status=status.HTTP_400_BAD_REQUEST
                    )
                owner = None
            else:
                return prepare_response(
                    message=constants.UNAUTHORIZED_TO_CREATE_PROPERTY,
                    status=status.HTTP_403_FORBIDDEN
                )
            parent_property = Property.objects.create(
                property_name=property_unit_name,
                Property_code=property_code,
                created_by=user_profile.user  
            )
            new_property_unit = PropertyUnitDetails.objects.create(
                created_by=user_profile.user,
                property_unit_name=property_unit_name,
                land_dm_no=land_dm_no,
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
                apartment_floor_no=apartment_floor_no,
                no_of_floors=no_of_floors,
                property_code=property_code,
                owner=owner,
                company=company,
                property=parent_property,
                step_status="BASIC_DETAILS"
            )
            return prepare_response(
                message=constants.PROPERTY_ADDED,
                content={"id": new_property_unit.id},
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            return prepare_response(
                message={"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


    else:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

@is_request_authenticated
def property_images(request):
    try:
        if request.method == "GET":
            property_id = request.GET.get("property_id")
            if not property_id:
                return prepare_response(message=constants.PROPERTY_ID_REQUIRED, status=400)

            try:
                property_obj = PropertyUnitDetails.objects.get(id=property_id)
            except PropertyUnitDetails.DoesNotExist:
                return prepare_response(message=constants.INVALID_PROPERTY_ID, status=404)

            images_qs = PropertyImages.objects.filter(property=property_obj).order_by("-id")
            final_images = []

            for img in images_qs:
                base64_data = fetch_s3_presigned_url(img.image_path, file_name=img.file_name)
                final_images.append({
                    "id": img.id,
                    "file_name": img.file_name,
                    "data": base64_data,
                    "type": img.image_type
                })

            return prepare_response(
                message=constants.DATA_FETCHED_SUCCESSFULLY,
                content={
                    "images": final_images,
                    "property_id": property_id,
                    "step_choice": property_obj.step_status
                },
                status=200
            )
        if request.method == "POST":
            body = json.loads(request.body)
            property_id = body.get("property_id")
            images = body.get("images", [])

            if not property_id:
                return prepare_response(message=constants.PROPERTY_ID_REQUIRED, status=400)
            if not isinstance(images, list) or not images:
                return prepare_response(message="Images must be a list", status=400)

            try:
                property_obj = PropertyUnitDetails.objects.get(id=property_id)
            except PropertyUnitDetails.DoesNotExist:
                return prepare_response(message=constants.PROPERTY_NOT_FOUND, status=404)

            uploaded_files = []
            for img in images:
                file_name = img.get("file_name")
                base64_data = img.get("data")
                img_type = img.get("type", "INTERIOR").upper()

                if not file_name or not base64_data:
                    return prepare_response(message=constants.MISSING_FILE_OR_DATA, status=400)

                object_name = f"property_images/{property_id}/{file_name}"
                image_url = upload_file_to_s3_base64(base64_data, object_name)

                PropertyImages.objects.create(
                    property=property_obj,
                    file_name=file_name,
                    image_path=image_url,
                    image_type=img_type,
                    created_by = request.user.user

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
                status=201
            )
        
        if request.method == "PUT":
            body = json.loads(request.body)
            property_id = body.get("property_id")
            images = body.get("images", [])

            if not property_id:
                return prepare_response(message=constants.PROPERTY_ID_REQUIRED, status=400)
            if not isinstance(images, list):
                return prepare_response(message="Images must be a list", status=400)

            try:
                property_obj = PropertyUnitDetails.objects.get(id=property_id)
            except PropertyUnitDetails.DoesNotExist:
                return prepare_response(message=constants.PROPERTY_NOT_FOUND, status=404)

            updated_files = []
            for img in images:
                file_name = img.get("file_name")
                base64_data = img.get("data")
                img_type = img.get("type", "INTERIOR").upper()

                if not file_name or not base64_data:
                    return prepare_response(message=constants.MISSING_FILE_OR_DATA, status=400)

                img_obj, created = PropertyImages.objects.update_or_create(
                    property=property_obj,
                    file_name=file_name,
                    defaults={"image_type": img_type}
                )

                object_name = f"property_images/{property_id}/{file_name}"
                image_url = upload_file_to_s3_base64(base64_data, object_name)
                img_obj.image_path = image_url
                img_obj.save()

                updated_files.append({
                    "file_name": file_name,
                    "image_url": image_url,
                    "image_type": img_type,
                    "status": "created" if created else "updated"
                })

            return prepare_response(
                message=constants.IMAGE_UPLOADED_SUCCESS,
                content={"updated": updated_files},
                status=200
            )

    except Exception as e:
        return prepare_response(message=str(e), status=500)



@is_request_authenticated
def property_documents(request):
    try:
    
        if request.method == "GET":
            property_id = request.GET.get("property_id")
            if not property_id:
                return prepare_response(message=constants.PROPERTY_ID_REQUIRED, status=400)

            try:
                property_obj = PropertyUnitDetails.objects.get(id=property_id)
            except PropertyUnitDetails.DoesNotExist:
                return prepare_response(message=constants.INVALID_PROPERTY_ID, status=404)

            docs_qs = property_obj.property_documents.select_related('document').order_by("-id")
            final_docs = []

            for mapping in docs_qs:
                doc = mapping.document
                base64_data = fetch_s3_presigned_url(doc.file_path, file_name=doc.file_name)
                final_docs.append({
                    "id": mapping.id,
                    "file_name": doc.file_name,
                    "data": base64_data,
                    "type": mapping.document_choice
                })

            return prepare_response(
                message=constants.DATA_FETCHED_SUCCESSFULLY,
                content={
                    "documents": final_docs,
                    "property_id": property_id,
                    "step_choice": property_obj.step_status
                },
                status=200
            )

   
        if request.method == "POST":
            body = json.loads(request.body)
            property_id = body.get("property_id")
            documents = body.get("documents", [])

            if not property_id:
                return prepare_response(message=constants.PROPERTY_ID_REQUIRED, status=400)
            if not isinstance(documents, list) or not documents:
                return prepare_response(message=constants.DOCUMENTS_MUST_BE_LIST, status=400)

            try:
                property_obj = PropertyUnitDetails.objects.get(id=property_id)
            except PropertyUnitDetails.DoesNotExist:
                return prepare_response(message=constants.PROPERTY_NOT_FOUND, status=404)

            uploaded_files = []

            for doc in documents:
                file_name = doc.get("file_name")
                base64_data = doc.get("data")
            
                doc_type = doc.get("type", constants.FLOOR_PLAN).upper()

                if not file_name or not base64_data:
                    return prepare_response(message=constants.MISSING_FILE_OR_DATA, status=400)

                object_name = f"property_documents/{property_id}/{file_name}"
                file_url = upload_file_to_s3_base64(base64_data, object_name)

         
                doc_obj = Documents.objects.create(
                    file_name=file_name,
                    file_path=file_url,
                    created_by=request.user.user
                )

                PropertyDocumentsMapping.objects.create(
                    property=property_obj,
                    document=doc_obj,
                    document_choice=doc_type,
                    created_by=request.user.user
                )

                uploaded_files.append({
                    "file_name": file_name,
                    "file_url": file_url,
                    "type": doc_type
                })

            property_obj.step_status = "DOCUMENTS_DETAILS"
            property_obj.save()

            return prepare_response(
                message=constants.DOCUMENTS_UPLOAD_SUCCESS,
                content={"uploaded": uploaded_files},
                status=201
            )

        if request.method == "PUT":
            body = json.loads(request.body)
            property_id = body.get("property_id")
            documents = body.get("documents", [])

            if not property_id:
                return prepare_response(message=constants.PROPERTY_ID_REQUIRED, status=400)
            if not isinstance(documents, list):
                return prepare_response(message=constants.DOCUMENTS_MUST_BE_LIST, status=400)

            try:
                property_obj = PropertyUnitDetails.objects.get(id=property_id)
            except PropertyUnitDetails.DoesNotExist:
                return prepare_response(message=constants.PROPERTY_NOT_FOUND, status=404)

            updated_files = []

            for doc in documents:
                file_name = doc.get("file_name")
                base64_data = doc.get("data")
                doc_type = doc.get("type", constants.FLOOR_PLAN).upper()

                if not file_name or not base64_data:
                    return prepare_response(message=constants.MISSING_FILE_OR_DATA, status=400)

                mapping_obj = PropertyDocumentsMapping.objects.filter(
                    property=property_obj,
                    document__file_name=file_name
                ).select_related('document').first()

                if mapping_obj:
                    doc_obj = mapping_obj.document
                    mapping_obj.document_choice = doc_type
                    status_text = "updated"
                else:
                    doc_obj = Documents.objects.create(
                        file_name=file_name,
                        file_path="",
                        created_by=request.user.user
                    )
                    mapping_obj = PropertyDocumentsMapping.objects.create(
                        property=property_obj,
                        document=doc_obj,
                        document_choice=doc_type,
                        created_by=request.user.user
                    )
                    status_text = "created"

                object_name = f"property_documents/{property_id}/{file_name}"
                file_url = upload_file_to_s3_base64(base64_data, object_name)

                doc_obj.file_path = file_url
                doc_obj.save()
                mapping_obj.save()

                updated_files.append({
                    "file_name": file_name,
                    "file_url": file_url,
                    "type": doc_type,
                    "status": status_text
                })

            return prepare_response(
                message=constants.DOCUMENTS_UPLOAD_SUCCESS,
                content={"updated": updated_files},
                status=200
            )

        return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=405)

    except Exception as e:
        return prepare_response(message=str(e), status=500)






@is_request_authenticated
def tenant_table_view(request):
    user = request.user 
    search = request.GET.get("search", "").strip()
    tenant_id = request.GET.get("tenant_id")
    page = int(request.GET.get("page", 1))
    limit = int(request.GET.get("limit", 10))

    try:
        data = []

        if tenant_id:
         
            tenant_obj = UserProfile.objects.select_related('user').get(id=tenant_id, user_role=constants.TENANT)
            tenant_data = {
                "tenant_id": tenant_obj.id,
                "first_name": tenant_obj.user.first_name if tenant_obj.user else "",
                "last_name": tenant_obj.user.last_name if tenant_obj.user else "",
                "email": tenant_obj.user.email if tenant_obj.user else "",
                "contact_number": tenant_obj.contact_number,
                "city": tenant_obj.city,
                "address": tenant_obj.address,
                "emirate_id": tenant_obj.emirate_id,
            }

            lease_qs = LeasePropertyDetails.objects.filter(tenant=tenant_obj).select_related(
                "tenant", "lease_property", "lease_property__owner", "lease_property__company"
            )

   
        elif user.user_role == constants.OWNER:
            lease_qs = LeasePropertyDetails.objects.filter(owner=user).select_related(
                "tenant", "lease_property", "lease_property__owner", "lease_property__company"
            )


        elif user.user_role == constants.COMPANY_USER:
            company = Company.objects.filter(company_user=user).first()
            if not company:
                return prepare_response(message="Company not found", status=400)
            lease_qs = LeasePropertyDetails.objects.filter(
                lease_property__company=company
            ).select_related(
                "tenant", "lease_property", "lease_property__owner", "lease_property__company"
            )
        else:
            return prepare_response(message="Unauthorized user role", status=403)

        if search:
            lease_qs = lease_qs.filter(
                Q(tenant__user__email__icontains=search) |
                Q(tenant__contact_number__icontains=search) |
                Q(lease_property__property_unit_name__icontains=search)
            )

        lease_qs = lease_qs.order_by("-id")


        paginator = Paginator(lease_qs, limit)
        try:
            lease_page = paginator.page(page)
        except EmptyPage:
            lease_page = paginator.page(paginator.num_pages)

        for lease in lease_page:
            tenant = lease.tenant
            prop_unit = lease.lease_property
            data.append({
                "lease_id": lease.id,
                "tenant_name": tenant.user.email if tenant.user else None,
                "contact_number": tenant.contact_number,
                "property_assigned": prop_unit.property_unit_name if prop_unit else None,
                "property_id": prop_unit.id if prop_unit else None,
                "owner_name": prop_unit.owner.user.email if prop_unit and prop_unit.owner else None,
                "company_name": prop_unit.company.company_name if prop_unit and prop_unit.company else None,
                "lease_start_date": lease.lease_start_date,
                "lease_end_date": lease.lease_end_date,
            })

    
        response_content = {"leases": data}
        if tenant_id:
            response_content["tenant"] = tenant_data

        pagination_meta = {
            "current_page": lease_page.number,
            "limit": limit,
            "total_records": paginator.count,
            "total_pages": paginator.num_pages
        }

        return prepare_response(
            content=response_content,
            message="Tenant data fetched successfully",
            pagination=pagination_meta,
            status=200
        )

    except Exception as e:
        return prepare_response(
            message=f"Error fetching tenant data: {str(e)}",
            status=500
        )





@is_request_authenticated
def company_owners_view(request):
    user = request.user 
    search = request.GET.get("search", "").strip()
    owner_id = request.GET.get("owner_id")
    page = int(request.GET.get("page", 1))
    limit = int(request.GET.get("limit", 10))

    try:
        company = Company.objects.filter(company_user=user).first()
        if not company:
            return prepare_response(message="Company not found", status=400)
        if owner_id:
            owner = UserProfile.objects.filter(id=owner_id, user_role="OWNER").first()
            if not owner:
                return prepare_response(message="Owner not found", status=404)
            lease_qs = LeasePropertyDetails.objects.filter(
                lease_property__owner=owner,
                lease_property__company=company
            ).select_related(
                "tenant", "lease_property"
            )

            if search:
                lease_qs = lease_qs.filter(
                    Q(tenant__user__first_name__icontains=search) |
                    Q(tenant__user__last_name__icontains=search) |
                    Q(lease_property__property_unit_name__icontains=search) |
                    Q(tenant__contact_number__icontains=search)
                )

            lease_qs = lease_qs.order_by("-id")

            paginator = Paginator(lease_qs, limit)
            try:
                lease_page = paginator.page(page)
            except EmptyPage:
                lease_page = paginator.page(paginator.num_pages)

            data = []
            for lease in lease_page:
                tenant = lease.tenant
                prop_unit = lease.lease_property
                data.append({
                    "tenant_id": tenant.id,
                    "tenant_name": f"{tenant.user.first_name} {tenant.user.last_name}" if tenant.user else "",
                    "contact_number": tenant.contact_number,
                    "property_name": prop_unit.property_unit_name if prop_unit else None,
                    "tenancy_status": lease.lease_status,
                    "agreement": lease.pdf_path if lease.pdf_path else None,
                })

            pagination_meta = {
                "current_page": lease_page.number,
                "limit": limit,
                "total_records": paginator.count,
                "total_pages": paginator.num_pages
            }

            return prepare_response(
                content=data,
                message=f"Tenant details for owner {owner.user.email if owner.user else owner.id}",
                pagination=pagination_meta,
                status=200
            )

        owners_qs = UserProfile.objects.filter(
            user_role="OWNER",
            owner_properties__company=company
        ).distinct().prefetch_related(
            Prefetch(
                'owner_properties',
                queryset=PropertyUnitDetails.objects.filter(company=company)
            )
        )

        if search:
            owners_qs = owners_qs.filter(
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(user__email__icontains=search) |
                Q(contact_number__icontains=search)
            )

        owners_qs = owners_qs.annotate(property_count=Count('owner_properties'))

        paginator = Paginator(owners_qs, limit)
        try:
            owners_page = paginator.page(page)
        except EmptyPage:
            owners_page = paginator.page(paginator.num_pages)

        data = []
        for owner in owners_page:
            properties = owner.owner_properties.all()
            data.append({
                "owner_id": owner.id,
                "first_name": owner.user.first_name if owner.user else "",
                "last_name": owner.user.last_name if owner.user else "",
                "email": owner.user.email if owner.user else "",
                "contact_number": owner.contact_number,
                "property_count": owner.property_count,
                "properties": [{"id": prop.id, "name": prop.property_unit_name} for prop in properties]
            })

        pagination_meta = {
            "current_page": owners_page.number,
            "limit": limit,
            "total_records": paginator.count,
            "total_pages": paginator.num_pages
        }

        return prepare_response(
            content=data,
            message="Owners fetched successfully",
            pagination=pagination_meta,
            status=200
        )

    except Exception as e:
        return prepare_response(
            message=f"Error fetching data: {str(e)}",
            status=500
        )
    







@is_request_authenticated
def owner_pmc_view(request):
    user = request.user
    company_user_id = request.GET.get("company_user_id")
    search = request.GET.get("search", "").strip()
    page = int(request.GET.get("page", 1))
    limit = int(request.GET.get("limit", 10))

    try:
      
        if user.user_role == "OWNER" and not company_user_id:
         
            properties = PropertyUnitDetails.objects.filter(owner=user)
            pmc_ids = properties.values_list('company__company_user', flat=True).distinct()
            pmc_qs = UserProfile.objects.filter(id__in=pmc_ids, user_role="COMPANY_USER").prefetch_related(
                Prefetch(
                    'company_user',
                    queryset=Company.objects.all()
                ),
                Prefetch(
                    'assigned_properties',
                    queryset=PropertyUnitDetails.objects.filter(owner=user)
                )
            )

            if search:
                pmc_qs = pmc_qs.filter(
                    Q(user__first_name__icontains=search) |
                    Q(user__last_name__icontains=search) |
                    Q(user__email__icontains=search)
                )

            paginator = Paginator(pmc_qs, limit)
            try:
                pmc_page = paginator.page(page)
            except EmptyPage:
                pmc_page = paginator.page(paginator.num_pages)

            data = []
            for pmc in pmc_page:
                companies = pmc.company_user.all()
                for comp in companies:
                    owner_props = PropertyUnitDetails.objects.filter(owner=user, company=comp)
                    leased_count = LeasePropertyDetails.objects.filter(
                        lease_property__in=owner_props
                    ).count()
                    total_count = owner_props.count()
                    tenancy_ratio = f"{leased_count}/{total_count}" if total_count else "0/0"
                    data.append({
                        "company_id": comp.id,
                        "company_name": comp.company_name,
                        "company_address": comp.company_address,
                        "owner_property_count": total_count,
                        "tenancy_ratio": tenancy_ratio
                    })

            pagination_meta = {
                "current_page": pmc_page.number,
                "limit": limit,
                "total_records": paginator.count,
                "total_pages": paginator.num_pages
            }

            return prepare_response(
                content=data,
                message="PMC list fetched successfully",
                pagination=pagination_meta,
                status=200
            )

      
        elif company_user_id:
            company_user = UserProfile.objects.filter(id=company_user_id, user_role="COMPANY_USER").first()
            if not company_user:
                return prepare_response(message="Company user not found", status=404)
            properties = PropertyUnitDetails.objects.filter(company__company_user=company_user)
            lease_qs = LeasePropertyDetails.objects.filter(lease_property__in=properties).select_related(
                'lease_property', 'tenant', 'owner'
            )

            if search:
                lease_qs = lease_qs.filter(
                    Q(lease_property__property_unit_name__icontains=search) |
                    Q(tenant__user__first_name__icontains=search) |
                    Q(tenant__user__last_name__icontains=search) |
                    Q(tenant__user__email__icontains=search)
                )

            paginator = Paginator(lease_qs, limit)
            try:
                lease_page = paginator.page(page)
            except EmptyPage:
                lease_page = paginator.page(paginator.num_pages)

            data = []
            for lease in lease_page:
                tenant = lease.tenant
                prop = lease.lease_property
                owner = lease.owner
                data.append({
                    "property_id": prop.id,
                    "property_name": prop.property_unit_name,
                    "tenant_name": f"{tenant.user.first_name} {tenant.user.last_name}" if tenant.user else None,
                    "tenancy_status": lease.lease_status,
                    "bedrooms": prop.bedrooms,
                    "lease_id": lease.id,
                    "owner": {
                        "id": owner.id if owner else None,
                        "first_name": owner.user.first_name if owner and owner.user else "",
                        "last_name": owner.user.last_name if owner and owner.user else "",
                        "email": owner.user.email if owner and owner.user else "",
                        "profile_image": owner.profile_image if owner else None,
                        "pin_code": owner.pin_code if owner else None
                    }
                })

            pagination_meta = {
                "current_page": lease_page.number,
                "limit": limit,
                "total_records": paginator.count,
                "total_pages": paginator.num_pages
            }

            return prepare_response(
                content=data,
                message=f"Properties handled by company user {company_user.user.email if company_user.user else company_user.id}",
                pagination=pagination_meta,
                status=200
            )

        else:
            return prepare_response(message="Unauthorized access or missing parameters", status=403)

    except Exception as e:
        return prepare_response(
            message=f"Error fetching data: {str(e)}",
            status=500
        )




@is_request_authenticated
def send_invitation(request):
    if request.method != "POST":
        return prepare_response(message="Invalid request", status=405)

    try:
        user_profile = request.user  
        data = json.loads(request.body)

        email = data.get("email")
        invite_type = data.get("invitation_type") 

        if not email:
            return prepare_response(message="Email is required", status=400)

        if invite_type not in ["OWNER_TO_PMC", "PMC_TO_OWNER", "PMC_TO_TENANT"]:
            return prepare_response(message="Invalid invitation type", status=400)

      
        if invite_type == "OWNER_TO_PMC" and user_profile.user_role != constants.OWNER:
            return prepare_response(message="Only owners can invite PMC", status=403)

        if invite_type in ["PMC_TO_OWNER", "PMC_TO_TENANT"] and user_profile.user_role != constants.COMPANY_USER:
            return prepare_response(message="Only PMC can send this invitation", status=403)

        
        template_map = {
            "OWNER_TO_PMC": "email_templates/invite_owner_to_pmc.html",
            "PMC_TO_OWNER": "email_templates/invite_pmc_to_owner.html",
            "PMC_TO_TENANT": "email_templates/invite_tenant_by_pmc.html",
        }

        template_name = template_map[invite_type]

       
        invitation, error = create_and_send_invitation(
            invited_by_profile=user_profile,
            email=email,
            invitation_type=invite_type,
            template_name=template_name
        )

        if error:
            return prepare_response(message=error, status=400)

        return prepare_response(
            content={
                "email": invitation.email,
                "token": invitation.token,
                "status": invitation.status,
                "invitation_type": invitation.invitation_type
            },
            message="Invitation sent successfully",
            status=201
        )

    except Exception as e:
        return prepare_response(
            message=f"Error: {str(e)}",
            status=500
        )



@is_request_authenticated
def lease_details_view(request):
    user_profile = request.user
    if request.method == "GET":
        try:
            lease_id = request.GET.get("lease_id")

            if not lease_id:
                return prepare_response(
                    message="lease_id is required",
                    status=status.HTTP_400_BAD_REQUEST,
                )

            lease = LeasePropertyDetails.objects.filter(id=lease_id).first()
            if not lease:
                return prepare_response(
                    message="Lease not found",
                    status=status.HTTP_404_NOT_FOUND,
                )

            return prepare_response(
                content=serialize_lease(lease),
                message="Lease fetched",
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return prepare_response(message=str(e), status=500)

 
    elif request.method == "POST":
        try:
            body = json.loads(request.body)

            property_id = body.get("property_id")
            tenant_id = body.get("tenant_id")
            owner_id = body.get("owner_id")

            if not property_id or not tenant_id:
                return prepare_response(
                    message="property_id and tenant_id are required",
                    status=400
                )

            property_obj = PropertyUnitDetails.objects.filter(id=property_id).first()
            tenant_obj = UserProfile.objects.filter(id=tenant_id, user_role="TENANT").first()

            if not property_obj or not tenant_obj:
                return prepare_response(message="Invalid property or tenant", status=400)

            owner_obj = None
            if owner_id:
                owner_obj = UserProfile.objects.filter(id=owner_id, user_role="OWNER").first()

            # ---------------- Epoch Conversion ----------------
            lease_start_date = safe_epoch_to_datetime(body.get("lease_start_date"))
            lease_end_date = safe_epoch_to_datetime(body.get("lease_end_date"))

            if not lease_start_date or not lease_end_date:
                return prepare_response(message="Invalid lease dates", status=400)

            lease_grace_start_date = safe_epoch_to_datetime(body.get("lease_grace_start_date")) if body.get("lease_grace_start_date") else None
            lease_grace_end_date = safe_epoch_to_datetime(body.get("lease_grace_end_date")) if body.get("lease_grace_end_date") else None
            lease = LeasePropertyDetails.objects.create(
                created_by=user_profile,
                lease_property=property_obj,
                tenant=tenant_obj,
                owner=owner_obj,

                lease_start_date=lease_start_date,
                lease_end_date=lease_end_date,
                lease_grace_start_date=lease_grace_start_date,
                lease_grace_end_date=lease_grace_end_date,
                lease_remarks=body.get("lease_remarks"),

                step_status="LEASE_DETAILS",

           
                annual_amount=body.get("annual_amount", 0),
                actual_annual_amount=body.get("actual_annual_amount"),
                rent=body.get("rent", 0),
                booking_amount=body.get("booking_amount"),
                security_deposit=body.get("security_deposit"),
                maintenance_charges=body.get("maintenance_charges"),
                commission_percentage=body.get("commission_percentage"),
                notice_period=body.get("notice_period"),
                discount=body.get("discount"),
            )

            return prepare_response(
                message="Lease created successfully",
                content={"lease_id": lease.id},
                status=201,
            )

        except Exception as e:
            return prepare_response(message=str(e), status=500)

    elif request.method == "PUT":
        try:
            body = json.loads(request.body)
            lease_id = body.get("lease_id")

            if not lease_id:
                return prepare_response(message="lease_id is required", status=400)

            lease = LeasePropertyDetails.objects.filter(id=lease_id).first()
            if not lease:
                return prepare_response(message="Lease not found", status=404)

            basic_fields = [
                "lease_remarks",
                "step_status",
            ]
            for field in basic_fields:
                if field in body and body[field] is not None:
                    setattr(lease, field, body[field])
            if "lease_start_date" in body:
                lease.lease_start_date = safe_epoch_to_datetime(body["lease_start_date"])

            if "lease_end_date" in body:
                lease.lease_end_date = safe_epoch_to_datetime(body["lease_end_date"])

            if "lease_grace_start_date" in body:
                lease.lease_grace_start_date = safe_epoch_to_datetime(body["lease_grace_start_date"])

            if "lease_grace_end_date" in body:
                lease.lease_grace_end_date = safe_epoch_to_datetime(body["lease_grace_end_date"])

            commercial_fields = [
                "annual_amount", "actual_annual_amount", "rent",
                "booking_amount", "security_deposit", "maintenance_charges",
                "commission_percentage", "notice_period", "discount"
            ]
            for field in commercial_fields:
                if field in body:
                    setattr(lease, field, body[field])
            if "tenant_id" in body:
                tenant_obj = UserProfile.objects.filter(
                    id=body["tenant_id"], user_role="TENANT"
                ).first()
                if tenant_obj:
                    lease.tenant = tenant_obj

            if "owner_id" in body:
                owner_obj = UserProfile.objects.filter(
                    id=body["owner_id"], user_role="OWNER"
                ).first()
                lease.owner = owner_obj

            lease.save()

            return prepare_response(
                message="Lease updated successfully",
                content={"lease_id": lease.id},
                status=200
            )

        except Exception as e:
            return prepare_response(message=str(e), status=500)
    else:
        return prepare_response(message="Invalid request method", status=405)



