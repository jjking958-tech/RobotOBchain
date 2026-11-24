# -*- coding: utf-8 -*-
"""W-MSR(Weighted-Mean Subsequence Reduced)算法基线.

经典拜占庭容错分布式一致性算法(对应论文中的对比方法): 每轮迭代中,
每个机器人丢弃邻居值中 f 个最大值与 f 个最小值, 对剩余值与自身值取平均。
其容错上界受先验参数 f 制约: 当实际拜占庭数量超过 f 时收敛失效。

出处: H. Zhang et al., "Distributed subsequence reduction approach to
byzantine fault tolerance", 以及 V. Savkin 等的相关工作; 论文实验中取 F=2。
"""
from __future__ import annotations

import numpy as np


def wmsr_estimate(values: np.ndarray, adj: np.ndarray, f: int,
                  max_iter: int = 200, tol: float = 0.02) -> np.ndarray:
    """W-MSR 迭代一致性.

    Args:
        values: 初始估计向量 [N].
        adj: 0/1 邻接矩阵 [N, N](通信拓扑).
        f: 每端丢弃的极值个数(先验容错上限参数).
        max_iter: 最大迭代次数.
        tol: 收敛容差(max-min < tol 视为收敛).

    Returns:
        收敛后的估计向量 [N].
    """
    x = values.astype(float).copy()
    n = len(x)
    for _ in range(max_iter):
        x_new = x.copy()
        for i in range(n):
            nb = np.where(adj[i] > 0)[0]
            if len(nb) == 0:
                continue
            nb_vals = np.sort(x[nb])
            keep = nb_vals[f: len(nb_vals) - f] if 2 * f < len(nb_vals) else nb_vals
            x_new[i] = (np.mean(keep) + x[i]) / 2.0 if len(keep) else x[i]
        x = x_new
        if np.max(x) - np.min(x) < tol:
            break
    return x


def wmsr_trimmed_mean(values: np.ndarray, f: int) -> float:
    """全局截尾均值: 丢弃 f 个最大与 f 个最小后取均值(集中式对照)."""
    s = np.sort(values)
    return float(np.mean(s[f: len(s) - f])) if 2 * f < len(s) else float(np.mean(s))
