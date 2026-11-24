# -*- coding: utf-8 -*-
"""任务管理模块: 协同推理任务的划分、分配、执行与结果共识.

对应任务书研究内容四中的任务管理模块: 接收深度学习推理任务后,
1) 依据资源聚合模块提供的算力视图, 调用细粒度 DAG 图划分算法
   (能力增强传播链 + 路径回溯优化)生成跨机器人划分方案;
2) 将子任务分配至各机器人并行执行(推理延迟按异构延迟模型仿真);
3) 各机器人执行结果经共同认知模块上链共识, 形成一致的最终输出。
"""
from __future__ import annotations

import numpy as np

from swarm_collab.dag import (ModelDAG, evaluate, partition_path_backtracking,
                              partition_propagation_chain)
from .cognition import SwarmCognition
from .resource_pool import ResourcePool


class TaskManager:
    """集群任务管理器."""

    def __init__(self, pool: ResourcePool, cognition: SwarmCognition, seed: int = 0):
        self.pool = pool
        self.cognition = cognition
        self.rng = np.random.default_rng(seed)

    # ------------------------------------------------------------------
    def plan_inference(self, dag: ModelDAG) -> dict:
        """阶段1: 资源聚合视图上的细粒度 DAG 划分(算法1 + 算法2)."""
        fleet = self.pool.to_fleet()
        plan = partition_propagation_chain(dag, fleet)
        plan = partition_path_backtracking(dag, fleet, plan)
        return {"assignment": plan, "evaluation": evaluate(dag, plan, fleet)}

    # ------------------------------------------------------------------
    def execute_inference(self, dag: ModelDAG, plan: dict) -> dict:
        """阶段2: 各机器人并行执行所分配的子任务(延迟仿真), 生成结果事件."""
        assignment = plan["assignment"]
        fleet = self.pool.to_fleet()
        exec_log = {}
        for r in fleet.ids():
            nodes = [n for n, rr in assignment.items() if rr == r]
            compute_ms = sum(dag.nodes[n].flops_mflops / fleet.gflops(r) for n in nodes)
            exec_log[r] = {"layers": len(nodes),
                           "compute_ms": round(compute_ms, 2),
                           "outputs": [f"out-{n}" for n in sorted(nodes)]}
        return {"exec_log": exec_log,
                "makespan_ms": round(max(v["compute_ms"] for v in exec_log.values()), 2)}

    # ------------------------------------------------------------------
    def consensus_on_results(self, exec_result: dict, max_rounds: int = 300) -> dict:
        """阶段3: 执行结果事件经 Hashgraph 共识形成共同认知."""
        expected = []
        for r, log in exec_result["exec_log"].items():
            for out in log["outputs"]:
                eid = self.cognition.make_event_id(f"r{r}")
                self.cognition.submit(r, eid)
                expected.append(eid)
        return self.cognition.run_until_consensus(expected, max_rounds=max_rounds)

    # ------------------------------------------------------------------
    def run_inference_task(self, dag: ModelDAG, max_rounds: int = 300) -> dict:
        """端到端: 资源聚合 -> DAG 划分 -> 并行执行 -> 结果共识."""
        plan = self.plan_inference(dag)
        exec_result = self.execute_inference(dag, plan)
        consensus = self.consensus_on_results(exec_result, max_rounds=max_rounds)
        return {**plan, **exec_result, "consensus": consensus}
