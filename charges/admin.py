from django.contrib import admin
from .models import Charge


@admin.register(Charge)
class ChargeAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "description",
        "country",
        "amount",
        "vat_display",  
        "vat_amount",
        "total_amount",
        "is_editable",
    )

    fields = (
        "description",
        "country",
        "amount",
        "tax_code",
        "vat_amount",
        "total_amount",
        "is_editable",
    )

    readonly_fields = ("vat_amount", "total_amount")

    def vat_display(self, obj):
        return obj.tax_label

    vat_display.short_description = "Tax code"


    