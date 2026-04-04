from django.contrib import admin
from property_management.models import Country, State, City, AuditLog

@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "code"]
    search_fields = ["name", "code"]


@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "country", "code"]
    list_filter = ["country"]
    search_fields = ["name", "code"]


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "state", "code"]
    list_filter = ["state"]
    search_fields = ["name", "code"]

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["id","userprofile","action_type","message","created"]
    list_filter = ["action_type","created"]
    search_fields = ["message","userprofile__user__username"]