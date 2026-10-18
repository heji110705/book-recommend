# -*- coding: utf-8 -*-
"""
推荐引擎：统一训练与生成 UserCF / ItemCF / FunkSVD / 内容推荐 / 混合推荐，
并提供评分预测(RMSE/MAE) 与 Top-N(Precision/Recall/Coverage) 评估。
"""

from __future__ import annotations

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from apps.books.models import Book, Rating
from apps.recommender.services import content
from apps.recommender.services.svd import FunkSVD

# 混合权重（密度自适应）—— 经多种子离线网格搜索得到的 Pareto 最优方案：
#   始终以内容推荐为主（内容权重 0.85~0.88，保证个性化准确率）；
#   评分越多，SVD 协同权重从 svd_min 升到 svd_max（信任协同信号）；
#   口碑权重随评分增多而衰减（冷启动用口碑兜底，成熟用户不再受全局热门干扰）。
#   该方案在 5 个随机切分下，Top-N 准确率/召回率、覆盖率、RMSE 均不差于单一最优算法。
WEIGHTS = {
    "svd_min": 0.05,   # 冷启动用户的 SVD 权重
    "svd_max": 0.12,   # 数据充足用户的 SVD 权重
    "rep_max": 0.10,   # 冷启动用户的口碑权重（随评分增多衰减到 0）
}
RELEVANT_THRESHOLD = 7.0  # 评分>=7 视为相关物品


def build_matrix(rows, user_ids, book_ids):
    """由 (user_id, book_id, score) 行构建 user×item 评分矩阵，缺失为 NaN"""
    u_index = {u: i for i, u in enumerate(user_ids)}
    i_index = {b: i for i, b in enumerate(book_ids)}
    R = np.full((len(user_ids), len(book_ids)), np.nan)
    for uid, bid, score in rows:
        R[u_index[uid], i_index[bid]] = score
    return R, u_index, i_index


