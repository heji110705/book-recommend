from django.contrib.auth.models import User
from django.db import models


class Book(models.Model):
    """图书"""

    CATEGORY_CHOICES = [
        ("文学小说", "文学小说"),
        ("历史人文", "历史人文"),
        ("哲学宗教", "哲学宗教"),
        ("社会科学", "社会科学"),
        ("心理励志", "心理励志"),
        ("经济管理", "经济管理"),
        ("科学科普", "科学科普"),
        ("艺术设计", "艺术设计"),
        ("传记纪实", "传记纪实"),
        ("少儿读物", "少儿读物"),
        ("诗歌散文", "诗歌散文"),
        ("语言文化", "语言文化"),
    ]

    subject_id = models.CharField("豆瓣ID", max_length=20, blank=True, default="", db_index=True)
    isbn = models.CharField("ISBN", max_length=20, blank=True, default="", db_index=True)
    title = models.CharField("书名", max_length=200, db_index=True)
    subtitle = models.CharField("副标题", max_length=200, blank=True, default="")
    author = models.CharField("作者", max_length=100, blank=True, default="", db_index=True)
    publisher = models.CharField("出版社", max_length=100, blank=True, default="")
    pub_date = models.CharField("出版日期", max_length=30, blank=True, default="")
    pub_year = models.IntegerField("出版年份", null=True, blank=True)
    pages = models.IntegerField("页数", null=True, blank=True)
    price = models.FloatField("价格", null=True, blank=True)
    category = models.CharField("分类", max_length=50, default="未分类", db_index=True)
    tags = models.TextField("标签", blank=True, default="", help_text="逗号分隔")
    description = models.TextField("简介", blank=True, default="")
    cover = models.ImageField("封面", upload_to="covers/", blank=True, null=True)
    source = models.CharField("数据来源", max_length=20, default="douban", blank=True)

    # 数据源原始评分（豆瓣）与系统聚合
    douban_rating = models.FloatField("豆瓣评分", default=0)
    douban_votes = models.IntegerField("豆瓣评分人数", default=0)
    quote = models.CharField("一句话推荐", max_length=200, blank=True, default="")

    # 聚合与算法结果
    rating_avg = models.FloatField("系统平均评分", default=0)
    rating_count = models.IntegerField("系统评分人数", default=0)
    topic = models.IntegerField("LDA主题编号", null=True, blank=True)
    sentiment_score = models.FloatField("口碑情感分", default=0)
    positive_rate = models.FloatField("好评率", default=0)

    dedup_hash = models.CharField("去重标识", max_length=64, unique=True, null=True, blank=True)
    created_at = models.DateTimeField("入库时间", auto_now_add=True)

    class Meta:
        verbose_name = "图书"
        verbose_name_plural = verbose_name
        ordering = ["-rating_count", "-rating_avg"]

    def __str__(self):
        return self.title

    def tag_list(self):
        import re
        return [t.strip() for t in re.split(r"[，,]", self.tags or "") if t.strip()]

    @property
    def positive_rate_pct(self):
        """好评率百分比（0-100 整数）"""
        return round(self.positive_rate * 100)

    @property
    def display_rating(self):
        """卡片/详情展示的评分：有系统评分用系统分，否则用豆瓣原始分"""
        return self.rating_avg if self.rating_count > 0 else self.douban_rating

    @property
    def display_votes(self):
        """展示的评分人数：系统评分优先，否则用豆瓣人数"""
        return self.rating_count if self.rating_count > 0 else self.douban_votes

    @property
    def star_percent(self):
        """5 星制填充百分比（评分是 10 分制）"""
        return round(self.display_rating / 10.0 * 100)


class Rating(models.Model):
    """用户对图书的评分（1-10）"""

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="ratings", verbose_name="用户"
    )
    book = models.ForeignKey(
        Book, on_delete=models.CASCADE, related_name="ratings", verbose_name="图书"
    )
    score = models.FloatField("评分")
    created_at = models.DateTimeField("评分时间", auto_now_add=True)

    class Meta:
        verbose_name = "评分"
        verbose_name_plural = verbose_name
        unique_together = ("user", "book")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} - {self.book.title} - {self.score}"


class Comment(models.Model):
    """图书评论（含情感分析结果）"""

    POLARITY_CHOICES = [
        ("pos", "好评"),
        ("neu", "中评"),
        ("neg", "差评"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="comments", verbose_name="用户"
    )
    book = models.ForeignKey(
        Book, on_delete=models.CASCADE, related_name="comments", verbose_name="图书"
    )
    content = models.TextField("评论内容")
    sentiment = models.FloatField("情感得分", default=0)
    polarity = models.CharField("情感极性", max_length=3, choices=POLARITY_CHOICES, default="neu")
    keywords = models.CharField("情感关键词", max_length=200, blank=True, default="")
    created_at = models.DateTimeField("评论时间", auto_now_add=True)

    class Meta:
        verbose_name = "评论"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} 评《{self.book.title}》"


class Bookshelf(models.Model):
    """书架：想读 / 在读 / 读过"""

    STATUS_CHOICES = [
        ("want", "想读"),
        ("reading", "在读"),
        ("read", "读过"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="bookshelf", verbose_name="用户"
    )
    book = models.ForeignKey(
        Book, on_delete=models.CASCADE, related_name="bookshelf_entries", verbose_name="图书"
    )
    status = models.CharField("状态", max_length=10, choices=STATUS_CHOICES, default="want")
    created_at = models.DateTimeField("添加时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "书架"
        verbose_name_plural = verbose_name
        unique_together = ("user", "book")
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.user.username} - {self.book.title} - {self.get_status_display()}"


class Favorite(models.Model):
    """收藏"""

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="favorites", verbose_name="用户"
    )
    book = models.ForeignKey(
        Book, on_delete=models.CASCADE, related_name="favorited_by", verbose_name="图书"
    )
    created_at = models.DateTimeField("收藏时间", auto_now_add=True)

    class Meta:
        verbose_name = "收藏"
        verbose_name_plural = verbose_name
        unique_together = ("user", "book")
        ordering = ["-created_at"]


class ClickLog(models.Model):
    """浏览日志（用于行为分析）"""

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="click_logs", verbose_name="用户"
    )
    book = models.ForeignKey(
        Book, on_delete=models.CASCADE, related_name="click_logs", verbose_name="图书"
    )
    created_at = models.DateTimeField("浏览时间", auto_now_add=True)

    class Meta:
        verbose_name = "浏览日志"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]
