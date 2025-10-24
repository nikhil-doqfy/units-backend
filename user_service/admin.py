from django.contrib import admin
from user_service.models import UserProfile


# ---------- Register your models here ----------

class UserProfileAdmin(admin.ModelAdmin):
    list_display = ["id", "email", "user_type"]


admin.site.register(UserProfile, UserProfileAdmin)