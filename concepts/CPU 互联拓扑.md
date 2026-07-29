---
title: CPU 互联拓扑
category: concepts
tags: [cpu, interconnect, upi, cxl, snoop-filter, home-agent, numa, active]
created: 2026-07-29
updated: 2026-07-29
summary: >-
    CPU 到 CPU、CPU 到内存、CPU 到加速器的互联拓扑。Intel UPI（Ultra Path
    Interconnect）多路拓扑（Ring/Mesh/Grid）、Snoop Filter/HoMA 一致性协议、
    AMD GMI/xGMI/IF 互联、内存延迟 map 与负载均衡、NUMA 多跳延迟、
    CXL（Compute Express Link）协议栈（CXL.io/CXL.mem/CXL.cache）、
    PCIe Gen5/6 拓扑，面向数据面大系统内存布局的理解。
base_confidence: 0.85
lifecycle: draft
---

# CPU 互联拓扑

> 前置 [[concepts/CPU 核心架构]]（NUMA 拓扑基础），[[concepts/CPU Cache 高级优化]]（DDIO）。
> 本文聚焦 "核-核/核-内存/核-加速器" 之间的互联路径与延迟。

## 1. Intel Xeon 互联拓扑演进

```
Xeon E5 v3 (Haswell) → Ring Bus       2S
Xeon SP (Skylake)    → Mesh           2S-8S
Xeon SP (Ice Lake)   → Mesh + UPI     2S-8S
Xeon SP (Sapphire Rapids)→ Mesh + UPI 2S-8S
Xeon 6 (Granite Rapids) → Mesh + UPI  2S-8S
```

### 1.1 Ring Bus（旧）

```
┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐
│Core0│  │Core1│  │Core2│  │Core3│
├─────┤  ├─────┤  ├─────┤  ├─────┤
│L3   │  │L3   │  │L3   │  │L3   │
└──┬──┘  └──┬──┘  └──┬──┘  └──┬──┘
   └─────── Ring Bus ──────────┘
               │
               │  (cross-ring 延迟随核数线性增长)
         ┌─────▼─────┐
         │  Home Agent │ → 内存控制器
         └───────────┘
```

**缺点**：环上每增加一个核，最远跳数增加，延迟线性增长。12 核以上已不可扩展。

### 1.2 Mesh（现代）

```
                Col 0  Col 1  Col 2  Col 3
              ┌───────────────...
Row 0         │ Core0   Core1   Core2   Core3
              │ L3      L3      L3      L3
              ├────┬────┬────┬────┬─ ...
Row 1         │Core4│Core5│Core6│Core7│...
              │ L3  │ L3  │ L3  │ L3  │
              ├────┼────┼────┼────┼─ ...
Row 2         │ ...  ...  ...  ...  │
              ├────┴────┴────┴────┴─ ...
              │ Memory Controller (Col 0, 2)
              │ UPI Ports (Row 0, 3)
              └────────────────────
```

**Mesh 延迟公式**：
- 同 Row 邻接 Core：1 hop × ~10ns（LLC hit）
- 跨 Row + Col：|Δrow| + |Δcol| hops
- 到内存控制器：|row - MC_row| + |col - MC_col| hops
- 每 hop 约 10ns（频率 3GHz = 30 cy）

**实测**：
```bash
# Ice Lake 核心间延迟矩阵（通过 Intel MLC 或自写
./latency_test --core-pair 0,1       # 同 tile: ~40ns
./latency_test --core-pair 0,4       # 邻接: ~50ns
./latency_test --core-pair 0,15      # 对角: ~80ns
./latency_test --core-pair 0,30      # 最远: ~110ns
```

## 2. UPI（Ultra Path Interconnect）

### 2.1 多路拓扑

```
2S: UPI ×3 (每 CPU)
┌────────┐      ┌────────┐
│ CPU 0  │ ←UPI→ │ CPU 1  │
│ DDR0   │      │ DDR1   │
└────────┘      └────────┘

4S: UPI ×6 (每 CPU)
    ┌────────┐
    │ CPU 0  │
    ├──┬──┬──┤
    │  │  │  │
┌───▼┐│  │  │┌───▼──┐
│CPU1││  │  ││CPU 3 │
│    ││  │  ││      │
└───┬┘│  │  │└───┬──┘
    │  │  │  │    │
    │  ├──▼──┤    │
    │  │CPU2 │    │
    │  └─────┘    │
    └─────────────┘
    （全互联 Mesh 拓扑）
```

### 2.2 UPI 参数

