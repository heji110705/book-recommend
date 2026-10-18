from django.contrib import admin

from .models import Book, Bookshelf, ClickLog, Comment, Favorite, Rating


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "author",
        "category",
        "publisher",
        "pub_year",
        "rating_avg",
        "rating_count",
        "positive_rate",
        "topic",
    )
    list_filter = ("category", "pub_year", "topic")
    search_fields = ("title", "author", "publisher", "tags", "isbn")
    list_per_page = 30


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "book", "score", "created_at")
    list_filter = ("score",)
    search_fields = ("user__username", "book__title")
    list_per_page = 30


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "book", "polarity", "sentiment", "short_content", "created_at")
    list_filter = ("polarity",)
    search_fields = ("user__username", "book__title", "content")
    list_per_page = 30

    @admin.display(description="评论摘要")
    def short_content(self, obj):
        return obj.content[:30]


@admin.register(Bookshelf)
class BookshelfAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "book", "status", "updated_at")
    list_filter = ("status",)
    search_fields = ("user__username", "book__title")
    list_per_page = 30


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "book", "created_at")
    search_fields = ("user__username", "book__title")
    list_per_page = 30


@admin.register(ClickLog)
class ClickLogAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "book", "created_at")
    search_fields = ("user__username", "book__title")
    list_per_page = 30
