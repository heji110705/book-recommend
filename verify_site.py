# -*- coding: utf-8 -*-
"""端到端验证：访问所有页面、测试关键交互（POST 部分事务回滚，不污染演示数据）。"""
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.db import connection
from django.test import Client

failures = []


def req(c, label, method, url, data=None, expect=200):
    try:
        if method == "GET":
            r = c.get(url)
        else:
            r = c.post(url, data=data or {})
        ok = r.status_code == expect
        flag = "OK " if ok else "FAIL"
        if not ok:
            failures.append((label, r.status_code, r.url if hasattr(r, "url") else ""))
        print(f"[{flag}] {label:14s} {r.status_code}  {url}")
        return r
    except Exception as e:
        failures.append((label, "EXC", str(e)))
        print(f"[FAIL] {label:14s} 异常 {e}")
        return None


# 关闭自动提交，验证结束整体回滚
connection.set_autocommit(False)
try:
    from apps.books.models import Book
    first_id = Book.objects.order_by("id").first().id
    target_id = Book.objects.order_by("?").first().id

    c = Client()

    # 匿名访问
    req(c, "首页", "GET", "/")
    req(c, "书库", "GET", "/books/")
    req(c, "搜索筛选", "GET", "/books/?q=心理&category=科学科普&order=rating")
    req(c, "图书详情", "GET", f"/books/{first_id}/")
    req(c, "登录页", "GET", "/accounts/login/")
    req(c, "注册页", "GET", "/accounts/register/")
    req(c, "数据分析看板", "GET", "/analytics/")
    req(c, "后台(匿名跳转)", "GET", "/admin/", expect=302)

    # admin 登录后台
    ca = Client()
    ca.login(username="admin", password="admin12345")
    req(ca, "后台首页", "GET", "/admin/")

    # demo 登录
    print("demo 登录：", c.login(username="demo", password="demo12345"))
    r = req(c, "智能推荐(混合)", "GET", "/recommend/")
    if r and ("推荐度" in r.content.decode() or "bk-grid" in r.content.decode()):
        print("      -> 推荐页已输出推荐书单")
    else:
        failures.append(("推荐内容为空", "", ""))
        print("      -> [FAIL] 推荐页未输出书单")
    if r and r.content.decode().count("💡") >= 10:
        print("      -> 每条推荐均给出可解释理由")
    else:
        failures.append(("推荐理由缺失", "", ""))
        print("      -> [FAIL] 部分推荐缺少理由")
    for algo in ["svd", "content", "itemcf", "usercf"]:
        req(c, "推荐-"+algo, "GET", f"/recommend/?algo={algo}")
    req(c, "个人中心", "GET", "/accounts/profile/")

    # 交互（会回滚，成功后 302 重定向到详情页）
    req(c, "评分", "POST", f"/books/{target_id}/rate/", {"score": "9"}, expect=302)
    r = req(c, "评论(情感)", "POST", f"/books/{target_id}/comment/",
            {"content": "这本书写得非常透彻，收获很大，强烈推荐！"}, expect=302)
    req(c, "加入书架", "POST", f"/books/{target_id}/shelf/", {"status": "reading"}, expect=302)
    req(c, "收藏", "POST", f"/books/{target_id}/favorite/", {}, expect=302)
    req(c, "详情(登录后)", "GET", f"/books/{target_id}/")

    # 冷启动新用户：注册 -> 兴趣引导 -> 偏好冷启动
    c2 = Client()
    r = c2.post("/accounts/register/",
                {"username": "newbie001", "email": "",
                 "password1": "Newbie123456!", "password2": "Newbie123456!"})
    print("新用户注册：", r.status_code, "->", r.get("Location", ""))
    if r.status_code == 302 and "onboarding" in r.get("Location", ""):
        print("      -> 注册后正确跳转兴趣引导")
    else:
        failures.append(("未跳兴趣引导", "", ""))
    og = req(c2, "兴趣引导页", "GET", "/accounts/onboarding/")
    if og and og.content.decode().count('name="categories"') == 12:
        print("      -> 引导页展示 12 个分类")
    else:
        failures.append(("引导页分类数不对", "", ""))
    op = req(c2, "提交偏好", "POST", "/accounts/onboarding/",
             {"categories": ["科学科普", "心理励志"]}, expect=302)
    r = req(c2, "偏好冷启动推荐", "GET", "/recommend/")
    if r and "兴趣" in r.content.decode():
        print("      -> 偏好冷启动推荐理由正确")
    else:
        failures.append(("偏好冷启动失败", "", ""))

    # 未完成引导的新用户走热门兜底（另建一个不提交偏好的用户）
    c3 = Client()
    c3.post("/accounts/register/",
            {"username": "newbie002", "email": "",
             "password1": "Newbie123456!", "password2": "Newbie123456!"})
    r = req(c3, "未引导冷启动", "GET", "/recommend/")
    if r and "冷启动" in r.content.decode():
        print("      -> 正确进入冷启动热门兜底")

finally:
    connection.rollback()
    connection.set_autocommit(True)

print("\n==== 结果 ====")
if failures:
    print("失败项：", failures)
else:
    print("全部页面与交互验证通过 ✅")
