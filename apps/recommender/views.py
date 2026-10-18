from collections import OrderedDict

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.books.models import Book, Rating
from .services import engine as engine_mod

ALGO_LABELS = OrderedDict([
    ("hybrid", "混合推荐（自适应）"),
    ("svd", "SVD 矩阵分解"),
    ("content", "基于内容"),
    ("itemcf", "基于物品协同过滤"),
    ("usercf", "基于用户协同过滤"),
    ("hot", "热门推荐（冷启动）"),
])
PERSONAL_ALGOS = ["hybrid", "svd", "content", "itemcf", "usercf"]


def _parse_categories(text):
    return [c.strip() for c in (text or "").replace(",", "，").split("，") if c.strip()]


@login_required
def recommend_page(request):
    algo = request.GET.get("algo", "hybrid")
    if algo not in ALGO_LABELS:
        algo = "hybrid"

    engine = engine_mod.get_engine()
    user = request.user
    uid = user.id
    profile = getattr(user, "profile", None)
    preferred = _parse_categories(profile.fav_categories if profile else "")
    n_rated = Rating.objects.filter(user=user).count()
    cold = (uid not in engine.u_index) or (n_rated < 3)

    reasons = {}
    if cold:
        algo = "hot"
        pairs = engine.hot_items(n=15, preferred_categories=preferred or None)
        notice = "你的评分记录较少，系统先按你的兴趣偏好与图书口碑为你冷启动推荐；多给图书评分后，将获得个性化推荐。"
    else:
        ui = engine.u_index[uid]
        pairs = engine.recommend(ui, algo=algo, n=15)
        for bid, _ in pairs:
            reasons[bid] = engine.explain(ui, engine.i_index[bid], algo)
        notice = ""

    book_map = Book.objects.in_bulk([bid for bid, _ in pairs])
    rec_books = []
    for bid, score in pairs:
        if bid not in book_map:
            continue
        book = book_map[bid]
        if cold:
            if preferred and book.category in preferred:
                reason = f"符合你选择的「{book.category}」兴趣，且口碑出色"
            else:
                reason = f"高人气{book.category}作品，{book.display_votes} 人评价"
        else:
            reason = reasons.get(bid, "")
        # 统一换算为 0~100 推荐度：混合分是 0~1，热门分是 10 分制
        if score <= 1.0:
            score_pct = round(min(score, 1.0) * 100, 1)
        else:
            score_pct = round(min(score / 10.0, 1.0) * 100, 1)
        rec_books.append({
            "book": book,
            "score": score_pct,
            "reason": reason,
        })

    needs_onboarding = bool(profile is not None and not profile.onboarded and n_rated < 3)

    context = {
        "algo": algo,
        "algo_label": ALGO_LABELS[algo],
        "algo_labels": ALGO_LABELS,
        "personal_algos": [] if cold else PERSONAL_ALGOS,
        "rec_books": rec_books,
        "cold": cold,
        "notice": notice,
        "needs_onboarding": needs_onboarding,
        "n_rated": n_rated,
    }
    return render(request, "recommend/recommend.html", context)
