from django.db import models
from django.forms.models import model_to_dict
from utilities.helper_functions import datetime_to_epoch
from utilities import constants
from property_management.models import Base, LeasePropertyDetails
from user_service.models import City

#========================================
#PROPERTY MANAGEMENT PAYMENT FLOW MODELS
#========================================
class Bank(Base):
    name = models.CharField(max_length=100)
    city = models.ForeignKey(City, on_delete=models.CASCADE)
    branch_name = models.CharField(max_length=150, null=True, blank=True)
    branch_code = models.CharField(max_length=20, null=True, blank=True)
    bank_code = models.CharField(max_length=10, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    swift_code = models.CharField(max_length=11, null=True, blank=True)
    
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
    

class ChargeType(Base):
    name = models.CharField(max_length=100)
    default_tax_code = models.CharField(max_length=20)
    
    def __str__(self):
        return self.name
    
    def _get_charge_type_info(self):
        data = model_to_dict(
            self, 
            fields=(
                "id",
                "name",
                "default_tax_code",
            )
        )
        data["created"] = datetime_to_epoch(self.created)
        return data


class ChargeDetails(Base):
    lease = models.ForeignKey(LeasePropertyDetails, on_delete=models.CASCADE)
    description = models.ForeignKey(ChargeType, on_delete=models.CASCADE)
    tax_code = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    vat_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    is_selected = models.BooleanField(default=True)
    
    def __str__(self): 
        return "{}-{}".format(self.description.name, self.tax_code)
    
    def _get_charge_details_info(self):
        data =  model_to_dict(self, fields=(
            "id", 
            "description", 
            "amount",
            "tax_code",
            "vat_amount",
            "total_amount",
            "is_selected"
        ))
        data["lease_detail"] = model_to_dict(self, fields=["id", "lease_number"])
        data["created"] = datetime_to_epoch(self.created)
        return data
    
 
class Payment(Base):
    PAYMENT_METHODS_CHOICES = (
    (constants.CASH, "Cash"),
    (constants.CHEQUE, "Cheque"),
    (constants.CREDIT_CARD, "Credit Card"),
    (constants.DEBIT_CARD, "Debit Card"),
    (constants.NET_BANKING, "Net Banking"),
)
    
    REASONS_TYPE_CHOICES = (
        (constants.RENT, "Rent"),
        (constants.OTHER, "Other"),
    )
    
    PAYMENT_STATUS_CHOICES = (
        (constants.PAYMENT_PENDING, "Payment Pending"),
        (constants.PAYMENT_SUCCESSFUL, "Payment Successful"),
        (constants.PAYMENT_FAILED, "Payment Failed"),
        (constants.PAYMENT_BOUNCED, "Payment Bounced"),
    )
         
    rental_account = models.ForeignKey(LeasePropertyDetails, related_name='payments', on_delete=models.CASCADE)
    bank = models.ForeignKey(Bank, on_delete=models.CASCADE, null=True, blank=True)
    method = models.CharField(max_length=20, choices=PAYMENT_METHODS_CHOICES, default=constants.CHEQUE)
    reason_type = models.CharField(max_length=20, choices=REASONS_TYPE_CHOICES, default=constants.RENT)
    amount = models.FloatField(default=0)
    payee_name = models.CharField(max_length=100, null=True, blank=True)
    payee_email = models.CharField(max_length=100, null=True, blank=True)
    payee_contact = models.CharField(max_length=100, null=True, blank=True)
    account_number = models.CharField(max_length=50, blank=True, null=True)
    cheque_number = models.CharField(max_length=50, blank=True, null=True)
    cheque_date = models.DateTimeField(null=True, blank=True)
    scanned_image = models.ImageField(upload_to='scans/', null=True, blank=True)
    status = models.CharField(max_length=50,choices=PAYMENT_STATUS_CHOICES, default=constants.PAYMENT_PENDING)
 
    def __str__(self): 
        return "{}-{}-{}".format(self.payee_name, self.account_number, self.status)
    
    def _get_payment_info(self):
        data =  model_to_dict(self, fields=(
            "id", 
            "amount", 
            "payee_name",
            "payee_email",
            "payee_contact",
            "account_number",
            "cheque_number"
        )) 
        data["lease_detail"] = model_to_dict(self, fields=["id", "lease_number"])
        data["payment_method"] = {"Key": self.method, "value": self.get_method_display()}
        data["reason_type"] = {"key": self.reason_type, "value": self.get_reason_type_display()}
        data["status"] = {"key": self.status, "value": self.get_status_display()}
        data["created"] = datetime_to_epoch(self.created)
        return data




