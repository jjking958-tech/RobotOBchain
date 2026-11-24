# -*- coding: utf-8 -*-
"""异构机器人编队的协同推理延迟模型与对比基线.

延迟模型:
- 计算延迟: 层 i 在机器人 r 上耗时 t_i = flops_i(MFLOPs) / cap_r(GFLOPS) (ms);
- 传输延迟: 跨机器人边 (u,v) 耗时 c_uv = bytes_uv * 8 / (BW_uv Mbps) (ms),
  传输开销计入发送方机器人;
- 目标(完成时间): makespan = max_r (计算延迟 + 传输延迟)。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .model_dag import ModelDAG


@dataclass
class RobotProfile:
    """机器人异构计算能力描述."""

    id: int
    gflops: float          # 峰值算力(GFLOPS, 单精度)


@dataclass
class Fleet:
    """机器人编队: 算力画像 + 链路带宽矩阵(Mbps)."""

    robots: list[RobotProfile]

    def __post_init__(self):
        self.n = len(self.robots)
        self._bw = np.full((self.n, self.n), 25.0)  # 默认 25 Mbps(弱连接)
        np.fill_diagonal(self._bw, np.inf)

    def set_bandwidth(self, u: int, v: int, mbps: float):
        self._bw[u, v] = self._bw[v, u] = mbps

    def bw(self, u: int, v: int) -> float:
        return self._bw[u, v]

    def gflops(self, r: int) -> float:
        return self.robots[r].gflops

    def ids(self) -> list[int]:
        return [r.id for r in self.robots]

    def capability_chain(self) -> list[int]:
        """按算力降序排列的机器人链(能力增强传播链的遍历顺序)."""
        return [r.id for r in sorted(self.robots, key=lambda r: -r.gflops)]


def compute_ms(flops_mflops: float, gflops: float) -> float:
    """单层计算延迟(ms)."""
    return flops_mflops / gflops


def transmit_ms(n_bytes: int, mbps: float) -> float:
    """跨节点传输延迟(ms)."""
    return n_bytes * 8.0 / (mbps * 1e3)


def evaluate(dag: ModelDAG, assignment: dict[int, int], fleet: Fleet,
             partial: bool = False) -> dict:
    """评估划分方案的延迟.

    Args:
        partial: 允许部分分配(未分配节点不计入), 供贪心基线逐步评估.

    Returns:
        dict(loads={robot_id: ms}, makespan=ms, cut_edges=跨机器人边数,
             comm_ms=总传输延迟)
    """
    loads = {r: 0.0 for r in fleet.ids()}
    cut_edges = 0
    comm_total = 0.0
    for (u, v), b in dag.edge_bytes.items():
        ru, rv = assignment.get(u), assignment.get(v)
        if ru is None or rv is None:
            if partial:
                continue
            raise KeyError(f"edge ({u}, {v}) touches unassigned node")
        if ru != rv:
            cut_edges += 1
            t = transmit_ms(b, fleet.bw(ru, rv))
            loads[ru] += t          # 发送方承担传输
            loads[rv] += t * 0.5    # 接收方承担一半写入开销
            comm_total += t
    for nid, r in assignment.items():
        loads[r] += compute_ms(dag.nodes[nid].flops_mflops, fleet.gflops(r))
    return {
        "loads": loads,
        "makespan": max(loads.values()),
        "cut_edges": cut_edges,
        "comm_ms": comm_total,
    }


# ---------------------------------------------------------------------------
# 对比基线
# ---------------------------------------------------------------------------
def partition_round_robin(dag: ModelDAG, fleet: Fleet) -> dict[int, int]:
    """基线: 拓扑序轮转分配."""
    ids = fleet.ids()
    return {nid: ids[i % fleet.n] for i, nid in enumerate(dag.topo_order())}


def partition_single(dag: ModelDAG, fleet: Fleet) -> dict[int, int]:
    """基线: 全部部署在最强机器人上(无协同推理)."""
    best = max(fleet.ids(), key=lambda r: fleet.gflops(r))
    return {nid: best for nid in dag.nodes}


def partition_greedy(dag: ModelDAG, fleet: Fleet) -> dict[int, int]:
    """基线: 按(深度, 计算量)降序逐节点贪心放置到边际 makespan 最小的机器人."""
    depth = dag.depth_of()
    order = sorted(dag.nodes.values(), key=lambda n: (-depth[n.id], -n.flops_mflops))
    assignment = {}
    for node in order:
        best_r, best_mk = None, float("inf")
        for r in fleet.ids():
            trial = dict(assignment)
            trial[node.id] = r
            mk = evaluate(dag, trial, fleet, partial=True)["makespan"]
            if mk < best_mk:
                best_r, best_mk = r, mk
        assignment[node.id] = best_r
    return assignment
