# -*- coding: utf-8 -*-
"""实验4: "通信兵"机器人主动传播对共同认知收敛的影响.

场景: 3 个群体 x 4 台机器人, 群内链路畅通、群间断开(弱连接/拒止);
通信兵机器人按航线巡回驻留各群体, 与成员双向 gossip 同步, 在群体间
摆渡事件。度量全体交易达成公平排序共识所需轮次。

对比: 无通信兵 / 1 台(dwell=5,2) / 2 台(dwell=2)。

输出: results/exp_messenger.csv, results/exp_messenger.png
运行: python experiments/exp_messenger.py
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from swarm_collab.messenger import run_scenario

OUT = Path(__file__).resolve().parents[1] / "results"
CONFIGS = [(0, 3), (1, 5), (1, 2), (2, 2)]     # (通信兵数, 驻留轮数)


def main():
    OUT.mkdir(exist_ok=True)
    rows = []
    for n_m, dwell in CONFIGS:
        for seed in range(3):
            res = run_scenario(n_m, dwell, seed=seed)
            rows.append({"n_messengers": n_m, "dwell": dwell, "seed": seed,
                         "converged": res["converged"],
                         "convergence_rounds": res["convergence_rounds"]})
            print(f"messengers={n_m}, dwell={dwell}, seed={seed}: "
                  f"converged={res['converged']}, rounds={res['convergence_rounds']}")

    with open(OUT / "exp_messenger.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"saved: {OUT / 'exp_messenger.csv'}")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = [f"{m} messenger\ndwell={d}" for m, d in CONFIGS]
    means = [np.mean([r["convergence_rounds"] for r in rows
                      if r["n_messengers"] == m and r["dwell"] == d])
             for m, d in CONFIGS]
    fig, ax = plt.subplots(figsize=(6.5, 4))
    bars = ax.bar(labels, means, color=["#999999", "#4C72B0", "#4C72B0", "#DD8452"])
    ax.set_ylabel("gossip rounds to global consensus")
    ax.set_title("Messenger-robot active propagation (3 groups x 4 robots, inter-group links cut)")
    for b, v, m, d in zip(bars, means, [c[0] for c in CONFIGS], [c[1] for c in CONFIGS]):
        note = "never converges" if (m == 0) else ""
        ax.text(b.get_x() + b.get_width() / 2, v + 2,
                note or f"{v:.0f}", ha="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT / "exp_messenger.png", dpi=150)
    print(f"saved: {OUT / 'exp_messenger.png'}")


if __name__ == "__main__":
    main()
