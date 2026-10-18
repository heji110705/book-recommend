from django.contrib import admin

from .models import RecommendResult


@admin.register(RecommendResult)
class RecommendResultAdmin(admin.ModelAdmin):
    list_display = ("id", "algo", "user", "book", "score", "rank", "created_at")
    list_filter = ("algo",)
    search_fields = ("user__username", "book__title")
    list_per_page = 50
