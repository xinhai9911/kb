---
title: XDP 高速数据路径
category: concepts
tags: [ebpf, xdp, networking, ddos, load-balancer]
created: 2026-07-29
updated: 2026-07-29
summary: XDP (eXpress Data Path) — 在网卡驱动层以纳秒级处理数据包的 eBPF 框架
base_confidence: 0.80
lifecycle: draft
lifecycle_changed: 2026-07-29
sources:
  - sources/eBPF 调研来源
---

# XDP 高速数据路径

## 概述

XDP (eXpress Data Path) 是 Linux 内核最快的包处理路径。eBPF 程序在网卡驱动层（分配 skb 之前）直接运行，以纳秒级处理数据包。XDP 是 eBPF 网络应用的基石。

## 架构位置

```
网卡硬件
  ↓ DMA
驱动 RX 队列
  ↓
[XDP 程序]         ← 最佳处理点：skb 尚未分配
  ↓ (XDP_PASS / XDP_DROP / XDP_TX / XDP_REDIRECT)
  ↓
SKB 分配
  ↓
内核网络栈 (TCP/IP)
  ↓
应用层 socket
```

## 五个返回动作

| 动作 | 含义 | 典型用例 |
|------|------|---------|
| XDP_PASS | 继续到内核网络栈 | 正常流量放行 |
| XDP_DROP | 丢弃包（不分配 skb） | DDoS 过滤，纳秒级丢弃 |
| XDP_TX | 从接收到的网卡原路转发 | 负载均衡器反弹 |
| XDP_REDIRECT | 转发到其他网卡/CPU/用户空间 | 内核旁路、AF_XDP |
| XDP_ABORTED | 程序错误（触发 tracepoint） | 调试用 |

## 三种运行模式

| 模式 | 机制 | 性能 | 支持 |
|------|------|------|------|
| **Native XDP** | 驱动内置支持，NDO 在 RX 路径中 | 最快 (< 50 ns) | ixgbe、i40e、mlx5、bnxt、nfp 等 |
| **Offloaded XDP** | 卸载到 SmartNIC 硬件 | 最快（硬件加速） | Netronome nfp、部分 Mellanox BlueField |
| **Generic XDP** | 内核软件模拟（skb 分配后） | 较慢 (~200 ns) | 所有网卡，仅调试 |

## 关键特性

### Direct DMA 访问
XDP 程序直接操作 DMA 映射的内存（`xdp_buff`），包含 `data`、`data_end`、`data_meta` 指针：
- 读包头：`data + offset`
- 修改包头：`bpf_xdp_adjust_head()` / `bpf_xdp_adjust_tail()`
- 元数据：`bpf_xdp_adjust_meta()` （在包前预留元数据区）

### XDP metadata kfuncs（6.4+）
从网卡硬件获取链路上元数据，无需解析包：
- `bpf_xdp_metadata_rx_timestamp` — 硬件时间戳
- `bpf_xdp_metadata_rx_hash` — 流哈希（RSS）
- `bpf_xdp_metadata_rx_vlan_tag` — VLAN 标签

### AF_XDP (XSK)
- 用户空间通过 AF_XDP socket 直接读取/写入 DMA 缓冲区
- 零拷贝路径：网卡 DMA → 用户空间（跳过内核网络栈）
- 需要 `BPF_MAP_TYPE_XSKMAP` 将 XDP 程序绑定到 AF_XDP socket
- 适用场景：DPDK 替代品，但保留内核驱动管理

### CPUMAP / DEVMAP
- **CPUMAP (BPF_MAP_TYPE_CPUMAP)**：将包重定向到指定 CPU 处理
- **DEVMAP (BPF_MAP_TYPE_DEVMAP)**：将包重定向到其他网卡接口
- 实现跨 CPU 核负载均摊和多网卡汇聚

## 生产案例

### Cloudflare — DDoS 防御
- L4Drop 在驱动层用 3 条 XDP 规则过滤 IP 黑名单
- 处理 10M+ pps 单机，过滤 7 Tbps 以上的 DDoS 攻击
- 相比 iptables 节省 10 倍 CPU
- 降低基础设施成本 30%

### Meta (Facebook) — Katran L4 负载均衡
- 基于 XDP 的开源 L4 负载均衡器
- 单机支持 ~200 Gbps 流量
- 每个进入 Meta 数据中心的包经 Katran 处理（2017 年起）
- 一致性哈希分发 → 最少连接备选

### LinkedIn — XDP 重构
- XDP 用 ~144 条 iptables 规则替代了 125,000 条
- 函数计算 (Lambda) 快照网络提升 20x
- 通过 XDP 批量操作替换了循环遍历

## 限制

- 需驱动层支持（Native XDP）—— 虚拟化环境中不可用（但 VMware vSphere 8+ 和 Hyper-V 2022+ 开始支持）
- 程序复杂度受验证器限制（栈 512B、指令 1M）
- 协议解析完全由程序员自己管理（验证器保证不越界）
- 包修改有限（不能改变包大小超出 headroom/tailroom）

## 参考来源

- [[sources/eBPF 调研来源]]
- [[concepts/eBPF 核心架构]]
- [[concepts/eBPF 程序类型与全挂载点]]
- [[synthesis/eBPF 技术全景]]
