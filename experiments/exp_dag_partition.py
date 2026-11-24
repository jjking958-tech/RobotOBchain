# -*- coding: utf-8 -*-
"""实验1: 细粒度 DAG 图划分算法对比.

对比方法:
- single        单机部署(全部层置于最强机器人, 无协同推理)
- round_robin   拓扑序轮转基线
- greedy        贪心基线
- chain         算法1: 能力增强传播链划分
- chain+bt      算法1 + 算法2(路径回溯优化)

场景: 4 机低算力编队(1/2/4/8 GFLOPS, CPU 级机载计算机)在不同
机间带宽下执行类 GoogLeNet 视觉推理任务(0.7 GFLOPs, 224x224)。

输出: results/exp_dag_partition.csv, results/exp_dag_partition.png
运行: python experiments/exp_dag_partition.py
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from swarm_collab.dag import (Fleet, ModelDAG, RobotProfile, evaluate,
                              googlenet_like_dag, partition_greedy,
                              partition_propagation_chain,
                              partition_path_backtracking,
                              partition_round_robin, partition_single)

OUT = Path(__file__).resolve().parents[1] / "results"


def main():
    OUT.mkdir(exist_ok=True)
    dag = googlenet_like_dag()
    print(dag.summary())
    rows = []
    for label, caps in (("fleet4-weak", [1, 2, 4, 8]), ("fleet5-mixed", [2, 4, 8, 16, 32])):
        for bw in (100, 250, 500, 1000):
            fleet = Fleet([RobotProfile(i, g) for i, g in enumerate(caps)])
            for u in range(len(caps)):
                for v in range(len(caps)):
                    if u != v:
                        fleet.set_bandwidth(u, v, bw)
            methods = {
                "single": partition_single(dag, fleet),
                "round_robin": partition_round_robin(dag, fleet),
                "greedy": partition_greedy(dag, fleet),
                "propagation_chain": partition_propagation_chain(dag, fleet),
            }
            methods["chain+backtracking"] = partition_path_backtracking(
                dag, fleet, methods["propagation_chain"])
            for name, a in methods.items():
                ev = evaluate(dag, a, fleet)
                rows.append({"fleet": label, "n_robots": len(caps), "bw_mbps": bw,
                             "method": name, "makespan_ms": round(ev["makespan"], 2),
                             "cut_edges": ev["cut_edges"],
                             "comm_ms": round(ev["comm_ms"], 2)})
                print(f"{label} @{bw}Mbps {name:20s} makespan={ev['makespan']:8.2f} ms "
                      f"cuts={ev['cut_edges']}")

    with open(OUT / "exp_dag_partition.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"saved: {OUT / 'exp_dag_partition.csv'}")

    # ---- 绘图: fleet4-weak 各带宽下方法对比 ----
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    sub = [r for r in rows if r["fleet"] == "fleet4-weak"]
    bws = sorted({r["bw_mbps"] for r in sub})
    methods = ["single", "round_robin", "greedy", "propagation_chain", "chain+backtracking"]
    x = range(len(bws))
    width = 0.15
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for k, m in enumerate(methods):
        vals = [next(r["makespan_ms"] for r in sub if r["bw_mbps"] == b and r["method"] == m)
                for b in bws]
        ax.bar([xx + (k - 2) * width for xx in x], vals, width, label=m)
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"{b} Mbps" for b in bws])
    ax.set_ylabel("inference makespan (ms)")
    ax.set_title("DAG collaborative inference: 4-robot weak fleet (GoogLeNet-like, 0.7 GFLOPs)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "exp_dag_partition.png", dpi=150)
    print(f"saved: {OUT / 'exp_dag_partition.png'}")


if __name__ == "__main__":
    main()
