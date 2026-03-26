import json
from terms.models import TermsAndConditions, TermCategory
from property_management.models import Country
from utilities.decorator import is_request_authenticated
from utilities.helper_functions import prepare_response
from utilities import constants, status


# ✅ Helper Function
def format_terms_data(terms_queryset):
    return [
        {
            "id": term.id,
            "key": term.key,
            "title": term.title,
            "description": term.description,
            "category": term.category.code,
            "country": term.country.code,
        }
        for term in terms_queryset
    ]


@is_request_authenticated
def terms_api(request):

    if request.method == constants.GET:
        key = request.GET.get("type") or request.GET.get("key")
        country_codes = request.GET.getlist("country")
        category_code = request.GET.get("category")

        terms = TermsAndConditions.objects.select_related(
            "country", "category"
        ).filter(is_active=True)

        if key:
            terms = terms.filter(key__iexact=key.strip())

        if country_codes:
            country_codes = [c.strip().upper() for c in country_codes]
            terms = terms.filter(country__code__in=country_codes)

        if category_code:
            terms = terms.filter(category__code__iexact=category_code.strip())

        terms = terms.order_by("id")

        return prepare_response(
            status=status.HTTP_200_OK,
            message="Terms fetched successfully",
            content=format_terms_data(terms)
        )

    # ===================== BODY PARSE =====================
    try:
        body = json.loads(request.body)
    except Exception:
        return prepare_response(
            message="Invalid JSON body",
            status=status.HTTP_400_BAD_REQUEST
        )

    if request.method == constants.POST:
        key = body.get("key", "").strip().lower()
        title = body.get("title", "").strip()
        description = body.get("description", "").strip()
        country_code = body.get("country", "").strip().upper()
        category_code = body.get("category", "").strip().lower()

        if not all([key, title, description, country_code, category_code]):
            return prepare_response(
                message="All fields are required",
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            country_obj = Country.objects.get(code__iexact=country_code)
        except Country.DoesNotExist:
            return prepare_response(
                message="Country not found",
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            category_obj = TermCategory.objects.get(code__iexact=category_code)
        except TermCategory.DoesNotExist:
            return prepare_response(
                message="Invalid category",
                status=status.HTTP_400_BAD_REQUEST
            )

        if TermsAndConditions.objects.filter(
            key=key,
            country=country_obj,
            category=category_obj,
            is_active=True
        ).exists():
            return prepare_response(
                message="Term already exists",
                status=status.HTTP_400_BAD_REQUEST
            )

        TermsAndConditions.objects.create(
            key=key,
            title=title,
            description=description,
            country=country_obj,
            category=category_obj,
            created_by=request.user.user
        )

        return prepare_response(
            status=status.HTTP_201_CREATED,
            message="Term created successfully"
        )

    if request.method == constants.PUT:

        term_id = body.get("id")
        title = body.get("title")
        description = body.get("description")

        if not term_id:
            return prepare_response(
                message="Term ID is required",
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            term = TermsAndConditions.objects.get(id=term_id, is_active=True)
        except TermsAndConditions.DoesNotExist:
            return prepare_response(
                message="Term not found",
                status=status.HTTP_404_NOT_FOUND
            )

        if title:
            term.title = title.strip()

        if description:
            term.description = description.strip()

        term.save()

        return prepare_response(
            status=status.HTTP_200_OK,
            message="Term updated successfully"
        )

    if request.method == constants.DELETE:

        term_id = body.get("id")

        if not term_id:
            return prepare_response(
                message="Term ID is required",
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            term_id = int(term_id)
        except (TypeError, ValueError):
            return prepare_response(
                message="Invalid Term ID",
                status=status.HTTP_400_BAD_REQUEST
            )

        term = TermsAndConditions.objects.filter(id=term_id).first()

        if not term:
            return prepare_response(
                message="Term not found",
                status=status.HTTP_404_NOT_FOUND
            )

        term.delete()

        return prepare_response(
            status=status.HTTP_200_OK,
            message="Term deleted successfully"
        )

    return prepare_response(
        message="Method not allowed",
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )