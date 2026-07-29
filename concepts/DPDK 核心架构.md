---
title: DPDK 核心架构
category: concepts
tags: [dpdk, packet-processing, kernel-bypass, pmd, eal]
created: 2026-07-29
updated: 2026-07-29
summary: DPDK (Data Plane Development Kit) 核心架构 — 环境抽象层、Poll Mode Driver、巨页内存模型、无锁队列与包处理流水线
base_confidence: 0.85
lifecycle: draft
lifecycle_changed: 2026-07-29
sources:
  - sources/eBPF 调研来源
---

# DPDK 核心架构

## 概述

DPDK (Data Plane Development Kit) 是 Linux Foundation 旗下的开源项目，提供一套用户空间的数据平面库和轮询模式网卡驱动，实现内核旁路 (kernel bypass) 的高速包处理。

- **创造者**：Intel 工程师 Venky Venkatesan（"DPDK 之父"），2010 年
- **开源社区**：2013 年由 6WIND 在 dpdk.org 建立
- **Linux Foundation**：2017 年加入
- **最新稳定版**：26.03（2026 年 3 月）
- **许可**：核心库 BSD-3-Clause，内核模块 GPL-2.0
- **支持架构**：x86、ARM、PowerPC
- **支持 OS**：Linux、FreeBSD、Windows

### 设计目标

绕过 Linux 内核协议栈，在用户空间直接处理数据包，消除中断处理、上下文切换、内存拷贝等开销。典型场景相比内核协议栈提升 10x+ 吞吐量。

## 架构分层

```
┌──────────────────────────────────────────────────┐
│              用户应用 (App)                        │
│   L2FWD / L3FWD / 负载均衡 / 防火墙 / vSwitch     │
├──────────────────────────────────────────────────┤
│              数据平面库 (Data Plane Libraries)      │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌────────┐  │
│  │ EAL  │ │Mempool│ │Ring  │ │Mbuf  │ │Timer   │  │
│  └──────┘ └──────┘ └──────┘ └──────┘ └────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │ PMD 驱动  │ │ Classify │ │ QoS / Metro      │  │
│  └──────────┘ └──────────┘ └──────────────────┘  │
├──────────────────────────────────────────────────┤
│                内核态模块                          │
│   ┌──────────────┐  ┌─────────────────────────┐  │
│   │ IGB_UIO/UIO  │  │  KNI (Kernel NIC I/F)   │  │
│   │ (设备映射)    │  │  (与内核协议栈交互)       │  │
│   └──────────────┘  └─────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

## 核心组件

### 1. EAL (Environment Abstraction Layer)

环境抽象层是 DPDK 的初始化与抽象核心，隐藏底层硬件和 OS 细节：

- **Hugepage 分配**：初始化时预分配 2MB/1GB 巨页内存池
- **CPU 亲和性**：将线程绑定到指定核（lcore），避免调度抖动
- **PCI 设备映射**：将 PCI 网卡寄存器映射到用户空间（通过 UIO/VFIO）
- **内存管理**：统一 NUMA 感知的内存分配
- **原子操作 / 锁**：提供无锁原语
- **时间参考 / 日志 / 调试**

DPDK 程序启动流程：
```
rte_eal_init() →
  1. 解析命令行参数（-c coremask, -n channel 等）
  2. 分配 hugepage 内存
  3. 初始化 PCI 总线并映射设备
  4. 初始化 log/trace 系统
  5. 启动从核进入主循环
```

### 2. PMD (Poll Mode Driver)

DPDK 最关键的创新 —— 轮询模式驱动替代传统中断驱动：

| 特性 | 传统内核驱动 | DPDK PMD |
|------|-----------|---------|
| 收包通知 | 硬件中断 → 内核响应 | 应用轮询 RX 描述符 |
| 数据路径 | DMA → 内核 → skb → socket 拷贝 | DMA → 用户内存（零拷贝） |
| 上下文切换 | 每次中断触发 | 零上下文切换 |
| 延迟 | 微秒级（中断合并） | 亚微秒级 |
| 批量处理 | 单包处理 | burst 收/发（32-64 包/次） |

PMD 工作流程：
```
loop:
  nb_rx = rte_eth_rx_burst(port, queue, mbufs, BURST_SIZE)  // 轮询收包
  for i in 0..nb_rx:
    process_packet(mbufs[i])                                    // 处理
  nb_tx = rte_eth_tx_burst(port, queue, mbufs, nb_rx)          // 发送
```

**支持厂商**：Intel (1G/10G/25G/40G/100G)、Mellanox/NVIDIA (ConnectX 系列)、Broadcom、Marvell、Netronome 等

### 3. Mempool (rte_mempool)

- 启动时预分配固定大小对象池
- 对象分布在所有 DRAM channel 上（channel/rank 对齐）
- 使用 ring 管理空闲对象
- 典型用法：mbuf pool

### 4. Mbuf (rte_mbuf)

数据包缓冲区结构体，设计关键点：

- 头部固定部分存放 metadata（port, VLAN, hash 等）
- 数据部分存放实际包内容
- 支持单段/多段链式 mbuf（jumbo frame）
- 零拷贝：仅传递指针（mempool 预分配，不动态分配）

### 5. Ring (rte_ring)

无锁环形队列，DPDK 最基础的数据结构：

- 单生产者单消费者 (SPSC)：无锁
- 多生产者多消费者 (MPMC)：CAS 原子操作
- 支持批量入队/出队，分摊 CAS 开销
- 所有分配在 ring 外的内存操作均为 lock-free
- 用于：数据包队列、消息传递、跨核通信

### 6. Timer (rte_timer)

基于 HPET/TSC 的精确定时器，用于周期性检查或超时管理。

## 包处理模型

### Run-to-Completion (RTC)
每个 lcore 独自完成收包 → 处理 → 发包全流程：
```
loop:
  rx_burst → process → tx_burst
