---
title: Linux 内核网络栈
category: concepts
tags: [linux, kernel, networking, napi, tc, netfilter, sk_buff, data-plane, active]
created: 2026-07-29
updated: 2026-07-29
summary: >-
    数据包从网卡进入内核到用户空间的完整路径。NAPI 轮询/中断合并、
    sk_buff 结构布局、GRO/GSO/LRO/RRO 硬件/软件分段卸载、
    TC（Traffic Control）入口/出口挂接点、Netfilter 连接跟踪、
    RPS/RFS/XPS CPU 分发、flow offload 硬件卸载。对照 DPDK/XDP 理解内核路径。
base_confidence: 0.85
lifecycle: draft
---

# Linux 内核网络栈

> 前置 [[concepts/CPU 核心架构]]（中断/DDIO），[[concepts/CPU 中断与MSI-X]]（NAPI）。
> 本文是从 NIC 收包到 socket 接收的完整主线路径。

## 1. 收包主线路径

```
NIC 收到包 (RX Queue 0)
  │
  ├── (1) DMA write to DRAM (or DDIO → LLC)
  │       sk_buff 从 SKB pool 中预先分配
  │
  ├── (2) MSI-X 中断 → IRQ handler → napi_schedule()
  │       → 关中断，切 NAPI 轮询模式
  │
  ├── (3) NAPI poll() → 网卡驱动 ndo_poll
  │       → 收包预算（dev_weight，默认 64）
  │       → GRO 合并（相同流的小包合并为大包）
  │
  ├── (4) netif_receive_skb()
  │       → TC ingress hook (BPF)
  │       → RPS (可能跨 CPU 分发)
  │
  ├── (5) ip_rcv() → netfilter PREROUTING
  │       → 路由判决（查找 FIB）
  │
  ├── (6) LOCAL_IN：tcp_v4_rcv() → TCP 状态机
  │  或  FORWARD：netfilter FORWARD → ip_forward()
  │       → netfilter POSTROUTING → dev_queue_xmit()
  │
  └── (7) socket 接收队列 → 用户态 read/recvfrom
```

### 1.1 NAPI 细节

```c
// NAPI poll 循环（mlx5 示例）
int mlx5e_napi_poll(struct napi_struct *napi, int budget) {
    int work_done = 0;
    // 不断收包直到 budget 用完或没有包
    while (work_done < budget) {
        pkts = mlx5e_skb_from_cqe(sq, cqe);  // CQE → sk_buff
        if (!pkts) break;
        napi_gro_receive(napi, pkts);         // GRO 合并
        work_done++;
    }
    if (work_done < budget) {
        napi_complete(napi);                  // 关 NAPI，开中断
        mlx5e_cq_arm(cq);
    }
    return work_done;
}
// budget 调大（默认 64）→ 吞吐高但中断延迟增加
// budget 调小 → 延迟低但吞吐下降（NAPI 切换频繁）

// 调整预算
echo 128 | sudo tee /sys/class/net/eth0/gro_flush_timeout
```

### 1.2 sk_buff 结构（关键字段）

```c
struct sk_buff {
    // ---- 前 64B（hot cache line）----
    union { struct tcphdr *th; ... };   // 各层的头指针
    struct sock     *sk;                // 关联 socket
    struct net_device *dev;             // 输入设备
    struct net_device *skb_iif;         // 输入 ifindex
    unsigned int     len;              // 总长度
    __u16           protocol;           // L3 协议号
    __u16           queue_mapping;      // TX 队列
    // ---- 后 64B+ ----
    char            cb[48];            // 控制块（TC/Netfilter 存元数据）
    struct skb_shared_info *shinfo;     // 分片信息
    // ...
};
// 分配：kmem_cache_alloc(skbuff_cache) 约 200cy
// 对齐：__aligned(64) → 存于 slab 且对齐
// 释放：kfree_skb()
```

## 2. 硬件卸载

| 卸载 | 方向 | 描述 | 收益 |
|------|------|------|------|
| **TSO/GSO** | TX | TCP Segmentation Offload：大块 TCP 数据一次交网卡分段 | 减少 CPU 分片开销，批量处理 |
| **GRO** | RX | Generic Receive Offload：合并同流小包为一个大包提交 | 减少协议栈处理次数（单次处理 1 个大包 vs 64 个小包） |
| **LRO** | RX | Large Receive Offload（GRO 前身，GRO 更灵活） | 同 GRO |
| **RRO** | RX | Receive Reorder Offload（重排序） | 缓解多队列乱序 |
| **GENEVE/VXLAN** | TX/RX | 隧道封装卸载（NIC 计算外层的 UDP+IP+ETH 头和校验和） | 减少 VXLAN 封装 CPU 开销 |
| **checksum** | TX/RX | 校验和计算/验证卸载（IP/TCP/UDP） | 零 CPU |

```bash
# 查看当前卸载设置
ethtool -k eth0 | grep -E "tcp-segmentation-offload|generic-receive-offload|tx-checksumming"

# 关 GRO（数据面场景：需包级可见时关掉）
ethtool -K eth0 gro off

# 关 TSO（DDoS 场景：防止 TCP 攻击放大）
ethtool -K eth0 tso off

# DPDK 接管后：网卡全部卸载由 PMD 直接控制
# VPP 接管后：GRO/TSO 由 VPP 设备 input node 处理
```

## 3. TC（Traffic Control）

### 3.1 Ingress / Egress

