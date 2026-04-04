from lease.models import Lease, LeaseTransaction
from utilities.helper_functions import prepare_response, datetime_to_epoch_millis
from utilities import status, constants
from utilities.decorator import is_request_authenticated
from django.core.paginator import Paginator


#=====================================
#PAYMENT METHOD VIEWS
#=====================================
@is_request_authenticated
def access_rental_account(request):
    if request.method == "GET":
        req_data = request.GET
        lease_id = req_data.get("lease_id")

        kwargs = {}

        if lease_id:
            kwargs["id"] = lease_id

        leases = Lease.objects.filter(**kwargs)

        lease_details = [
            lease._get_lease_details_info()
            for lease in leases
        ]
        return prepare_response(
            content=lease_details,
            message=constants.DATA_FETCHED_SUCCESSFULLY,
            status=status.HTTP_200_OK
        )

    else:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_400_BAD_REQUEST
        )


@is_request_authenticated
def owner_rent_amounts(request):
    if request.method != "GET":
        return prepare_response(
            message="Invalid request",
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        user = request.user

        page  = int(request.GET.get("page", 1))
        limit = int(request.GET.get("limit", 10))

        leases = Lease.objects.select_related(
            "unit__property_block_tower__property",
            "tenant__user",
        ).filter(
            unit__unit_owners__owner_id=user.id
        ).distinct().order_by("-id")

        paginator = Paginator(leases, limit)
        page_obj  = paginator.get_page(page)

        response = []
        for lease in page_obj:
            unit     = lease.unit
            pb       = unit.property_block_tower if unit else None
            prop     = pb.property if pb else None
            tenant   = lease.tenant

            response.append({
                "tenant_name": tenant.user.get_full_name() if tenant and tenant.user else None,
                "tenant_no":   getattr(tenant, "user_code", None) if tenant else None,
                "property_name": prop.property_name if prop else None,
                "room_no":       unit.unit_name or unit.code if unit else None,
                "unit_type":     getattr(unit, "property_type", None) if unit else None,
                "lease_no":     lease.code,
                "lease_status": lease.lease_status,
                "period_from":  datetime_to_epoch_millis(lease.start_date),
                "period_to":    datetime_to_epoch_millis(lease.end_date),
                "year_rent":     lease.annual_amount,
                "vat":           None,
                "other_charges": None,
                "total_rent":    None,
            })

        return prepare_response(
            content=response,
            paginator=page_obj,
            total_records=paginator.count,
            message="Rent amounts fetched successfully",
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return prepare_response(
            message=str(e),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@is_request_authenticated
def rental_payments(request):
    user_profile = request.user
    auth_user = request.user.user

    if request.method == "GET":
        lease_id = request.GET.get("lease_id")

        filters = {"created_by": auth_user}

        if lease_id:
            filters["lease_id"] = lease_id

        transactions = LeaseTransaction.objects.filter(**filters).select_related(
            "origin_bank", "lease"
        )

        data = []
        for t in transactions:
            data.append({
                "id": t.id,
                "origin_bank": t.origin_bank.name if t.origin_bank else None,
                "origin_account_number": t.origin_account_number,
                "cheque_number": t.cheque_number,
                "cheque_date": datetime_to_epoch_millis(t.cheque_date),
                "payment_type": t.payment_type,
                "cheque_type": t.cheque_type,
                "amount": t.amount,
                "status": t.status,
                "created": datetime_to_epoch_millis(t.created),
                "lease": {
                    "id": t.lease.id,
                    "lease_number": t.lease.code
                } if t.lease else None
            })

        return prepare_response(
            content=data,
            message="Rental payment data fetched successfully",
            status=status.HTTP_200_OK
        )
    else:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_400_BAD_REQUEST
        )
