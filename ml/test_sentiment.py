# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from apps.recommender.services.sentiment import analyze_comment

tests = [
    "这本书非常精彩，深入浅出，让我受益匪浅，强烈推荐！",
    "内容通俗易懂，干货满满，作者很用心，值得一读。",
    "感觉一般般，有些枯燥，不过后半部分还可以。",
    "纸张质量太差了，内容晦涩难懂，完全是浪费时间，后悔买了。",
    "名不副实，注水严重，很多错误，不推荐购买。",
    "书还行，印刷不错，但是物流很慢，包装破损。",
]
for t in tests:
    r = analyze_comment(t)
    print(f"[{r['polarity']:3}] score={r['score']:+.2f} pos={r['pos_words']} neg={r['neg_words']}")
    print("     ", t)
