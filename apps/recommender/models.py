from django.contrib.auth.models import User
from django.db import models

from apps.books.models import Book


class RecommendResult(models.Model):
    """离线生成的推荐结果（可按算法切换查看）"""

    ALGO_CHOICES = [
        ("hot", "热门推荐"),
        ("usercf", "基于用户的协同过滤"),
        ("itemcf", "基于物品的协同过滤"),
        ("svd", "SVD矩阵分解"),
        ("content", "基于内容推荐"),
        ("hybrid", "混合推荐(口碑加权)"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="recommend_results",
        null=True,
        blank=True,
        verbose_name="用户(空表示全局)",
    )
    book = models.ForeignKey(
        Book, on_delete=models.CASCADE, related_name="recommend_entries", verbose_name="图书"
    )
    algo = models.CharField("算法", max_length=20, choices=ALGO_CHOICES, db_index=True)
    score = models.FloatField("推荐得分", default=0)
    rank = models.IntegerField("排名", default=0)
    created_at = models.DateTimeField("生成时间", auto_now_add=True)

    class Meta:
        verbose_name = "推荐结果"
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=["algo", "user"]),
        ]
        ordering = ["algo", "user", "rank"]

    def __str__(self):
        return f"{self.get_algo_display()} - {self.user or '全局'} - {self.book.title}"
