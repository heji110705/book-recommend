# -*- coding: utf-8 -*-
"""
豆瓣图书 Top250 公开数据采集脚本（教学/毕设演示用途）。
- 抓取列表页：书名、副标题、作者、出版社、出版日期、价格、评分、评价人数、一句话、封面、详情链接
- 可选抓取详情页：完整简介、标签（用于分类）
- 封面下载到 media/covers/，结构化数据保存到 data/douban_top250.json
请礼貌爬取：控制延时、不用于商业用途、遵守目标站点 robots 与条款。
"""
import json
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = "https://book.douban.com/top250?start={}"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9",
}
IMAGE_HEADERS = dict(HEADERS, Referer="https://book.douban.com/")

ROOT = Path(__file__).resolve().parent.parent
COVER_DIR = ROOT / "media" / "covers"
OUT_JSON = ROOT / "data" / "douban_top250.json"


def parse_pub_line(text):
    """解析 '作者 / 译者 / 出版社 / 日期 / 价格' 这一行"""
    parts = [p.strip() for p in text.split("/") if p.strip()]
    author, publisher, pub_date, price = "", "", "", ""
    if len(parts) >= 4:
        author = parts[0]
        price = parts[-1]
        pub_date = parts[-2]
        publisher = parts[-3]
    elif len(parts) == 3:
        author, publisher, pub_date = parts
    elif parts:
        author = parts[0]
    year = ""
    m = re.search(r"(19|20)\d{2}", pub_date)
    if m:
        year = m.group(0)
    return author, publisher, year, price, pub_date


def parse_list_page(html):
    soup = BeautifulSoup(html, "lxml")
    books = []
    for tr in soup.select("tr.item"):
        a = tr.select_one("div.pl2 a")
        if not a:
            continue
        link = a.get("href", "").strip()
        title = a.get_text(strip=True)
        subtitle = ""
        sub = tr.select_one("div.pl2 span.pl")
        if sub:
            subtitle = sub.get_text(strip=True).strip(" :：[]")
        cover = ""
        img = tr.select_one("a.nbg img") or tr.select_one("img")
        if img:
            cover = img.get("src", "").strip()
        pub_p = tr.select_one("p.pl")
        author, publisher, year, price, pub_date = parse_pub_line(
            pub_p.get_text(" ", strip=True) if pub_p else ""
        )
        rating = tr.select_one("span.rating_nums")
        rating = float(rating.get_text(strip=True)) if rating else 0.0
        rating_count = 0
        cnt = tr.select_one("span.pl")
        if cnt:
            m = re.search(r"(\d+)", cnt.get_text().replace(",", ""))
            if m:
                rating_count = int(m.group(1))
        quote = ""
        q = tr.select_one("span.inq")
        if q:
            quote = q.get_text(strip=True)
        m = re.search(r"subject/(\d+)", link)
        subject_id = m.group(1) if m else ""
        books.append({
            "subject_id": subject_id,
            "title": title,
            "subtitle": subtitle,
            "author": author,
            "publisher": publisher,
            "year": int(year) if year else None,
            "pub_date": pub_date,
            "price": price,
            "rating": rating,
            "rating_count": rating_count,
            "quote": quote,
            "cover_url": cover,
            "link": link,
            "summary": "",
            "tags": "",
        })
    return books


def crawl_list(delay=2.0):
    all_books = []
    for start in range(0, 250, 25):
        url = BASE.format(start)
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        books = parse_list_page(r.text)
        print(f"start={start:3d}  解析到 {len(books)} 本  累计 {len(all_books)+len(books)}")
        all_books.extend(books)
        time.sleep(delay)
    return all_books


def fetch_detail(book, delay=2.0):
    """抓取详情页：完整简介 + 标签"""
    if not book.get("link"):
        return book
    try:
        r = requests.get(book["link"], headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return book
        soup = BeautifulSoup(r.text, "lxml")
        intro = soup.select_one("div.intro")
        if intro:
            paras = [p.get_text(strip=True) for p in intro.select("p") if p.get_text(strip=True)]
            # 去掉末尾“(展开全部)”等噪音
            text = "\n".join(paras)
            text = re.sub(r"\s*（展开全部）\s*$", "", text)
            book["summary"] = text[:600]
        tags = [t.get_text(strip=True) for t in soup.select("a.tag")]
        if tags:
            book["tags"] = "，".join(tags[:8])
    except Exception as e:
        print("  详情抓取失败：", book["title"], e)
    time.sleep(delay)
    return book


def download_cover(book, cover_dir=COVER_DIR):
    url = book.get("cover_url", "")
    if not url:
        return ""
    sid = book.get("subject_id") or str(abs(hash(book["title"])))
    ext = ".jpg"
    path = cover_dir / f"{sid}{ext}"
    if path.exists() and path.stat().st_size > 0:
        return f"covers/{sid}{ext}"
    try:
        r = requests.get(url, headers=IMAGE_HEADERS, timeout=20)
        if r.status_code == 200 and r.content:
            path.write_bytes(r.content)
            return f"covers/{sid}{ext}"
    except Exception as e:
        print("  封面下载失败：", book["title"], e)
    return ""


if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "list"
    COVER_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)

    if mode in ("list", "all"):
        books = crawl_list()
        with open(OUT_JSON, "w", encoding="utf-8") as f:
            json.dump(books, f, ensure_ascii=False, indent=2)
        print(f"列表已保存：{OUT_JSON}  共 {len(books)} 本")

    if mode in ("all", "details"):
        books = json.load(open(OUT_JSON, encoding="utf-8"))
        for i, b in enumerate(books):
            if not b.get("summary"):
                fetch_detail(b)
            if (i + 1) % 25 == 0:
                print(f"详情进度 {i+1}/{len(books)}")
                with open(OUT_JSON, "w", encoding="utf-8") as f:
                    json.dump(books, f, ensure_ascii=False, indent=2)
        with open(OUT_JSON, "w", encoding="utf-8") as f:
            json.dump(books, f, ensure_ascii=False, indent=2)
        print("详情补充完成")

    if mode == "covers":
        books = json.load(open(OUT_JSON, encoding="utf-8"))
        ok = 0
        for i, b in enumerate(books):
            rel = download_cover(b)
            if rel:
                b["cover"] = rel
                ok += 1
            if (i + 1) % 25 == 0:
                print(f"封面进度 {i+1}/{len(books)} 成功 {ok}")
        with open(OUT_JSON, "w", encoding="utf-8") as f:
            json.dump(books, f, ensure_ascii=False, indent=2)
        print(f"封面下载完成：{ok}/{len(books)}")
