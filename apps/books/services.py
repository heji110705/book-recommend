# -*- coding: utf-8 -*-
"""图书业务辅助函数"""
from django.db.models import Avg, Count, Q

from apps.recommender.services import sentiment


def recompute_book(book):
    """重算单本图书的评分与口碑聚合字段"""
    r = book.ratings.aggregate(avg=Avg("score"), cnt=Count("id"))
    book.rating_avg = round(r["avg"] or 0, 2)
    book.rating_count = r["cnt"] or 0

    c = book.comments.aggregate(
        mean=Avg("sentiment"),
        total=Count("id"),
        pos=Count("id", filter=Q(polarity="pos")),
    )
    total = c["total"] or 0
    book.sentiment_score = round(c["mean"] or 0, 4)
    book.positive_rate = round(c["pos"] / total, 4) if total else 0.0
    book.save(update_fields=["rating_avg", "rating_count", "sentiment_score", "positive_rate"])
    return book


def analyze_and_save_comment(comment):
    """对评论做情感分析并保存结果"""
    result = sentiment.analyze_comment(comment.content)
    comment.sentiment = result["score"]
    comment.polarity = result["polarity"]
    comment.keywords = result["keywords"]
    return comment
