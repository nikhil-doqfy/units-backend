from django.contrib import admin
from .models import Charge

class ChargeAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "description",
        "amount",
        "tax_code",  
        "vat_amount",
        "total_amount",
        "is_editable",
    ]

    fields = [
        "description",
        "country",
        "amount",
        "tax_code",
        "vat_amount",
        "total_amount",
        "is_editable",
    ]

    readonly_fields = ["vat_amount", "total_amount"]

admin.site.register(Charge, ChargeAdmin)


    