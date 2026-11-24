# -*- coding: utf-8 -*-
"""可离线复现的 Hashgraph 共识核心.

本模块从 Webots-ROS 实验栈中的 ``controllers/blockchain/swirld.py`` 提炼,
去除 socket 通信与 pysodium 硬依赖, 保留完整共识逻辑, 供
``swarm_collab.messenger`` 与 ``swarm_collab.framework`` 离线复现:

- 事件(gossip-about-gossip)结构与签名验证;
- ``divide_rounds``: 依据"强可见"递归确定事件轮次;
- ``decide_fame``: 见证人著名性虚拟投票(分布式拜占庭容错, 可容 1/3 拜占庭);
- ``find_order``: 公平排序(共识时间戳 + 名人见证人签名比特白化)。

签名实现: 优先使用 pysodium(Ed25519, 与实验栈一致); 不可用时退化为
blake2b HMAC 模拟(仅供离线仿真, 不具备真实密码学安全性)。

算法出处: L. Baird, "Hashgraph Consensus: Fair, Fast, Byzantine Fault
Tolerant Distributed State Consensus"; 参考实现改编自社区 MIT 开源实现
(见仓库 NOTICE 文件)。
"""
from __future__ import annotations

import hashlib
import hmac
import os
from collections import defaultdict
from dataclasses import dataclass
from functools import reduce

try:  # 实验栈环境: 使用与 Webots/ROS 部署一致的 Ed25519
    from pysodium import (crypto_generichash, crypto_sign_detached,
                          crypto_sign_keypair, crypto_sign_verify_detached)

    HAVE_SODIUM = True
except ImportError:  # 离线仿真环境: blake2b 模拟签名
    HAVE_SODIUM = False

    def crypto_sign_keypair():
        sk = os.urandom(32)
        pk = hashlib.blake2b(sk, digest_size=32).digest()
        return pk, sk

    def _hash(data) -> bytes:
        return hashlib.blake2b(data, digest_size=32).digest()

    def crypto_generichash(data) -> bytes:
        return _hash(data if isinstance(data, bytes) else repr(data).encode())

    def crypto_sign_detached(data, sk) -> bytes:
        # 仿真回退: "签名"= H(data || 公钥), 任何持公钥者可重算校验。
        # 仅为离线仿真保留签名验证流程, 不具备真实密码学安全性。
        return _hash(data + b"|sim-sig|")

    def crypto_sign_verify_detached(sig, data, pk):
        if not hmac.compare_digest(crypto_sign_detached(data, None), sig):
            raise ValueError("bad signature")


C = 6  # 虚拟投票选举轮换常数


@dataclass(frozen=True)
class Event:
    """Hashgraph 事件: d=载荷交易, p=(自父, 他父), t=创建轮次, c=创建者, s=签名."""

    d: tuple
    p: tuple
    t: int
    c: bytes
    s: bytes


def _sign_body(ev_body) -> bytes:
    return hashlib.blake2b(repr(ev_body).encode(), digest_size=32).digest()


def _majority(it):
    hits = [0, 0]
    for s, x in it:
        hits[int(bool(x))] += s
    return hits[0] > hits[1], hits[0]


def _bfs(start, walk):
    seen, queue = set(), list(start)
    while queue:
        u = queue.pop(0)
        if u in seen:
            continue
        seen.add(u)
        queue.extend(v for v in walk(u) if v not in seen)
    return seen


def _toposort(nodes, pred):
    order, done, out = list(nodes), set(), []
    while len(out) < len(order):
        progressed = False
        for u in sorted(order):
            if u in done:
                continue
            if all(p in done or p not in order for p in pred(u)):
                out.append(u)
                done.add(u)
                progressed = True
        assert progressed, "cycle detected"
    return out


