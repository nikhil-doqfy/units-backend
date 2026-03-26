from lease.models import Lease
from payment.models import Payment,ChargeDetails
from utilities.helper_functions import prepare_response ,datetime_to_epoch_millis
from utilities import status, constants
from utilities.decorator import is_request_authenticated
from django.db.models import Sum
from django.db.models import Prefetch

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
        user = request.user  # UserProfile (Owner)

        page  = int(request.GET.get("page", 1))
        limit = int(request.GET.get("limit", 10))

        # Lease → unit → unit_owners (UnitOwner) → owner (Owner extends UserProfile)
        leases = Lease.objects.select_related(
            "unit__property_block_tower__property",
            "tenant__user",
        ).filter(
            unit__unit_owners__owner_id=user.id
        ).distinct().order_by("-id")

        from django.core.paginator import Paginator
        paginator = Paginator(leases, limit)
        page_obj  = paginator.get_page(page)

        response = []
        for lease in page_obj:
            unit     = lease.unit
            pb       = unit.property_block_tower if unit else None
            prop     = pb.property if pb else None
            tenant   = lease.tenant

            response.append({
                # 🔹 Tenant
                "tenant_name": tenant.user.get_full_name() if tenant and tenant.user else None,
                "tenant_no":   getattr(tenant, "user_code", None) if tenant else None,

                # 🔹 Property info
                "property_name": prop.property_name if prop else None,
                "room_no":       unit.unit_name or unit.code if unit else None,
                "unit_type":     getattr(unit, "property_type", None) if unit else None,

                # 🔹 Lease info
                "lease_no":     lease.code,
                "lease_status": lease.lease_status,
                "period_from":  datetime_to_epoch_millis(lease.start_date),
                "period_to":    datetime_to_epoch_millis(lease.end_date),

                # 🔹 Rent details
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

        filters = {
            "created_by": auth_user
        }

        if lease_id:
            filters["rental_account_id"] = lease_id

        payments = Payment.objects.filter(**filters).select_related(
            "bank", "rental_account"
        )

        data = []
        for payment in payments:
            data.append({
                "id": payment.id,
                "bank": payment.bank.name if payment.bank else None,
                "bank_account": payment.account_number,
                "cheque_number": payment.cheque_number,
                "cheque_date": datetime_to_epoch_millis(payment.cheque_date),
                "payment_type": {
                    "key": payment.method,
                    "value": payment.get_method_display()
                },
                "purpose": payment.reason_type,
           
                "amount": payment.amount,
                 "status":  payment.status,
               
                "created": datetime_to_epoch_millis(payment.created),
                "lease": {
                    "id": payment.rental_account.id,
                    "lease_number": payment.rental_account.lease_number
                }
            })

        return prepare_response(
            content=data,
            message="Rental payment data fetched successfully",
            status=status.HTTP_200_OK
        )
    else:
        return prepare_response(
          
            message=constants.INVALID_METHOD,
            status=status.HTTP_200_OK
        )



