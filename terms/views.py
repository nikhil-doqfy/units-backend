import json
from terms.models import TermsAndConditions, TermCategory
from property_management.models import Country
from utilities.decorator import is_request_authenticated
from utilities.helper_functions import prepare_response
from utilities import constants, status  


def format_terms_data(terms_queryset):  # helper function
    data = []

    for term in terms_queryset:
        data.append({
            "key": term.key,
            "title": term.title,
            "description": term.description,
            "category": term.category.code.lower(),
            "country": term.country.name.upper()
        })

    return data


@is_request_authenticated
def terms_api(request):

    if request.method == constants.GET:

        key = request.GET.get("type") or request.GET.get("key")
        country_codes = request.GET.getlist("country")
        category_code = request.GET.get("category")   

        terms = TermsAndConditions.objects.select_related(
            "country", "category"
        ).filter(is_active=True)

        # Filter by key
        if key:
            terms = terms.filter(key__iexact=key)

        # Filter by country
        if country_codes:
            country_codes = [c.upper() for c in country_codes]
            terms = terms.filter(country__code__in=country_codes)

        # Filter by category
        if category_code:
            terms = terms.filter(category__code__iexact=category_code)

        terms = terms.order_by("id")

        data = format_terms_data(terms)

        return prepare_response(
            status=status.HTTP_200_OK,
            message=constants.DATA_FETCHED_SUCCESS,
            content=data
        )


    try:
        body = json.loads(request.body)
    except Exception:
        return prepare_response(
            message=constants.INVALID_JSON_BODY,
            status=status.HTTP_400_BAD_REQUEST
        )

    if request.method == constants.POST:

        key = body.get("key", "").lower()
        title = body.get("title")
        description = body.get("description")
        country_code = body.get("country")
        category_code = body.get("category", "").lower()

        if not all([key, title, description, country_code, category_code]):
            return prepare_response(
                message=constants.ALL_FIELD_REQUIRED,
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            country_obj = Country.objects.get(code__iexact=country_code)
        except Country.DoesNotExist:
            return prepare_response(
                message=constants.COMPANY_NOT_FOUND,
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            category_obj = TermCategory.objects.get(code__iexact=category_code)
        except TermCategory.DoesNotExist:
            return prepare_response(
                message=constants.ROLE_DOES_NOT_EXIST,
                status=status.HTTP_400_BAD_REQUEST
            )

        if TermsAndConditions.objects.filter(
            key=key,
            country=country_obj,
            category=category_obj,
            is_active=True
        ).exists():
            return prepare_response(
                message=constants.TERMS_MUST_BE_LIST,
                status=status.HTTP_400_BAD_REQUEST
            )

        TermsAndConditions.objects.create(
            key=key,
            title=title,
            description=description,
            country=country_obj,
            category=category_obj
        )

        return prepare_response(
            status=status.HTTP_201_CREATED,
            message=constants.TERMS_CREATED_SUCCESS
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
            term.title = title

        if description:
            term.description = description

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
            term = TermsAndConditions.objects.get(id=term_id, is_active=True)
        except TermsAndConditions.DoesNotExist:
            return prepare_response(
                message="Term not found",
                status=status.HTTP_404_NOT_FOUND
            )

        term.is_active = False
        term.save()

        return prepare_response(
            status=status.HTTP_200_OK,
            message="Term deleted successfully"
        )

    return prepare_response(
        message=constants.METHOD_NOT_ALLOWED,
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )