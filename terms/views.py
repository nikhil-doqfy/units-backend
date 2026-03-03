import json
from terms.models import TermsAndConditions, TermCategory
from user_service.models import Country
from utilities.decorator import is_request_authenticated
from utilities.helper_functions import prepare_response
from utilities import constants

@is_request_authenticated
def terms_api(request):
    if request.method == constants.GET:
        key = request.GET.get("type") or request.GET.get("key")
        country_codes = request.GET.getlist("country")
        terms = TermsAndConditions.objects.select_related("country", "category").filter(is_active=True)

        if key:
            terms = terms.filter(key__iexact=key)

        if country_codes:
            country_codes = [c.upper() for c in country_codes]
            terms = terms.filter(country__code__in=country_codes)

        terms = terms.order_by('id')

        data = [
            {
                "key": term.key,
                "title": term.title,
                "description": term.description,
                "category": term.category.code.lower(),
                "country": term.country.code
            }
            for term in terms
        ]

        return prepare_response(
            status=200,
            message=constants.DATA_FETCHED_SUCCESS,
            content=data
        )

    try:
        body = json.loads(request.body)
    except Exception:
        return prepare_response(message=constants.INVALID_JSON_BODY, status=400)

    if request.method == constants.POST:
        key = body.get("key", "").lower()
        title = body.get("title")
        description = body.get("description")
        country_code = body.get("country")
        category_code = body.get("category", "").lower()

        if not key or not title or not description or not country_code or not category_code:
            return prepare_response(message=constants.ALL_FIELD_REQUIRED, status=400)

        try:
            country_obj = Country.objects.get(code__iexact=country_code)
        except Country.DoesNotExist:
            return prepare_response(message=constants.COMPANY_NOT_FOUND, status=400)

        try:
            category_obj = TermCategory.objects.get(code__iexact=category_code)
        except TermCategory.DoesNotExist:
            return prepare_response(message=constants.ROLE_DOES_NOT_EXIST, status=400)

        if TermsAndConditions.objects.filter(key=key, country=country_obj, category=category_obj, is_active=True).exists():
            return prepare_response(message=constants.TERMS_MUST_BE_LIST, status=400)

        term = TermsAndConditions.objects.create(
            key=key,
            title=title,
            description=description,
            country=country_obj,
            category=category_obj
        )

        return prepare_response(
            status=201,
            message=constants.TERMS_CREATED_SUCCESS,
            content={
                "key": term.key,
                "title": term.title,
                "description": term.description,
                "category": term.category.code.lower(),
                "country": term.country.code
            }
        )

    if request.method == constants.PUT:
        term_id = body.get("id")
        if not term_id:
            return prepare_response(message="Term ID is required", status=400)

        try:
            term = TermsAndConditions.objects.get(id=term_id, is_active=True)
        except TermsAndConditions.DoesNotExist:
            return prepare_response(message="Term not found", status=404)

        term.title = body.get("title", term.title)
        term.description = body.get("description", term.description)
        term.is_active = body.get("is_active", term.is_active)
        term.save()

        return prepare_response(
            status=200,
            message="Term updated successfully",
            content={
                "key": term.key,
                "title": term.title,
                "description": term.description,
                "category": term.category.code.lower(),
                "country": term.country.code
            }
        )

    if request.method == constants.DELETE:
        term_id = body.get("id")
        if not term_id:
            return prepare_response(message="Term ID is required", status=400)

        try:
            term = TermsAndConditions.objects.get(id=term_id, is_active=True)
        except TermsAndConditions.DoesNotExist:
            return prepare_response(message="Term not found", status=404)

        term.is_active = False
        term.save()

        return prepare_response(
            status=200,
            message="Term deleted successfully"
        )

    return prepare_response(message=constants.METHOD_NOT_ALLOWED, status=405)