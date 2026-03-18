from django.db import models
from django.forms.models import model_to_dict
from property_management.models import Base, Country


class Charge(Base): 

    description = models.CharField(max_length=255)

    country = models.ForeignKey(
        Country,
        on_delete=models.CASCADE,
        related_name="charges"
    )

    tax_code = models.FloatField(default=0)
    amount = models.FloatField()
    vat_amount = models.FloatField(default=0)
    total_amount = models.FloatField(default=0)
    is_editable = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        percent = self.tax_code or 0
        self.vat_amount = (self.amount * percent) / 100
        self.total_amount = self.amount + self.vat_amount
        super().save(*args, **kwargs)

    def __str__(self):
        return "{}-{}".format(self.description, self.country.name)

    def _get_charge_info(self):
        data = model_to_dict(self, fields=(
            "id",
            "description",
            "amount",
            "tax_code",
            "vat_amount",
            "total_amount",
            "is_editable"
        ))

        data["country"] = self.country._get_country_info()

        return data 
        