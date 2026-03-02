from django.db.models import Q
from rest_framework.decorators import api_view
from rest_framework import status

from terms.models import TermAndCondition, TermCategory
from user_service.models import Country
from utilities.helper_functions import prepare_response


ALLOWED_KEYS = ["login_signup", "commercial"]


@api_view(["GET", "POST"])
def terms_list_create(request):

    if request.method == "GET":

        country_param = request.GET.get("country")
        category_param = request.GET.get("category")
        key_param = request.GET.get("key")

        terms = TermAndCondition.objects.filter(is_active=True)

        if country_param:
            terms = terms.filter(
                Q(country__code__iexact=country_param) |
                Q(country__name__icontains=country_param)
            )

        if category_param:
            terms = terms.filter(
                category__code__iexact=category_param
            )

        if key_param:
            terms = terms.filter(
                key__iexact=key_param
            )

        content = [
            {
                "id": term.id,
                "key": term.key,
                "title": term.title,
                "description": term.description,
                "country": term.country.code,
                "category": term.category.code,
            }
            for term in terms
        ]

        return prepare_response(
            content=content,
            message="Terms fetched successfully",
            status=status.HTTP_200_OK,
        )


    if request.method == "POST":

        key = request.data.get("key", "").lower()
        title = request.data.get("title")
        description = request.data.get("description")
        country_param = request.data.get("country")
        category_param = request.data.get("category")

        if not all([key, title, description, country_param, category_param]):
            return prepare_response(
                message="All fields are required",
                status=status.HTTP_400_BAD_REQUEST,
            )

        if key not in ALLOWED_KEYS:
            return prepare_response(
                message="Invalid key. Allowed: login_signup, commercial",
                status=status.HTTP_400_BAD_REQUEST,
            )

 
        try:
            country = Country.objects.get(
                Q(code__iexact=country_param) |
                Q(name__icontains=country_param)
            )
        except Country.DoesNotExist:
            return prepare_response(
                message="Invalid country",
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            category = TermCategory.objects.get(
                code__iexact=category_param
            )
        except TermCategory.DoesNotExist:
            return prepare_response(
                message="Invalid category",
                status=status.HTTP_400_BAD_REQUEST,
            )

        if TermAndCondition.objects.filter(
            key=key,
            country=country,
            category=category
        ).exists():
            return prepare_response(
                message="Term already exists for this country and category",
                status=status.HTTP_400_BAD_REQUEST,
            )

        term = TermAndCondition.objects.create(
            key=key,
            title=title,
            description=description,
            country=country,
            category=category,
        )

        content = {
            "id": term.id,
            "key": term.key,
            "title": term.title,
            "description": term.description,
            "country": term.country.code,
            "category": term.category.code,
        }

        return prepare_response(
            content=content,
            message="Term created successfully",
            status=status.HTTP_201_CREATED,
        )


@api_view(["PUT", "PATCH", "DELETE"])
def terms_update_delete(request, pk):

    try:
        term = TermAndCondition.objects.get(id=pk)
    except TermAndCondition.DoesNotExist:
        return prepare_response(
            message="Term not found",
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method in ["PUT", "PATCH"]:

        key = request.data.get("key", term.key).lower()
        title = request.data.get("title", term.title)
        description = request.data.get("description", term.description)
        country_param = request.data.get("country")
        category_param = request.data.get("category")

        if key not in ALLOWED_KEYS:
            return prepare_response(
                message="Invalid key",
                status=status.HTTP_400_BAD_REQUEST,
            )

        if country_param:
            try:
                term.country = Country.objects.get(
                    Q(code__iexact=country_param) |
                    Q(name__icontains=country_param)
                )
            except Country.DoesNotExist:
                return prepare_response(
                    message="Invalid country",
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if category_param:
            try:
                term.category = TermCategory.objects.get(
                    code__iexact=category_param
                )
            except TermCategory.DoesNotExist:
                return prepare_response(
                    message="Invalid category",
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if TermAndCondition.objects.filter(
            key=key,
            country=term.country,
            category=term.category
        ).exclude(id=term.id).exists():
            return prepare_response(
                message="Duplicate term exists",
                status=status.HTTP_400_BAD_REQUEST,
            )

        term.key = key
        term.title = title
        term.description = description
        term.save()

        content = {
            "id": term.id,
            "key": term.key,
            "title": term.title,
            "description": term.description,
            "country": term.country.code,
            "category": term.category.code,
        }

        return prepare_response(
            content=content,
            message="Term updated successfully",
            status=status.HTTP_200_OK,
        )

    if request.method == "DELETE":
        term.delete()
        return prepare_response(
            message="Term deleted successfully",
            status=status.HTTP_200_OK,
        )