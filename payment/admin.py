from django.contrib import admin

from payment.models import Bank


class BankAdmin(admin.ModelAdmin):
    list_display = ["id", "name"]


admin.site.register(Bank, BankAdmin)
