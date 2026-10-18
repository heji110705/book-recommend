from django.urls import path

from . import views

urlpatterns = [
    path("", views.recommend_page, name="recommend_page"),
]
