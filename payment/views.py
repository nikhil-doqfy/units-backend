from property_management.models import LeasePropertyDetails
from utilities.helper_functions import prepare_response
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