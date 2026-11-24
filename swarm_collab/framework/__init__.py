# -*- coding: utf-8 -*-
"""多机器人自组织协同框架原型.

对应任务书研究内容四: 构建包括资源聚合模块、共同认知模块和任务管理
模块的原型框架, 实现从资源发现、知识共享到任务分配与执行的完整协同流程。

- :mod:`.resource_pool`  资源聚合模块: 机器人异构算力注册与聚合视图
- :mod:`.cognition`      共同认知模块: 基于 Hashgraph 的事件共识服务
- :mod:`.task_manager`   任务管理模块: 深度学习任务 DAG 划分、分配与执行
- :mod:`.demo`           端到端演示脚本
"""
from .resource_pool import RobotProfile, ResourcePool
from .cognition import SwarmCognition
from .task_manager import TaskManager

__all__ = ["RobotProfile", "ResourcePool", "SwarmCognition", "TaskManager"]
