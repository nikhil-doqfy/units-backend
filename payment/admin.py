from django.contrib import admin

from payment.models import (
    Bank,
    ChargeType,
    ChargeDetails,
    Payment
)


class BankAdmin(admin.ModelAdmin):
    list_display = ["id", "name"]
    

class ChargeTypeAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "default_tax_code"]


class ChargeDetailsAdmin(admin.ModelAdmin):
    list_display = ["id", "tax_code", "vat_amount", "total_amount"]


class PaymentAdmin(admin.ModelAdmin):
    list_display = ["id", "payee_name", "payee_contact", "account_number", "cheque_number", "status","created"]
    search_fields = ["cheque_number"]
    
admin.site.register(Bank, BankAdmin)
admin.site.register(ChargeType, ChargeTypeAdmin)
admin.site.register(ChargeDetails, ChargeDetailsAdmin)
admin.site.register(Payment, PaymentAdmin)