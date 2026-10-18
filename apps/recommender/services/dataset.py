# -*- coding: utf-8 -*-
"""
数据集生成器（豆瓣图书 Top250 真实书目 + 模拟用户行为）
----------------------------------------------------
- 图书：来自 data/douban_top250.json 的豆瓣 Top250 真实图书（含真实封面、作者、
  出版社、出版年份、价格、豆瓣评分与评分人数、简介）；
- 用户：模拟读者；
- 评分：以"豆瓣真实评分作为图书质量先验"，再叠加用户偏置、分类偏好、隐因子
  点积与噪声，使评分矩阵具备协同过滤 / SVD 可学习的真实结构；
- 评论：按评分高/中/低从模板生成（使用情感词，供情感分析识别）；
- 书架/收藏/浏览：按评分派生。
固定随机种子，结果可复现。
"""

from __future__ import annotations

import hashlib
import random
from pathlib import Path

import numpy as np
from django.contrib.auth.models import User
from django.utils import timezone

from apps.books.models import Book, Bookshelf, ClickLog, Comment, Favorite, Rating
from data.douban_loader import load_douban_books

SEED = 20261018
K_FACTORS = 8  # 隐因子维度

# 评论模板（含明确的正/负向情感词，情感分析可识别）
POS_COMMENTS = [
    "这本书非常精彩，内容深入浅出，读完让我受益匪浅，强烈推荐！",
    "作者文笔生动，故事引人入胜，看得我很感动，非常喜欢。",
    "干货满满，通俗易懂，对学习和工作都很有帮助，值得一读。",
    "逻辑严密，观点独到，高屋建瓴，读完豁然开朗，很有收获。",
    "印刷清晰，排版精美，作者也很用心，物超所值，非常满意。",
    "经典中的经典，百读不厌，每次重读都有新的体会，值得收藏。",
    "情节扣人心弦，感人至深，好几次看到落泪，强烈推荐给大家。",
    "内容丰富详实，讲解清晰，专业又不失趣味，让人爱不释手。",
    "醍醐灌顶，茅塞顿开，很多困惑都解决了，真是相见恨晚。",
    "语言幽默风趣，读起来轻松愉快，既涨知识又治愈，很棒。",
    "买来送给朋友的，对方非常喜欢，包装精美，内容也好，好评。",
    "浅显易懂，循序渐进，非常适合入门，老师推荐的，确实靠谱。",
    "纸质不错，没有异味，字迹清楚，内容扎实，买得很放心。",
    "作者学识渊博，见解深刻，读这样的书是一种享受，大赞。",
    "很有启发性的一本书，发人深省，读完充满正能量，会继续追作者。",
    "不愧是豆瓣高分，读完久久不能平静，里面的观点影响了我很多。",
]
NEU_COMMENTS = [
    "整体还可以，内容中规中矩，有些地方比较出彩，也有些地方一般。",
    "还行吧，随便翻翻，部分章节有收获，其他的写得比较平淡。",
    "书的质量不错，不过内容对我来说有点简单，适合入门读者。",
    "印刷可以，内容一般般，不算差也没有特别惊艳，给个三星。",
    "前半部分比较枯燥，后半部分还可以，总体一般，勉强读完。",
    "作者有自己的观点，但不够深入，很多点到为止，期待续作。",
    "物流挺快，包装还行，书的内容一般，需要自己多体会。",
    "框架不错，细节稍显啰嗦，压缩一下会更好，总体可以接受。",
    "作为入门读物还算合适，想深入的话还得再看更专业的资料。",
    "文笔一般，翻译有些地方生硬，不过内容是完整的，将就着看。",
    "名作出品但没有预期那么震撼，可能是年代不同，先给中评。",
]
NEG_COMMENTS = [
    "太糟糕了，内容晦涩难懂，像在浪费时间，看完很失望，后悔买了。",
    "名不副实，注水严重，很多错误，完全是营销出来的，不推荐购买。",
    "纸张质量差，印刷粗糙还有错别字，粗制滥造，看着很难受。",
    "内容空洞、肤浅，观点片面，很多地方前后矛盾，无法忍受。",
    "枯燥乏味，啰嗦冗长，完全看不下去，催眠效果一流，不值这个价。",
    "翻译非常生硬，语句不通顺，读起来很费劲，劝退，不建议。",
    "书脊开胶、内页缺页，破损严重，客服还敷衍，糟糕的一次购物。",
    "大失所望，宣传言过其实，实际内容都是陈词滥调，智商税。",
    "逻辑混乱，条理不清，不知所云，看了几章就放弃了，浪费钱。",
    "前面吹得天花乱坠，实际全是套话和拼凑，没有干货，差评。",
    "包装破损，书角压坏，还有异味，内容也一般，非常不满意。",
    "写得太死板，照本宣科，没有自己的见解，还不如看网上的免费资料。",
]


