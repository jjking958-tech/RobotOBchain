# -*- coding: utf-8 -*-
"""基于细粒度DAG图划分的深度学习协同推理方法.

将复杂神经网络(如GoogLeNet)抽象为DAG图, 依据机器人异构计算能力与
网络链路带宽, 通过启发式算法实现高效划分, 最小化推理与传输延迟:

- :mod:`.model_dag`          神经网络 -> DAG 抽象(逐层计算量/激活传输量)
- :mod:`.planner`            异构延迟模型与贪心/轮转对比基线
- :mod:`.propagation_chain`  算法1: 基于能力增强传播链的模型划分算法
- :mod:`.path_backtracking`  算法2: 基于路径回溯的模型划分优化算法
"""
from .model_dag import LayerNode, ModelDAG, googlenet_like_dag
from .planner import (Fleet, RobotProfile, evaluate, partition_greedy,
                      partition_round_robin, partition_single)
from .propagation_chain import partition_propagation_chain
from .path_backtracking import partition_path_backtracking

__all__ = [
    "LayerNode", "ModelDAG", "googlenet_like_dag",
    "Fleet", "RobotProfile", "evaluate", "partition_greedy", "partition_round_robin",
    "partition_single", "partition_propagation_chain", "partition_path_backtracking",
]
