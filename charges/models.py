from django.db import models
from django.forms.models import model_to_dict
from user_service.models import Country


class Charge(models.Model):
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


    @property
    def tax_label(self):
        if not self.tax_code or self.tax_code <= 0:
            return "VAT@nil"

        country_name = self.country.name.lower()

        if country_name == "india":
            return f"GST@{self.tax_code}%"
        elif country_name in ["uae", "dubai", "united arab emirates"]:
            return f"VAT@{self.tax_code}%"
        else:
            return f"VAT@{self.tax_code}%"

    def __str__(self):
        return f"{self.description} - {self.country.name}"

    def _get_charge_info(self):
        data = model_to_dict(self, fields=(
            "id",
            "description",
            "amount",  
            "tax_code",
            "vat_amount",
            "total_amount",
            "is_editable",
        ))

        
        data["country"] = {
            "id": self.country.id,
            "name": self.country.name,
            "code": self.country.code,
        }

        data["tax_label"] = self.tax_label
        return data

        