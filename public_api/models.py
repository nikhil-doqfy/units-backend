from django.db import models
from django.forms.models import model_to_dict
from utilities.helper_functions import (
    datetime_to_epoch,
)
from utilities import constants
from property_management.models import (
    Base,
)
from user_service.models import (
    UserProfile,
)



# =============================================================================
# Property Management – Public APIs
# =============================================================================

class APIList(models.Model):
    REQUEST_METHOD_CHOICES = (
        (constants.GET, "GET"),
        (constants.POST, "POST"),
        (constants.PUT, "PUT"),
        (constants.DELETE, "DELETE"),
        (constants.PATCH, "Patch"),
        (constants.OPTION, "Option")
    )
    name = models.CharField(max_length=255, unique=True)
    endpoint = models.CharField(max_length=255)
    request_method = models.CharField(max_length=50, choices=REQUEST_METHOD_CHOICES)

    def __str__(self): 
        return "{}-{}-{}".format(self.name, self.endpoint, self.request_method)

    def _get_api_info(self):
        data = model_to_dict(
            self,
            fields=(
                "id", 
                "name", 
                "path", 
                "request_method"
            )
        )
        data["created"] = datetime_to_epoch(self.created)
        return data


class ApiAccess(Base):
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    apis = models.ManyToManyField(APIList)
    api_key = models.CharField(max_length=32, unique=True)
    secret_key = models.CharField(max_length=64, unique=True)


    class Meta:
        unique_together = ("user_profile", "api_key", "secret_key")
    
    def __str__(self): 
        return "{} - {}".format(self.api_key, self.secret_key)
    
    def _get_api_access_info(self):
        data = model_to_dict(
            self,
            fields=(
                "id",
                "api_key",
                "secret_key",
            )
        )
        data["created"] = datetime_to_epoch(self.created)
        data["apis"] = [
            api._get_api_info()
            for api in self.apis.all()
        ]
        data["apis_count"] = self.apis.count()
        data["user_profile"] = self.user_profile._get_user_basic_info()
        return data