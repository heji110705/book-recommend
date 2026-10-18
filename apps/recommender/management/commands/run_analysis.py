# -*- coding: utf-8 -*-
"""
分析管线：
1. 对所有评论执行情感分析（情感分、极性、关键词）；
2. 重算每本书的评分均值/人数、口碑情感分/好评率；
3. LDA 主题模型，为图书分配主题并导出主题关键词。
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db.models import Avg, Count, Q

from apps.books.models import Book, Comment, Rating
from apps.recommender.services import content, sentiment
from config.settings import BASE_DIR


class Command(BaseCommand):
    help = "评论情感分析 + 图书聚合 + LDA 图书主题画像"

    def handle(self, *args, **options):
        out_dir = Path(BASE_DIR) / "ml" / "output"
        out_dir.mkdir(parents=True, exist_ok=True)

        # 1. 评论情感分析
        self.stdout.write("① 对评论进行情感分析 ...")
        comments = list(Comment.objects.all())
        for c in comments:
            r = sentiment.analyze_comment(c.content)
            c.sentiment = r["score"]
            c.polarity = r["polarity"]
            c.keywords = r["keywords"]
        Comment.objects.bulk_update(comments, ["sentiment", "polarity", "keywords"])

        # 2. 评分聚合
        self.stdout.write("② 重算图书评分聚合 ...")
        rating_stats = {
            r["book_id"]: (r["avg"], r["cnt"])
            for r in Rating.objects.values("book_id").annotate(avg=Avg("score"), cnt=Count("id"))
        }

        # 3. 口碑情感聚合
        comment_stats = {
            r["book_id"]: (r["mean"], r["total"], r["pos"])
            for r in Comment.objects.values("book_id").annotate(
                mean=Avg("sentiment"), total=Count("id"),
                pos=Count("id", filter=Q(polarity="pos")),
            )
        }

        books = list(Book.objects.all())
        for b in books:
            avg, cnt = rating_stats.get(b.id, (0, 0))
            b.rating_avg = round(avg or 0, 2)
            b.rating_count = cnt
            mean, total, pos = comment_stats.get(b.id, (0, 0, 0))
            b.sentiment_score = round(mean or 0, 4)
            b.positive_rate = round(pos / total, 4) if total else 0.0

        # 4. LDA 主题模型
        self.stdout.write("③ 训练 LDA 主题模型 ...")
        n_topics = min(12, len(books))
        lda, topics, topic_words = content.fit_lda(books, n_topics=n_topics)
        for b, t in zip(books, topics):
            b.topic = int(t)

        Book.objects.bulk_update(
            books,
            ["rating_avg", "rating_count", "sentiment_score", "positive_rate", "topic"],
        )

        # 导出主题信息供论文/看板使用
        payload = {
            "n_topics": n_topics,
            "topic_words": topic_words,
            "topic_counts": [int((topics == i).sum()) for i in range(n_topics)],
            "n_comments": len(comments),
            "n_books": len(books),
        }
        with open(out_dir / "content_analysis.json", "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        self.stdout.write(self.style.SUCCESS("分析完成。LDA 主题关键词："))
        for i, words in enumerate(topic_words):
            self.stdout.write(f"  主题{i:02d}: {', '.join(words)}")
        self.stdout.write(self.style.SUCCESS(f"结果已保存到 {out_dir / 'content_analysis.json'}"))
