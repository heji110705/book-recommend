import json
import re
from collections import Counter
from pathlib import Path

from django.contrib.auth.models import User
from django.db.models import Avg, Count
from django.shortcuts import render

from apps.books.models import Book, Comment, Rating
from config.settings import BASE_DIR


def _load_topics():
    path = Path(BASE_DIR) / "ml" / "output" / "content_analysis.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("topic_words", [])
    return []


def _load_evaluation():
    """读取离线评估结果（RMSE/MAE、Precision/Recall）"""
    path = Path(BASE_DIR) / "ml" / "output" / "evaluation.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def dashboard(request):
    books = Book.objects.all()

    # 1. 分类数量
    cat_rows = list(
        books.values("category").annotate(
            n=Count("id"), avg=Avg("rating_avg"), pos=Avg("positive_rate")
        )
    )
    cat_rows.sort(key=lambda r: -r["n"])
    categories = [r["category"] for r in cat_rows]
    cat_counts = [r["n"] for r in cat_rows]
    cat_rating = [round(r["avg"] or 0, 2) for r in cat_rows]
    cat_pos = [round((r["pos"] or 0) * 100, 1) for r in cat_rows]

    # 2. 评分分布（按用户评分）
    hist = [0] * 10  # 1-2,...,9-10
    for score in Rating.objects.values_list("score", flat=True):
        idx = min(int((score - 1) // 1), 9)
        hist[idx] += 1
    hist_labels = [f"{i}-{i+1}" for i in range(1, 11)]

    # 3. 出版年份
    year_rows = (
        books.exclude(pub_year__isnull=True)
        .values("pub_year")
        .annotate(n=Count("id"))
        .order_by("pub_year")
    )
    years = [int(r["pub_year"]) for r in year_rows]
    year_counts = [r["n"] for r in year_rows]

    # 4. 评论情感极性
    polarity = {
        "好评": Comment.objects.filter(polarity="pos").count(),
        "中评": Comment.objects.filter(polarity="neu").count(),
        "差评": Comment.objects.filter(polarity="neg").count(),
    }

    # 5. 出版社/作者
    publisher_rows = list(
        books.values("publisher").annotate(n=Count("id")).order_by("-n")[:10]
    )
    publishers = [r["publisher"] or "未知" for r in publisher_rows]
    publisher_counts = [r["n"] for r in publisher_rows]

    # 6. 标签词频
    tag_counter = Counter()
    for tags in books.values_list("tags", flat=True):
        for t in re.split(r"[，,]", tags or ""):
            t = t.strip()
            if t:
                tag_counter[t] += 1
    top_tags = tag_counter.most_common(30)

    # 7. 高分图书
    top_books = list(books.order_by("-rating_avg", "-rating_count")[:10])

    # 8. 总体指标
    stats = {
        "books": books.count(),
        "users": User.objects.count(),
        "ratings": Rating.objects.count(),
        "comments": Comment.objects.count(),
        "avg_rating": round(
            Rating.objects.aggregate(a=Avg("score"))["a"] or 0, 2
        ),
    }

    chart_data = {
        "categories": categories,
        "cat_counts": cat_counts,
        "cat_rating": cat_rating,
        "cat_pos": cat_pos,
        "hist_labels": hist_labels,
        "hist": hist,
        "years": years,
        "year_counts": year_counts,
        "polarity": polarity,
        "publishers": publishers,
        "publisher_counts": publisher_counts,
        "top_tags": top_tags,
        "topics": _load_topics(),
        "evaluation": _load_evaluation(),
    }

    context = {
        "stats": stats,
        "top_books": top_books,
        "chart_data": json.dumps(chart_data, ensure_ascii=False),
    }
    return render(request, "analytics/dashboard.html", context)
