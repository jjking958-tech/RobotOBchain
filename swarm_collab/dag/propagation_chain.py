# -*- coding: utf-8 -*-
"""算法1: 基于能力增强传播链的模型划分算法.

思想(对应任务书研究内容一): 将复杂神经网络按拓扑序线性化, 划分方案作为
"提议(proposal)"在机器人间传播:

1. 依据机器人异构算力构建**能力增强传播链**(capability-enhanced
   propagation chain), 机器人按算力降序排列, 划分提议沿链逐跳传播;
2. 提议初始化为按算力比例的连续分段(强机器人承担更多层);
3. 提议每到达链上一个机器人, 该机器人即与拓扑相邻段的"邻居机器人"
   协商段边界: 逐层试探边界移动(细粒度到单层), 若能降低全局 makespan
   则接受——即利用邻居节点的计算能力迭代优化划分;
4. 重复传播直至提议不再改进(收敛)。

DAG 划分问题不存在多项式时间最优解, 本算法为启发式近似求解。
"""
from __future__ import annotations

import numpy as np

from .model_dag import ModelDAG
from .planner import Fleet, evaluate


def _initial_split(dag: ModelDAG, fleet: Fleet, chain: list[int]) -> dict[int, int]:
    """按算力比例生成初始连续分段(强者多承担)."""
    order = dag.topo_order()
    cum = np.cumsum([dag.nodes[n].flops_mflops for n in order])
    total_flops = cum[-1]
    total_cap = sum(fleet.gflops(r) for r in chain)
    assignment = {}
    seg = 0
    for i, nid in enumerate(order):
        while seg < len(chain) - 1 and cum[i] / total_flops > sum(
                fleet.gflops(r) for r in chain[: seg + 1]) / total_cap:
            seg += 1
        assignment[nid] = chain[seg]
    return assignment


def partition_propagation_chain(dag: ModelDAG, fleet: Fleet,
                                refine_rounds: int = 6,
                                verbose: bool = False) -> dict[int, int]:
    """基于能力增强传播链的模型划分.

    Args:
        dag: 神经网络 DAG 抽象.
        fleet: 异构机器人编队.
        refine_rounds: 提议沿链传播的最大轮数.
        verbose: 打印每轮收敛信息.

    Returns:
        {node_id -> robot_id} 划分方案.
    """
    chain = fleet.capability_chain()          # 能力增强传播链(算力降序)
    order = dag.topo_order()
    assignment = _initial_split(dag, fleet, chain)
    best = evaluate(dag, assignment, fleet)["makespan"]
    history = [best]

    for rnd in range(refine_rounds):
        improved = False
        # 提议沿链传播: 依次到达链上每个机器人, 与拓扑相邻段的邻居协商边界
        for r in chain:
            # 找到 r 当前持有的段在拓扑序中的边界
            mine = [n for n in order if assignment[n] == r]
            if not mine:
                continue
            first, last = order.index(mine[0]), order.index(mine[-1])
            # 与前一个拓扑段邻居协商
            if first > 0:
                nb = assignment[order[first - 1]]
                if nb != r:
                    best, imp = _negotiate_boundary(
                        dag, fleet, assignment, order, first, r, nb, best)
                    improved |= imp
            # 与后一个拓扑段邻居协商
            if last + 1 < len(order):
                nb = assignment[order[last + 1]]
                if nb != r:
                    best, imp = _negotiate_boundary(
                        dag, fleet, assignment, order, last + 1, r, nb, best)
                    improved |= imp
        history.append(best)
        if verbose:
            print(f"[propagation_chain] round {rnd + 1}: makespan={best:.2f} ms")
        if not improved:
            break

    return assignment


def _negotiate_boundary(dag: ModelDAG, fleet: Fleet, assignment: dict,
                        order: list[int], b_pos: int, r_a: int, r_b: int,
                        best_mk: float, max_shift: int | None = None):
    """邻居边界协商: 试探把边界位置 ``b_pos`` 附近的层在 r_a/r_b 间移动.

    细粒度候选: 移动粒度为单层; 候选范围默认覆盖整个相邻段
    (允许弱机器人整段移交, 由 makespan 改进准则自动取舍)。
    Returns:
        (best_makespan, improved)
    """
    improved = False
    lo = 0 if max_shift is None else max(0, b_pos - max_shift)
    hi = len(order) - 1 if max_shift is None else min(len(order) - 1, b_pos + max_shift)
    # 候选: 把 order[lo..b_pos-1] 归 r_b / 把 order[b_pos..hi] 归 r_a
    candidates = []
    for shift in range(lo, hi + 1):
        take_from_a = order[b_pos: b_pos + shift + 1]      # r_a 吸收 r_b 段的前缀
        give_to_a = order[b_pos - shift - 1: b_pos]        # r_b 吸收 r_a 段的后缀
        candidates.append(("absorb", take_from_a))
        candidates.append(("release", give_to_a))
    for kind, nodes in candidates:
        if not nodes:
            continue
        trial = dict(assignment)
        target = r_a if kind == "absorb" else r_b
        for n in nodes:
            trial[n] = target
        mk = evaluate(dag, trial, fleet)["makespan"]
        if mk < best_mk - 1e-9:
            assignment.update(trial)
            best_mk = mk
            improved = True
    return best_mk, improved
