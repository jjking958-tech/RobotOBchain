# -*- coding: utf-8 -*-
"""基于"通信兵"机器人的主动传播共同认知机制(离线仿真).

对应任务书研究内容二: 大范围开放环境下机器人活动分散、群体间网络连接
不畅, 引入移动能力强、通信能力强的"通信兵"机器人, 在群体间主动传递
消息, 加速一致视图收敛。

仿真设计:
- 集群划分为 G 个群体, 群内链路畅通, 群间链路断开(弱连接);
- 通信兵机器人按固定航线巡回访问各群体, 驻留 dwell 轮, 期间与群内
  成员执行 Hashgraph gossip 同步, 把上一群体的"事件包裹"摆渡过去;
- 度量: 全体交易达成公平排序共识所需的总轮次(收敛时间)。

通过 messenger_sim.run_scenario 可对比: 无通信兵(群间永不收敛)、
不同通信兵数量与驻留时长下的收敛速度, 为通信兵配置策略提供依据。
"""
from __future__ import annotations

from dataclasses import dataclass

from swarm_collab.consensus import GossipSwarm

import numpy as np


@dataclass
class MessengerConfig:
    n_groups: int = 3
    group_size: int = 4          # 每群体普通机器人数
    n_messengers: int = 1        # 通信兵数量
    dwell: int = 3               # 通信兵在每群体的驻留轮数
    max_rounds: int = 600        # 收敛判定上限
    seed: int = 0


class MessengerSim:
    """分组集群 + 通信兵摆渡的共同认知收敛仿真."""

    def __init__(self, cfg: MessengerConfig):
        self.cfg = cfg
        self.rng = np.random.default_rng(cfg.seed)
        n = cfg.n_groups * cfg.group_size
        self.robot_ids = list(range(n))
        self.messenger_ids = list(range(n, n + cfg.n_messengers))
        self.group_of = {i: i // cfg.group_size for i in self.robot_ids}
        # 构建全连通回调网络(通信能力具备), 群间可达性由 _apply_link 按轮门控
        self.swarm = GossipSwarm(self.robot_ids + self.messenger_ids, link=None)
        # 交易负载: 每个普通机器人 1 笔
        self.txs = [f"tx{i}" for i in self.robot_ids]
        for i, tx in zip(self.robot_ids, self.txs):
            self.swarm.broadcast(i, tx)

    def _apply_link(self, position: dict[int, int]):
        """按通信兵当前位置动态重设链路: 群内全连通, 群间断开."""
        link = {}
        for i in self.robot_ids:
            for j in self.robot_ids:
                if i != j and self.group_of[i] == self.group_of[j]:
                    link[(i, j)] = True
        for m in self.messenger_ids:
            g = position[m]
            for i in self.robot_ids:
                if self.group_of[i] == g:
                    link[(m, i)] = True
                    link[(i, m)] = True
        for a, b in zip(self.messenger_ids, self.messenger_ids[1:]):
            link[(a, b)] = link[(b, a)] = True
        self.swarm.link = link

    def run(self) -> dict:
        cfg = self.cfg
        # 通信兵初始分布于不同群体
        position = {m: k % cfg.n_groups for k, m in enumerate(self.messenger_ids)}
        countdown = {m: cfg.dwell for m in self.messenger_ids}
        rng = np.random.default_rng(cfg.seed + 1)

        reached = None
        for r in range(cfg.max_rounds):
            self._apply_link(position)
            # 群内常规 gossip: 每个成员与同群随机邻居同步一次
            pairs = []
            for g in range(cfg.n_groups):
                members = [i for i in self.robot_ids if self.group_of[i] == g]
                for i in members:
                    peers = [j for j in members if j != i]
                    if peers:
                        pairs.append((i, peers[int(rng.integers(len(peers)))]))
            # 通信兵与驻留群体成员双向同步(主动传播: 携带跨群事件包裹)
            for m in self.messenger_ids:
                members = [i for i in self.robot_ids if self.group_of[i] == position[m]]
                # 通信兵每轮向随机2个成员发起收集(模拟无线会合的真实开销)
                k = min(2, len(members))
                idx = rng.choice(len(members), size=k, replace=False)
                for idx_i in idx:
                    pairs.append((m, members[int(idx_i)]))
                for i in members:
                    pairs.append((i, m))    # 本群成员拉取通信兵携带的跨群事件
            # 通信兵之间相遇交换
            for a, b in zip(self.messenger_ids, self.messenger_ids[1:]):
                pairs.append((a, b))
            self.swarm.gossip_round(pairs)

            if reached is None and self.swarm.consensus_reached(self.txs) \
                    and self.swarm.all_equal():
                reached = r + 1
                break

            # 通信兵巡回: 驻留倒计时结束后前往下一群体
            for m in self.messenger_ids:
                countdown[m] -= 1
                if countdown[m] <= 0:
                    position[m] = (position[m] + 1) % cfg.n_groups
                    countdown[m] = cfg.dwell

        return {
            "n_messengers": cfg.n_messengers,
            "dwell": cfg.dwell,
            "converged": reached is not None,
            "convergence_rounds": reached if reached is not None else cfg.max_rounds,
            "events_per_node": len(self.swarm.nodes[self.robot_ids[0]].hg),
        }


def run_scenario(n_messengers: int, dwell: int, seed: int = 0,
                 n_groups: int = 3, group_size: int = 4,
                 max_rounds: int = 600) -> dict:
    cfg = MessengerConfig(n_groups=n_groups, group_size=group_size,
                          n_messengers=n_messengers, dwell=dwell,
                          max_rounds=max_rounds, seed=seed)
    return MessengerSim(cfg).run()
