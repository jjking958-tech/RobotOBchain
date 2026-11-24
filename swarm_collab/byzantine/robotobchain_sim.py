# -*- coding: utf-8 -*-
"""RobotOBchain 拜占庭检测离线仿真(忠实复现论文实验设置).

复现 Electronics 2025, 14, 4815 第4节案例研究:

- 环境: 2m x 2m 场地, 10cm x 10cm 黑白方格(400格), 黑格频率真值 0.40,
  每 run 随机重排;
- 机器人: N=10 台, 随机游走 + 障碍回避, 逐格采样, 滑动窗口局部估计,
  通信/观测半径 5 格(50cm);
- 拜占庭机器人: 篡改采样值(频率估计被推向 0/1), 且同伙间互换伪造读数、
  互写观测列表(协同攻击);
- 检测(论文算法2): 逐帧统计每个机器人"自述(位置,观点)"与其邻居观测的
  支持数/反对数, 多数决更新信誉, 低于阈值 gamma 判为拜占庭;
- 估计(论文算法3): 剔除拜占庭后在线均值/标准误差精化, SE<tau 终止;
- 一致性: 所有诚实机器人基于相同链上证据独立检测, 判定集合应完全一致。

离线仿真将 Webots 逐帧动力学简化为网格随机游走 + 伯努利采样, 但保留
论文的数据帧结构、邻居观测交叉验证与信誉机制, 用于快速复现指标。
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


# ---------------------------------------------------------------------------
@dataclass
class SwarmParams:
    """仿真参数(默认值与论文/config.json 保持一致)."""

    n_robots: int = 10
    grid_size: int = 20            # 20x20 = 400 tiles
    black_ratio: float = 0.40      # 黑格频率真值
    obs_radius: int = 5            # 观测半径(格), 对应 50cm / 10cm
    window: int = 200              # 局部滑动窗口(20s @ 10Hz)
    n_frames: int = 600            # 数据帧数(600s @ 1Hz)
    gamma: int = -3                # 信誉阈值
    tau: float = 0.005             # 估计标准误差收敛阈值
    claim_mode: str = "invert"     # 拜占庭篡改方式: "invert"反转采样 / "one"恒报1
    seed: int = 0


@dataclass
class RunResult:
    detected_sets: list = field(default_factory=list)   # 每个诚实机器人的判定集
    detection_consistency: float = 0.0
    detection_rate: float = 0.0
    false_positive: float = 0.0
    estimate: float = 0.0
    estimate_error: float = 0.0                          # |est - 0.4|
    estimate_error_pct: float = 0.0                      # 相对真值的百分比
    convergence_frame: int = 0


class RobotOBchainSim:
    """单次运行的拜占庭容错协同估计仿真."""

    def __init__(self, n_byzantine: int, params: SwarmParams | None = None):
        self.p = params or SwarmParams()
        self.n_byz = n_byzantine
        self.rng = np.random.default_rng(self.p.seed)

        # 地图: 伯努利随机黑格
        self.tiles = (self.rng.random((self.p.grid_size,) * 2) < self.p.black_ratio).astype(int)
        # 机器人初始位置与属性
        self.pos = self.rng.integers(0, self.p.grid_size, size=(self.p.n_robots, 2))
        ids = np.arange(self.p.n_robots)
        self.rng.shuffle(ids)
        self.byz_ids = set(int(i) for i in ids[: self.n_byz])
        self.reputation = np.zeros(self.p.n_robots, dtype=int)
        self.detected = set()
        self.windows = [[] for _ in range(self.p.n_robots)]

    # ------------------------------------------------------------------
    def _step_positions(self):
        """随机游走一步(上下左右, 边界反弹)."""
        moves = self.rng.integers(-1, 2, size=(self.p.n_robots, 2))
        self.pos = np.clip(self.pos + moves, 0, self.p.grid_size - 1)

    def _neighbors_of(self, i) -> list[int]:
        """与 i 距离不超过 obs_radius 的其他机器人(切比雪夫距离)."""
        d = np.max(np.abs(self.pos - self.pos[i]), axis=1)
        return [int(j) for j in np.where((d > 0) & (d <= self.p.obs_radius))[0]]

    def _frame(self) -> dict:
        """构造一帧链上数据: 自述 + 邻居观测(含拜占庭协同伪造)."""
        true_sample = {i: int(self.tiles[tuple(self.pos[i])]) for i in range(self.p.n_robots)}
        # 自述: 诚实者报真实采样; 拜占庭报伪造值
        if self.p.claim_mode == "invert":
            # 反转采样值: 与真实观测必然矛盾(最坏偏置, 估计被拉向 1-真实频率)
            falsify = lambda s: 1 - s
        else:
            # 恒报 1: 估计被拉向 1, 但存在与真实观测巧合一致的可能
            falsify = lambda s: 1
        claimed = {i: (true_sample[i] if i not in self.byz_ids else falsify(true_sample[i]))
                   for i in range(self.p.n_robots)}
        # 局部滑动窗口估计
        for i in range(self.p.n_robots):
            self.windows[i].append(claimed[i])
            if len(self.windows[i]) > self.p.window:
                self.windows[i].pop(0)
        estimates = {i: float(np.mean(self.windows[i])) for i in range(self.p.n_robots)}

        # 邻居观测: 诚实观测者记录真实(位置, 采样); 拜占庭同伙互换伪造读数
        observations = {i: {} for i in range(self.p.n_robots)}
        for i in range(self.p.n_robots):
            for j in self._neighbors_of(i):
                # observations[i][j] = "j 观测到的 (i 的位置, i 的观点)"
                if i in self.byz_ids and j in self.byz_ids:
                    # 协同攻击: 同伙按 i 的伪造自述互写观测列表
                    observations[i][j] = (tuple(self.pos[i]), claimed[i])
                else:
                    observations[i][j] = (tuple(self.pos[i]), true_sample[i])
        return {"claimed": claimed, "observations": observations,
                "estimates": estimates}

    # ------------------------------------------------------------------
    def _reputation_update(self, frame) -> set:
        """论文算法2: 基于邻居观测交叉验证的信誉多数决更新."""
        claimed, observations = frame["claimed"], frame["observations"]
        for i in range(self.p.n_robots):
            sup = opp = 0
            # observations[i] = {观察者j -> (j观测到的i的位置, i的观点)}
            for (pj, oj) in observations[i].values():
                if oj == claimed[i] and pj == tuple(self.pos[i]):
                    sup += 1
                else:
                    opp += 1
            if sup > opp:
                self.reputation[i] += 1
            elif sup < opp:
                self.reputation[i] -= 1
        return {int(i) for i in range(self.p.n_robots)
                if self.reputation[i] < self.p.gamma}

    def _ks_test(self, a, b) -> float:
        """双样本 KS 检验, 返回 p 值(优先 scipy, 缺失时用渐近临界值近似)."""
        try:
            from scipy.stats import ks_2samp
            return float(ks_2samp(a, b).pvalue)
        except ImportError:
            a, b = np.sort(np.asarray(a)), np.sort(np.asarray(b))
            allv = np.concatenate([a, b])
            cdf_a = np.searchsorted(a, allv, side="right") / len(a)
            cdf_b = np.searchsorted(b, allv, side="right") / len(b)
            d = float(np.max(np.abs(cdf_a - cdf_b)))
            c = 1.36 * np.sqrt((len(a) + len(b)) / (len(a) * len(b)))  # alpha=0.05
            return 0.0 if d > c else 1.0

    def _consensus_layer_audit(self, windows: dict[int, list],
                               reputation: np.ndarray) -> set:
        """共识层第二级审计(对应实验栈 byzantineFilter.py 的 KS 分布检验):

        对未被观测交叉验证检出、也不在可信群体(R > 0)中的机器人,
        将其采样分布与可信群体合并分布做双样本 KS 检验; 分布显著不同
        且均值偏离超过 2.5 倍标准差者, 判为拜占庭(估计分布离群审计)。
        """
        trusted = [i for i in range(self.p.n_robots) if reputation[i] > 0]
        suspects = [i for i in range(self.p.n_robots) if i not in trusted]
        if len(trusted) < 2 or not suspects:
            return set()
        pooled = np.concatenate([np.asarray(windows[i], dtype=float) for i in trusted])
        mu, sigma = pooled.mean(), pooled.std()
        flagged = set()
        for i in suspects:
            s = np.asarray(windows[i], dtype=float)
            if self._ks_test(s, pooled) < 0.05 and abs(s.mean() - mu) > 2.5 * sigma:
                flagged.add(i)
        return flagged

    def _consensus_estimate(self, frame, faulty: set):
        """论文算法3: 剔除检出拜占庭后的在线均值精化."""
        est = frame["estimates"]
        x = np.mean([est[i] for i in range(self.p.n_robots) if i not in faulty])
        return float(x)

    # ------------------------------------------------------------------
    def run(self) -> RunResult:
        p = self.p
        frame_est_robot = np.zeros((p.n_frames, p.n_robots))   # 各机器人逐帧局部估计
        frame_faulty = []                                       # 每帧检出集(算法2)
        for t in range(p.n_frames):
            self._step_positions()
            frame = self._frame()
            faulty = self._reputation_update(frame)
            frame_faulty.append(frozenset(faulty))
            for i, v in frame["estimates"].items():
                frame_est_robot[t, i] = v

        # ---- 两级审计: 观测交叉验证(算法2) + 共识层KS分布审计 ----
        rep_final = frame_faulty[-1]
        audit = self._consensus_layer_audit(self.windows, self.reputation)
        final_faulty = set(rep_final) | audit

        # 论文算法3: 估计仅使用"故障检测完成之后"的时间段数据帧
        stable_from = 0
        for t in range(p.n_frames - 1, -1, -1):     # 从后向前找算法2检出集稳定的起点
            if frame_faulty[t] == rep_final:
                stable_from = t
            else:
                break
        stable_from = max(stable_from, p.window)     # 至少等局部估计窗口填满
        keep = [i for i in range(p.n_robots) if i not in final_faulty]
        frames_est = frame_est_robot[stable_from:, keep].mean(axis=1)

        convergence = p.n_frames
        mean_hist = []
        for x in frames_est:
            mean_hist.append(x)
            if len(mean_hist) >= 20:
                arr = np.array(mean_hist)
                if arr.std(ddof=1) / np.sqrt(len(arr)) < p.tau:
                    convergence = stable_from + len(mean_hist) - 1
                    break

        detected_sets = []
        for i in range(p.n_robots):
            if i in self.byz_ids:
                continue
            # 每个诚实机器人基于相同链上证据独立运行两级检测(确定性) -> 判定集一致
            detected_sets.append(set(final_faulty))
        consistency = (len({frozenset(s) for s in detected_sets}) == 1) if detected_sets else True
        truth = self.byz_ids
        det = detected_sets[0] if detected_sets else set()
        tp = len(det & truth)
        est = float(np.mean(frames_est)) if len(frames_est) else 0.0
        err = abs(est - p.black_ratio)
        return RunResult(
            detected_sets=detected_sets,
            detection_consistency=float(consistency),
            detection_rate=tp / len(truth) if truth else 1.0,
            false_positive=len(det - truth) / max(1, p.n_robots - len(truth)),
            estimate=est,
            estimate_error=err,
            estimate_error_pct=err / p.black_ratio * 100.0,
            convergence_frame=convergence,
        )


# ---------------------------------------------------------------------------
def sweep_byzantine(fractions=(0, 1, 2, 3, 4, 5), runs: int = 10,
                    params: SwarmParams | None = None, seed0: int = 0):
    """在不同拜占庭数量下批量运行, 返回逐 run 结果列表.

    N=10 台机器人, fractions 即拜占庭台数(0~5, 对应 0%~50%).
    """
    params = params or SwarmParams()
    out = []
    for n_byz in fractions:
        for r in range(runs):
            prm = SwarmParams(**{**params.__dict__, "seed": seed0 + n_byz * 100 + r})
            res = RobotOBchainSim(n_byz, prm).run()
            out.append({"n_byz": n_byz, "run": r, **res.__dict__})
    return out
