# -*- coding: utf-8 -*-
"""
推荐算法评估指标
- 评分预测：RMSE / MAE
- Top-N 推荐：Precision@N / Recall@N / Coverage
"""

from __future__ import annotations

import numpy as np


def rmse(y_true, y_pred):
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def mae(y_true, y_pred):
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    return float(np.mean(np.abs(y_true - y_pred)))


def precision_recall_at_n(recommendations: dict, relevant: dict, n: int = 10):
    """
    recommendations: {user_id: [book_id, ...]}  每个用户 Top-N 推荐
    relevant:      {user_id: set(book_id)}      测试集中用户相关（如评分>=阈值）的图书
    返回 precision@N, recall@N
    """
    hits = 0
    n_rec = 0
    n_rel = 0
    for user, recs in recommendations.items():
        top = recs[:n]
        rel = relevant.get(user, set())
        if not rel:
            continue
        hit = len(set(top) & rel)
        hits += hit
        n_rec += len(top)
        n_rel += len(rel)
    precision = hits / n_rec if n_rec else 0.0
    recall = hits / n_rel if n_rel else 0.0
    return precision, recall


def coverage(all_items: set, recommendations: dict) -> float:
    """覆盖率：所有推荐结果中出现过的物品占整个物品库的比例"""
    recommended = set()
    for recs in recommendations.values():
        recommended.update(recs)
    return len(recommended & all_items) / len(all_items) if all_items else 0.0


def intra_list_diversity(recommendations: dict, sim_index: dict, sim_matrix) -> float:
    """列表内多样性（Intra-list Diversity）
    每个用户推荐列表中，物品两两的平均距离 = 1 - 内容余弦相似度，取值 [0,1]，越大越多样。
    sim_index: {book_id: 物品下标}，sim_matrix: 物品×物品余弦相似度
    """
    import itertools

    values = []
    for recs in recommendations.values():
        idxs = [sim_index.get(b) for b in recs if sim_index.get(b) is not None]
        if len(idxs) < 2:
            continue
        pair_dist = []
        for a, b in itertools.combinations(idxs, 2):
            pair_dist.append(1.0 - float(sim_matrix[a, b]))
        values.append(float(np.mean(pair_dist)))
    return float(np.mean(values)) if values else 0.0


def novelty(recommendations: dict, item_popularity: dict) -> float:
    """新颖度：推荐物品的平均自信息 -log2(流行度)，越大越偏向长尾、越新颖。
    item_popularity: {book_id: 该物品被评分用户占比}
    """
    total = 0.0
    count = 0
    for recs in recommendations.values():
        for b in recs:
            p = item_popularity.get(b, 0.0)
            if p > 0:
                total += -float(np.log2(p))
                count += 1
    return float(total / count) if count else 0.0
