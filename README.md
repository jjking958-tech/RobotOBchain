# RobotOBchain: Neighbor Observation for Byzantine Detection in Multi-Robot Systems

低空拒止环境下无人集群自组织协同关键技术研究 —— 开源代码与实验复现

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Project](https://img.shields.io/badge/%E6%B9%98%E6%B1%9F%E5%AE%9E%E9%AA%8C%E5%AE%A4-25XJ03014-blue)](README.md)

本仓库是湘江实验室一般项目 **《低空拒止环境下无人集群自组织协同关键技术研究》（项目编号：25XJ03014）** 的开源代码库，包含两部分：

1. **Webots-ROS-Hashgraph 实验栈**（`controllers/`、`worlds/`、`scripts/`）——论文 *RobotOBchain: Neighbor Observation for Byzantine Detection in Multi-Robot Systems*（Electronics, 2025, 14, 4815）的原始实验代码：多机器人黑白格频率协同估计、链上观测存证、智能合约拜占庭过滤。
2. **`swarm_collab/` 离线复现包**——任务书四项研究内容的算法实现与可复现实验（无需 Webots/ROS 即可运行）。

## 1. 研究内容与代码对应关系

| 任务书研究内容 | 代码位置 | 说明 |
|---|---|---|
| （一）基于细粒度DAG图划分的深度学习协同推理方法 | `swarm_collab/dag/` | 神经网络→DAG 抽象（类 GoogLeNet 含 Inception 并行分支）、**算法1：基于能力增强传播链的模型划分**（`propagation_chain.py`）、**算法2：基于路径回溯的模型划分优化**（`path_backtracking.py`）、异构延迟模型与对比基线（`planner.py`） |
| （二）基于Hashgraph和主动传播的共同认知方法 | `swarm_collab/consensus/`、`swarm_collab/messenger/`、`controllers/blockchain/swirld*.py` | Hashgraph 共识核心（事件/gossip-about-gossip/虚拟投票/公平排序，可离线复现）；**"通信兵"机器人主动传播机制**仿真（群间断连 + 摆渡） |
| （三）基于智能合约的应用层拜占庭机器人容错方法 | `swarm_collab/byzantine/`、`controllers/blockchain/byzantineFilter.py` | **RobotOBchain 双层检测**离线仿真：邻居观测交叉验证信誉多数决（论文算法2）+ 共识层 KS 分布审计；W-MSR(F=2) 对比基线 |
| （四）多机器人自组织协同框架原型 | `swarm_collab/framework/` | 资源聚合模块（`resource_pool.py`）+ 共同认知模块（`cognition.py`）+ 任务管理模块（`task_manager.py`）+ 端到端演示（`demo.py`） |

## 2. 快速开始

```bash
pip install -r requirements.txt   # numpy, matplotlib, scipy, scikit-learn, pyemd

# 端到端演示(资源聚合 -> DAG划分协同推理 -> 结果共识 -> 拜占庭检测估计)
python swarm_collab/framework/demo.py

# 四组可复现实验(输出 CSV 与图至 results/)
python experiments/exp_dag_partition.py       # 实验1: DAG划分算法对比
python experiments/exp_consensus.py           # 实验2: Hashgraph 共识收敛
python experiments/exp_byzantine_detection.py # 实验3: 拜占庭检测与容错(vs W-MSR)
python experiments/exp_messenger.py           # 实验4: 通信兵主动传播
```

`swarm_collab/` 仅依赖 numpy/matplotlib（KS 审计可选 scipy，缺失时自动退化）。

## 3. 主要实验结果（本仓库离线复现，`results/` 内含数据与图）

### 3.1 细粒度 DAG 协同推理（实验1）

4 机低算力编队（1/2/4/8 GFLOPS 机载计算机）、类 GoogLeNet 任务（0.7 GFLOPs）：

| 机间带宽 | single 单机 | round_robin | greedy | **算法1传播链** | **算法1+算法2回溯** |
|---|---|---|---|---|---|
| 1000 Mbps | 87.6 ms | 246.7 ms | 98.6 ms | 87.4 ms | **74.3 ms** |
| 250 Mbps | 87.6 ms | 619.6 ms | 214.9 ms | 152.4 ms | **136.8 ms** |

协同推理相对单机部署降低端到端延迟最高约 **15%**；低带宽（100 Mbps）下传输开销占主导，单机部署反而更优——与协同推理文献一致，机间带宽是协同推理收益的关键约束。

### 3.2 Hashgraph 共识（实验2）

6~12 节点集群、每节点 1 笔交易：全体节点在数十个 gossip 轮内达成**完全一致的公平排序**（各节点最终交易序列逐位相同），验证了无中心节点环境下共同认知视图的快速形成。

### 3.3 拜占庭容错（实验3）

10 台机器人、黑白格频率真值 0.40、拜占庭数量 f = 0~5（0%~50%），10 次独立运行：

- **判定一致性 100%、误报率 0%**（各诚实机器人基于相同链上证据独立判定，结果完全一致）；
- 拜占庭检出率：f ≤ 30% 为 **100%**，f = 40% 为 95%，f = 50%（理论边界）为 72%；
- 剔除拜占庭后的估计误差（相对地图实际频率）：f ≤ 30% 时 **≤ 3%**；
- W-MSR(F=2) 在 f ≤ 2 时误差较小，f > 2 后被拜占庭拖偏（最高 26%），RobotOBchain 全程显著更优——验证了摆脱先验故障上限 F 的价值。

> 说明：50% 为多数决机制的理论边界（论文讨论节同样指出）。离线复现中恰好在 50% 处检出率下降；Webots 实验栈的完整结论见论文。

### 3.4 "通信兵"主动传播（实验4）

3 群体 × 4 机、群间断连，通信兵按航线巡回驻留各群体并与成员双向 gossip：

- **无通信兵：永不收敛**（群间断连的集群无法形成共同认知）；
- **1 台通信兵**即可使全体交易达成公平排序共识：驻留 2 轮时 53~75 轮收敛，驻留 5 轮时 81~436 轮；
- **2 台通信兵并不稳定更快**（均值反而高于单台驻留 2 轮）——通信兵引入的额外事件会拖慢哈希图虚拟投票收敛，说明通信兵数量与驻留节奏存在**最优配置问题**，与任务书"研究机器人数量、驻留等因素对一致视图收敛速度的影响，优化配置与使用策略"相呼应。

## 4. Webots-ROS-Hashgraph 实验栈（原始论文实验）

- `worlds/black-white-grid.wbt`：e-puck2 多机器人黑白格采样场景；
- `controllers/data_sampling/`：机器人采样控制（10 Hz 采样、滑动窗口估计、RSA 签名广播）；
- `controllers/blockchain/swirld*.py`：Hashgraph 共识节点（socket gossip、虚拟投票、公平排序、分组均值收敛）；
- `controllers/blockchain/byzantineFilter.py`：智能合约拜占庭过滤（KS 检验 + KMeans 分布审计）；
- `controllers/supervisor/`、`scripts/`：裁判与数据后处理。

依赖：Webots + ROS + python3（pysodium, scipy, sklearn, pyemd, rsa），在 Ubuntu 环境部署。

## 5. 引用

```bibtex
@article{luo2025robotobchain,
  author  = {Luo, Jie and Guo, Yumeng and Cao, Tiancheng and Zhu, Wuyang},
  title   = {RobotOBchain: Neighbor Observation for Byzantine Detection in Multi-Robot Systems},
  journal = {Electronics},
  year    = {2025},
  volume  = {14},
  number  = {24},
  pages   = {4815},
  doi     = {10.3390/electronics14244815}
}
```

本项目受湘江实验室一般项目（25XJ03014）资助。

## 6. 许可

MIT License，见 [LICENSE](LICENSE)；第三方组件致谢见 [NOTICE](NOTICE)。
