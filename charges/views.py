import json
from utilities.helper_functions import prepare_response
from utilities import status, constants
from utilities.decorator import is_request_authenticated
from .models import Charge
from user_service.models import Country


@is_request_authenticated
def charges_api(request):
    try:

        if request.method == "POST":
            data = json.loads(request.body)

            description = data.get("description")
            amount = data.get("amount")
            tax_code = data.get("tax_code", 0)
            is_editable = data.get("is_editable", True)

            #  Accept country name 
            country_name = data.get("country")   # "India" or "UAE"

            if not description or not amount or not country_name:
                return prepare_response(
                    message=constants.FIELD_REQUIRED,
                    status=status.HTTP_400_BAD_REQUEST
                )

            country = Country.objects.filter(name__iexact=country_name).first()
            if not country:
                return prepare_response(
                    message="Invalid country name",
                    status=status.HTTP_400_BAD_REQUEST
                )

            charge = Charge.objects.create(
                description=description,
                amount=float(amount),
                tax_code=float(tax_code),
                country=country,
                is_editable=is_editable
            )

            return prepare_response(
                content=charge._get_charge_info(),
                message="Charge created successfully",
                status=status.HTTP_201_CREATED
            )

        if request.method == "GET":
            country_name = request.GET.get("country")

            charges = Charge.objects.all()

            if country_name:
                charges = charges.filter(country__name__iexact=country_name)

            charges = charges.order_by("id")

            data = [c._get_charge_info() for c in charges]

            return prepare_response(
                content=data,
                message=constants.DATA_FETCHED_SUCCESSFULLY,
                status=status.HTTP_200_OK
            )

        if request.method == "PUT":
            data = json.loads(request.body)
            charge_id = data.get("id")

            charge = Charge.objects.filter(id=charge_id).first()
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
                charge.is_editable = data["is_editable"]


            if "country" in data:
                country = Country.objects.filter(name__iexact=data["country"]).first()
                if not country:
                    return prepare_response(
                        message="Invalid country name",
                        status=status.HTTP_400_BAD_REQUEST
                    )
                charge.country = country

            charge.save()

            return prepare_response(
                content=charge._get_charge_info(),
                message="Charge updated successfully",
                status=status.HTTP_200_OK
            )

        if request.method == "DELETE":
            charge_id = request.GET.get("id")

            charge = Charge.objects.filter(id=charge_id).first()
            if not charge:
                return prepare_response(
                    message=constants.NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )

            charge.delete()

            return prepare_response(
                message="Charge deleted successfully",
                status=status.HTTP_200_OK
            )

        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    except Exception as e:
        return prepare_response(
            message=str(e),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

