from django.db import models
from property_management.models import Base
from utilities import constants
from user_service.models import Documents
from charges.models import Charge


class Template(Base):
    name = models.CharField(max_length=100, null=True, blank=True)
    template_path = models.CharField(max_length=1000, null=True, blank=True)
    is_predefined = models.BooleanField(default=False)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


class TemplateField(Base):
    FIELD_TYPE_CHOICES = (
        (constants.NUMBER, "Number"),
        (constants.DATE, "Date"),
        (constants.TEXT, "Text"),
        (constants.RADIO, "Radio"),
        (constants.CHOICE, "Choice"),
        (constants.CHECKBOX, "Check Box"),
    )
    template = models.ForeignKey(Template, on_delete=models.CASCADE, null=True, blank=True)
    name_attribute = models.CharField(max_length=150, null=True, blank=True)
    id_attribute = models.CharField(max_length=150, null=True, blank=True)
    value_attribute = models.CharField(max_length=150, null=True, blank=True)
    class_attribute = models.CharField(max_length=150, null=True, blank=True)
    label_attribute = models.CharField(max_length=150)
    html_tag = models.CharField(max_length=20, choices=FIELD_TYPE_CHOICES)
    required = models.BooleanField(default=False)
    min_value = models.IntegerField(null=True, blank=True)
    max_value = models.IntegerField(null=True, blank=True)
    min_length = models.IntegerField(null=True, blank=True)
    max_length = models.IntegerField(null=True, blank=True)
    pattern = models.CharField(max_length=20, null=True, blank=True)
    predefined_value = models.CharField(max_length=200, null=True, blank=True)

    def __str__(self):
        return f"{self.label_attribute} - {self.template.name}"


class TemplateValue(Base):
    template_field = models.ForeignKey(TemplateField, on_delete=models.CASCADE, null=True, blank=True)
    value = models.TextField(blank=True, default="")
    lease = models.ForeignKey(
        "Lease",
        on_delete=models.CASCADE, null=True, blank=True
    )

    def __str__(self):
        return f"Field: {self.template_field} | Lease ID: {self.lease.id}"


class Lease(Base):
    code = models.CharField(max_length=255, blank=True)
    unit = models.ForeignKey(
        "property.Unit",
        on_delete=models.CASCADE,
        related_name="leases",
    )

    tenant = models.ForeignKey(
        "user_service.Tenant",
        on_delete=models.CASCADE
    )

    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    grace_start_date = models.DateTimeField(null=True, blank=True)
    grace_end_date = models.DateTimeField(null=True, blank=True)
    remarks = models.TextField(null=True, blank=True)
    lease_status = models.CharField(
        max_length=20,
        choices=constants.LEASE_STATUS_CHOICES,
        default=constants.LEASE_STATUS_CHOICES[0][0]
    )
    lease_stage = models.CharField(
        max_length=20,
        choices=constants.LEASE_STAGE_CHOICES,
        default=constants.BASIC_DETAILS,
    )
    pdf_path = models.CharField(max_length=2000, null=True, blank=True)
    annual_amount = models.FloatField(null=True, blank=True)
    actual_annual_amount = models.FloatField(null=True, blank=True)
    booking_amount = models.FloatField(null=True, blank=True)
    maintenance_charges = models.FloatField(null=True, blank=True)
    rent = models.FloatField(null=True, blank=True)
    security_deposit = models.FloatField(null=True, blank=True)
    commission = models.FloatField(null=True, blank=True)
    notice_period = models.IntegerField(null=True, blank=True)
    discount = models.FloatField(null=True, blank=True)
    contract_amount = models.FloatField(null=True, blank=True)
    payment_count = models.IntegerField(null=True, blank=True, help_text="Number of installments")
    shell_and_core = models.BooleanField(default=False, help_text="Is the property Shell?")
    platform = models.CharField(
        max_length=20,
        choices=constants.PLATFORM_CHOICES,
        null=True,
        blank=True,
    )

    def __str__(self):
        return "{}-{}".format(self.code or self.id, self.lease_status)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.code:
            self.code = f"LS{self.pk:05d}"
            Lease.objects.filter(pk=self.pk).update(code=self.code)



class LeaseDocuments(Documents):
    lease = models.ForeignKey(Lease, on_delete=models.CASCADE, related_name="lease_documents")

    def __str__(self):
        return f"{self.lease}"


class LeaseTransaction(Documents):
    code = models.CharField(max_length=255, blank=True)
    lease = models.ForeignKey(Lease, on_delete=models.CASCADE, related_name="lease_cheques")
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    cheque_date = models.DateTimeField()
    origin_bank = models.ForeignKey("payment.Bank", on_delete=models.CASCADE, related_name="origin_cheques")
    selltlement_bank = models.ForeignKey("payment.Bank", on_delete=models.CASCADE, related_name="settlement_cheques")
    origin_account_number = models.IntegerField()
    settlement_account_number = models.IntegerField()
    amount = models.IntegerField()
    cheque_type = models.CharField(
        max_length=20,
        choices=constants.CHEQUE_TYPE_CHOICES,
        default=constants.RENT_CHEQUE,
    )
    payment_type = models.CharField(
        max_length=20,
        choices=constants.PAYMENT_TYPE_CHOICES,
        default=constants.PAYMENT_TYPE_CHEQUE,
    )
    cheque_number = models.CharField(max_length=100, null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=constants.CHEQUE_STATUS_CHOICES,
        default=constants.CHEQUE_STATUS_BALANCE,
    )

    def __str__(self):
        return "{}-{}".format(self.code or self.id, self.lease_id)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.code:
            self.code = f"LT{self.pk:05d}"
            LeaseTransaction.objects.filter(pk=self.pk).update(code=self.code)


class LeaseCharge(Base):
    lease = models.ForeignKey(Lease, on_delete=models.CASCADE, related_name="lease_charges")
    charge = models.ForeignKey(Charge, on_delete=models.CASCADE, related_name="lease_charges")
    amount = models.FloatField()
    vat = models.FloatField(default=0)
    total = models.FloatField(default=0)

    def save(self, *args, **kwargs):
        self.vat = round(self.amount * (self.charge.tax_code or 0) / 100, 2)
        self.total = round(self.amount + self.vat, 2)
        super().save(*args, **kwargs)

    def _serialize(self):
        return {
            "id": self.id,
            "charge_id": self.charge_id,
            "description": self.charge.description,
            "amount": self.amount,
            "tax_code": self.charge.tax_code,
            "vat": self.vat,
            "total": self.total,
        }