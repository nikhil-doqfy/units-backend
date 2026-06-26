from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema


PROPERTY_TAG = ["Property"]


# Common schemas
owner_schema = openapi.Schema(
    type=openapi.TYPE_ARRAY,
    items=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "owner_name": openapi.Schema(type=openapi.TYPE_STRING, example="Himanshu Kolhe"),
            "email": openapi.Schema(type=openapi.TYPE_STRING, example="himanshu@doqfy.in"),
            "contact_number": openapi.Schema(type=openapi.TYPE_STRING, example="+911234567890"),
            "emirates_id": openapi.Schema(type=openapi.TYPE_STRING, example="784-1990-1234567-1"),
        },
    ),
)

image_schema = openapi.Schema(
    type=openapi.TYPE_ARRAY,
    items=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "file_name": openapi.Schema(type=openapi.TYPE_STRING, example="front.jpg"),
            "type": openapi.Schema(type=openapi.TYPE_STRING, example="EXTERIOR"),
            "data": openapi.Schema(type=openapi.TYPE_STRING, example="data:image/jpeg;base64,/9j/4AAQSkZJRgABAQ..."),
        },
    ),
)

document_schema = openapi.Schema(
    type=openapi.TYPE_ARRAY,
    items=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "document_type_id": openapi.Schema(type=openapi.TYPE_INTEGER, example=1),
            "file_name": openapi.Schema(type=openapi.TYPE_STRING, example="title_deed.pdf"),
            "data": openapi.Schema(type=openapi.TYPE_STRING, example="data:application/pdf;base64,JVBERi0xLjQK..."),
        },
    ),
)

blocks_schema = openapi.Schema(
    type=openapi.TYPE_ARRAY,
    items=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "block_name": openapi.Schema(type=openapi.TYPE_STRING, example="Tower A"),
            "makani_no": openapi.Schema(type=openapi.TYPE_STRING, example="MK123"),
            "no_of_floors": openapi.Schema(type=openapi.TYPE_INTEGER, example=10),
            "no_of_parking": openapi.Schema(type=openapi.TYPE_INTEGER, example=20),
            "no_of_units": openapi.Schema(type=openapi.TYPE_INTEGER, example=40),
        },
    ),
)


property_get = swagger_auto_schema(
    method="get",
    tags=PROPERTY_TAG,
    operation_summary="Get property list or single property",
    manual_parameters=[
        openapi.Parameter("property_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("search", openapi.IN_QUERY, type=openapi.TYPE_STRING, required=False, example="Marina"),
        openapi.Parameter("property_type", openapi.IN_QUERY, type=openapi.TYPE_STRING, required=False, example="APARTMENT"),
        openapi.Parameter("status", openapi.IN_QUERY, type=openapi.TYPE_STRING, required=False, example="DRAFT"),
        openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("page_size", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=10),
        openapi.Parameter("export", openapi.IN_QUERY, type=openapi.TYPE_STRING, required=False, example="csv"),
    ],
)

property_post = swagger_auto_schema(
    method="post",
    tags=PROPERTY_TAG,
    operation_summary="Create property",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["property_name"],
        properties={
            "property_name": openapi.Schema(type=openapi.TYPE_STRING, example="Marina Heights"),
            "property_type": openapi.Schema(type=openapi.TYPE_STRING, example="APARTMENT"),
            "no_of_blocks": openapi.Schema(type=openapi.TYPE_INTEGER, example=2),
            "no_of_units": openapi.Schema(type=openapi.TYPE_INTEGER, example=50),
            "land_area": openapi.Schema(type=openapi.TYPE_NUMBER, example=25000),
            "land_area_unit": openapi.Schema(type=openapi.TYPE_STRING, example="SQ_FT"),
            "land_dm_no": openapi.Schema(type=openapi.TYPE_STRING, example="DM12345"),
            "plot_no": openapi.Schema(type=openapi.TYPE_STRING, example="PLOT-101"),
            "dewa_no": openapi.Schema(type=openapi.TYPE_STRING, example="DEWA123"),
            "address_line_1": openapi.Schema(type=openapi.TYPE_STRING, example="Dubai Marina"),
            "address_line_2": openapi.Schema(type=openapi.TYPE_STRING, example="Dubai"),
            "landmark": openapi.Schema(type=openapi.TYPE_STRING, example="Near Metro Station"),
            "pincode": openapi.Schema(type=openapi.TYPE_STRING, example="00000"),
            "latitude": openapi.Schema(type=openapi.TYPE_NUMBER, example=25.2048),
            "longitude": openapi.Schema(type=openapi.TYPE_NUMBER, example=55.2708),
            "map_address": openapi.Schema(type=openapi.TYPE_STRING, example="Dubai Marina, Dubai"),
            "approx_rent": openapi.Schema(type=openapi.TYPE_NUMBER, example=75000),
        },
    ),
)