| 代际 | 速率 (GT/s) | 带宽 (单向) | 每链路延迟 |
|------|-----------|-----------|----------|
| Skylake SP | 10.4 GT/s | ~21 GB/s | ~20ns |
| Ice Lake SP | 11.2 GT/s | ~22 GB/s | ~20ns |
| Sapphire Rapids | 16 GT/s | ~33 GB/s | ~15ns |
| Granite Rapids | 20 GT/s | ~40 GB/s | ~15ns |

```bash
# 查看 UPI 拓扑
numactl --hardware

# 本 CPU 内存域
lstopo --no-io --no-legend

# 检查 UPI 速率
dmesg | grep "UPI" | grep "speed"
# [    0.123456] CPU0: UPI speed 11.2 GT/s

# 跨 socket 延迟（大概率延迟 x2）
mlc --idle_latency -l256 -c1   # local 延迟
mlc --idle_latency -l256 -R    # remote 延迟
```

### 2.3 Snoop 协议模式

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| **Early Snoop** | 请求先查询 snoop filter 再发到 Home Agent | 低延迟敏感（数据库） |
| **Home Snoop** | 请求经过 Home Agent 仲裁，不查 snoop filter | 高带宽（HPC） |
| **Cluster on Die (COD)** | 把多 Die 视为一个 NUMA domain | Intel SKX 多 Die 场景 |
| **SNC (Sub-NUMA Clustering)** | 将 LLC 分组为多个簇，降低延迟 | 数据面推荐 |

**SNC** 是目前 Intel Xeon 数据面的推荐配置：
```
SNC=2 模式（每个 Socket 分成 2 个 NUMA domain）：
Socket 0 → NUMA 0 (cores 0-7) + NUMA 1 (cores 8-15)
Socket 1 → NUMA 2 (cores 16-23) + NUMA 3 (cores 24-31)
好处：LLC 切片后延迟降约 20%，带宽改约 15%
```
**注意**：必须确认 DPDK 应用支持 SNC（需等分 core + 绑同 SNC 内）

## 3. AMD 互联模型

```
AMD EPYC (Zen 2/3/4):
┌──────────┐   ┌──────────┐
│ CCD 0    │   │ CCD 1    │   ← 4-8 core / CCD
│ ┌──────┐ │   │ ┌──────┐ │
│ │Core0 │ │   │ │Core4 │ │
│ │Core1 │ │   │ │Core5 │ │
│ │  ... │ │   │ │  ... │ │
│ └──────┘ │   │ └──────┘ │
└────┬─────┘   └────┬─────┘
     │ xGMI         │ xGMI
┌────▼──────────────▼─────┐
│     I/O Die (IOD)        │
│   (Memory Controllers)   │
│   (PCIe / IF)            │
└──────────────────────────┘
```

- **CCD (Core Complex Die)**：含 4-8 个 Zen 核心 + 共享 L3
- **IOD (I/O Die)**：内存控制器、PCIe、Infinity Fabric 互联
- **xGMI**：CCD ↔ IOD 互联（~100 GB/s per link）
- **跨 CCD 延迟**：~80ns vs 同 CCD ~20ns
- **跨 Socket**：~150ns

```bash
# AMD 拓扑查看
lscpu | grep "Model name\|NUMA"
# Thread(s) per core: 2
# Core(s) per socket: 64
# Socket(s): 2
# NUMA node0 CPU(s): 0-31,64-95
# NUMA node1 CPU(s): 32-63,96-127

# CCD 分组（Zen 4：8 core / CCD）
# NUMA node 0 可能存在 8 个 CCD，跨 CCD 延迟差异明显

# 跨 CCD 访问模型：
# 同 CCD（0-3 之间）→ L3 hit ~40 cy
# 同 Socket 跨 CCD → 跨 xGMI ~80cy
# 跨 Socket → 跨 IF + UPI ~150cy
```

## 4. CXL（Compute Express Link）

### 4.1 协议栈

```
CXL 基于 PCIe Gen5/6 物理层，增加三个上层协议：

┌──────────────────────────────────────────────────┐
│ CXL.io  (PCIe 兼容) I/O 语义                       │
│ - 设备枚举、配置空间、DMA、MSI-X                    │
│ - 等同于 PCIe 事务层                               │
├──────────────────────────────────────────────────┤
│ CXL.mem (内存语义)                                 │
│ - CPU 直接 load/store 远端内存                     │
│ - 类似 NUMA 但更细粒度（64B cache line 粒度）       │
│ - 支持内存池化、内存扩展                             │
├──────────────────────────────────────────────────┤
│ CXL.cache (缓存语义)                               │
│ - 设备缓存 CPU 内存行的 snoop 请求                   │
│ - 加速器可直接缓存和修改主存                         │
│ - 对数据面：网卡/FPGA 直接缓存 mbuf                │
└──────────────────────────────────────────────────┘
```