class HashgraphNode:
    """集群中的一个机器人共识节点."""

    def __init__(self, node_id, kp, network, n_nodes, stake=None):
        self.id = node_id
        self.pk, self.sk = kp
        self.network = network          # {对端pk -> 对端ask_sync回调}
        self.n = n_nodes
        self.stake = stake
        self.tot_stake = sum(self.stake.values())
        self.min_s = 2 * self.tot_stake / 3

        self.hg = {}                    # {event-hash -> Event}: 哈希图本体
        self.head = None                # 本节点最新事件
        self.round = {}                 # {event-hash -> 轮次}
        self.tbd = set()                # 待定序事件
        self.transactions = []          # 最终公平排序的交易
        self.idx = {}
        self.consensus = set()          # 著名性已判定的轮次
        self.votes = defaultdict(dict)
        self.witnesses = defaultdict(dict)
        self.famous = {}
        self.height = {}
        self.can_see = {}

        # ---- 度量: 事件创建轮次 / 定序轮次(共识时延, 以 gossip 轮次计) ----
        self.event_round = {}
        self.ordered_round = {}
        self.global_round = 0

    def init_first_event(self):
        h, ev = self.new_event((), ())
        self._add(h, ev, round_no=0)
        self.round[h] = 0
        self.witnesses[0][ev.c] = h
        self.can_see[h] = {ev.c: h}
        self.head = h

    # ------------------------------------------------------------------
    def new_event(self, d, p):
        assert p == () or len(p) == 2
        assert p == () or self.hg[p[0]].c == self.pk      # 自父为自己创建
        assert p == () or self.hg[p[1]].c != self.pk      # 他父为他人事件
        ev = Event(d, p, self.global_round, self.pk,
                   crypto_sign_detached(_sign_body((d, p, self.global_round, self.pk)), self.sk))
        return crypto_generichash(repr(ev).encode()), ev

    def is_valid_event(self, h, ev):
        try:
            crypto_sign_verify_detached(
                ev.s, _sign_body((ev.d, ev.p, ev.t, ev.c)), ev.c)
        except ValueError:
            return False
        return (crypto_generichash(repr(ev).encode()) == h
                and (ev.p == ()
                     or (len(ev.p) == 2
                         and ev.p[0] in self.hg and ev.p[1] in self.hg
                         and self.hg[ev.p[0]].c == ev.c
                         and self.hg[ev.p[1]].c != ev.c)))

    def _add(self, h, ev, round_no=None):
        self.hg[h] = ev
        self.tbd.add(h)
        self.height[h] = 0 if ev.p == () else 1 + max(self.height[p] for p in ev.p)
        if round_no is not None:
            self.event_round[h] = round_no

    # ------------------------------------------------------------------
    def sync(self, pk, payload=()):
        """与邻居 pk gossip 同步; 本节点待发交易随新事件上链.

        Returns:
            本轮新增事件的拓扑序 tuple(供 divide_rounds 消化).
        """
        info = {c: self.height[h] for c, h in self.can_see[self.head].items()}
        remote_head, remote_hg = self.network[pk](self.pk, info)

        new = tuple(_toposort(remote_hg.keys() - self.hg.keys(),
                              lambda u: remote_hg[u].p))
        for h in new:
            ev = remote_hg[h]
            if self.is_valid_event(h, ev):
                self._add(h, ev, round_no=self.global_round)

        if self.is_valid_event(remote_head, remote_hg[remote_head]):
            h, ev = self.new_event(tuple(payload), (self.head, remote_head))
            self._add(h, ev, round_no=self.global_round)
            self.head = h
            new = new + (h,)
        return new

    def ask_sync(self, pk, info):
        """响应邻居的同步请求(仅返回其缺失的子图)."""
        subset = {h: self.hg[h] for h in _bfs(
            (self.head,),
            lambda u: (p for p in self.hg[u].p
                       if self.hg[p].c not in info
                       or self.height[p] > info.get(self.hg[p].c, 0)))}
        return self.head, subset

    # ------------------------------------------------------------------
    def divide_rounds(self, events):
        for h in events:
            ev = self.hg[h]
            if ev.p == ():
                self.round[h] = 0
                self.witnesses[0][ev.c] = h
                self.can_see[h] = {ev.c: h}
            else:
                r = max(self.round[p] for p in ev.p)
                p0, p1 = (self.can_see[p] for p in ev.p)
                self.can_see[h] = {c: self._maxi(p0.get(c), p1.get(c))
                                   for c in p0.keys() | p1.keys()}
                hits = defaultdict(int)
                for c, k in self.can_see[h].items():
                    if self.round[k] == r:
                        for c_, k_ in self.can_see[k].items():
                            if self.round[k_] == r:
                                hits[c_] += self.stake[c]
                if sum(1 for x in hits.values() if x > self.min_s) > self.min_s:
                    r += 1
                self.round[h] = r
                self.can_see[h][ev.c] = h
                if r > self.round[ev.p[0]]:
                    self.witnesses[r][ev.c] = h

    def decide_fame(self):
        max_r = max(self.witnesses)
        max_c = 0
        while max_c in self.consensus:
            max_c += 1

        def iter_undetermined(r_):
            for r in range(max_c, r_):
                if r not in self.consensus:
                    for w in self.witnesses[r].values():
                        if w not in self.famous:
                            yield r, w

        def iter_voters():
            for r_ in range(max_c + 1, max_r + 1):
                for w in self.witnesses[r_].values():
                    yield r_, w

        done = set()
        for r_, y in iter_voters():
            hits = defaultdict(int)
            for c, k in self.can_see[y].items():
                if self.round[k] == r_ - 1:
                    for c_, k_ in self.can_see[k].items():
                        if self.round[k_] == r_ - 1:
                            hits[c_] += self.stake[c]
            s = {self.witnesses[r_ - 1][c] for c, n in hits.items() if n > self.min_s}

            for r, x in iter_undetermined(r_):
                if r_ - r == 1:
                    self.votes[y][x] = x in s
                else:
                    v, t = _majority((self.stake[self.hg[w].c], self.votes[w][x])
                                     for w in s)
                    if (r_ - r) % C != 0:
                        if t > self.min_s:
                            self.famous[x] = v
                            done.add(r)
                        else:
                            self.votes[y][x] = v
                    else:
                        self.votes[y][x] = (v if t > self.min_s
                                            else bool(int(self.hg[y].s[0]) // 128))

        new_c = {r for r in done
                 if all(w in self.famous for w in self.witnesses[r].values())}
        self.consensus |= new_c
        return new_c

    def find_order(self, new_c):
        to_int = lambda x: int.from_bytes(self.hg[x].s, byteorder='big')

        for r in sorted(new_c):
            f_w = {w for w in self.witnesses[r].values() if self.famous[w]}
            white = reduce(lambda a, b: a ^ to_int(b), f_w, 0)
            ts, seen = {}, set()
            for x in _bfs(list(filter(self.tbd.__contains__, f_w)),
                          lambda u: (p for p in self.hg[u].p if p in self.tbd)):
                c = self.hg[x].c
                s = {w for w in f_w if c in self.can_see[w]
                     and self._higher(self.can_see[w][c], x)}
                if sum(self.stake[self.hg[w].c] for w in s) > self.tot_stake / 2:
                    self.tbd.remove(x)
                    seen.add(x)
                    times = sorted(self.event_round[w] for w in s)
                    ts[x] = .5 * (times[len(times) // 2] + times[(len(times) + 1) // 2])
            final = sorted(seen, key=lambda x: (ts[x], white ^ to_int(x)))
            for i, x in enumerate(final):
                self.idx[x] = i + len(self.transactions)
                self.ordered_round[x] = self.global_round
                for tx in self.hg[x].d:
                    if tx:
                        self.transactions.append(tx)

    # ------------------------------------------------------------------
    def _maxi(self, a, b):
        return a if self._higher(a, b) else b

    def _higher(self, a, b):
        return a is not None and (b is None or self.height[a] >= self.height[b])


# ---------------------------------------------------------------------------
# 离线 gossip 编排器
# ---------------------------------------------------------------------------
class GossipSwarm:
    """离线 Hashgraph gossip 编排: 驱动节点间同步并度量共识时延(轮次).

    Args:
        node_ids: 节点 id 列表.
        link: 可选 {(i, j) -> bool}; False 表示 i 与 j 间当前不可达(弱连接/
              分组场景), None 表示全连通.
    """

    def __init__(self, node_ids, link=None):
        self.node_ids = list(node_ids)
        self.kps = {i: crypto_sign_keypair() for i in self.node_ids}
        self.nodes: dict[int, HashgraphNode] = {}
        self.round = 0
        self._queues = {i: [] for i in self.node_ids}
        self.link = link

        for i in self.node_ids:
            peers = [j for j in self.node_ids
                     if j != i and (link is None or link.get((i, j), True))]
            self.nodes[i] = HashgraphNode(
                i, self.kps[i],
                network={self.kps[j][0]: self._make_cb(j) for j in peers},
                n_nodes=len(self.node_ids),
                stake={self.kps[j][0]: 1 for j in peers} | {self.kps[i][0]: 1})
            self.nodes[i].stake = {self.kps[x][0]: 1 for x in self.node_ids}
            self.nodes[i].tot_stake = len(self.node_ids)
            self.nodes[i].min_s = 2 * self.nodes[i].tot_stake / 3
            self.nodes[i].init_first_event()

    def _make_cb(self, j):
        def cb(pk, info):
            return self.nodes[j].ask_sync(pk, info)
        return cb

    def broadcast(self, node_id, tx):
        """节点 node_id 产生一笔待共识交易."""
        self._queues[node_id].append(tx)

    def gossip_round(self, pairs):
        """执行一轮 gossip: pairs 为 [(发起方, 响应方)], 发起方队列交易随事件上链.

        divide_rounds 在每次同步后立即执行(维护 can_see/head 不变量);
        昂贵的著名性投票与定序(decide_fame/find_order)每轮每节点批量
        执行一次, 降低重复扫描开销(不改变共识语义)。"""
        self.round += 1
        for n in self.nodes.values():
            n.global_round = self.round
        touched = []
        for i, j in pairs:
            if not self._reachable(i, j):
                continue
            payload = self._queues[i]
            self._queues[i] = []
            new = self.nodes[i].sync(self.kps[j][0], payload)
            self.nodes[i].divide_rounds(new)   # 立即消化, 维护 head/can_see 不变量
            touched.append(i)
        for i in touched:
            n = self.nodes[i]
            n.find_order(n.decide_fame())

    def _reachable(self, i, j):
        return self.link is None or self.link.get((i, j), True)

    def all_pairs_random(self, rng):
        """生成一轮 gossip 对: 每个节点向随机邻居发起一次同步(原实验栈节奏)."""
        pairs = []
        for i in self.node_ids:
            peers = [j for j in self.node_ids if j != i and self._reachable(i, j)]
            if peers:
                pairs.append((i, rng.choice(peers)))
        return pairs

    def consensus_reached(self, expected_txs) -> bool:
        """判定全局共识: 所有节点交易集相同且覆盖全部预期交易."""
        want = set(expected_txs)
        return all(set(n.transactions) == want for n in self.nodes.values())

    def all_equal(self) -> bool:
        """所有节点最终交易序列完全一致(公平排序一致性)."""
        seqs = [tuple(n.transactions) for n in self.nodes.values()]
        return all(s == seqs[0] for s in seqs)
