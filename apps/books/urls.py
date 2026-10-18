from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("books/", views.book_list, name="book_list"),
    path("books/<int:pk>/", views.book_detail, name="book_detail"),
    path("books/<int:pk>/rate/", views.rate_book, name="rate_book"),
    path("books/<int:pk>/comment/", views.add_comment, name="add_comment"),
    path("books/<int:pk>/shelf/", views.toggle_shelf, name="toggle_shelf"),
    path("books/<int:pk>/favorite/", views.toggle_favorite, name="toggle_favorite"),
]
