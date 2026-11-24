# -*- coding: utf-8 -*-
"""算法2: 基于路径回溯的模型划分优化算法.

思想(对应任务书研究内容一): 在能力增强传播链算法给出的粗粒度划分基础上,
沿 DAG 的关键路径(critical path)**回溯**:

1. 找到当前 makespan 瓶颈机器人及其承担的关键路径层;
2. 从瓶颈层出发沿前驱方向回溯, 枚举关键路径上的可重切分点;
3. 遇到高性能节点(算力充裕的空闲机器人)时, 重新评估并优化划分方案:
   将关键层(或其所在的 Inception 并行分支)迁移至空闲算力, 降低瓶颈负载;
4. 迭代直至无改进或达到最大迭代次数。

与算法1配合, 实现细粒度(单层/单分支粒度)的模型划分优化。
"""
from __future__ import annotations

from .model_dag import ModelDAG
from .planner import Fleet, evaluate


def _critical_path(dag: ModelDAG, assignment: dict, fleet: Fleet) -> list[int]:
    """按延迟模型求全局最长(关键)路径: 权重 = 计算延迟 + 首个跨段传输延迟."""
    order = dag.topo_order()
    weight = {}
    for u in order:
        w = dag.nodes[u].flops_mflops / fleet.gflops(assignment[u])
        preds = dag.pred[u]
        if preds:
            best_p, best_acc = None, -1.0
            for p in preds:
                acc = weight[p][0]
                e = dag.edge_bytes[(p, u)]
                if assignment[p] != assignment[u]:
                    from .planner import transmit_ms
                    from .planner import Fleet as _F  # noqa
                    acc += _edge_ms(dag, assignment, fleet, p, u)
                if acc > best_acc:
                    best_p, best_acc = p, acc
            weight[u] = (best_acc + w, best_p)
        else:
            weight[u] = (w, None)
    # 回溯关键路径
    end = max(order, key=lambda u: weight[u][0])
    path = []
    cur = end
    while cur is not None:
        path.append(cur)
        cur = weight[cur][1]
    return list(reversed(path))


def _edge_ms(dag, assignment, fleet, u, v) -> float:
    from .planner import transmit_ms
    ru, rv = assignment[u], assignment[v]
    if ru == rv:
        return 0.0
    return transmit_ms(dag.edge_bytes[(u, v)], fleet.bw(ru, rv))


def _branch_groups(dag: ModelDAG) -> dict[int, int]:
    """识别并行分支: fork 节点的每个直接后继作为分支组 id(细粒度迁移单位)."""
    group = {}
    gid = 0
    for u in dag.topo_order():
        succs = sorted(dag.succ[u])
        if len(succs) > 1:
            for s in succs:
                # 分支头及其直到 merge 的链上节点归入同一分支组
                cur, seen = s, set()
                while cur not in seen:
                    seen.add(cur)
                    group.setdefault(cur, gid)
                    nxt = [v for v in dag.succ[cur] if len(dag.pred[v]) == 1]
                    if len(nxt) == 1 and len(dag.succ[cur]) == 1:
                        cur = nxt[0]
                    else:
                        break
                gid += 1
    return group


def partition_path_backtracking(dag: ModelDAG, fleet: Fleet,
                                assignment: dict[int, int],
                                max_iter: int = 30,
                                verbose: bool = False) -> dict[int, int]:
    """路径回溯优化: 在给定划分上迭代回溯关键路径并重切分.

    Args:
        dag: 神经网络 DAG.
        fleet: 编队.
        assignment: 初始划分(通常来自算法1).
        max_iter: 最大迭代次数.
        verbose: 打印每轮信息.

    Returns:
        优化后的划分方案 {node_id -> robot_id}.
    """
    assignment = dict(assignment)
    branch = _branch_groups(dag)
    best = evaluate(dag, assignment, fleet)["makespan"]

    for it in range(max_iter):
        ev = evaluate(dag, assignment, fleet)
        bottleneck = max(ev["loads"], key=ev["loads"].get)
        path = _critical_path(dag, assignment, fleet)
        # 关键路径上属于瓶颈机器人的层(回溯起点)
        critical_mine = [n for n in path if assignment[n] == bottleneck]
        if not critical_mine:
            break
        # 空闲机器人(按剩余算力排序的高性能节点)
        idle = [r for r in fleet.ids()
                if r != bottleneck and ev["loads"][r] < 0.7 * ev["makespan"]]
        idle.sort(key=lambda r: -(fleet.gflops(r) - ev["loads"][r]))
        if not idle:
            break

        # 沿关键路径回溯: 对回溯路径上的每个瓶颈层, 试探迁移到空闲高性能机器人
        best_move, best_mk = None, best
        for n in reversed(critical_mine):
            group = branch.get(n)
            nodes = ([x for x, g in branch.items() if g == group]
                     if group is not None else [n])
            for r in idle[:3]:                      # 仅考虑前3个空闲高性能节点
                trial = dict(assignment)
                for x in nodes:
                    trial[x] = r
                mk = evaluate(dag, trial, fleet)["makespan"]
                if mk < best_mk - 1e-9:
                    best_move, best_mk = (nodes, r), mk

        if best_move is None:
            break
        nodes, target = best_move
        for x in nodes:
            assignment[x] = target
        best = best_mk
        if verbose:
            print(f"[path_backtracking] iter {it + 1}: moved {len(nodes)} layer(s) "
                  f"-> robot {target}, makespan={best:.2f} ms")

    return assignment
