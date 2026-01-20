import json
from utilities.helper_functions import (
    prepare_response,
)
from utilities import (
    constants,
    status,
)
from user_service.models import (
    UserProfile
)
from utilities.decorator import is_request_authenticated
from public_api.models import (
    APIList,
    ApiAccess,
)
from public_api.utils import (
    generate_api_key,
    generate_secret_key,
)


@is_request_authenticated
def generate_keys(request):
    if request.method == "POST":
        data = json.loads(request.body)
        api_ids = data.get("api_ids", [])
        user_profile_id = data.get("user_profile_id")

        try:
            api_access = ApiAccess.objects.get(user_profile__id=user_profile_id)

            authorization_data = {
                "api_key": api_access.api_key,
                "secret_key": api_access.secret_key
            }

            return prepare_response(
                content=authorization_data,
                message=constants.API_KEY_SECRET_KEY_FETCHED, 
                status=status.HTTP_200_OK
            )
        
        except ApiAccess.DoesNotExist:

            api_key = generate_api_key()
            secret_key = generate_secret_key()

            api_objects = APIList.objects.filter(id__in=api_ids)
            user_profile = UserProfile.objects.get(id=user_profile_id)

            new_api_access = ApiAccess.objects.create(
                user_profile=user_profile,
                api_key=api_key,
                secret_key=secret_key,
                created_by=request.user
            )

            new_api_access.apis.add(*api_objects)
            authorization_data = {
                "api_key": new_api_access.api_key,
                "secret_key": new_api_access.secret_key
            }

        return prepare_response(
            content=authorization_data,
            message=constants.API_KEY_SECRET_KEY_CREATED, 
            status=status.HTTP_200_OK
        )

    else:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD, 
            status=status.HTTP_400_BAD_REQUEST
        )