def _hash_key(*parts):
    return hashlib.md5("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:16]


def clear_data():
    """清空业务数据（保留超级用户）"""
    from apps.recommender.models import RecommendResult

    ClickLog.objects.all().delete()
    Comment.objects.all().delete()
    Favorite.objects.all().delete()
    Bookshelf.objects.all().delete()
    Rating.objects.all().delete()
    RecommendResult.objects.all().delete()
    Book.objects.all().delete()
    # 删除非超级用户，便于重新生成
    User.objects.filter(is_superuser=False).delete()


def _create_books():
    """从豆瓣 Top250 JSON 创建图书（含真实封面、豆瓣评分）"""
    data = load_douban_books()
    books = []
    for d in data:
        book = Book(
            subject_id=d["subject_id"],
            title=d["title"],
            subtitle=d["subtitle"],
            author=d["author"],
            publisher=d["publisher"],
            pub_date=d["pub_date"],
            pub_year=d["pub_year"],
            price=d["price"],
            category=d["category"],
            tags=d["tags"],
            description=d["description"],
            cover=d["cover"] or None,
            source="douban",
            douban_rating=d["douban_rating"] or 0,
            douban_votes=d["douban_votes"] or 0,
            quote=d["quote"],
            rating_avg=d["douban_rating"] or 0,  # 初始用豆瓣评分兜底
            rating_count=0,
            dedup_hash=_hash_key(d["subject_id"] or d["title"], d["author"]),
        )
        books.append(book)
    Book.objects.bulk_create(books)
    return list(Book.objects.all())


def generate_all(n_users=100, n_book_max=None, verbose=True):
    """生成完整数据集。"""
    rng = np.random.default_rng(SEED)
    py_rng = random.Random(SEED)

    def log(msg):
        if verbose:
            print(msg)

    log("① 清理旧数据...")
    clear_data()

    log("② 导入豆瓣 Top250 图书...")
    books = _create_books()
    if n_book_max:
        books = books[:n_book_max]
    categories = sorted({b.category for b in books})
    cat_index = {c: i for i, c in enumerate(categories)}
    book_cat = np.array([cat_index[b.category] for b in books])
    M = len(books)

    # 以豆瓣真实评分作为图书质量先验
    global_mean = float(np.mean([b.douban_rating for b in books if b.douban_rating]))
    book_quality = np.array([
        (b.douban_rating - global_mean) if b.douban_rating else 0.0 for b in books
    ])
    book_vec = rng.normal(0, 1, (M, K_FACTORS))

    log(f"③ 生成 {n_users} 位用户及其偏好...")
    demo = User.objects.create_user(username="demo", password="demo12345",
                                    email="demo@example.com", first_name="演示用户")
    demo.profile.fav_categories = ""
    demo.profile.save()

    users = []
    for i in range(1, n_users + 1):
        u = User.objects.create_user(username=f"reader{i:03d}", password="reader12345",
                                     email=f"reader{i:03d}@example.com")
        users.append(u)
    all_users = [demo] + users
    N = len(all_users)

    # 用户偏好
    user_bias = rng.normal(0, 0.6, N)
    user_cat = rng.normal(0, 1.0, (N, len(categories)))
    user_vec = rng.normal(0, 1, (N, K_FACTORS))
    # 演示账号偏科学科普、心理励志、经济管理
    demo_aff = np.zeros(len(categories))
    for c, w in [("科学科普", 2.0), ("心理励志", 1.4), ("经济管理", 1.0), ("历史人文", 0.6)]:
        if c in cat_index:
            demo_aff[cat_index[c]] = w
    user_cat[0] = demo_aff

    log("④ 生成评分（豆瓣质量先验 + 潜在因子结构）...")
    ratings = []
    rated_pairs = {}
    counts = np.empty(N, dtype=int)
    for u in range(N):
        if u == 0:
            counts[u] = 55  # 演示账号
        else:
            r = rng.random()
            if r < 0.10:
                counts[u] = int(rng.integers(1, 4))      # 冷启动用户
            elif r < 0.30:
                counts[u] = int(rng.integers(55, 110))   # 活跃用户
            else:
                counts[u] = int(rng.integers(18, 46))
    counts = np.clip(counts, 1, M)

    for ui, user in enumerate(all_users):
        pref = np.exp(user_cat[ui][book_cat] / 1.1)
        pref = pref / pref.sum()
        # 80% 按偏好选书、20% 随机探索（部分探索书会得低分，形成真实分布）
        weights = 0.8 * pref + 0.2 * np.ones(M) / M
        weights = weights / weights.sum()
        n = int(counts[ui])
        chosen = rng.choice(M, size=n, replace=False, p=weights)
        rated = set()
        for bi in chosen:
            book = books[bi]
            raw = (
                global_mean
                + user_bias[ui]
                + book_quality[bi]
                + user_cat[ui][book_cat[bi]] * 1.4
                + float(np.dot(user_vec[ui], book_vec[bi])) * 0.9
                + rng.normal(0, 0.45)
            )
            score = float(np.clip(raw, 1.0, 10.0))
            score = round(score, 1)
            ratings.append(Rating(user=user, book=book, score=score))
            rated.add(book.id)
        rated_pairs[user.id] = rated

    Rating.objects.bulk_create(ratings)
    log(f"   共生成 {len(ratings)} 条评分（豆瓣均分基准 {global_mean:.2f}）")

    log("⑤ 生成评论、书架、收藏、浏览记录...")
    comments, shelves, favorites, clicks = [], [], [], []
    for r in ratings:
        s = r.score
        p_comment = 0.55 if s >= 8.0 or s <= 4.0 else 0.22
        if rng.random() < p_comment:
            if s >= 7.0:
                text = py_rng.choice(POS_COMMENTS)
            elif s < 5.0:
                text = py_rng.choice(NEG_COMMENTS)
            else:
                text = py_rng.choice(NEU_COMMENTS)
            if rng.random() < 0.4:
                text = f"《{r.book.title}》：" + text
            comments.append(Comment(user=r.user, book=r.book, content=text))

        if rng.random() < 0.6:
            if s >= 7.0:
                status = "read" if rng.random() < 0.75 else "reading"
            elif s >= 5.0:
                status = py_rng.choice(["reading", "want"])
            else:
                status = "want"
            shelves.append(Bookshelf(user=r.user, book=r.book, status=status))
        if s >= 8.0 and rng.random() < 0.3:
            favorites.append(Favorite(user=r.user, book=r.book))
        clicks.append(ClickLog(user=r.user, book=r.book))

    for ui, user in enumerate(all_users):
        extra = 8 if user.id == demo.id else int(rng.integers(1, 8))
        rated = rated_pairs.get(user.id, set())
        candidates = [b for b in books if b.id not in rated]
        if candidates:
            for b in rng.choice(len(candidates), size=min(extra, len(candidates)), replace=False):
                clicks.append(ClickLog(user=user, book=candidates[int(b)]))

    Comment.objects.bulk_create(comments)
    Bookshelf.objects.bulk_create(shelves)
    Favorite.objects.bulk_create(favorites)
    ClickLog.objects.bulk_create(clicks)

    for ui, user in enumerate(all_users):
        top = np.argsort(-user_cat[ui])[:2]
        user.profile.fav_categories = "，".join(categories[int(i)] for i in top)
        user.profile.save()

    log(f"   评论 {len(comments)} 条 / 书架 {len(shelves)} 条 / 收藏 {len(favorites)} 条 / 浏览 {len(clicks)} 条")
    log("数据生成完成。")
    return {
        "books": M,
        "users": N,
        "ratings": len(ratings),
        "comments": len(comments),
        "shelves": len(shelves),
        "favorites": len(favorites),
        "clicks": len(clicks),
    }
