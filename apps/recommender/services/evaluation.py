# -*- coding: utf-8 -*-
"""
推荐算法离线评估
- 按用户划分训练/测试集（保留每用户至少 1 条训练）；
- 评分预测 RMSE/MAE；
- Top-N 推荐 Precision@N / Recall@N / Coverage；
- 推荐多样性 Intra-list Diversity、新颖度 Novelty（自信息）；
- 为消除随机切分带来的波动，默认在 5 个随机种子上评估并报告均值。
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np

from apps.books.models import Book, Rating
from apps.recommender.services import content, metrics
from apps.recommender.services.engine import (
    RELEVANT_THRESHOLD,
    TrainedModel,
    build_matrix,
)

ALGOS = ["usercf", "itemcf", "svd", "content", "hybrid"]
# 多随机种子，保证评估结论稳健、可复现
DEFAULT_SEEDS = (42, 7, 123, 2024, 99)


def split_train_test(rows, test_ratio=0.2, seed=42):
    """按用户分层划分，保证至少 1 条训练数据"""
    rng = np.random.default_rng(seed)
    by_user = defaultdict(list)
    for r in rows:
        by_user[r[0]].append(r)
    train, test = [], []
    for uid, items in by_user.items():
        items = items[:]
        rng.shuffle(items)
        if len(items) < 5:
            train.extend(items)
            continue
        n_test = max(1, int(round(len(items) * test_ratio)))
        if len(items) - n_test < 1:
            n_test = len(items) - 1
        test.extend(items[:n_test])
        train.extend(items[n_test:])
    return train, test


def _evaluate_once(book_objs, rows, user_ids, book_ids, content_sim,
                   test_ratio, top_n, n_factors, seed):
    """单个随机切分下的完整评估"""
    train_rows, test_rows = split_train_test(rows, test_ratio=test_ratio, seed=seed)
    R_train, u_index, i_index = build_matrix(train_rows, user_ids, book_ids)
    model = TrainedModel(R_train, user_ids, book_ids, book_objs, content_sim,
                         n_factors=n_factors)

    # 1) 评分预测
    y_true_all = []
    y_pred = {a: [] for a in ALGOS}
    baseline_global, baseline_item = [], []
    for uid, bid, score in test_rows:
        u, i = u_index.get(uid), i_index.get(bid)
        if u is None or i is None:
            continue
        y_true_all.append(score)
        for a in ALGOS:
            p = model.predict(u, i, a)
            if np.isfinite(p):
                y_pred[a].append(p)
        baseline_global.append(model.global_mean)
        baseline_item.append(model.item_means[i])

    rating_metrics = {}
    for a in ALGOS:
        if a == "content":
            ctrue, cpred = [], []
            for uid, bid, score in test_rows:
                u, i = u_index.get(uid), i_index.get(bid)
                if u is None or i is None:
                    continue
                p = model.predict_content(u, i)
                if np.isfinite(p):
                    ctrue.append(score)
                    cpred.append(p)
            rating_metrics[a] = {"rmse": metrics.rmse(ctrue, cpred),
                                 "mae": metrics.mae(ctrue, cpred)}
        else:
            n = len(y_pred[a])
            rating_metrics[a] = {
                "rmse": metrics.rmse(y_true_all[:n], y_pred[a]),
                "mae": metrics.mae(y_true_all[:n], y_pred[a])}
    rating_metrics["baseline_global"] = {
        "rmse": metrics.rmse(y_true_all, baseline_global),
        "mae": metrics.mae(y_true_all, baseline_global)}
    rating_metrics["baseline_item"] = {
        "rmse": metrics.rmse(y_true_all, baseline_item),
        "mae": metrics.mae(y_true_all, baseline_item)}

    # 2) Top-N 推荐
    test_by_user = defaultdict(list)
    for uid, bid, score in test_rows:
        test_by_user[uid].append((bid, score))
    all_items = set(book_ids)

    # 物品流行度（训练集中评分用户占比，用于新颖度）
    pop_count = defaultdict(set)
    for uid, bid, _ in train_rows:
        pop_count[bid].add(uid)
    n_users = len(user_ids)
    item_popularity = {bid: len(us) / n_users for bid, us in pop_count.items()}

    topn_metrics = {}
    for a in ALGOS:
        recs, rel = {}, {}
        for uid, pairs in test_by_user.items():
            u = u_index.get(uid)
            if u is None:
                continue
            relevant = {bid for bid, s in pairs if s >= RELEVANT_THRESHOLD}
            if not relevant:
                continue
            rec_list = model.recommend(u, algo=a, n=top_n, exclude_seen=True)
            recs[uid] = [bid for bid, _ in rec_list]
            rel[uid] = relevant
        if recs:
            p, r = metrics.precision_recall_at_n(recs, rel, n=top_n)
            cov = metrics.coverage(all_items, recs)
            div = metrics.intra_list_diversity(recs, i_index, content_sim)
            nov = metrics.novelty(recs, item_popularity)
        else:
            p = r = cov = div = nov = 0.0
        topn_metrics[a] = {
            "precision": p, "recall": r, "coverage": cov,
            "diversity": div, "novelty": nov,
        }

    return {
        "n_train": len(train_rows),
        "n_test": len(test_rows),
        "rating": rating_metrics,
        "topn": topn_metrics,
        "svd_loss": model.svd.train_rmse_history,
    }


def _aggregate(runs, keys):
    """把多次评估的同名指标取均值与标准差"""
    out = {}
    for algo in runs[0]:
        out[algo] = {}
        for k in keys:
            vals = np.array([r[algo][k] for r in runs], dtype=float)
            out[algo][k] = float(vals.mean())
            out[algo][k + "_std"] = float(vals.std(ddof=0))
    return out


def evaluate(test_ratio=0.2, top_n=10, n_factors=12, seeds=DEFAULT_SEEDS):
    """在多个随机切分上评估，返回各指标均值（附带标准差 *_std）"""
    book_objs = list(Book.objects.all().order_by("id"))
    book_ids = [b.id for b in book_objs]
    rows = list(Rating.objects.values_list("user_id", "book_id", "score"))
    user_ids = sorted({r[0] for r in rows})

    _, tfidf, _ = content.build_tfidf(book_objs)
    content_sim = content.content_similarity(tfidf)

    runs = [
        _evaluate_once(book_objs, rows, user_ids, book_ids, content_sim,
                       test_ratio, top_n, n_factors, seed)
        for seed in seeds
    ]

    rating_keys = ["rmse", "mae"]
    # 基线算法只在每次评估中出现，同样参与聚合
    rating_runs = [r["rating"] for r in runs]
    rating_all = _aggregate(rating_runs, rating_keys)
    topn_keys = ["precision", "recall", "coverage", "diversity", "novelty"]
    topn_runs = [r["topn"] for r in runs]
    topn_all = _aggregate(topn_runs, topn_keys)

    return {
        "n_train": int(np.mean([r["n_train"] for r in runs])),
        "n_test": int(np.mean([r["n_test"] for r in runs])),
        "rating": rating_all,
        "topn": topn_all,
        "svd_loss": runs[0]["svd_loss"],  # 收敛曲线取一次代表
        "top_n": top_n,
        "seeds": list(seeds),
        "multi_seed": True,
    }
