# -*- coding: utf-8 -*-
"""
图书内容画像：jieba 分词 + TF-IDF + LDA 主题模型
--------------------------------------------------
- 以"标签（重复加权）+ 简介"作为图书文本；
- TF-IDF 向量化，用于基于内容的推荐（余弦相似度）；
- LDA 对图书做主题聚类，输出每本书主题及主题关键词。
"""

from __future__ import annotations

import re
from typing import List, Tuple

import logging

import jieba
import numpy as np
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

jieba.setLogLevel(logging.WARNING)

# 中文停用词与高频泛化词
STOPWORDS = {
    "的", "了", "是", "一", "在", "与", "和", "等", "中", "为", "对", "也", "就", "都",
    "而", "及", "这", "那", "有", "个", "本", "以及", "通过", "进行", "由", "于", "从",
    "到", "被", "把", "让", "之", "其", "以", "或", "但", "并", "可", "能", "会", "更",
    "最", "很", "着", "地", "得", "上", "下", "你", "我", "他", "她", "它", "们", "并",
    "书", "本书", "阅读", "作者", "读者", "内容", "一部", "讲述", "介绍", "关于", "如何",
    "我们", "自己", "一个", "一种", "这些", "那些", "可以", "没有", "不仅", "而且", "同时",
    "其中", "方面", "进行", "成为", "通过", "对于", "已经", "还是", "就是", "这个", "那个",
}


def tokenize(text: str) -> List[str]:
    """中文分词并去停用词，保留长度>=2 的词语与英文数字词"""
    words = jieba.lcut(text)
    result = []
    for w in words:
        w = w.strip()
        if not w:
            continue
        if w in STOPWORDS:
            continue
        if re.fullmatch(r"[A-Za-z0-9]+", w) and len(w) < 2:
            continue
        if len(w) >= 2 or re.fullmatch(r"[A-Za-z0-9_+]+", w):
            result.append(w)
    return result


def book_document(book) -> str:
    """图书文本：标签重复以提高权重，再接简介"""
    tags = book.tag_list()
    tag_text = " ".join(tags * 2)
    return f"{tag_text} {book.category} {book.title} {book.description}"


def build_tfidf(books):
    """构建 TF-IDF 矩阵，返回 (vectorizer, matrix, ids)"""
    docs = [" ".join(tokenize(book_document(b))) for b in books]
    vectorizer = TfidfVectorizer(
        tokenizer=lambda s: s.split(),
        token_pattern=None,
        lowercase=False,
        min_df=1,
    )
    matrix = vectorizer.fit_transform(docs)
    ids = [b.id for b in books]
    return vectorizer, matrix, ids


def content_similarity(tfidf_matrix):
    """图书两两内容余弦相似度"""
    return cosine_similarity(tfidf_matrix)


def fit_lda(books, n_topics: int = 10, n_top_words: int = 10, random_state: int = 42):
    """
    LDA 主题模型
    返回：lda 模型, 每本书主题编号数组, 主题关键词列表(每主题 n_top_words 个)
    """
    docs = [" ".join(tokenize(book_document(b))) for b in books]
    cv = CountVectorizer(
        tokenizer=lambda s: s.split(),
        token_pattern=None,
        lowercase=False,
        min_df=2,
    )
    X = cv.fit_transform(docs)
    n_topics = min(n_topics, X.shape[0])
    lda = LatentDirichletAllocation(
        n_components=n_topics,
        random_state=random_state,
        learning_method="batch",
        max_iter=40,
        doc_topic_prior=0.1,
        topic_word_prior=0.1,
    )
    doc_topic = lda.fit_transform(X)
    topics = doc_topic.argmax(axis=1)
    feature_names = cv.get_feature_names_out()
    topic_words = []
    for topic in lda.components_:
        top_idx = topic.argsort()[: -n_top_words - 1: -1]
        topic_words.append([feature_names[i] for i in top_idx])
    return lda, topics, topic_words