```
In the Linux network path:

TX Side:                          RX Side:
socket                             NIC
  ↓                                  ↓
  ↓ (1) BPF_PROG_TYPE_SK_MSG       TC ingress (clsact qdisc)
  ↓                                  → BPF_PROG_TYPE_SCHED_CLS
  ↓ (2) TC egress (clsact)           → 分流/丢弃/重定向
  ↓ → BPF/SKB prio                   ↓
  ↓                                  ↓
  ↓ (3) netfilter LOCAL_OUT         netif_receive_skb
  ↓ → nf_hook                        ↓
  ↓                                ip_rcv → netfilter
  ↓ (4) ndo_start_xmit             PREROUTING
  NIC                                ↓
                                   ROUTE
```

### 3.2 BPF 在 TC 中的使用

```c
// TC BPF ingress hook: XDP 之后的第二层（可丢/改/重定向包）
// TC BPF 可访问 sk_buff，比 XDP 层级高（可查路由/取 socket）
// XDP 优先（更早、更快），TC BPF 作为补充

// TC BPF 重定向到用户 socket (AF_XDP 的备选方案)
// bpf_redirect_neigh 重定向到邻接节点
// bpf_redirect 重定向到 ifindex

// TCIngress 常用场景：
// - DDoS 清洗第 2 层（XDP 改不了 IP/UDP 需要查连接跟踪的）
// - 容器流量隔离（Cilium 使用 TC BPF + XDP）
```

## 4. Netfilter 与连接跟踪

```bash
# Netfilter 5 个 hook point
# NF_INET_PRE_ROUTING       → raw PREROUTING / conntrack
# NF_INET_LOCAL_IN          → mangle INPUT / filter INPUT / nat INPUT
# NF_INET_FORWARD           → filter FORWARD
# NF_INET_LOCAL_OUT         → raw OUTPUT / conntrack / mangle OUTPUT / nat OUTPUT / filter OUTPUT
# NF_INET_POST_ROUTING      → mangle POSTROUTING / nat POSTROUTING

# conntrack 开销
# 每条连接需 ~256B 存储
# 新建连接：查表 + 插入，约 200-500 cy
# 已有连接转发：查表，约 50-100 cy

# 查看 conntrack 内容
cat /proc/net/nf_conntrack | head
# 每秒新建连接数
conntrack -S | grep insert

# 数据面场景（>1M pps）：
# - conntrack 成为瓶颈（锁争用）
# - 用 flow offload 或 DPDK 绕过
```

## 5. RPS/RFS/XPS

| 技术 | 作用 | 配置 |
|------|------|------|
| **RPS** (Receive Packet Steering) | 软件 RSS：收到包后通过 hash 分发到指定 CPU | `/sys/class/net/eth0/queues/rx-*/rps_cpus` |
| **RFS** (Receive Flow Steering) | 把流分发到消费它的 CPU（增加 locality） | `rps_flow_cnt` + 应用 CPU hint |
| **XPS** (Transmit Packet Steering) | 发送队列亲和到 CPU（TX queue → core mapping） | `/sys/class/net/eth0/queues/tx-*/xps_cpus` |

```bash
# 数据面场景：RPS/RFS/XPS 在 DPDK 直通时不需配置
# 但在 kernel 网络栈中有效：
# 每队列 rps_cpus 设到对应 NUMA 的核

echo "f0" | sudo tee /sys/class/net/eth0/queues/rx-0/rps_cpus
# 多队列时每队列绑不同核
```

## 6. Flow Offload

```bash
# Linux flow offload（5.x+）：
# 把 conntrack 建立的流直接写到网卡硬件流转发表
# 硬件直接转发，不再经过 kernel 协议栈

# 配置（TC 链式动作）：
tc filter add dev eth0 ingress prio 1 flower \
    ip_proto tcp dst_ip 10.0.0.1 \
    action ct commit \
    action ct clear \
    action mirred egress redirect dev eth1

# 硬件 offload 标志：
ethtool -k eth0 | grep "flow-offload\|hw-tc-offload"

# 数据面场景：
# - OVS 使用 flow offload 把流表推到网卡（>100k 流）
# - 硬件转发 → 零 CPU 开销
# - 局限：仅支持 TCP/UDP、少量匹配字段、流表容量有限
# - 对照 DPDK：纯软件线速（不依赖硬件 offload 容量）
```

## 7. 数据面路径延迟对比

| 路径 | 每包延迟（估计） | 包/秒（单核） |
|------|---------------|-------------|
| DPDK PMD (轮询) | ~500 ns | ~20 M |
| XDP (内核内) | ~1000 ns | ~10 M |
| AF_XDP (零拷贝) | ~800 ns | ~12 M |
| NAPI + GRO (主线) | ~5 μs | ~1-2 M |
| NAPI + GRO + conntrack | ~10 μs | ~500 K |
| + Netfilter + iptables | ~20 μs | ~200 K |
| + tc + BPF | ~15 μs | ~300 K |

## 参考来源

- [[concepts/CPU 核心架构]]
- [[entities/CPU 中断与MSI-X]]
- Linux kernel: Documentation/networking/scaling.rst (RPS/RFS/XPS)
- Linux kernel: Documentation/networking/NAPI_HOWTO.txt
- kernel.org: `sk_buff` struct documentation
- DPDK vs Kernel Networking comparison (6WIND, 2019)
- Cilium: BPF and XDP Reference Guide
