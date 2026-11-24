# -*- coding: utf-8 -*-
"""共同认知模块: 基于 Hashgraph 的集群事件共识服务.

对应任务书研究内容四中的共同认知模块: 将集群中各机器人产生的事件
(环境感知结论、任务执行结果、投票等)通过 Hashgraph 共识形成公平排序、
不可篡改的共同认知视图, 供任务管理模块与智能合约审计使用。
"""
from __future__ import annotations

from swarm_collab.consensus import GossipSwarm


class SwarmCognition:
    """集群共同认知服务(封装离线 Hashgraph gossip 编排器)."""

    def __init__(self, node_ids, seed: int = 0):
        import random
        self.node_ids = list(node_ids)
        self.swarm = GossipSwarm(self.node_ids, link=None)
        self.rng = random.Random(seed)
        self._next_seq = 0

    def submit(self, node_id: int, payload: str):
        """机器人 node_id 产生一条待共识事件(交易)."""
        self.swarm.broadcast(node_id, payload)

    def make_event_id(self, prefix: str) -> str:
        self._next_seq += 1
        return f"{prefix}-{self._next_seq:04d}"

    def run_until_consensus(self, expected_txs, max_rounds: int = 300) -> dict:
        """驱动 gossip 直至全体事件达成公平排序共识.

        Returns:
            dict(rounds=实际轮次, converged=bool, latency=平均共识时延(轮),
                 order=最终排序)
        """
        while self.swarm.round < max_rounds:
            self.swarm.gossip_round(self.swarm.all_pairs_random(self.rng))
            if self.swarm.consensus_reached(expected_txs) and self.swarm.all_equal():
                lat = [n.ordered_round[h] - n.event_round[h]
                       for n in self.swarm.nodes.values()
                       for h in n.ordered_round if n.hg[h].d]
                return {
                    "rounds": self.swarm.round,
                    "converged": True,
                    "latency": sum(lat) / len(lat) if lat else 0.0,
                    "order": list(self.swarm.nodes[self.node_ids[0]].transactions),
                }
        return {"rounds": self.swarm.round, "converged": False,
                "latency": None, "order": []}
