from django.contrib import admin

from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "gender", "fav_categories", "created_at")
    list_filter = ("gender",)
    search_fields = ("user__username", "bio")
    list_per_page = 30
