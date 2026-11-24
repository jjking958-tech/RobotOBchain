# -*- coding: utf-8 -*-
"""资源聚合模块: 机器人异构计算能力的注册与聚合视图.

对应任务书研究内容四中的资源聚合模块: 在无中心节点条件下, 各机器人
自主上报算力/内存画像, 形成集群统一的资源聚合视图, 供任务管理模块
进行协同推理任务划分。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from swarm_collab.dag import RobotProfile


@dataclass
class ResourcePool:
    """集群资源聚合视图(去中心化注册表)."""

    profiles: dict[int, RobotProfile] = field(default_factory=dict)
    bandwidth_mbps: float = 1000.0   # 默认机间链路带宽(Mbps, 5G/WiFi6E 机间_mesh)

    def register(self, robot_id: int, gflops: float):
        """资源发现: 机器人加入集群并上报算力画像."""
        self.profiles[robot_id] = RobotProfile(robot_id, gflops)
        return self

    def to_fleet(self):
        """转换为 DAG 划分器使用的编队对象."""
        from swarm_collab.dag import Fleet
        fleet = Fleet(list(self.profiles.values()))
        ids = fleet.ids()
        for u in ids:
            for v in ids:
                if u != v:
                    fleet.set_bandwidth(u, v, self.bandwidth_mbps)
        return fleet

    def ids(self) -> list[int]:
        return list(self.profiles.keys())

    def total_gflops(self) -> float:
        return sum(r.gflops for r in self.profiles.values())

    def summary(self) -> str:
        rows = ", ".join(f"robot{r.id}:{r.gflops}GF" for r in self.profiles.values())
        return f"ResourcePool({len(self.profiles)} robots, total {self.total_gflops():.0f} GFLOPS: {rows})"
