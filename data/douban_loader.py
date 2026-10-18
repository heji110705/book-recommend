# -*- coding: utf-8 -*-
"""
豆瓣 Top250 数据加载与分类：
- 读取 data/douban_top250.json
- 非小说类（历史/哲学/心理/经济/科学/少儿/诗歌/艺术/传记/社科/语言）用经过校准的标题映射；
  其余长篇小说/科幻/推理/武侠/经典文学统一归入"文学小说"。
- 解析价格、生成标签（分类 + 题材标签）。
"""
import json
import re
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOUBAN_JSON = ROOT / "data" / "douban_top250.json"

CATEGORIES = [
    "文学小说", "历史人文", "哲学宗教", "社会科学", "心理励志", "经济管理",
    "科学科普", "艺术设计", "传记纪实", "少儿读物", "诗歌散文", "语言文化",
]

# 每个分类的题材标签池（用于内容画像，确定性抽取）
CATEGORY_TAGS = {
    "文学小说": ["小说", "文学", "长篇", "经典", "人性", "命运", "情感", "故事", "当代文学", "外国文学", "科幻", "推理", "武侠", "名著"],
    "历史人文": ["历史", "人文", "通史", "史料", "文明", "朝代", "史料考据", "历史规律", "中国史", "世界史"],
    "哲学宗教": ["哲学", "宗教", "思想", "佛学", "道家", "儒家", "思辨", "人生哲理", "西方哲学", "存在主义"],
    "社会科学": ["社会学", "社会", "政治", "制度", "女性主义", "人类学", "法治", "文化研究", "公共议题", "纪实观察"],
    "心理励志": ["心理", "自我成长", "情绪", "沟通", "认知", "治愈", "人际关系", "积极心理", "疗愈", "个人成长"],
    "经济管理": ["经济", "金融", "商业", "管理", "投资", "思维", "决策", "企业", "市场", "产业"],
    "科学科普": ["科普", "物理", "宇宙", "科学", "数学", "生物", "演化", "天文", "科学思维", "量子"],
    "艺术设计": ["艺术", "设计", "美学", "美术", "音乐", "电影", "视觉", "建筑", "艺术史", "摄影"],
    "传记纪实": ["传记", "回忆录", "纪实", "人物传记", "自传", "口述", "人生", "时代", "非虚构", "纪实文学"],
    "少儿读物": ["儿童", "童话", "绘本", "亲子", "成长", "启蒙", "童趣", "想象力", "儿童文学", "少儿"],
    "诗歌散文": ["诗歌", "散文", "随笔", "诗词", "文集", "杂文", "散文诗", "古典文学", "现代诗", "随笔集"],
    "语言文化": ["语言", "阅读", "文字", "文化", "写作", "汉语", "阅读方法", "语言学", "工具书", "人文"],
}

