from django.db import models
from django.forms.models import model_to_dict
from utilities.helper_functions import datetime_to_epoch
from property_management.models import Base, City

#========================================
#PROPERTY MANAGEMENT PAYMENT FLOW MODELS
#========================================
class Bank(Base):
    name = models.CharField(max_length=100)
    city = models.ForeignKey(City, on_delete=models.CASCADE)
    branch_name = models.CharField(max_length=150)
    branch_code = models.CharField(max_length=20)
    bank_code = models.CharField(max_length=10, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    ifsc_code = models.CharField(max_length=11, null=True, blank=True)
    
    def __str__(self):
        return "{}-{}".format(self.name, self.city.name)
    
    def _get_bank_info(self):
        data = model_to_dict(
            self, 
            fields=(
                "id",
                "name",
            )
        )
        data["created"] = datetime_to_epoch(self.created)
        data["city"] = model_to_dict(self, fields=["id", "code", "name"])
        return data
    
