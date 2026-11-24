# -*- coding: utf-8 -*-
"""神经网络 -> DAG 抽象.

将复杂神经网络(如 GoogleNet)抽象为 DAG 图:
- 图中每个节点表示原网络中的一个卷积/池化/全连接层, 记录其计算量(MFLOPs);
- 有向边表示层间数据依赖, 记录激活张量传输量(字节), 作为划分算法中
  通信开销的输入。

DAG 划分问题不存在多项式时间内的最优解, 本模块为启发式划分算法
(见 :mod:`.propagation_chain` 与 :mod:`.path_backtracking`)提供输入。
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LayerNode:
    """DAG 节点: 原神经网络中的一个层.

    Attributes:
        id: 节点唯一编号(拓扑序约定 id 递增).
        name: 层名称, 如 ``inception3_5x5``.
        flops_mflops: 该层前向计算量(百万次浮点运算).
        out_bytes: 该层输出激活张量大小(字节, fp32), 决定跨节点传输开销.
    """

    id: int
    name: str
    flops_mflops: float
    out_bytes: int

    def __post_init__(self):
        if self.out_bytes is None:
            raise ValueError(f"layer {self.name}: out_bytes required")


def conv_flops(cout: int, k: int, cin: int, hw: int) -> float:
    """卷积层计算量(MFLOPs): cout*k*k*cin*hw*hw."""
    return cout * k * k * cin * hw * hw / 1e6


def conv_bytes(cout: int, hw: int) -> int:
    """卷积层输出激活大小(字节, fp32)."""
    return cout * hw * hw * 4


def _add_conv(dag, nid, name, cout, k, cin, hw):
    dag.add_node(LayerNode(nid, name, conv_flops(cout, k, cin, hw), conv_bytes(cout, hw)))
    return nid


def _add_pool(dag, nid, name, cout, hw_out):
    """stride-2 池化层: 计算量可忽略, 激活尺寸减半(天然的低通信切分点)."""
    dag.add_node(LayerNode(nid, name, 0.0, conv_bytes(cout, hw_out)))
    return nid


def googlenet_like_dag() -> ModelDAG:
    """构建类 GoogleNet 的深度神经网络 DAG(224x224 输入, 约0.75 GFLOPs).

    结构: 卷积主干(含 stride-2 池化) -> 3 个 Inception 模块(每个含 4 条
    并行分支, 体现细粒度并行性, 模块间以池化层衔接) -> 全局平均池化 ->
    全连接层。池化层输出激活较小, 是协同推理的自然切分点。
    """
    dag = ModelDAG()
    nid = 0

    # ---- stem ----
    s1 = _add_conv(dag, nid, "conv1_7x7_s2", 64, 7, 3, 112); nid += 1
    p1 = _add_pool(dag, nid, "pool1_3x3_s2", 64, 56); nid += 1
    s2 = _add_conv(dag, nid, "conv2_3x3_reduce", 64, 1, 64, 56); nid += 1
    s3 = _add_conv(dag, nid, "conv2_3x3", 192, 3, 64, 56); nid += 1
    p2 = _add_pool(dag, nid, "pool2_3x3_s2", 192, 28); nid += 1
    dag.add_edge(s1, p1); dag.add_edge(p1, s2); dag.add_edge(s2, s3); dag.add_edge(s3, p2)
    prev = p2

    # ---- inception modules (parallel branches -> fine-grained DAG) ----
    inc_specs = [
        # (in_ch, hw, b1_1x1, b3_reduce, b3_3x3, b5_reduce, b5_5x5, pool_proj)
        (192, 28, 64, 96, 128, 16, 32, 32),
        (256, 14, 128, 128, 192, 32, 96, 64),
        (480, 7, 192, 96, 208, 16, 48, 64),
    ]
    for m, (cin, hw, b1, b3r, b3, b5r, b5, pp) in enumerate(inc_specs, start=1):
        branch_heads = []
        b1_n = _add_conv(dag, nid, f"inc{m}_1x1", b1, 1, cin, hw); nid += 1
        branch_heads.append(b1_n)
        b3r_n = _add_conv(dag, nid, f"inc{m}_3x3_reduce", b3r, 1, cin, hw); nid += 1
        b3_n = _add_conv(dag, nid, f"inc{m}_3x3", b3, 3, b3r, hw); nid += 1
        dag.add_edge(b3r_n, b3_n)
        branch_heads.append(b3r_n)
        b5r_n = _add_conv(dag, nid, f"inc{m}_5x5_reduce", b5r, 1, cin, hw); nid += 1
        b5_n = _add_conv(dag, nid, f"inc{m}_5x5", b5, 5, b5r, hw); nid += 1
        dag.add_edge(b5r_n, b5_n)
        branch_heads.append(b5r_n)
        pp_n = _add_conv(dag, nid, f"inc{m}_pool_proj", pp, 1, cin, hw); nid += 1
        branch_heads.append(pp_n)
        for bh in branch_heads:
            dag.add_edge(prev, bh)
        cat = nid; nid += 1
        # concat 仅聚合, 计算量置0; 输出为各分支激活之和
        dag.add_node(LayerNode(cat, f"inc{m}_concat", 0.0,
                               sum(dag.nodes[b].out_bytes for b in branch_heads)))
        for bh in branch_heads:
            dag.add_edge(bh, cat)
        prev = cat
        if m < len(inc_specs):
            pl = _add_pool(dag, nid, f"pool{m + 2}_3x3_s2", dag.nodes[cat].out_bytes // (4 * 4), hw // 2)
            nid += 1
            # 池化输出通道与 concat 一致
            dag.nodes[pl] = LayerNode(pl, f"pool{m + 2}_3x3_s2", 0.0,
                                      cout_bytes_for(cin_total(dag, cat), hw // 2))
            dag.add_edge(cat, pl)
            prev = pl

    # ---- head ----
    gap = nid; nid += 1
    dag.add_node(LayerNode(gap, "global_avg_pool", 0.0, 2048))
    dag.add_edge(prev, gap)
    fc = dag.add_node(LayerNode(nid, "fc", 512 * 1000 / 1e6, 4000))
    dag.add_edge(gap, fc)
    return dag


def cin_total(dag, cat_id):
    return dag.nodes[cat_id].out_bytes // (4 * 49)  # 依据 concat 输出反推通道数(7x7)


def cout_bytes_for(cout, hw):
    return cout * hw * hw * 4


@dataclass
class ModelDAG:
    """神经网络 DAG 图.

    Attributes:
        nodes: {node_id -> LayerNode}
        succ:  {node_id -> set(后继节点)}
        pred:  {node_id -> set(前驱节点)}
        edge_bytes: {(u, v) -> 激活传输字节}
    """

    nodes: dict = field(default_factory=dict)
    succ: dict = field(default_factory=lambda: {})
    pred: dict = field(default_factory=lambda: {})
    edge_bytes: dict = field(default_factory=lambda: {})

    def add_node(self, node: LayerNode) -> int:
        self.nodes[node.id] = node
        self.succ.setdefault(node.id, set())
        self.pred.setdefault(node.id, set())
        return node.id

    def add_edge(self, u: int, v: int, bytes_: int | None = None):
        assert u in self.nodes and v in self.nodes
        self.succ[u].add(v)
        self.pred[v].add(u)
        b = bytes_ if bytes_ is not None else self.nodes[u].out_bytes
        self.edge_bytes[(u, v)] = b

    # ------------------------------------------------------------------
    def topo_order(self) -> list[int]:
        """Kahn 拓扑排序(稳定: 同层按 id 升序)."""
        indeg = {v: len(self.pred[v]) for v in self.nodes}
        order, queue = [], sorted(v for v in self.nodes if indeg[v] == 0)
        while queue:
            u = queue.pop(0)
            order.append(u)
            for v in sorted(self.succ[u]):
                indeg[v] -= 1
                if indeg[v] == 0:
                    queue.append(v)
            queue.sort(key=lambda x: self.nodes[x].id)
        assert len(order) == len(self.nodes), "graph has a cycle"
        return order

    def total_flops(self) -> float:
        return sum(n.flops_mflops for n in self.nodes.values())

    def depth_of(self) -> dict[int, int]:
        """节点深度(最长路径边数), 用于关键路径分析."""
        depth = {}
        for u in self.topo_order():
            depth[u] = 0 if not self.pred[u] else 1 + max(depth[p] for p in self.pred[u])
        return depth

    def summary(self) -> str:
        return (f"ModelDAG(nodes={len(self.nodes)}, edges={len(self.edge_bytes)}, "
                f"total_flops={self.total_flops():.1f} MFLOPs)")
