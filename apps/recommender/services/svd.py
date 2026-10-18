# -*- coding: utf-8 -*-
"""
FunkSVD（隐语义矩阵分解）
-------------------------
将用户-物品评分矩阵 R 分解为：
    R_hat[u, i] = mu + bu[u] + bi[i] + P[u] · Q[i]
使用随机梯度下降在观测评分上最小化带 L2 正则的平方误差。
"""

from __future__ import annotations

import numpy as np


class FunkSVD:
    def __init__(
        self,
        n_users: int,
        n_items: int,
        n_factors: int = 12,
        lr: float = 0.005,
        reg: float = 0.02,
        epochs: int = 80,
        random_state: int = 42,
    ):
        self.n_users = n_users
        self.n_items = n_items
        self.n_factors = n_factors
        self.lr = lr
        self.reg = reg
        self.epochs = epochs
        self.random_state = random_state

        rng = np.random.default_rng(random_state)
        self.P = rng.normal(0, 0.1, (n_users, n_factors))
        self.Q = rng.normal(0, 0.1, (n_items, n_factors))
        self.bu = np.zeros(n_users)
        self.bi = np.zeros(n_items)
        self.mu = 0.0
        self.train_rmse_history = []

    def fit(self, rows):
        """
        rows: 可迭代的 (user_idx, item_idx, rating)
        """
        rows = np.asarray(list(rows), dtype=float)
        if len(rows) == 0:
            return self
        self.mu = float(rows[:, 2].mean())
        u_idx = rows[:, 0].astype(int)
        i_idx = rows[:, 1].astype(int)
        ratings = rows[:, 2]

        for epoch in range(self.epochs):
            # 每个 epoch 打乱顺序
            order = np.random.default_rng(self.random_state + epoch).permutation(len(rows))
            se = 0.0
            for idx in order:
                u, i, r = u_idx[idx], i_idx[idx], ratings[idx]
                pu, qi = self.P[u], self.Q[i]
                pred = self.mu + self.bu[u] + self.bi[i] + np.dot(pu, qi)
                err = r - pred
                se += err ** 2

                # 梯度更新
                bu_old = self.bu[u]
                bi_old = self.bi[i]
                self.bu[u] += self.lr * (err - self.reg * bu_old)
                self.bi[i] += self.lr * (err - self.reg * bi_old)
                self.P[u] = pu + self.lr * (err * qi - self.reg * pu)
                self.Q[i] = qi + self.lr * (err * pu - self.reg * qi)

            self.train_rmse_history.append(float(np.sqrt(se / len(rows))))
        return self

    def predict(self, u: int, i: int) -> float:
        if u >= self.n_users or i >= self.n_items:
            return self.mu
        pred = self.mu + self.bu[u] + self.bi[i] + np.dot(self.P[u], self.Q[i])
        return float(np.clip(pred, 1.0, 10.0))

    def predict_all(self):
        """返回完整的预测评分矩阵"""
        preds = self.mu + self.bu[:, None] + self.bi[None, :] + self.P @ self.Q.T
        return np.clip(preds, 1.0, 10.0)