### 4.2 CXL 类型

| 类型 | 协议 | 用途 | 延迟 |
|------|------|------|------|
| Type 1 | CXL.io + CXL.cache | Smart NIC, 加速器 | ~100ns (cache) |
| Type 2 | CXL.io + CXL.mem + CXL.cache | GPU, FPGA | ~100ns (mem) |
| Type 3 | CXL.io + CXL.mem | 内存扩展（CXL 内存） | ~160-200ns (1 hop) |

### 4.3 对数据面的影响

```
传统：
CPU ←→ DDR4/5 (100ns)
  ↓
PCIe ←→ NIC (1μs+ DMA)

CXL 场景 1：内存扩展
CPU ←→ CXL Type 3 内存池 (200ns)
→ 可用于大流表（正常 8MB LLC 不够，扩展到 CXL 内存上）→ 延迟比 DRAM 高但可接受

CXL 场景 2：SmartNIC
CPU ← CXL.cache → SmartNIC (100ns)
→ 网卡直接缓存接收队列描述符到本地，无需 PCIe round-trip
→ 降低 30-50% packet 接收延迟

CXL 场景 3：加速器共享内存
CPU + FPGA 共享同一内存语义访问
→ FPGA 做正则匹配/加密，CPU 直接读结果
→ 无 PCIe 驱动开销（不需要 copy / MMIO）
```

## 5. 内存延迟 Map

```bash
#!/bin/bash
# core-latency-map.sh — 生成核心间延迟矩阵（用 Intel MLC 或自写 pingpong）

# 用 mlc 测延迟
sudo mlc --latency_matrix | grep "000000"
# 输出 64×64 矩阵（0-63 core），每单元格 = 延迟 ns

# 解读要点：
# - 对角线上 = 同核心（L1/L2 命中）
# - 同 Socket 邻接 = 同 LLC 片
# - 同 Socket 最远 = mesh 对角
# - 跨 Socket = UPI 一跳
# - 最坏延迟 / 最好延迟 ≤ 2 为正常

# 简化版：单 Socket 从 core0 到所有 core
for target in $(seq 0 31); do
    lat=$(mlc --idle_latency -l$target -c0 2>/dev/null | \
          grep "idle_latency" | awk '{print $NF}')
    echo "Core 0 → Core $target: ${lat}ns"
done
```

**参考延迟值（Ice Lake Xeon 2S）**：

| 路径 | 延迟 (ns) | cycles (3GHz) |
|------|----------|---------------|
| L1 hit | ~1 | 4 |
| L2 hit | ~4 | 12 |
| L3 hit (local tile) | ~10 | 30 |
| L3 hit (mesh 1 hop) | ~20 | 60 |
| L3 hit (mesh 4 hop) | ~50 | 150 |
| DRAM (local NUMA) | ~100 | 300 |
| DRAM (remote NUMA) | ~160 | 480 |
| DRAM (cross socket) | ~190 | 570 |
| CXL (Type 3, 1 hop) | ~180 | 540 |

## 6. 数据面部署策略总结

| 场景 | 推荐互联配置 | 原因 |
|------|------------|------|
| 高吞吐 100G | 同 Socket + SNC=2 | 最小化 mesh hop 延迟 |
| 多线程流表 | 同 CCD/同 SNC | 共享 L3 减少跨片访问 |
| 双路 NFV | pin vCPU 到同 Socket | 避免跨 UPI 延迟 2x |
| 大量内存（>1TB） | 启动 SNC + 启用 CXL | 扩展内存带宽 |
| SmartNIC | 启用 CXL.cache | 零拷贝包提交 |
| NUMA 不平衡 | 检查 BIOS NUMA 配置 | 内存通道对称均衡 |

```bash
# 内核视角验证互联
numastat -c                          # NUMA 命中/Miss
cat /sys/devices/system/cpu/cpu*/topology/die_id | sort -u  # 每个 Die 的核
lstopo --no-io --no-legend -l 1     # 拓扑可视化
```

## 参考来源

- [[concepts/CPU 核心架构]]
- [[concepts/CPU Cache 高级优化]]
- Intel Xeon Processor Scalable Family Specification Update
- AMD Zen 4 Core / CCD / IOD Architecture Docs
- CXL Consortium Specification (Rev 3.1)
- Intel MLC (Memory Latency Checker) 工具文档