property_put = swagger_auto_schema(
    method="put",
    tags=PROPERTY_TAG,
    operation_summary="Update property",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["property_id"],
        properties={
            "property_id": openapi.Schema(type=openapi.TYPE_INTEGER, example=1),
            "property_name": openapi.Schema(type=openapi.TYPE_STRING, example="Marina Heights Updated"),
            "property_type": openapi.Schema(type=openapi.TYPE_STRING, example="APARTMENT"),
            "no_of_blocks": openapi.Schema(type=openapi.TYPE_INTEGER, example=3),
            "no_of_units": openapi.Schema(type=openapi.TYPE_INTEGER, example=80),
            "land_area": openapi.Schema(type=openapi.TYPE_NUMBER, example=30000),
            "address_line_1": openapi.Schema(type=openapi.TYPE_STRING, example="Business Bay"),
            "approx_rent": openapi.Schema(type=openapi.TYPE_NUMBER, example=85000),
        },
    ),
)


property_blocks_get = swagger_auto_schema(
    method="get",
    tags=PROPERTY_TAG,
    operation_summary="Get property blocks",
    manual_parameters=[
        openapi.Parameter("property_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=True, example=1),
    ],
)

property_blocks_post = swagger_auto_schema(
    method="post",
    tags=PROPERTY_TAG,
    operation_summary="Create property blocks",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["property_id", "blocks"],
        properties={
            "property_id": openapi.Schema(type=openapi.TYPE_INTEGER, example=1),
            "blocks": blocks_schema,
        },
    ),
)

property_blocks_put = swagger_auto_schema(
    method="put",
    tags=PROPERTY_TAG,
    operation_summary="Update property blocks",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["property_id", "blocks"],
        properties={
            "property_id": openapi.Schema(type=openapi.TYPE_INTEGER, example=1),
            "blocks": blocks_schema,
        },
    ),
)


property_images_get = swagger_auto_schema(
    method="get",
    tags=PROPERTY_TAG,
    operation_summary="Get property images",
    manual_parameters=[
        openapi.Parameter("property_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=True, example=1),
    ],
)

property_images_post = swagger_auto_schema(
    method="post",
    tags=PROPERTY_TAG,
    operation_summary="Upload property images",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["property_id", "images"],
        properties={
            "property_id": openapi.Schema(type=openapi.TYPE_INTEGER, example=1),
            "images": image_schema,
        },
    ),
)