```
**优点**：无锁，无跨核通信，性能最优
**缺点**：处理逻辑耦合

### Pipeline
将处理拆分为多个阶段，通过 ring 连接不同 lcore：
```
lcore0: rx → parser → ring1
lcore1: ring1 → classify → ring2
lcore2: ring2 → modify → tx
```
**优点**：灵活组合，模块化
**缺点**：跨核 ring 有 CAS 开销

## 内存模型

### Hugepage 技术

| 页面大小 | TLB 覆盖 | 典型配置 |
|---------|---------|---------|
| 4KB（默认） | 2MB/512 条 | 不适用于 DPDK |
| 2MB | 1GB/512 条 | 最常用 |
| 1GB | 512GB/512 条 | 大内存场景 |

性能收益：使用 2MB 页面比 4KB 页面性能提升 10-15%（TLB miss 大幅降低）。

### NUMA 感知

DPDK 在主核 (master lcore) 初始化时检测 NUMA 拓扑。每个 lcore 优先使用本地内存：

```
Socket 0 (NUMA node 0): lcore 0-7, 本地内存
Socket 1 (NUMA node 1): lcore 8-15, 本地内存
  ↓
mempool 创建时指定 socket_id
网卡挂在哪个 socket 就用哪个 socket 的内存
```

跨 NUMA 访问会导致 1.2-1.5x 延迟惩罚。

### IOVA (I/O Virtual Address)

DPDK 管理两种内存地址映射：
- **PA (Physical Address)**：物理地址，直接用于 DMA
- **VA (Virtual Address)**：虚拟地址，用户程序访问
- **IOVA mode**：PA mode（默认）或 VA mode（VFIO 场景）

## 性能特性

### 典型吞吐量

| 配置 | 吞吐量 (64B 包) |
|------|----------------|
| 单核 1x10GbE | ~14.88 Mpps（线速） |
| 8 核 1x40GbE | ~59.52 Mpps（线速） |
| 单核 1x100GbE | 受 PCIe 带宽限制 |

### 延迟

- PMD 轮询模式：接收到处理 < 100ns
- 完整 L2 forwarding：~1µs
- 远优于传统中断驱动方式（10-50µs）

### CPU 开销

- 轮询空队列时会空耗 CPU（~100% 核，即使无流量）
- 优化手段：`rte_eth_dev_rx_intr_enable` 在低流量时休眠
- 实践中通过 CPU 隔离 (isolcpus) 和 DPDK lcore 绑定避免影响其他进程

## 关键性能优化技术

| 技术 | 原理 | 收益 |
|------|------|------|
| Cache line 对齐 | 数据结构 64B 对齐避免 false sharing | 多核扩展性 |
| rte_prefetch0 | 提前加载数据到 L1 cache | 掩盖内存延迟 |
| Burst 处理 | 一次批量处理 32-64 包分摊函数调用 | 摊销控制逻辑开销 |
| 分支预测优化 | likely/unlikely 宏 | 减少流水线冲刷 |
| NUMA 本地内存 | lcore 绑本地内存 | 避免跨插槽延迟 |
| 无锁数据结构 | rte_ring / per-core 独立 | 消除锁竞争 |

## 生态系统项目

### 网络功能虚拟化 (NFV)

| 项目 | 角色 |
|------|------|
| FD.io/VPP | 高性能用户空间网络栈，L2-L4 转发 |
| OVS-DPDK | Open vSwitch 的 DPDK 数据路径 |
| OPNFV | 开源 NFV 平台集成 |
| SKYLB (京东) | 基于 DPDK 的 L4 负载均衡器 |

### 存储

| 项目 | 角色 |
|------|------|
| SPDK | 存储性能开发套件（NVMe over Fabrics） |
| ISA-L | Intel 存储加速库 |

### TCP/IP 协议栈

| 项目 | 方式 |
|------|------|
| F-Stack | DPDK + FreeBSD 协议栈 + POSIX API |
| TLDK | FD.io 的传输层开发套件 |
| Seastar | DPDK + 共享无状态 TCP/IP |
| mTCP | 多核 TCP 协议栈 |

### DPDK 与 Kubernetes

- **dpservice**：基于 DPDK 的 K8s 原生 SDN
- **SR-IOV + DPDK**：容器直接使用 VF，配合 DPDK pmd
- **AF_XDP PMD**：DPDK 通过 AF_XDP socket 使用 eBPF XDP 路径间接接管网卡（适用于云环境）

## 局限

- 独占网卡设备 —— 使用 PMD 的网卡对内核不可见（除非 KNI）
- 空轮询消耗 CPU —— 无流量时核依然 100% 运转
- 用户空间协议栈需自行实现（或依赖 F-Stack/VPP）
- 运维复杂度高 —— CPU 隔离、hugepage 配置、设备绑定
- 虚拟化环境中需 SR-IOV/直通，灵活性受限

## 开发指引

- [[entities/DPDK 开发实战]] — 环境搭建、l2fwd 示例、多核 pipeline、API 详解、调试与调优

## 参考来源

- [[sources/eBPF 调研来源]]
- [[synthesis/DPDK 与 eBPF XDP 技术对比]]
- [[synthesis/eBPF 技术全景]]
- [[concepts/XDP 高速数据路径]]
