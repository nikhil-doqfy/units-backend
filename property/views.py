import json
import uuid
from .models import Unit, Property, PropertyOwner, PropertyBlocks, PropertyImages, PropertyDocuments
from user_service.models import Owner, PropertyManager, DocumentType
from django.contrib.auth.models import User
from utilities.decorator import is_request_authenticated
from utilities.helper_functions import prepare_response, generate_property_code, upload_file_to_s3_base64, fetch_s3_presigned_url, get_extension_from_base64
from utilities import status, constants
from property_management.utils import audit_logs


@is_request_authenticated
def property(request):
    user_profile = request.user

    if request.method == "GET":
        property_id = request.GET.get("property_id")
        if property_id:
            prop = Property.objects.filter(id=property_id).first()
            if not prop:
                return prepare_response(
                    message=constants.PROPERTY_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )
            return prepare_response(content=prop._serialize_property(), status=status.HTTP_200_OK)

        properties = Property.objects.all().order_by("-id")
        return prepare_response(
            content=[p._serialize_property() for p in properties],
            status=status.HTTP_200_OK
        )

    elif request.method == "POST":
        data = json.loads(request.body)

        property_name = data.get("property_name")
        if not property_name:
            return prepare_response(
                message=constants.PROPERTY_NAME_REQUIRED,
                status=status.HTTP_400_BAD_REQUEST
            )

        pm_profile = PropertyManager.objects.filter(pk=user_profile.pk).select_related('company').first()
        pmc = pm_profile.company if pm_profile else None
        if not pmc:
            return prepare_response(
                message=constants.NOT_VERIFIED_PROPERTY_MANAGER,
                status=status.HTTP_403_FORBIDDEN
            )

        prop = Property.objects.create(
            created_by=user_profile.user,
            property_name=property_name,
            property_type=data.get("property_type") or constants.APARTMENT,
            no_of_blocks=data.get("no_of_blocks") or 1,
            no_of_units=data.get("no_of_units") or 1,
            land_area=data.get("land_area"),
            land_area_unit=data.get("land_area_unit") or constants.SQ_FT,
            land_dm_no=data.get("land_dm_no"),
            plot_no=data.get("plot_no"),
            makani_no=data.get("makani_no"),
            dewa_no=data.get("dewa_no"),
            address_line_1=data.get("address_line_1") or '',
            address_line_2=data.get("address_line_2") or '',
            landmark=data.get("landmark") or '',
            pincode=data.get("pincode") or '',
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            map_address=data.get("map_address"),
            approx_rent=data.get("approx_rent"),
            pmc=pmc,
        )

        # Resolve multiple owners from list
        for owner_data in data.get("property_owners") or []:
            owner_email = owner_data.get("email")
            if not owner_email:
                continue
            existing_user = User.objects.filter(email=owner_email).first()
            if existing_user:
                owner_obj = Owner.objects.filter(user=existing_user).first()
            else:
                name_parts = (owner_data.get("property_owner_name") or "").split(" ", 1)
                new_user = User.objects.create_user(
                    username=owner_email,
                    email=owner_email,
                    password=uuid.uuid4().hex,
                    first_name=name_parts[0],
                    last_name=name_parts[1] if len(name_parts) > 1 else '',
                )
                owner_obj = Owner.objects.create(
                    created_by=user_profile.user,
                    user=new_user,
                    contact_number=owner_data.get("contact_number"),
                    emirate_id=owner_data.get("emirates_id"),
                )
            if owner_obj:
                PropertyOwner.objects.create(
                    created_by=user_profile.user,
                    property=prop,
                    owner=owner_obj,
                )

        audit_logs(request, f"Property '{prop.property_name}' created", constants.CREATED)
        return prepare_response(
            message=constants.PROPERTY_ADDED,
            content={"id": prop.id},
            status=status.HTTP_201_CREATED
        )

    elif request.method == "PUT":
        data = json.loads(request.body)
        property_id = data.get("property_id")
        if not property_id:
            return prepare_response(
                message=constants.PROPERTY_ID_REQUIRED,
                status=status.HTTP_400_BAD_REQUEST
            )

        prop = Property.objects.filter(id=property_id).first()
        if not prop:
            return prepare_response(
                message=constants.PROPERTY_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        for field in ["property_name", "property_type", "no_of_blocks", "no_of_units",
                      "land_area", "land_area_unit", "land_dm_no", "plot_no", "makani_no",
                      "dewa_no", "address_line_1", "address_line_2", "landmark", "pincode",
                      "latitude", "longitude", "map_address", "approx_rent"]:
            if field in data and data[field] is not None:
                setattr(prop, field, data[field])

        pm_profile = PropertyManager.objects.filter(pk=user_profile.pk).select_related('company').first()
        if pm_profile and pm_profile.company:
            prop.pmc = pm_profile.company

        prop.save()

        # Sync property owners if provided
        if "property_owners" in data:
            PropertyOwner.objects.filter(property=prop).delete()
            for owner_data in data.get("property_owners") or []:
                owner_email = owner_data.get("email")
                if not owner_email:
                    continue
                existing_user = User.objects.filter(email=owner_email).first()
                if existing_user:
                    owner_obj = Owner.objects.filter(user=existing_user).first()
                else:
                    name_parts = (owner_data.get("property_owner_name") or "").split(" ", 1)
                    new_user = User.objects.create_user(
                        username=owner_email,
                        email=owner_email,
                        password=uuid.uuid4().hex,
                        first_name=name_parts[0],
                        last_name=name_parts[1] if len(name_parts) > 1 else '',
                    )
                    owner_obj = Owner.objects.create(
                        created_by=user_profile.user,
                        user=new_user,
                        contact_number=owner_data.get("contact_number"),
                        emirate_id=owner_data.get("emirates_id"),
                    )
                if owner_obj:
                    PropertyOwner.objects.create(
                        created_by=user_profile.user,
                        property=prop,
                        owner=owner_obj,
                    )

        audit_logs(request, f"Parent property '{prop.property_name}' updated", constants.UPDATED)
        return prepare_response(
            message=constants.PROPERTY_UPDATE_SUCCESS,
            content={"id": prop.id},
            status=status.HTTP_200_OK
        )
    else:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )


