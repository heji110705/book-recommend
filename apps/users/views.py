from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.shortcuts import redirect, render

from apps.books.models import Book, Bookshelf, ClickLog, Favorite, Rating


class RegisterForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("username", "email")


def register(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            messages.success(request, "注册成功，欢迎来到墨韵书荐！先花 10 秒选几个你感兴趣的方向吧。")
            return redirect("onboarding")
    else:
        form = RegisterForm()
    return render(request, "users/register.html", {"form": form})


@login_required
def onboarding(request):
    """冷启动兴趣引导：选择偏好分类，作为新用户的初始画像"""
    profile = request.user.profile
    if request.method == "POST":
        valid_names = {name for name, _ in Book.CATEGORY_CHOICES}
        chosen = [c for c in request.POST.getlist("categories") if c in valid_names]
        if not chosen:
            messages.warning(request, "请至少选择一个感兴趣的分类。")
        else:
            profile.fav_categories = "，".join(chosen)
            profile.onboarded = True
            profile.save()
            messages.success(request, "兴趣已记录，马上为你生成专属书单！")
            return redirect("recommend_page")
    # 每个分类展示几本代表作供参考
    cats = []
    selected = [c for c in profile.fav_categories.replace(",", "，").split("，") if c]
    for name, _ in Book.CATEGORY_CHOICES:
        sample = Book.objects.filter(category=name).order_by(
            "-douban_rating", "-douban_votes")[:4]
        cats.append({"name": name, "books": sample,
                     "checked": name in selected})
    return render(request, "users/onboarding.html", {"cats": cats})


@login_required
def profile(request):
    ratings = (
        Rating.objects.filter(user=request.user)
        .select_related("book")
        .order_by("-created_at")
    )
    shelf = Bookshelf.objects.filter(user=request.user).select_related("book")
    shelves = {
        "want": shelf.filter(status="want"),
        "reading": shelf.filter(status="reading"),
        "read": shelf.filter(status="read"),
    }
    favorites = Favorite.objects.filter(user=request.user).select_related("book")
    n_clicks = ClickLog.objects.filter(user=request.user).count()
    context = {
        "ratings": ratings,
        "shelves": shelves,
        "favorites": favorites,
        "n_ratings": ratings.count(),
        "n_favorites": favorites.count(),
        "n_shelf": shelf.count(),
        "n_clicks": n_clicks,
    }
    return render(request, "users/profile.html", context)
