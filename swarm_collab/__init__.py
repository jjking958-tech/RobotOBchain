# -*- coding: utf-8 -*-
"""swarm_collab —— 低空拒止环境下无人集群自组织协同关键技术研究开源代码包.

本包对应项目 25XJ03014 任务书的四项研究内容:

1. :mod:`swarm_collab.dag`        基于细粒度DAG图划分的深度学习协同推理方法
2. :mod:`swarm_collab.consensus`  基于Hashgraph的群体共同认知核心算法(可离线复现)
3. :mod:`swarm_collab.byzantine`  基于邻居观测/智能合约审计的应用层拜占庭容错
4. :mod:`swarm_collab.messenger`  基于"通信兵"机器人的主动传播共同认知机制
5. :mod:`swarm_collab.framework`  多机器人自组织协同框架原型(资源聚合/共同认知/任务管理)

复现实验见 ``experiments/`` 目录。
"""

__version__ = "1.0.0"
PROJECT_ID = "25XJ03014"