# 经过校准的显式分类：标题包含任一关键词即归入对应分类（按类别给定）
MANUAL = {
    "历史人文": [
        "邓小平时代", "明朝那些事儿", "人类简史", "万历十五年", "南京大屠杀",
        "史记", "历史深处的忧虑", "筚路维艰", "天朝的崩溃", "东晋门阀政治",
        "國史大綱", "康熙的红票", "全球通史", "我也有一个梦想", "翦商",
        "奥斯维辛", "红星照耀中国", "二手时间", "显微镜下的大明", "中国历代政治得失",
        "大明王朝1566",
    ],
    "社会科学": [
        "寻路中国", "可能性的艺术", "毛泽东选集", "一间只属于自己的房间",
        "始于极限", "厌女", "看不见的女性", "从零开始的女性主义",
        "父权制与资本主义", "跨越边界的社区", "李光耀观天下",
    ],
    "哲学宗教": [
        "刘擎西方现代思想讲义", "道德经", "庄子", "论语", "苏菲的世界",
        "理想国", "会饮篇", "孙子兵法", "规训与惩罚", "悉达多",
        "爱的艺术", "人生的智慧",
    ],
    "心理励志": [
        "也许你该找个人聊聊", "亲密关系", "社会心理学", "最好的告别",
    ],
    "经济管理": [
        "置身事内", "经济学原理", "激荡三十年", "浪潮之巅",
    ],
    "科学科普": [
        "时间简史", "时间的秩序", "上帝掷骰子吗", "十万个为什么", "平面国",
    ],
    "艺术设计": [
        "艺术的故事", "美的历程", "现代艺术150年", "雕刻时光",
        "材质·结构",
    ],
    "传记纪实": [
        "史蒂夫·乔布斯传", "渴望生活", "你当像鸟飞往你的山", "昨日的世界",
        "天生有罪", "当呼吸化为空气", "打开一颗心", "一个女人的故事",
        "足利女童", "桶川跟踪狂", "我不知道该说什么", "我们仨",
        "成为波伏瓦", "黑箱", "少年凯歌",
    ],
    "诗歌散文": [
        "诗经", "唐诗三百首", "海子的诗", "飞鸟集", "人间词话", "浮生六记",
        "撒哈拉的故事", "哭泣的骆驼", "温柔的夜", "梦里花落知多少",
        "万水千山走遍", "雨季不再来", "野草", "坟", "我与地坛", "人间草木",
        "阿勒泰的角落", "我的阿勒泰", "冬牧场", "遥远的向日葵地",
        "送你一颗子弹", "野火集",
    ],
    "语言文化": [
        "古文观止", "人间词话",
    ],
    "少儿读物": [
        "哈利·波特", "小王子", "安徒生", "格林童话", "中国少年儿童百科全书",
        "窗边的小豆豆", "王尔德童话", "海的女儿", "一千零一夜",
        "草房子", "孩子你慢慢来",
    ],
}


def classify(title):
    """根据标题返回分类（默认文学小说）"""
    for cat, keys in MANUAL.items():
        for k in keys:
            if k in title:
                return cat
    return "文学小说"


def make_tags(title, category):
    """分类 + 确定性抽取的题材标签"""
    rng = random.Random(title)
    pool = CATEGORY_TAGS[category]
    picked = rng.sample(pool, min(4, len(pool)))
    tags = [category] + [p for p in picked if p != category]
    return "，".join(tags[:5])


def parse_price(raw):
    """从 '59.70元' / 'CNY 88.00' 等字符串解析价格"""
    if not raw:
        return None
    nums = re.findall(r"\d+\.?\d*", raw.replace(",", ""))
    vals = [float(n) for n in nums if 0.5 < float(n) < 2000]
    if not vals:
        return None
    return round(vals[0], 1)


def load_douban_books():
    """读取 JSON 并返回规整后的图书字典列表"""
    with open(DOUBAN_JSON, "r", encoding="utf-8") as f:
        raw = json.load(f)
    result = []
    for item in raw:
        title = item.get("title", "").strip()
        cat = classify(title)
        desc = item.get("summary") or item.get("quote") or ""
        result.append({
            "subject_id": item.get("subject_id", ""),
            "title": title,
            "subtitle": item.get("subtitle", "").strip(),
            "author": item.get("author", "").strip(),
            "publisher": item.get("publisher", "").strip(),
            "pub_date": item.get("pub_date", "").strip(),
            "pub_year": item.get("year"),
            "price": parse_price(item.get("price", "")),
            "category": cat,
            "tags": make_tags(title, cat),
            "description": desc,
            "quote": item.get("quote", "").strip(),
            "douban_rating": item.get("rating", 0),
            "douban_votes": item.get("rating_count", 0),
            "cover": item.get("cover", ""),
            "link": item.get("link", ""),
        })
    return result


if __name__ == "__main__":
    from collections import Counter
    books = load_douban_books()
    cnt = Counter(b["category"] for b in books)
    out = [f"共 {len(books)} 本，分类分布："]
    for c in CATEGORIES:
        out.append(f"  {c:6s} {cnt.get(c,0):3d}")
    out.append("")
    for c in CATEGORIES:
        titles = [b["title"] for b in books if b["category"] == c]
        out.append(f"【{c}】({len(titles)}) " + "、".join(titles[:14]))
    Path(ROOT / "_classify.txt").write_text("\n".join(out), encoding="utf-8")
    print("\n".join(out[:14]))
