from django.contrib import admin
from public_api.models import (
    APIList,
    ApiAccess,
)


class APIListAdmin(admin.ModelAdmin):
    list_display =("id", "name", "request_method")


class ApiAccessAdmin(admin.ModelAdmin):
    list_display = ("id", "api_key", "secret_key", "user_profile")
    search_fields = ["id", "user_profile"]


admin.site.register(APIList, APIListAdmin)
admin.site.register(ApiAccess, ApiAccessAdmin)