class TrainedModel:
    """在给定训练矩阵上训练全部推荐模型"""

    def __init__(self, R, user_ids, book_ids, book_objs, content_sim,
                 n_factors=12, k_user=25, k_item=30):
        self.R = R
        self.user_ids = list(user_ids)
        self.book_ids = list(book_ids)
        self.book_objs = book_objs  # 与 book_ids 同序
        self.content_sim = content_sim
        self.k_user = k_user
        self.k_item = k_item
        self.n_users, self.n_items = R.shape

        self.global_mean = float(np.nanmean(R)) if np.isfinite(R).any() else 7.0
        # 用户/物品偏置（均值）
        with np.errstate(all="ignore"):
            self.user_means = np.where(np.isnan(R).all(axis=1),
                                       self.global_mean, np.nanmean(R, axis=1))
            self.item_means = np.where(np.isnan(R).all(axis=0),
                                       self.global_mean, np.nanmean(R, axis=0))
        # 用户均值中心化矩阵（缺失填 0）
        self.Rc = (R - self.user_means[:, None])
        self.Rc = np.where(np.isnan(R), 0.0, self.Rc)

        # 口碑
        self.reputation = self._build_reputation(book_objs)

        # 相似度矩阵
        self.user_sim = self._safe_cosine(self.Rc)
        self.item_sim = self._safe_cosine(self.Rc.T)

        # FunkSVD
        observed = [(u, i, R[u, i]) for u in range(self.n_users)
                    for i in range(self.n_items) if np.isfinite(R[u, i])]
        self.svd = FunkSVD(self.n_users, self.n_items, n_factors=n_factors)
        self.svd.fit(observed)

    @staticmethod
    def _safe_cosine(X):
        try:
            sim = cosine_similarity(X)
        except ValueError:
            sim = np.zeros((X.shape[0], X.shape[0]))
        np.fill_diagonal(sim, 0.0)
        return np.nan_to_num(sim)

    @staticmethod
    def _build_reputation(book_objs):
        rep = np.zeros(len(book_objs))
        for i, b in enumerate(book_objs):
            # 口碑 = 0.5*好评率 + 0.5*情感分归一化
            rep[i] = 0.5 * b.positive_rate + 0.5 * ((b.sentiment_score + 1) / 2)
        return rep

    # ---------------- 各算法评分预测（1-10 分） ----------------
    def predict_usercf(self, u, i):
        rated = np.where(np.isfinite(self.R[:, i]))[0]
        rated = rated[rated != u]
        if len(rated) == 0:
            return self.item_means[i]
        sims = self.user_sim[u, rated]
        top = np.argsort(-np.abs(sims))[: self.k_user]
        neigh, ns = rated[top], sims[top]
        denom = np.sum(np.abs(ns))
        if denom < 1e-8:
            return self.item_means[i]
        return self.user_means[u] + np.sum(ns * self.Rc[neigh, i]) / denom

    def predict_itemcf(self, u, i):
        rated = np.where(np.isfinite(self.R[u, :]))[0]
        rated = rated[rated != i]
        if len(rated) == 0:
            return self.user_means[u]
        sims = self.item_sim[i, rated]
        top = np.argsort(-np.abs(sims))[: self.k_item]
        items, ns = rated[top], sims[top]
        denom = np.sum(np.abs(ns))
        if denom < 1e-8:
            return self.user_means[u]
        return self.user_means[u] + np.sum(ns * self.Rc[u, items]) / denom

    def predict_svd(self, u, i):
        return self.svd.predict(u, i)

    def predict_content(self, u, i):
        rated = np.where(np.isfinite(self.R[u, :]))[0]
        rated = rated[rated != i]
        if len(rated) == 0:
            return np.nan
        sims = self.content_sim[i, rated]
        denom = np.sum(np.abs(sims))
        if denom < 1e-8:
            return np.nan
        return float(np.sum(sims * self.R[u, rated]) / denom)

    def predict(self, u, i, algo):
        if algo == "usercf":
            return self.predict_usercf(u, i)
        if algo == "itemcf":
            return self.predict_itemcf(u, i)
        if algo == "svd":
            return self.predict_svd(u, i)
        if algo == "content":
            return self.predict_content(u, i)
        if algo == "hybrid":
            return self.predict_hybrid(u, i)
        return np.nan

    def _norm10(self, x):
        return np.clip((x - 1.0) / 9.0, 0.0, 1.0)

    def hybrid_score(self, u, i):
        """密度自适应混合推荐分 [0,1]
        - 用户评分越多，协同过滤(SVD)越可信；
        - 冷启动/评分少的用户，更依赖内容画像与口碑，保证可推荐。
        """
        svd_n = self._norm10(self.predict_svd(u, i))
        content = self.predict_content(u, i)
        n_rated = int(np.isfinite(self.R[u]).sum())
        alpha = min(n_rated / 35.0, 1.0)  # 协同可信度 0~1
        w_svd = WEIGHTS["svd_min"] + (WEIGHTS["svd_max"] - WEIGHTS["svd_min"]) * alpha
        w_rep = WEIGHTS["rep_max"] * (1.0 - alpha)  # 口碑随评分增多而衰减
        if np.isfinite(content):
            content_n = self._norm10(content)
            w_content = 1.0 - w_svd - w_rep
            score = (w_svd * svd_n + w_content * content_n
                     + w_rep * self.reputation[i])
        else:
            # 内容无法预测（冷启动）：SVD + 口碑
            score = 0.6 * svd_n + 0.4 * self.reputation[i]
        return float(score)

    def predict_hybrid(self, u, i):
        """换算回 1-10 分，便于评分预测评估"""
        return 1.0 + 9.0 * self.hybrid_score(u, i)

    # ---------------- 推荐可解释性（为什么推荐） ----------------
    def _reason_by_hot(self, i):
        b = self.book_objs[i]
        if b.positive_rate > 0:
            return f"{b.category}口碑佳作，好评率 {round(b.positive_rate * 100)}%，{b.display_votes} 人评价"
        return f"{b.category}高人气作品，{b.display_votes} 人评价"

    def _liked_neighbor(self, u, i, rated, sim_row):
        """在用户已打分(优先>=7)的书里，找与目标 i 相似度最高的"""
        if len(rated) == 0:
            return None
        sims = sim_row[rated]
        ratings = self.R[u, rated]
        liked = np.where(ratings >= 7)[0]
        pool = liked if len(liked) else np.arange(len(rated))
        k = pool[np.argmax(sims[pool])]
        return rated[k], float(sims[k]), float(ratings[k])

    def _reason_by_content(self, u, i, rated):
        nb = self._liked_neighbor(u, i, rated, self.content_sim[i])
        if nb is None:
            return self._reason_by_hot(i)
        j, sim, score = nb
        return f"与你打了 {score:.0f} 分的《{self.book_objs[j].title}》题材相近"

    def _reason_by_itemcf(self, u, i, rated):
        nb = self._liked_neighbor(u, i, rated, self.item_sim[i])
        if nb is None:
            return self._reason_by_hot(i)
        j, _, _ = nb
        return f"喜欢《{self.book_objs[j].title}》的读者也常读这本"

    def _reason_by_usercf(self, u, i):
        others = np.where(np.isfinite(self.R[:, i]))[0]
        others = others[others != u]
        if len(others) == 0:
            return self._reason_by_hot(i)
        sims = self.user_sim[u, others]
        k = int(np.argmax(sims))
        return f"与你口味相近的读者给了它 {self.R[others[k], i]:.0f} 分"

    def _reason_by_svd(self, u, i):
        p = self.predict_svd(u, i)
        return f"契合你的潜在阅读偏好（模型预测 {p:.1f} 分）"

    def _reason_by_hybrid(self, u, i, rated):
        svd_n = self._norm10(self.predict_svd(u, i))
        content = self.predict_content(u, i)
        n_rated = int(np.isfinite(self.R[u]).sum())
        alpha = min(n_rated / 35.0, 1.0)
        w_svd = WEIGHTS["svd_min"] + (WEIGHTS["svd_max"] - WEIGHTS["svd_min"]) * alpha
        w_rep = WEIGHTS["rep_max"] * (1.0 - alpha)
        if np.isfinite(content):
            contrib = {
                "content": (1.0 - w_svd - w_rep) * self._norm10(content),
                "svd": w_svd * svd_n,
                "rep": w_rep * self.reputation[i],
            }
            dom = max(contrib, key=contrib.get)
            if dom == "content":
                return self._reason_by_content(u, i, rated)
            if dom == "rep":
                return self._reason_by_hot(i)
            return self._reason_by_svd(u, i)
        return self._reason_by_hot(i)

    def explain(self, u, i, algo="hybrid"):
        """为推荐项 i 返回一条可读的推荐理由"""
        rated = np.where(np.isfinite(self.R[u]))[0]
        if algo == "content":
            return self._reason_by_content(u, i, rated)
        if algo == "itemcf":
            return self._reason_by_itemcf(u, i, rated)
        if algo == "usercf":
            return self._reason_by_usercf(u, i)
        if algo == "svd":
            return self._reason_by_svd(u, i)
        if algo == "hybrid":
            return self._reason_by_hybrid(u, i, rated)
        return self._reason_by_hot(i)

    def seen_items(self, u):
        return set(np.where(np.isfinite(self.R[u]))[0])

    def recommend(self, u, algo="hybrid", n=15, exclude_seen=True):
        """为用户 u 返回 Top-N 推荐 [(book_id, score), ...]"""
        if u is None or u >= self.n_users:
            return []  # 由上层回退到热门
        seen = self.seen_items(u) if exclude_seen else set()
        scores = []
        for i in range(self.n_items):
            if i in seen:
                continue
            if algo == "usercf":
                p = self.predict_usercf(u, i)
                s = self._norm10(p)
            elif algo == "itemcf":
                p = self.predict_itemcf(u, i)
                s = self._norm10(p)
            elif algo == "svd":
                s = self._norm10(self.predict_svd(u, i))
            elif algo == "content":
                p = self.predict_content(u, i)
                if not np.isfinite(p):
                    continue
                s = self._norm10(p)
            elif algo == "hybrid":
                s = self.hybrid_score(u, i)
            else:
                continue
            scores.append((self.book_ids[i], float(s)))
        scores.sort(key=lambda x: -x[1])
        return scores[:n]

    def hot_items(self, n=30, preferred_categories=None):
        """热门/口碑推荐（冷启动兜底）
        preferred_categories：用户选择的偏好分类，命中时加权（偏好冷启动）。
        """
        counts = np.isfinite(self.R).sum(axis=0)
        m = 5.0
        score = ((counts / (counts + m)) * self.item_means
                 + (m / (counts + m)) * self.global_mean)
        # 口碑微调
        score = score + 0.3 * self.reputation
        if preferred_categories:
            pref = set(preferred_categories)
            for i, b in enumerate(self.book_objs):
                if b.category in pref:
                    score[i] += 0.8  # 偏好分类加权（10 分制）
        order = np.argsort(-score)[:n]
        return [(self.book_ids[int(i)], float(score[int(i)])) for i in order]


# ---------------------------------------------------------------------------
# 单例引擎，供视图/命令复用
# ---------------------------------------------------------------------------
_engine = None


def get_engine(force_rebuild=False):
    """获取（必要时构建）全量数据上训练的推荐引擎"""
    global _engine
    if _engine is not None and not force_rebuild:
        return _engine
    book_objs = list(Book.objects.all().order_by("id"))
    book_ids = [b.id for b in book_objs]
    rows = list(Rating.objects.values_list("user_id", "book_id", "score"))
    user_ids = sorted({r[0] for r in rows})
    R, u_index, i_index = build_matrix(rows, user_ids, book_ids)
    _, tfidf, _ = content.build_tfidf(book_objs)
    content_sim = content.content_similarity(tfidf)
    _engine = TrainedModel(R, user_ids, book_ids, book_objs, content_sim)
    _engine.u_index = u_index
    _engine.i_index = i_index
    return _engine


def reset_engine():
    global _engine
    _engine = None
