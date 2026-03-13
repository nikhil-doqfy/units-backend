import csv
import json
import uuid
from django.http import HttpResponse
from .models import Unit, UnitImages, UnitDocuments, UnitOwner, Property, PropertyBlocks, PropertyImages, PropertyDocuments
from user_service.models import PropertyManager, DocumentType
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

        search = request.GET.get("search", "").strip()
        property_type = request.GET.get("property_type", "").strip()
        prop_status = request.GET.get("status", "").strip()
        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 10))
        export = request.GET.get("export", "").strip()

        properties = Property.objects.all().order_by("-id")
        if search:
            properties = properties.filter(property_name__icontains=search)
        if property_type:
            properties = properties.filter(property_type=property_type)
        if prop_status:
            properties = properties.filter(status=prop_status)

        if export == "csv":
            response = HttpResponse(content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="properties.csv"'
            writer = csv.writer(response)
            writer.writerow(["Property ID", "Property Name", "Type", "Status", "Address", "Blocks", "Units", "Plot No", "Makani No", "Dewa No"])
            for p in properties:
                s = p._serialize_property()
                writer.writerow([s.get("code"), s.get("property_name"), s.get("property_type"), s.get("status"), s.get("address_line_1"), s.get("no_of_blocks"), s.get("no_of_units"), s.get("plot_no"), s.get("makani_no"), s.get("dewa_no")])
            return response

        total = properties.count()
        start = (page - 1) * page_size
        properties = properties[start:start + page_size]

        return prepare_response(
            content=[p._serialize_property() for p in properties],
            pagination={"total_records": total, "page": page, "page_size": page_size},
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


@is_request_authenticated
def unit(request):
    user_profile = request.user

    if request.method == "GET":
        unit_id = request.GET.get("unit_id")
        if unit_id:
            u = Unit.objects.filter(id=unit_id).select_related(
                "property_block_tower__property"
            ).prefetch_related("unit_owners").first()
            if not u:
                return prepare_response(
                    message=constants.UNIT_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )
            return prepare_response(content=u._serialize_unit(), status=status.HTTP_200_OK)

        search = request.GET.get("search", "").strip()
        property_id = request.GET.get("property_id", "").strip()
        block_id = request.GET.get("block_id", "").strip()
        no_of_bedrooms = request.GET.get("no_of_bedrooms", "").strip()
        floor_no = request.GET.get("floor_no", "").strip()
        land_area_unit = request.GET.get("land_area_unit", "").strip()
        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 10))
        export = request.GET.get("export", "").strip()

        units = Unit.objects.all().select_related(
            "property_block_tower__property"
        ).prefetch_related("unit_owners").order_by("-id")

        if search:
            units = units.filter(unit_name__icontains=search)
        if property_id:
            units = units.filter(property_block_tower__property_id=property_id)
        if block_id:
            units = units.filter(property_block_tower_id=block_id)
        if no_of_bedrooms:
            units = units.filter(no_of_bedrooms=no_of_bedrooms)
        if floor_no:
            units = units.filter(floor_no=floor_no)
        if land_area_unit:
            units = units.filter(land_area_unit=land_area_unit)

        if export == "csv":
            response = HttpResponse(content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="units.csv"'
            writer = csv.writer(response)
            writer.writerow(["Unit ID", "Unit Name", "Property", "Block/Tower", "Bedrooms", "Floor No", "Plot No", "Land Area", "Makani No", "Dewa No", "Rent (AED)"])
            for u in units:
                s = u._serialize_unit()
                writer.writerow([s.get("code"), s.get("unit_name"), s.get("property_name"), s.get("block_name"), s.get("no_of_bedrooms"), s.get("floor_no"), s.get("plot_no"), f"{s.get('land_area') or ''} {s.get('land_area_unit') or ''}".strip(), s.get("makani_no"), s.get("dewa_no"), s.get("rent")])
            return response

        total = units.count()
        start = (page - 1) * page_size
        units = units[start:start + page_size]

        return prepare_response(
            content=[u._serialize_unit() for u in units],
            pagination={"total_records": total, "page": page, "page_size": page_size},
            status=status.HTTP_200_OK
        )

    elif request.method == "POST":
        data = json.loads(request.body)
        block_id = data.get("block_id")
        unit_name = data.get("unit_name")

        if not block_id:
            return prepare_response(
                message="block_id is required",
                status=status.HTTP_400_BAD_REQUEST
            )
        if not unit_name:
            return prepare_response(
                message="unit_name is required",
                status=status.HTTP_400_BAD_REQUEST
            )

        block = PropertyBlocks.objects.filter(id=block_id).first()
        if not block:
            return prepare_response(
                message="Block not found",
                status=status.HTTP_404_NOT_FOUND
            )

        u = Unit.objects.create(
            created_by=user_profile.user,
            property_block_tower=block,
            unit_name=unit_name,
            land_area=data.get("land_area") or 0,
            land_area_unit=data.get("land_area_unit") or constants.SQ_FT,
            land_dm_no=data.get("land_dm_no"),
            no_of_bedrooms=data.get("no_of_bedrooms"),
            floor_no=data.get("floor_no"),
            parking_no=data.get("parking_no"),
            no_of_balcony=data.get("no_of_balcony"),
            plot_no=data.get("plot_no"),
            makani_no=data.get("makani_no"),
            dewa_no=data.get("dewa_no"),
            rent=data.get("rent"),
            security_deposit=data.get("security_deposit"),
            booking_amount=data.get("booking_amount"),
            maintenance_charges=data.get("maintenance_charges"),
            cycle=data.get("cycle"),
            notice_period=data.get("notice_period"),
            commission_percent=data.get("commission_percent"),
        )

        for owner in data.get("unit_owners", []):
            if owner.get("email"):
                UnitOwner.objects.create(
                    created_by=user_profile.user,
                    unit=u,
                    name=owner.get("owner_name"),
                    email=owner.get("email"),
                    contact_number=owner.get("contact_number"),
                    emirates_id=owner.get("emirates_id"),
                )

        audit_logs(request, f"Unit '{u.unit_name}' created", constants.CREATED)
        return prepare_response(
            message="Unit added successfully",
            content={"id": u.id},
            status=status.HTTP_201_CREATED
        )

    elif request.method == "PUT":
        data = json.loads(request.body)
        unit_id = data.get("unit_id")
        if not unit_id:
            return prepare_response(
                message="unit_id is required",
                status=status.HTTP_400_BAD_REQUEST
            )

        u = Unit.objects.filter(id=unit_id).first()
        if not u:
            return prepare_response(
                message=constants.UNIT_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        for field in ["unit_name", "land_area", "land_area_unit", "land_dm_no",
                      "no_of_bedrooms", "floor_no", "parking_no", "no_of_balcony",
                      "plot_no", "makani_no", "dewa_no", "rent", "security_deposit",
                      "booking_amount", "maintenance_charges", "cycle",
                      "notice_period", "commission_percent"]:
            if field in data and data[field] is not None:
                setattr(u, field, data[field])

        if data.get("block_id"):
            block = PropertyBlocks.objects.filter(id=data["block_id"]).first()
            if block:
                u.property_block_tower = block

        u.save()

        if "unit_owners" in data:
            u.unit_owners.all().delete()
            for owner in data["unit_owners"]:
                if owner.get("email"):
                    UnitOwner.objects.create(
                        created_by=user_profile.user,
                        unit=u,
                        name=owner.get("owner_name"),
                        email=owner.get("email"),
                        contact_number=owner.get("contact_number"),
                        emirates_id=owner.get("emirates_id"),
                    )

        audit_logs(request, f"Unit '{u.unit_name}' updated", constants.UPDATED)
        return prepare_response(
            message="Unit updated successfully",
            content={"id": u.id},
            status=status.HTTP_200_OK
        )

    else:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )


@is_request_authenticated
def unit_images(request):
    user_profile = request.user

    if request.method == "GET":
        unit_id = request.GET.get("unit_id")
        if not unit_id:
            return prepare_response(
                message="unit_id is required",
                status=status.HTTP_400_BAD_REQUEST
            )
        images = UnitImages.objects.filter(unit_id=unit_id)
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
        unit_id = data.get("unit_id")
        images_data = data.get("images") or []

        if not unit_id:
            return prepare_response(
                message="unit_id is required",
                status=status.HTTP_400_BAD_REQUEST
            )

        u = Unit.objects.filter(id=unit_id).select_related(
            "property_block_tower__property"
        ).first()
        if not u:
            return prepare_response(
                message=constants.UNIT_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        property_id = u.property_block_tower.property_id
        created = []
        for img_data in images_data:
            base64_data = img_data.get("data")
            if not base64_data:
                continue
            file_name = img_data.get("file_name") or f"{uuid.uuid4()}.jpg"
            image_type = img_data.get("type") or "INTERIOR"
            ext = get_extension_from_base64(base64_data) or ".jpg"
            unique_filename = f"{uuid.uuid4()}{ext}"
            s3_key = f"property/{property_id}/unit/{unit_id}/{image_type.lower()}/{unique_filename}"
            url = upload_file_to_s3_base64(base64_data, s3_key)
            img = UnitImages.objects.create(
                created_by=user_profile.user,
                unit=u,
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
        UnitImages.objects.filter(id=image_id).delete()
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
def unit_document_types(request):
    if request.method != "GET":
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    doc_types = DocumentType.objects.filter(section=constants.UNIT).order_by("id")
    content = [{"id": dt.id, "name": dt.name} for dt in doc_types]
    return prepare_response(content=content, status=status.HTTP_200_OK)


@is_request_authenticated
def unit_documents(request):
    user_profile = request.user

    if request.method == "GET":
        unit_id = request.GET.get("unit_id")
        if not unit_id:
            return prepare_response(
                message="unit_id is required",
                status=status.HTTP_400_BAD_REQUEST
            )
        docs = UnitDocuments.objects.filter(unit_id=unit_id).select_related("document_type")
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
        unit_id = data.get("unit_id")
        documents_data = data.get("documents") or []

        if not unit_id:
            return prepare_response(
                message="unit_id is required",
                status=status.HTTP_400_BAD_REQUEST
            )

        u = Unit.objects.filter(id=unit_id).select_related(
            "property_block_tower__property"
        ).first()
        if not u:
            return prepare_response(
                message=constants.UNIT_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        property_id = u.property_block_tower.property_id
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
            s3_key = f"property/{property_id}/unit/{unit_id}/documents/{doc_type.id}/{unique_filename}"
            url = upload_file_to_s3_base64(base64_data, s3_key)
            doc = UnitDocuments.objects.create(
                created_by=user_profile.user,
                unit=u,
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
        UnitDocuments.objects.filter(id=document_id).delete()
        return prepare_response(
            message="Document deleted successfully",
            status=status.HTTP_200_OK
        )

    else:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
