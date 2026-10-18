# -*- coding: utf-8 -*-
"""一键初始化：生成种子数据 → 文本/情感分析 → 训练推荐算法并生成结果"""
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "一键执行 seed_data → run_analysis → build_recommender"

    def add_arguments(self, parser):
        parser.add_argument("--users", type=int, default=100)
        parser.add_argument("--topn", type=int, default=15)

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("==== 第1步：生成种子数据 ===="))
        call_command("seed_data", users=options["users"])
        self.stdout.write(self.style.MIGRATE_HEADING("\n==== 第2步：情感分析与文本挖掘 ===="))
        call_command("run_analysis")
        self.stdout.write(self.style.MIGRATE_HEADING("\n==== 第3步：训练推荐算法并生成推荐 ===="))
        call_command("build_recommender", topn=options["topn"])
        self.stdout.write(self.style.SUCCESS("\n全部初始化完成，可启动系统：python manage.py runserver"))
