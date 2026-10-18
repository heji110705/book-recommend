# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django

django.setup()

from django.db.models import Avg, Count, Q
from apps.books.models import Book, Comment

print("=== 评论极性分布 ===")
for p, label in [("pos", "好评"), ("neu", "中评"), ("neg", "差评")]:
    n = Comment.objects.filter(polarity=p).count()
    print(f"{label}: {n} ({n/Comment.objects.count()*100:.1f}%)")

print("\n=== 平均情感分 ===", round(Comment.objects.aggregate(Avg("sentiment"))["sentiment__avg"], 3))

print("\n=== 评分最高的5本书 ===")
for b in Book.objects.order_by("-rating_avg")[:5]:
    print(f"{b.title:<16} 评分{b.rating_avg:<5} 人数{b.rating_count:<4} 好评率{b.positive_rate*100:.0f}% 主题{b.topic}")

print("\n=== 评分最低的5本书 ===")
for b in Book.objects.order_by("rating_avg")[:5]:
    print(f"{b.title:<16} 评分{b.rating_avg:<5} 人数{b.rating_count:<4} 好评率{b.positive_rate*100:.0f}% 主题{b.topic}")
