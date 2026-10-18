from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from .models import Book, Bookshelf, ClickLog, Comment, Favorite, Rating
from .services import analyze_and_save_comment, recompute_book

ORDER_CHOICES = {
    "hot": ("-rating_count", "-rating_avg"),
    "rating": ("-douban_rating", "-rating_count"),
    "new": ("-pub_year", "-rating_count"),
    "price": ("price",),
}


def _category_counts():
    """有书的分类及数量，按数量降序"""
    rows = (
        Book.objects.values("category")
        .annotate(n=Count("id"))
        .order_by("-n")
    )
    return [(r["category"], r["n"]) for r in rows]


def home(request):
    """豆瓣风首页：榜单、高分、新书、标签云、数据概览"""
    top_rank = Book.objects.order_by("-douban_rating", "-douban_votes")[:10]
    hot = Book.objects.order_by("-rating_count", "-rating_avg")[:12]
    high = Book.objects.filter(douban_rating__gt=0).order_by("-douban_rating", "?")[:12]
    new_arrivals = Book.objects.filter(pub_year__isnull=False).order_by("-pub_year", "-rating_count")[:12]

    # 标签词频（排除与分类同名的首标签）
    tag_count = {}
    for tags in Book.objects.values_list("tags", flat=True):
        for t in tags.split("，")[1:]:
            t = t.strip()
            if t:
                tag_count[t] = tag_count.get(t, 0) + 1
    hot_tags = sorted(tag_count.items(), key=lambda x: -x[1])[:18]

    stats = {
        "books": Book.objects.count(),
        "users": User.objects.count(),
        "ratings": Rating.objects.count(),
        "comments": Comment.objects.count(),
    }
    context = {
        "top_rank": top_rank,
        "hot": hot,
        "high": high,
        "new_arrivals": new_arrivals,
        "hot_tags": hot_tags,
        "categories": _category_counts(),
        "stats": stats,
    }
    return render(request, "books/home.html", context)


def book_list(request):
    q = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()
    order = request.GET.get("order", "hot")

    qs = Book.objects.all()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(subtitle__icontains=q)
            | Q(author__icontains=q)
            | Q(tags__icontains=q)
            | Q(publisher__icontains=q)
            | Q(description__icontains=q)
        )
    if category:
        qs = qs.filter(category=category)
    qs = qs.order_by(*ORDER_CHOICES.get(order, ORDER_CHOICES["hot"]))

    paginator = Paginator(qs, 18)
    page = paginator.get_page(request.GET.get("page"))

    rank_side = Book.objects.order_by("-douban_rating", "-douban_votes")[:10]
    context = {
        "page_obj": page,
        "books": page.object_list,
        "categories": _category_counts(),
        "q": q,
        "category": category,
        "order": order,
        "rank_side": rank_side,
    }
    return render(request, "books/book_list.html", context)


def book_detail(request, pk):
    book = get_object_or_404(Book, pk=pk)
    if request.user.is_authenticated:
        ClickLog.objects.get_or_create(user=request.user, book=book)

    user_rating = None
    shelf_status = None
    is_favorite = False
    if request.user.is_authenticated:
        r = Rating.objects.filter(user=request.user, book=book).first()
        user_rating = r.score if r else None
        sh = Bookshelf.objects.filter(user=request.user, book=book).first()
        shelf_status = sh.status if sh else None
        is_favorite = Favorite.objects.filter(user=request.user, book=book).exists()

    similar = (
        Book.objects.filter(category=book.category)
        .exclude(pk=book.pk)
        .order_by("-rating_count", "-rating_avg")[:10]
    )
    comments = book.comments.select_related("user").all()

    # 五星分布（评分 1-10 映射到 5 星）
    bins = [("5星", 9.0, 10.1), ("4星", 7.0, 9.0), ("3星", 5.0, 7.0),
            ("2星", 3.0, 5.0), ("1星", 0.0, 3.0)]
    scores = list(Rating.objects.filter(book=book).values_list("score", flat=True))
    total_s = len(scores)
    star_dist = []
    for lab, lo, hi in bins:
        c = sum(1 for s in scores if lo <= s < hi)
        star_dist.append({"label": lab, "count": c,
                          "pct": round(c / total_s * 100) if total_s else 0})

    context = {
        "book": book,
        "user_rating": user_rating,
        "shelf_status": shelf_status,
        "is_favorite": is_favorite,
        "similar": similar,
        "comments": comments,
        "star_dist": star_dist,
    }
    return render(request, "books/book_detail.html", context)


@login_required
def rate_book(request, pk):
    book = get_object_or_404(Book, pk=pk)
    if request.method == "POST":
        try:
            score = float(request.POST.get("score", 0))
            score = max(1.0, min(10.0, score))
        except (TypeError, ValueError):
            score = 0
        if score:
            Rating.objects.update_or_create(
                user=request.user, book=book, defaults={"score": score}
            )
            recompute_book(book)
            messages.success(request, f"已为《{book.title}》评分 {score} 分。")
    return redirect("book_detail", pk=pk)


@login_required
def add_comment(request, pk):
    book = get_object_or_404(Book, pk=pk)
    if request.method == "POST":
        content = request.POST.get("content", "").strip()
        if content:
            comment = Comment(user=request.user, book=book, content=content)
            analyze_and_save_comment(comment)
            comment.save()
            recompute_book(book)
            messages.success(request, "评论已发布，系统已完成情感分析。")
        else:
            messages.warning(request, "评论内容不能为空。")
    return redirect("book_detail", pk=pk)


@login_required
def toggle_shelf(request, pk):
    book = get_object_or_404(Book, pk=pk)
    if request.method == "POST":
        status = request.POST.get("status", "want")
        if status not in dict(Bookshelf.STATUS_CHOICES):
            status = "want"
        obj = Bookshelf.objects.filter(user=request.user, book=book).first()
        if obj and obj.status == status:
            obj.delete()
            messages.info(request, "已从书架移除。")
        else:
            Bookshelf.objects.update_or_create(
                user=request.user, book=book, defaults={"status": status}
            )
            messages.success(request, f"已加入书架（{dict(Bookshelf.STATUS_CHOICES)[status]}）。")
    return redirect("book_detail", pk=pk)


@login_required
def toggle_favorite(request, pk):
    book = get_object_or_404(Book, pk=pk)
    if request.method == "POST":
        fav = Favorite.objects.filter(user=request.user, book=book).first()
        if fav:
            fav.delete()
            messages.info(request, "已取消收藏。")
        else:
            Favorite.objects.create(user=request.user, book=book)
            messages.success(request, "已收藏。")
    return redirect("book_detail", pk=pk)