@is_request_authenticated
def property_blocks(request):
    user_profile = request.user

    if request.method == "GET":
        property_id = request.GET.get("property_id")
        if not property_id:
            return prepare_response(
                message="property_id is required",
                status=status.HTTP_400_BAD_REQUEST
            )
        blocks = PropertyBlocks.objects.filter(property_id=property_id)
        content = [
            {
                "id": b.id,
                "block_name": b.block_name,
                "no_of_floors": b.no_of_floors,
                "no_of_parking": b.no_of_parking,
                "no_of_units": b.no_of_units,
            }
            for b in blocks
        ]
        return prepare_response(content=content, status=status.HTTP_200_OK)

    elif request.method == "POST":
        data = json.loads(request.body)
        property_id = data.get("property_id")
        blocks_data = data.get("blocks") or []

        if not property_id:
            return prepare_response(
                message="property_id is required",
                status=status.HTTP_400_BAD_REQUEST
            )

        prop = Property.objects.filter(id=property_id).first()
        if not prop:
            return prepare_response(
                message=constants.PROPERTY_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        created = []
        for block in blocks_data:
            b = PropertyBlocks.objects.create(
                created_by=user_profile.user,
                property=prop,
                block_name=block.get("block_name", ""),
                no_of_floors=block.get("no_of_floors") or 0,
                no_of_parking=block.get("no_of_parking") or 0,
                no_of_units=block.get("no_of_units") or 0,
            )
            created.append(b.id)

        return prepare_response(
            message="Blocks added successfully",
            content={"ids": created},
            status=status.HTTP_201_CREATED
        )

    elif request.method == "PUT":
        data = json.loads(request.body)
        property_id = data.get("property_id")
        blocks_data = data.get("blocks") or []

        if not property_id:
            return prepare_response(
                message="property_id is required",
                status=status.HTTP_400_BAD_REQUEST
            )

        prop = Property.objects.filter(id=property_id).first()
        if not prop:
            return prepare_response(
                message=constants.PROPERTY_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        # Replace all blocks for this property
        PropertyBlocks.objects.filter(property=prop).delete()
        for block in blocks_data:
            PropertyBlocks.objects.create(
                created_by=user_profile.user,
                property=prop,
                block_name=block.get("block_name", ""),
                no_of_floors=block.get("no_of_floors") or 0,
                no_of_parking=block.get("no_of_parking") or 0,
                no_of_units=block.get("no_of_units") or 0,
            )

        return prepare_response(
            message="Blocks updated successfully",
            status=status.HTTP_200_OK
        )

    else:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )


@is_request_authenticated
def property_images(request):
    user_profile = request.user

    if request.method == "GET":
        property_id = request.GET.get("property_id")
        if not property_id:
            return prepare_response(
                message="property_id is required",
                status=status.HTTP_400_BAD_REQUEST
            )
        images = PropertyImages.objects.filter(property_id=property_id)
        content = [
            {
                "id": img.id,
                "file_name": img.file_name,
                "image_type": img.image_type,
                "url": fetch_s3_presigned_url(img.image_path, img.file_name),
            }
            for img in images
        ]
        return prepare_response(content=content, status=status.HTTP_200_OK)

    elif request.method == "POST":
        data = json.loads(request.body)
        property_id = data.get("property_id")
        images_data = data.get("images") or []

        if not property_id:
            return prepare_response(
                message="property_id is required",
                status=status.HTTP_400_BAD_REQUEST
            )

        prop = Property.objects.filter(id=property_id).first()
        if not prop:
            return prepare_response(
                message=constants.PROPERTY_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        company_id = prop.pmc.id if prop.pmc else "unknown"
        created = []
        for img_data in images_data:
            base64_data = img_data.get("data")
            if not base64_data:
                continue
            file_name = img_data.get("file_name") or f"{uuid.uuid4()}.jpg"
            image_type = img_data.get("type") or "INTERIOR"
            ext = get_extension_from_base64(base64_data) or ".jpg"
            unique_filename = f"{uuid.uuid4()}{ext}"
            s3_key = f"company/{company_id}/property/{property_id}/{image_type.lower()}/{unique_filename}"
            url = upload_file_to_s3_base64(base64_data, s3_key)
            img = PropertyImages.objects.create(
                created_by=user_profile.user,
                property=prop,
                image_path=url,
                image_type=image_type,
                file_name=file_name,
            )
            created.append(img.id)

        return prepare_response(
            message="Images uploaded successfully",
            content={"ids": created},
            status=status.HTTP_201_CREATED
        )

    elif request.method == "DELETE":
        image_id = request.GET.get("image_id")
        if not image_id:
            return prepare_response(
                message="image_id is required",
                status=status.HTTP_400_BAD_REQUEST
            )
        PropertyImages.objects.filter(id=image_id).delete()
        return prepare_response(
            message="Image deleted successfully",
            status=status.HTTP_200_OK
        )

    else:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )


@is_request_authenticated
def property_document_types(request):
    """GET /property/document-types — returns DocumentType records for the PROPERTY section."""
    if request.method != "GET":
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    doc_types = DocumentType.objects.filter(section=constants.PROPERTY).order_by("id")
    content = [{"id": dt.id, "name": dt.name} for dt in doc_types]
    return prepare_response(content=content, status=status.HTTP_200_OK)


@is_request_authenticated
def property_documents(request):
    user_profile = request.user

    if request.method == "GET":
        property_id = request.GET.get("property_id")
        if not property_id:
            return prepare_response(
                message="property_id is required",
                status=status.HTTP_400_BAD_REQUEST
            )
        docs = PropertyDocuments.objects.filter(property_id=property_id).select_related("document_type")
        content = [
            {
                "id": doc.id,
                "file_name": doc.file_name,
                "document_type_id": doc.document_type.id,
                "document_type_name": doc.document_type.name,
                "url": fetch_s3_presigned_url(doc.file_path, doc.file_name),
            }
            for doc in docs
        ]
        return prepare_response(content=content, status=status.HTTP_200_OK)

    elif request.method == "POST":
        data = json.loads(request.body)
        property_id = data.get("property_id")
        documents_data = data.get("documents") or []

        if not property_id:
            return prepare_response(
                message="property_id is required",
                status=status.HTTP_400_BAD_REQUEST
            )

        prop = Property.objects.filter(id=property_id).first()
        if not prop:
            return prepare_response(
                message=constants.PROPERTY_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        company_id = prop.pmc.id if prop.pmc else "unknown"
        created = []
        for doc_data in documents_data:
            base64_data = doc_data.get("data")
            if not base64_data:
                continue
            file_name = doc_data.get("file_name") or f"{uuid.uuid4()}.pdf"
            document_type_id = doc_data.get("document_type_id")
            doc_type = DocumentType.objects.filter(id=document_type_id).first() if document_type_id else None
            if not doc_type:
                continue
            ext = get_extension_from_base64(base64_data) or ".pdf"
            unique_filename = f"{uuid.uuid4()}{ext}"
            s3_key = f"company/{company_id}/property/{property_id}/documents/{doc_type.id}/{unique_filename}"
            url = upload_file_to_s3_base64(base64_data, s3_key)
            doc = PropertyDocuments.objects.create(
                created_by=user_profile.user,
                property=prop,
                document_type=doc_type,
                file_name=file_name,
                file_path=url,
            )
            created.append(doc.id)

        return prepare_response(
            message="Documents uploaded successfully",
            content={"ids": created},
            status=status.HTTP_201_CREATED
        )

    elif request.method == "DELETE":
        document_id = request.GET.get("document_id")
        if not document_id:
            return prepare_response(
                message="document_id is required",
                status=status.HTTP_400_BAD_REQUEST
            )
        PropertyDocuments.objects.filter(id=document_id).delete()
        return prepare_response(
            message="Document deleted successfully",
            status=status.HTTP_200_OK
        )

    else:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
