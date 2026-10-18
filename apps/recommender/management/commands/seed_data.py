# -*- coding: utf-8 -*-
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from apps.recommender.services import dataset


class Command(BaseCommand):
    help = "生成种子数据（图书、用户、评分、评论、书架、收藏、浏览），并创建超管和演示账号"

    def add_arguments(self, parser):
        parser.add_argument("--users", type=int, default=100, help="模拟用户数量")
        parser.add_argument("--no-admin", action="store_true", help="不创建超级管理员")

    def handle(self, *args, **options):
        # 创建超级管理员（若不存在）
        if not options["no_admin"] and not User.objects.filter(username="admin").exists():
            User.objects.create_superuser(username="admin", password="admin12345",
                                          email="admin@example.com")
            self.stdout.write("已创建超级管理员：admin / admin12345")

        stats = dataset.generate_all(n_users=options["users"])
        self.stdout.write(self.style.SUCCESS(
            "种子数据完成：{books} 本图书、{users} 位用户、{ratings} 条评分、{comments} 条评论".format(
                **stats)))
        self.stdout.write("演示账号：demo / demo12345；后台账号：admin / admin12345")
