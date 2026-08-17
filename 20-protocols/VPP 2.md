---
aliases: ["vpp"]
title: VPP 知识（Vector Packet Processing）
tags: [protocol, vpp, networking, dpdk, active]
created: 2026-07-29
summary: >-
    VPP（Vector Packet Processing）是 FD.io 开源的高性能用户态网络数据面框架，基于 VLIB 向量化节点图架构，单核可达数十 Mpps。本文梳理其核心概念、架构、节点图机制与适用场景。
category: reference
updated: 2026-07-29
sources: []
base_confidence: 0.85
lifecycle: reviewed
---

# VPP 知识（Vector Packet Processing）

## 概述

VPP（Vector Packet Processing）是 Linux 基金会 FD.io 项目下的高性能、可编程、用户态网络数据面（dataplane）框架，源自 Cisco 的 VPP 技术（曾用于 CRS-1 等路由平台）。它不是内核协议栈，而是一套独立运行在用户态的**包处理逻辑框架**，常通过 DPDK / AF_XDP / 内核网卡接口收发包。

> 与 [[50-reference/VPP 用法|VPP 使用方法]] 互补：本文讲"是什么 / 为什么"，那边讲"怎么用"。

## 核心概念

### 1. 向量化（Vector）处理 —— 与标量处理的区别

传统网络栈（如内核 `netfilter`、多数 DPDK 程序）是**标量（scalar）/ 逐包**处理：每来一个包就走完整个流水线。VPP 是**向量化**处理：

- 一次从 RX 队列取出一批包（一个 *vector*，默认最多 256 个，由 `VLIB_FRAME_SIZE` 决定），组成一个包数组。
- 这一批包**整体**流经每个处理节点（node），到达一个节点时，循环处理整批包，再交给下一个节点。
- 好处：指令缓存（I-cache）命中率高、分支预测友好、跨包可批量化（SIMD）、函数调用开销被摊薄。

### 2. VLIB 节点图（Node Graph）

VPP 的处理流水线是一张有向图，每个处理单元是一个 **node**：

- 每个 node 有一个 `function`，签名形如 `vlib_node_function_t`，输入是 `vlib_frame_t`（含一批包的索引）。
- node 之间通过 **next-node 索引** 连接；一个 node 处理完后，给每个包打上"下一跳 node"的索引，整批交给下一节点。
- 图由 `vlib_register_node` + `VLIB_REGISTER_NODE` 宏注册，启动时由 `vlib_node_main` 解析依赖并拓扑排序。

常见内置 node 类型：
- `VLIB_NODE_TYPE_INTERNAL` —— 内部处理节点（如 `ip4-input`、`ethernet-input`）。
- `VLIB_NODE_TYPE_INPUT` —— 收包入口（如 DPDK 的 `dpdk-input`），驱动整张图"转动"。
- `VLIB_NODE_TYPE_PROCESS` —— 协作式多任务协程（见下），如 `flowtable-clear-process`（参见 NPP 的 [[50-reference/NPP 定时器 机制|定时触发机制]]）。
- `VLIB_NODE_TYPE_PRE_INPUT` —— 在所有 input 之前运行。

### 3. 协作式多任务（Process Node / vlib_process）

VPP 是**单线程、协作式、无抢占**的事件循环（per worker thread）。所谓"进程"是 VPP 自己实现的协程：

- 用 `vlib_process_create` 创建，内部是一个 `while(1){ ... wait_for_event_or_clock(timeout); ... }` 的协程体。
- 通过 `vlib_process_wait_for_event / vlib_process_signal_event` 实现等待/唤醒，或 `vlib_process_suspend` 让出 CPU。
- 因为非抢占，写 process node 时**不能阻塞、不能长时间占用 CPU**，否则会卡住整个数据面。

### 4. 缓冲管理（Buffer / BVI）

- 收包时，每个包分配一个 `vlib_buffer_t`（含头部元信息 + 包数据区），包数据默认驻留在**巨页（hugepage）**内存池（`vlib_buffer_main`）。
- 所有 node 之间传递的是**包索引**（buffer index，32 位），不是指针拷贝，零拷贝。
- 支持 **buffer chaining**：巨型包用多个 buffer 链表拼接。

### 5. 多线程模型

- **Worker 线程**：每个 worker 绑定一个核，跑一份独立的节点图（线程局部），通过 RSS / 流哈希把不同流分到不同 worker，避免锁。
- **Main 线程**：处理控制面（CLI、API、插件加载）。
- **读写锁 / 无锁结构**：数据面尽量无锁；控制面变更配置时通过 `barrier` 让 worker 在节点边界安全切换。

## 架构分层

```
┌──────────────────────────────────────────────┐
│              VPP 用户态进程 (vpp_main)          │
│                                                │
│  ┌──────────┐   ┌──────────────┐  ┌─────────┐ │
│  │ 插件层    │   │  VLIB 节点图   │  │ API/CLI │ │
│  │ plugins/ │──▶│ (dataplane)   │◀─│ 控制面   │ │
│  └──────────┘   └──────────────┘  └─────────┘ │
│         │                  │                   │
│  ┌──────▼──────┐   ┌───────▼──────┐            │
│  │ VNET 层      │   │ 缓冲/内存管理  │            │
│  │ 接口/路由/FIB│   │ (hugepages)   │            │
│  └─────────────┘   └──────────────┘            │
└───────────────────────┬────────────────────────┘
                        │ (PMD / AF_XDP / tun)
              ┌─────────▼─────────┐
              │  DPDK / NIC 驱动   │
              └───────────────────┘
```

- **VNET 层**：提供接口抽象、`ip4/v6` FIB、邻接表（adjacency）、ARP/ND、隧道（GRE/VXLAN/IPIP）等网络功能。上层功能（NAT、ACL、路由协议）都建立在 VNET 之上。
- **VPP 本身是框架**：很多功能以**插件（plugin）**形式存在（`.so` 动态加载，位于 `plugin_path`），如 `nat_plugin.so`、`acl_plugin.so`、`dpdk_plugin.so`。

## 关键性能特征

- 单核典型转发能力：**数十 Mpps**（小包），远低于内核栈的 ~1-2 Mpps。
- 性能来源：向量化、无锁 per-thread、巨页、轮询模式（PMD，无中断）、批处理、I-cache 友好。
- 延迟极低（微秒级），但代价是 CPU 100% 轮询占用。

## 与其它技术的关系

| 技术 | 关系 |
|---|---|
| DPDK | VPP 常用 DPDK 作为 PMD 收发包后端（也可选 AF_XDP / netmap / 内核 tun） |
| NPP | 本项目 [[50-reference/NPP 定时器 机制|NPP]] 即基于 VPP/VLIB 框架扩展插件 |
| 内核协议栈 | VPP 是旁路（bypass）内核栈的用户态替代，常用于 NFV、VNF、网关 |
| VPP vs OVS-DPDK | 二者都用户态高性能转发；VPP 更偏向路由/完整数据面框架，OVS 偏虚拟交换机 |

## 适用场景

- 软路由 / vRouter、CGNAT、BRAS、防火墙、负载均衡（VPP 可作为底层）。
- NFV 环境中的 VNF 数据面。
- 高性能网关、隧道终结（VXLAN/GRE/IPIP）、SRv6 端点。
- 本项目中的 NPP 流表清洗、协议识别等（在 VPP 节点图里挂自定义 node/plugin）。

## 延伸

- 使用方法见 [[50-reference/VPP 用法|VPP 使用方法]]。
- FD.io 文档：<https://s3-docs.fd.io/>
- 源码：`git clone https://github.com/FDio/vpp`
