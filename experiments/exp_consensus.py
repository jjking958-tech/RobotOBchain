# -*- coding: utf-8 -*-
"""实验2: Hashgraph 共识收敛与公平排序.

度量不同集群规模下, 全体节点就全部交易达成公平排序共识所需的
gossip 轮次与平均共识时延(事件产生到定序的轮次差)。

输出: results/exp_consensus.csv, results/exp_consensus.png
运行: python experiments/exp_consensus.py
"""
import csv
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from swarm_collab.consensus import GossipSwarm

OUT = Path(__file__).resolve().parents[1] / "results"


def run_once(n_nodes: int, seed: int, max_rounds: int = 500):
    rng = random.Random(seed)
    swarm = GossipSwarm(range(n_nodes), link=None)
    txs = [f"tx{i}" for i in range(n_nodes)]
    for i, tx in enumerate(txs):
        swarm.broadcast(i, tx)
    t0 = time.time()
    for _ in range(max_rounds):
        swarm.gossip_round(swarm.all_pairs_random(rng))
        if swarm.consensus_reached(txs) and swarm.all_equal():
            lat = [n.ordered_round[h] - n.event_round[h]
                   for n in swarm.nodes.values() for h in n.ordered_round if n.hg[h].d]
            return {"n_nodes": n_nodes, "seed": seed, "converged": True,
                    "rounds": swarm.round,
                    "latency_rounds": round(sum(lat) / len(lat), 2),
                    "events_per_node": len(swarm.nodes[0].hg),
                    "seconds": round(time.time() - t0, 2)}
    return {"n_nodes": n_nodes, "seed": seed, "converged": False,
            "rounds": max_rounds, "latency_rounds": None,
            "events_per_node": len(swarm.nodes[0].hg),
            "seconds": round(time.time() - t0, 2)}


def main():
    OUT.mkdir(exist_ok=True)
    rows = []
    for n in (4, 6, 8, 10, 12):
        seeds = (0, 1) if n >= 12 else (0, 1, 2)
        for seed in seeds:
            res = run_once(n, seed)
            rows.append(res)
            print(res)
    with open(OUT / "exp_consensus.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"saved: {OUT / 'exp_consensus.csv'}")

    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ns = sorted({r["n_nodes"] for r in rows})
    means = [np.mean([r["rounds"] for r in rows if r["n_nodes"] == nn]) for nn in ns]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(ns, means, "o-")
    ax.set_xlabel("swarm size (nodes)")
    ax.set_ylabel("gossip rounds to global fair consensus")
    ax.set_title("Hashgraph consensus convergence (1 tx per node)")
    fig.tight_layout()
    fig.savefig(OUT / "exp_consensus.png", dpi=150)
    print(f"saved: {OUT / 'exp_consensus.png'}")


if __name__ == "__main__":
    main()
