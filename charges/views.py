import json
from utilities.helper_functions import prepare_response
from utilities import status, constants
from utilities.decorator import is_request_authenticated
from property_management.utils import audit_logs
from .models import Charge
import logging

logger = logging.getLogger(__name__)
@is_request_authenticated
def charges(request):
    user_profile = request.user

    if not user_profile.city or not user_profile.city.state or not user_profile.city.state.country:
        logger.warning(
            "CHARGE_ACCESS_FAILED | user_id=%d | reason=COUNTRY_NOT_FOUND",request.user.id,)
        return prepare_response(
            message=constants.DATA_NOT_FOUND,
            status=status.HTTP_400_BAD_REQUEST
        )

    user_country = user_profile.city.state.country

    if request.method == "GET":
        charge_id = request.GET.get("charge_id")
        filters = {"country": user_country}

        if charge_id:
            filters["id"] = charge_id

        queryset = Charge.objects.filter(**filters).order_by("id")

        if charge_id:
            charge = queryset.first()
            if not charge:
                logger.warning(
                    "CHARGE_FETCH_FAILED | user_id=%d | charge_id=%s | reason=NOT_FOUND",
                    request.user.id, charge_id,)
                return prepare_response(
                    message=constants.NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )
            return prepare_response(
                content=charge._get_charge_info(),
                message=constants.DATA_FETCHED_SUCCESSFULLY,
                status=status.HTTP_200_OK
            )
        logger.info(
            "CHARGES_FETCHED_SUCCESS | user_id=%d | total_records=%d",
            request.user.id, queryset.count(),)
        return prepare_response(
            content=[c._get_charge_info() for c in queryset],
            message=constants.DATA_FETCHED_SUCCESSFULLY,
            status=status.HTTP_200_OK
        )

    elif request.method == "POST":
        data = json.loads(request.body)

        description = data.get("description")
        amount = data.get("amount")

        if not description or amount is None:
            logger.warning(
                "CHARGE_CREATE_FAILED | user_id=%d | reason=REQUIRED_FIELDS_MISSING",
                request.user.id,)
            return prepare_response(
                message=constants.FIELD_REQUIRED,
                status=status.HTTP_400_BAD_REQUEST
            )

        charge = Charge.objects.create(
            description=description,
            amount=float(amount),
            tax_code=float(data.get("tax_code", 0)),
            is_editable=bool(data.get("is_editable", True)),
            country=user_country,
            created_by=user_profile.user,
        )
        logger.info(
            "CHARGE_CREATED_SUCCESS | user_id=%d | charge_id=%d | description=%s | status=SUCCESS",
            request.user.id, charge.id, charge.description,)

        audit_logs(request, f"Charge '{charge.description}' created", constants.CREATED)
        return prepare_response(
            content=charge._get_charge_info(),
            message=constants.DATA_CREATED_SUCCESSFULLY,
            status=status.HTTP_201_CREATED
        )

    elif request.method == "PUT":
        data = json.loads(request.body)
        charge_id = data.get("charge_id")

        if not charge_id:
            logger.warning(
                "CHARGE_UPDATE_FAILED | user_id=%d | reason=CHARGE_ID_REQUIRED",
                request.user.id,)
            return prepare_response(
                message=constants.FIELD_REQUIRED,
                status=status.HTTP_400_BAD_REQUEST
            )

        charge = Charge.objects.filter(id=charge_id, country=user_country).first()
        if not charge:
            logger.warning(
                "CHARGE_UPDATE_FAILED | user_id=%d | charge_id=%s | reason=NOT_FOUND",
                request.user.id,charge_id,)
            return prepare_response(
                message=constants.NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        for field in ["description", "tax_code", "is_editable"]:
            if field in data and data[field] is not None:
                setattr(charge, field, data[field])

        if "amount" in data and data["amount"] is not None:
            charge.amount = float(data["amount"])

        if "tax_code" in data and data["tax_code"] is not None:
            charge.tax_code = float(data["tax_code"])

        charge.save()
        logger.info(
            "CHARGE_UPDATED_SUCCESS | user_id=%d | charge_id=%d | description=%s | status=SUCCESS",
            request.user.id, charge.id, charge.description, )
        audit_logs(request, f"Charge '{charge.description}' updated", constants.UPDATED)
        return prepare_response(
            content=charge._get_charge_info(),
            message=constants.DATA_UPDATED_SUCCESSFULLY,
            status=status.HTTP_200_OK
        )

    elif request.method == "DELETE":
        charge_id = request.GET.get("charge_id")

        if not charge_id:
            logger.warning(
                "CHARGE_DELETE_FAILED | user_id=%d | reason=CHARGE_ID_REQUIRED",request.user.id,)
            return prepare_response(
                message=constants.FIELD_REQUIRED,
                status=status.HTTP_400_BAD_REQUEST
            )

        charge = Charge.objects.filter(id=charge_id, country=user_country).first()
        if not charge:
            logger.warning("CHARGE_DELETE_FAILED | user_id=%d | charge_id=%s | reason=NOT_FOUND",
            request.user.id, charge_id,)
            return prepare_response(
                message=constants.NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        audit_logs(request, f"Charge '{charge.description}' deleted", constants.DELETED)
        logger.info(
            "CHARGE_DELETED_SUCCESS | user_id=%d | charge_id=%d | description=%s | status=SUCCESS",
            request.user.id, charge.id, charge.description, )
        charge.delete()

        return prepare_response(
            message=constants.DATA_DELETED_SUCCESSFULLY,
            status=status.HTTP_200_OK
        )

    else:
        logger.warning(
            "CHARGE_INVALID_METHOD | user_id=%d | method=%s",request.user.id,request.method,)
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
