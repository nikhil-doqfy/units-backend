import json
from utilities.helper_functions import prepare_response
from utilities import status, constants
from utilities.decorator import is_request_authenticated
from .models import Charge


@is_request_authenticated
def charges_api(request):

    user_profile = request.user

    if not user_profile.city or not user_profile.city.state or not user_profile.city.state.country:
        return prepare_response(
            message=constants.DATA_NOT_FOUND,
            status=status.HTTP_400_BAD_REQUEST
        )

    user_country = user_profile.city.state.country

    if request.method == "POST":

        data = json.loads(request.body or "{}")

        description = data.get("description")
        amount = data.get("amount")
        tax_code = data.get("tax_code", 0)
        is_editable = data.get("is_editable", True)

        if not description or amount is None:
            return prepare_response(
                message=constants.FIELD_REQUIRED,
                status=status.HTTP_400_BAD_REQUEST
            )

        charge = Charge.objects.create(
            description=description,
            amount=float(amount),
            tax_code=float(tax_code),
            country=user_country,
            is_editable=bool(is_editable),
            created_by=user_profile.user
        )

        return prepare_response(
            content=charge._get_charge_info(),
            message="Charges created successfully",
            status=status.HTTP_201_CREATED
        )

    if request.method == "GET":

        charge_id = request.GET.get("charge_id")

        filters = {"country": user_country}

        if charge_id:
            filters["id"] = charge_id

        charges = Charge.objects.filter(**filters).order_by("id")

        if charge_id:
            charge = charges.first()

            if not charge:
                return prepare_response(
                    message=constants.NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )

            return prepare_response(
                content=charge._get_charge_info(),
                message=constants.DATA_FETCHED_SUCCESSFULLY,
                status=status.HTTP_200_OK
            )

        data = [c._get_charge_info() for c in charges]

        return prepare_response(
            content=data,
            message=constants.DATA_FETCHED_SUCCESSFULLY,
            status=status.HTTP_200_OK
        )

    if request.method == "PUT":

        data = json.loads(request.body or "{}")
        charge_id = data.get("charge_id")

        if not charge_id:
            return prepare_response(
                message=constants.FIELD_REQUIRED,
                status=status.HTTP_400_BAD_REQUEST
            )

        charge = Charge.objects.filter(
            id=charge_id,
            country=user_country
        ).first()

        if not charge:
            return prepare_response(
                message=constants.NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        if "description" in data:
            charge.description = data["description"]

        if "amount" in data:
            charge.amount = float(data["amount"])

        if "tax_code" in data:
            charge.tax_code = float(data["tax_code"])

        if "is_editable" in data:
            charge.is_editable = bool(data["is_editable"])

        charge.save()

        return prepare_response(
            content=charge._get_charge_info(),
            message="Data updated successfully",
            status=status.HTTP_200_OK
        )

    if request.method == "DELETE":

        charge_id = request.GET.get("charge_id")

        if not charge_id:
            return prepare_response(
                message=constants.FIELD_REQUIRED,
                status=status.HTTP_400_BAD_REQUEST
            )

        charge = Charge.objects.filter(
            id=charge_id,
            country=user_country
        ).first()

        if not charge:
            return prepare_response(
                message=constants.NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        charge.delete()

        return prepare_response(
            message="Data deleted successfully",
            status=status.HTTP_200_OK
        )

    return prepare_response(
        message=constants.INVALID_REQUEST_METHOD,
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )

@is_request_authenticated
def toggle_charge_editable(request):

    if request.method != "PUT":
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    user_profile = request.user

    if not user_profile.city or not user_profile.city.state or not user_profile.city.state.country:
        return prepare_response(
            message=constants.DATA_NOT_FOUND,
            status=status.HTTP_400_BAD_REQUEST
        )

    user_country = user_profile.city.state.country

    data = json.loads(request.body or "{}")
    charge_id = data.get("charge_id")

    if not charge_id:
        return prepare_response(
            message=constants.FIELD_REQUIRED,
            status=status.HTTP_400_BAD_REQUEST
        )

    charge = Charge.objects.filter(
        id=charge_id,
        country=user_country
    ).first()

    if not charge:
        return prepare_response(
            message=constants.NOT_FOUND,
            status=status.HTTP_404_NOT_FOUND
        )

    charge.is_editable = not charge.is_editable
    charge.save()

    return prepare_response(
        content=charge._get_charge_info(),
        message="Charge editable status updated",
        status=status.HTTP_200_OK
    )