# -*- coding: utf-8 -*-
"""多机器人自组织协同框架原型: 端到端演示.

场景(对应任务书四大研究内容的集成验证):
1. 资源聚合: 5 台异构无人机加入集群并上报算力画像;
2. 协同推理: 集群协同执行一次类 GoogLeNet 视觉推理任务
   (细粒度 DAG 划分 -> 并行执行 -> 结果事件上链共识);
3. 共同认知与容错: 无人机群协同估计环境黑格频率(模拟灾害现场表决),
   其中 2 台为拜占庭机器人(篡改采样), 经邻居观测交叉验证 + 共识层
   KS 分布审计双层检测后剔除, 集群收敛到准确估计。

运行: python swarm_collab/framework/demo.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from swarm_collab.byzantine import RobotOBchainSim, SwarmParams
from swarm_collab.dag import googlenet_like_dag
from swarm_collab.framework import ResourcePool, SwarmCognition, TaskManager


def main():
    print("=" * 64)
    print("多机器人自组织协同框架原型演示 (项目 25XJ03014)")
    print("=" * 64)

    # ---------- 1. 资源聚合 ----------
    pool = ResourcePool(bandwidth_mbps=1000.0)
    for rid, gf in [(0, 2.0), (1, 4.0), (2, 8.0), (3, 16.0), (4, 32.0)]:
        pool.register(rid, gf)
    print("\n[1] 资源聚合:", pool.summary())

    # ---------- 2. 协同推理(DAG 划分 -> 执行 -> 共识) ----------
    dag = googlenet_like_dag()
    print("\n[2] 协同推理任务:", dag.summary())
    cognition = SwarmCognition(pool.ids(), seed=0)
    tm = TaskManager(pool, cognition, seed=0)
    result = tm.run_inference_task(dag)
    ev = result["evaluation"]
    print(f"    划分方案: {result['assignment']}")
    print(f"    makespan = {ev['makespan']:.1f} ms (跨机器人切边 {ev['cut_edges']} 条)")
    for r, log in result["exec_log"].items():
        print(f"    robot{r}: {log['layers']} 层, 计算 {log['compute_ms']} ms")
    cons = result["consensus"]
    print(f"    结果共识: {len(cons['order'])} 个结果事件, "
          f"第 {cons['rounds']} 轮达成, 平均时延 {cons['latency']:.1f} 轮")

    # ---------- 3. 共同认知 + 拜占庭容错(协同环境估计) ----------
    print("\n[3] 协同环境估计(含 2 台拜占庭机器人):")
    sim = RobotOBchainSim(2, SwarmParams(seed=7))
    res = sim.run()
    detected = sorted(res.detected_sets[0]) if res.detected_sets else []
    print(f"    预设拜占庭: {sorted(sim.byz_ids)}")
    print(f"    链上两级审计检出: {detected} (一致性 {res.detection_consistency:.0%}, "
          f"误报 {res.false_positive:.0%})")
    print(f"    剔除后集群估计: {res.estimate:.4f} (真值 0.40, 误差 {res.estimate_error_pct:.2f}%)")

    # ---------- 保存演示记录 ----------
    out = Path(__file__).resolve().parents[2] / "results" / "demo_result.json"
    out.parent.mkdir(exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({
            "inference": {"makespan_ms": ev["makespan"],
                          "cut_edges": ev["cut_edges"],
                          "assignment": {str(k): int(v) for k, v in result["assignment"].items()},
                          "consensus_rounds": cons["rounds"]},
            "estimation": {"byz_truth": sorted(sim.byz_ids),
                           "detected": detected,
                           "estimate": res.estimate,
                           "error_pct": res.estimate_error_pct},
        }, f, ensure_ascii=False, indent=2)
    print(f"\n演示记录已保存: {out}")


if __name__ == "__main__":
    main()
