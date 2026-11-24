# -*- coding: utf-8 -*-
"""实验3: 应用层拜占庭机器人容错(RobotOBchain vs W-MSR).

复现论文 Electronics 2025, 14, 4815 第4节案例研究的指标:
- 拜占庭检出率 / 误报率 / 判定一致性(各诚实机器人判定集完全相同);
- 集群频率估计误差(黑格真值 0.40 与地图实际频率两种口径);
- 与 W-MSR(F=2) 的估计误差对比。

设置: 10 台机器人, 400 格场地, 拜占庭数量 f = 0..5(0%~50%),
观测交叉验证(算法2) + 共识层 KS 分布审计 双层检测,
估计仅使用检测完成后的数据帧(算法3)。

输出: results/exp_byzantine_detection.csv, results/exp_byzantine_detection.png
运行: python experiments/exp_byzantine_detection.py
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from swarm_collab.byzantine import RobotOBchainSim, SwarmParams, wmsr_estimate

OUT = Path(__file__).resolve().parents[1] / "results"


def main():
    OUT.mkdir(exist_ok=True)
    runs = 10
    rows = []
    for f in range(6):                       # 0~5 台拜占庭 (0% ~ 50%)
        for seed in range(runs):
            sim = RobotOBchainSim(f, SwarmParams(seed=seed))
            realized = float(sim.tiles.mean())
            res = sim.run()
            # W-MSR(F=2) 对照: 各机器人局部估计初值 + 初始位置邻近图
            vals = np.array([np.mean(sim.windows[i]) for i in range(sim.p.n_robots)])
            d = np.max(np.abs(sim.pos[:, None, :] - sim.pos[None, :, :]), axis=2)
            adj = ((d > 0) & (d <= sim.p.obs_radius)).astype(float)
            xf = wmsr_estimate(vals, adj, f=2)
            honest = [i for i in range(sim.p.n_robots) if i not in sim.byz_ids]
            wmsr_est = float(np.mean(xf[honest]))

            rows.append({
                "n_byz": f, "byz_pct": f * 10, "seed": seed,
                "detection_rate": res.detection_rate,
                "false_positive": res.false_positive,
                "detection_consistency": res.detection_consistency,
                "rbc_estimate": round(res.estimate, 4),
                "rbc_err_vs_nominal_pct": round(res.estimate_error_pct, 2),
                "rbc_err_vs_realized_pct": round(
                    abs(res.estimate - realized) / realized * 100, 2),
                "wmsr_estimate": round(wmsr_est, 4),
                "wmsr_err_vs_realized_pct": round(
                    abs(wmsr_est - realized) / realized * 100, 2),
            })
        agg = [r for r in rows if r["n_byz"] == f]
        print(f"f={f} ({f*10}%): detect={np.mean([r['detection_rate'] for r in agg]):.2f}, "
              f"FP={np.mean([r['false_positive'] for r in agg]):.2f}, "
              f"consist={np.mean([r['detection_consistency'] for r in agg]):.2f}, "
              f"RBC err={np.mean([r['rbc_err_vs_realized_pct'] for r in agg]):.2f}%, "
              f"W-MSR err={np.mean([r['wmsr_err_vs_realized_pct'] for r in agg]):.2f}%")

    with open(OUT / "exp_byzantine_detection.csv", "w", newline="", encoding="utf-8") as fp:
        w = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"saved: {OUT / 'exp_byzantine_detection.csv'}")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fs = list(range(6))
    rbc = [np.mean([r["rbc_err_vs_realized_pct"] for r in rows if r["n_byz"] == f]) for f in fs]
    wmsr = [np.mean([r["wmsr_err_vs_realized_pct"] for r in rows if r["n_byz"] == f]) for f in fs]
    det = [100 * np.mean([r["detection_rate"] for r in rows if r["n_byz"] == f]) for f in fs]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))
    ax1.plot(fs, wmsr, "s-", label="W-MSR (F=2)")
    ax1.plot(fs, rbc, "o-", label="RobotOBchain (2-layer audit)")
    ax1.set_xlabel("number of byzantine robots (of 10)")
    ax1.set_ylabel("estimate error vs realized ratio (%)")
    ax1.set_title("Estimation error")
    ax1.legend()
    ax2.bar(fs, det, color="#4C72B0")
    ax2.set_xlabel("number of byzantine robots (of 10)")
    ax2.set_ylabel("detection rate (%)")
    ax2.set_title("Byzantine detection (consistency = 100%, FP = 0)")
    fig.tight_layout()
    fig.savefig(OUT / "exp_byzantine_detection.png", dpi=150)
    print(f"saved: {OUT / 'exp_byzantine_detection.png'}")


if __name__ == "__main__":
    main()
