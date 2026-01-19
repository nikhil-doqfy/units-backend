from property_management.models import LeasePropertyDetails
from payment.models import Payment,ChargeDetails
from utilities.helper_functions import prepare_response ,datetime_to_epoch_millis
from utilities import status, constants
from utilities.decorator import is_request_authenticated


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
        
        leases = LeasePropertyDetails.objects.filter(**kwargs)

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
        user = request.user  # UserProfile

        # 🔹 Payments related to OWNER via property_unit → owner
        payments = Payment.objects.select_related(
            "rental_account",
            "rental_account__tenant",
            "rental_account__lease_property",
            "rental_account__lease_property__property",
        ).filter(
            rental_account__lease_property__owner=user
        )

        response = []

        for payment in payments:
            lease = payment.rental_account
            tenant = lease.tenant
            unit = lease.lease_property
            property_obj = unit.property if unit else None

            charges = ChargeDetails.objects.filter(
                lease=lease,
                is_selected=True
            )

            response.append({
                # 🔹 Tenant
                "tenant_name": tenant.user.get_full_name() if tenant else None,
                "tenant_no": tenant.user_code if tenant else None,

                # 🔹 Property info
                "property_name": property_obj.property_name if property_obj else None,
                "room_no": unit.apartment_no if unit else None,
                "unit_type": unit.property_type if unit else None,

                # 🔹 Lease info
                "lease_no": lease.lease_number,
                "lease_status": lease.lease_status,
                "period_from": datetime_to_epoch_millis(lease.lease_start_date),
                "period_to":datetime_to_epoch_millis(lease.lease_end_date),

                # 🔹 Rent details
                "year_rent": lease.annual_amount,
                "vat":None,

                "other_charges":None,
                # "vat": float(vat_amount),
                "total_rent": None,

                "payment_amount": payment.amount,
                "payment_method": payment.method,
                "payment_status": payment.status,
                "payment_reason": payment.reason_type,
            })

        return prepare_response(
            content=response,
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
    auth_user = request.user
 
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