property_images_delete = swagger_auto_schema(
    method="delete",
    tags=PROPERTY_TAG,
    operation_summary="Delete property image",
    manual_parameters=[
        openapi.Parameter("image_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=True, example=1),
    ],
)


property_document_types_get = swagger_auto_schema(
    method="get",
    tags=PROPERTY_TAG,
    operation_summary="Get property document types",
)

property_documents_get = swagger_auto_schema(
    method="get",
    tags=PROPERTY_TAG,
    operation_summary="Get property documents",
    manual_parameters=[
        openapi.Parameter("property_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=True, example=1),
    ],
)

property_documents_post = swagger_auto_schema(
    method="post",
    tags=PROPERTY_TAG,
    operation_summary="Upload property documents",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["property_id", "documents"],
        properties={
            "property_id": openapi.Schema(type=openapi.TYPE_INTEGER, example=1),
            "documents": document_schema,
        },
    ),
)

property_documents_delete = swagger_auto_schema(
    method="delete",
    tags=PROPERTY_TAG,
    operation_summary="Delete property document",
    manual_parameters=[
        openapi.Parameter("document_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=True, example=1),
    ],
)


unit_get = swagger_auto_schema(
    method="get",
    tags=PROPERTY_TAG,
    operation_summary="Get unit list or single unit",
    manual_parameters=[
        openapi.Parameter("unit_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("search", openapi.IN_QUERY, type=openapi.TYPE_STRING, required=False, example="101"),
        openapi.Parameter("property_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("block_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("no_of_bedrooms", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=2),
        openapi.Parameter("floor_no", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=5),
        openapi.Parameter("land_area_unit", openapi.IN_QUERY, type=openapi.TYPE_STRING, required=False, example="SQ_FT"),
        openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("page_size", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=10),
        openapi.Parameter("export", openapi.IN_QUERY, type=openapi.TYPE_STRING, required=False, example="csv"),
    ],
)

unit_post = swagger_auto_schema(
    method="post",
    tags=PROPERTY_TAG,
    operation_summary="Create unit",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["block_id", "unit_name"],
        properties={
            "block_id": openapi.Schema(type=openapi.TYPE_INTEGER, example=1),
            "unit_name": openapi.Schema(type=openapi.TYPE_STRING, example="A-101"),
            "unit_size": openapi.Schema(type=openapi.TYPE_NUMBER, example=950),
            "area": openapi.Schema(type=openapi.TYPE_STRING, example="950 SQ_FT"),
            "dm_no": openapi.Schema(type=openapi.TYPE_STRING, example="DM123"),
            "no_of_bedrooms": openapi.Schema(type=openapi.TYPE_INTEGER, example=2),
            "floor_no": openapi.Schema(type=openapi.TYPE_INTEGER, example=5),
            "parking_no": openapi.Schema(type=openapi.TYPE_STRING, example="P-12"),
            "no_of_balcony": openapi.Schema(type=openapi.TYPE_INTEGER, example=1),
            "land_no": openapi.Schema(type=openapi.TYPE_STRING, example="LAND123"),
            "unit_usage": openapi.Schema(type=openapi.TYPE_STRING, example="RESIDENTIAL"),
            "unit_type": openapi.Schema(type=openapi.TYPE_STRING, example="APARTMENT"),
            "sub_type": openapi.Schema(type=openapi.TYPE_STRING, example="2BHK"),
            "makani_no": openapi.Schema(type=openapi.TYPE_STRING, example="MK123"),
            "dewa_no": openapi.Schema(type=openapi.TYPE_STRING, example="DEWA123"),
            "rent": openapi.Schema(type=openapi.TYPE_NUMBER, example=60000),
            "security_deposit": openapi.Schema(type=openapi.TYPE_NUMBER, example=5000),
            "booking_amount": openapi.Schema(type=openapi.TYPE_NUMBER, example=2000),
            "maintenance_charges": openapi.Schema(type=openapi.TYPE_NUMBER, example=1500),
            "cycle": openapi.Schema(type=openapi.TYPE_STRING, example="YEARLY"),
            "notice_period": openapi.Schema(type=openapi.TYPE_STRING, example="60"),
            "commission_percent": openapi.Schema(type=openapi.TYPE_NUMBER, example=5),
            "unit_owners": owner_schema,
        },
    ),
)

unit_put = swagger_auto_schema(
    method="put",
    tags=PROPERTY_TAG,
    operation_summary="Update unit",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["unit_id"],
        properties={
            "unit_id": openapi.Schema(type=openapi.TYPE_INTEGER, example=1),
            "block_id": openapi.Schema(type=openapi.TYPE_INTEGER, example=1),
            "unit_name": openapi.Schema(type=openapi.TYPE_STRING, example="A-102"),
            "rent": openapi.Schema(type=openapi.TYPE_NUMBER, example=65000),
            "unit_owners": owner_schema,
        },
    ),
)


unit_images_get = swagger_auto_schema(
    method="get",
    tags=PROPERTY_TAG,
    operation_summary="Get unit images",
    manual_parameters=[
        openapi.Parameter("unit_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=True, example=1),
    ],
)

unit_images_post = swagger_auto_schema(
    method="post",
    tags=PROPERTY_TAG,
    operation_summary="Upload unit images",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["unit_id", "images"],
        properties={
            "unit_id": openapi.Schema(type=openapi.TYPE_INTEGER, example=1),
            "images": image_schema,
        },
    ),
)

unit_images_delete = swagger_auto_schema(
    method="delete",
    tags=PROPERTY_TAG,
    operation_summary="Delete unit image",
    manual_parameters=[
        openapi.Parameter("image_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=True, example=1),
    ],
)


unit_document_types_get = swagger_auto_schema(
    method="get",
    tags=PROPERTY_TAG,
    operation_summary="Get unit document types",
)

unit_documents_get = swagger_auto_schema(
    method="get",
    tags=PROPERTY_TAG,
    operation_summary="Get unit documents",
    manual_parameters=[
        openapi.Parameter("unit_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=True, example=1),
    ],
)

unit_documents_post = swagger_auto_schema(
    method="post",
    tags=PROPERTY_TAG,
    operation_summary="Upload unit documents",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["unit_id", "documents"],
        properties={
            "unit_id": openapi.Schema(type=openapi.TYPE_INTEGER, example=1),
            "documents": document_schema,
        },
    ),
)

unit_documents_delete = swagger_auto_schema(
    method="delete",
    tags=PROPERTY_TAG,
    operation_summary="Delete unit document",
    manual_parameters=[
        openapi.Parameter("document_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=True, example=1),
    ],
)