---
title: CPU 中断模型与 MSI-X 亲和
category: entities
tags: [cpu, interrupt, msix, irq, affinity, dpdk, vpp, active]
created: 2026-07-29
updated: 2026-07-29
summary: >-
    x86/ARM64 中断模型深度：中断控制器拓扑（APIC/GIC）、
    MSI-X 的工作原理与配置、中断亲和性绑定、RSS 与多队列 IRQ 分配、
    DPDK 轮询 vs 中断模式选择、NAPI 与混合模型、
    irqbalance 配置、中断延迟测量、中断风暴排查。
    面向数据面实时性的完整中断管理方案。
base_confidence: 0.85
lifecycle: draft
---

# CPU 中断模型与 MSI-X 亲和

> 前置 [[concepts/CPU 核心架构]]（NUMA 拓扑），[[entities/CPU 隔离与实时调优]]（IRQ affinity）。
> 本文聚焦中断机制本身，而非隔离方案（已在隔离篇覆盖）。

## 1. 中断拓扑概览

```
x86 (APIC 体系)                     ARM (GIC 体系)
┌────────────┐                      ┌────────────┐
│   I/O APIC │← PCIe MSI/MSI-X     │   GICD     │← PCIe MSI (ITS)
│  (PCH/chip)│                      │(Distributor)│
└────┬───────┘                      └────┬────────┘
     │                                   │
┌────▼────────────────┐          ┌──────▼──────────┐
│ Local APIC (per-core)│          │  GICR (Redist)  │
│  + LVT (Local Vector)│          │  per-core / cluster
└────┬─────────────────┘          └──────┬──────────
     │  Interrupt                       │  IRQ
     ▼                                  ▼
  Core ISR                            Core IRQ handler
```

### x86 中断层级

| 层次 | 组件 | 说明 |
|------|------|------|
| 1 | IOAPIC | 桥片（PCH）中的中断控制器，处理旧引脚中断 |
| 2 | MSI/MSI-X | PCIe 设备直接写内存（写指定地址+数据）发给 Local APIC |
| 3 | Local APIC | 每个核一个，接收中断→查 IDT → 跳转 ISR |
| 4 | IDT | 中断描述符表，IRQ 号 → handler 函数指针 |

### ARM64 GIC 层级

| 层次 | 组件 | 说明 |
|------|------|------|
| 1 | GICD (Distributor) | 全局中断路由配置（SPI/PPI 转发） |
| 2 | ITS (Interrupt Translation Service) | MSI-X 翻译，PCIe 设备 → LPI 中断 |
| 3 | GICR (Redistributor) | per-core，产生 IRQ/FIQ 信号到 CPU 接口 |
| 4 | CPU Interface | M-Class 用 IRQ/FIQ，A-Class 用 IRQ + vGIC（虚拟化） |

## 2. MSI-X 详解

### 2.1 MSI vs MSI-X

| 特性 | MSI | MSI-X |
|------|-----|-------|
| 向量数 | 最多 32（PCI 限制） | 最多 2048（可配） |
| 表结构 | 固定 Message Address + Data | 独立表（BAR 中）每向量可独立配置 |
| 亲和性 | 所有中断共享 | 每向量可指定不同核 |
| per-vector mask | 不支持 | 支持（表中有 Mask 位） |

### 2.2 MSI-X 表结构

```
MSI-X Table 在 PCIe BAR 中：
┌──────────────────┐
│ Vector 0: Addr    │ ← 指向目标核 Local APIC
│        : Data     │ ← 中断号/优先级
│        : Mask     │ ← 1=屏蔽
├──────────────────┤
│ Vector 1: ...     │
├──────────────────┤
│ ...               │
├──────────────────┤
│ PBA (Pending Bit  │
│ Array)            │
└──────────────────┘

// Core target = Addr[20:12] (x86 APIC ID)
// 多队列网卡每个队列配一个 vector
```

### 2.3 配置 MSI-X 亲和

```bash
#!/bin/bash
# 设置网卡多队列 IRQ 亲和
# 假设 mlx5 网卡 8 队列，isolated cores: 0-7

DEV="mlx5_0"
NUM_QUEUES=8

for ((i=0; i<NUM_QUEUES; i++)); do
    # 找对应队列的 IRQ
    irq=$(grep "${DEV}-txrx-${i}" /proc/interrupts | awk '{print $1}' | tr -d :)
    if [[ -n "$irq" ]]; then
        # 绑到 core i
        echo "$i" | sudo tee /proc/irq/$irq/smp_affinity_list
    fi
done

# 查看网卡 MSI-X 向量数
grep -c "mlx5" /proc/interrupts   # 向量总数

# 查看 MSI-X 能力（lspci -vvv）
# Capabilities: [a0] MSI-X: Enable+ Count=32 Masked-
# Vector table: BAR=0 offset=00100000
# PBA: BAR=0 offset=00100800
```

### 2.4 DPDK/VPP 打断 MSI-X 亲和

DPDK PMD 接管网卡后会：
1. 关闭网卡中断（数据面纯轮询）
2. 把中断保留给控制面事件（link state change / error）
3. 控制面中断必须绑到 non-isolated 核

```bash
# DPDK 中断模式（非常用——仅控制面事件）
--interrupt-only   # DPDK 只通过中断收包（不使用轮询 PMD）

# VPP: 18.07+ 用 epoll 替代中断
# VPP worker 完全不依赖外部中断
# 只有 main thread 处理信号和事件 fd
```

## 3. 中断亲和脚本

```bash
#!/bin/bash
# set-irq-affinity.sh — 自动将设备所有 IRQ 绑到指定 core 范围

DEV_PATTERN="$1"    # 如 "mlx5|enp" 或 "mlx5_0"
CORE_RANGE="$2"     # 如 "0-15"

[[ -z "$DEV_PATTERN" || -z "$CORE_RANGE" ]] && {
    echo "Usage: $0 <device-pattern> <core-range>"
    echo "  e.g. $0 mlx5 0-15"
    exit 1
}

# 生成 core mask
# 解析 core_range 到 hex mask（或直接用 smp_affinity_list）

for irq_file in /proc/irq/*/smp_affinity_list; do
    desc=$(cat ${irq_file%/*}/affinity_hint 2>/dev/null || \
           cat ${irq_file%/*}/../name 2>/dev/null)
    [[ "$desc" =~ $DEV_PATTERN ]] || continue

    # 只在 non-isolated 范围内均匀分配
    echo "${CORE_RANGE}" | sudo tee "$irq_file" > /dev/null
done

# 验证
cat /proc/interrupts | head -30

# 优化均匀分配（每个队列轮询到一个核）：
# for i in $(seq 0 $((QUEUES-1))); do
#     core=$((START + (i % NUM_CORES)))
#     echo "$core" | sudo tee /proc/irq/${irqs[i]}/smp_affinity_list
# done
```

## 4. 轮询 vs 中断

| 模式 | 延迟 | 吞吐 | CPU 占用 | 适用场景 |
|------|------|------|---------|---------|
| 轮询 (PMD) | 稳定（无中断延迟） | 高（无中断开销） | 100%（独占核） | 高吞吐线速处理 |
| 中断 | 可变（+ISR 延迟） | 中（中断开销） | ~0%（空闲） | 控制面 / 管理面 |
| 混合 (NAPI) | 折中 | 高 | 动态 | Linux 内核网络栈 |
| 自适应中断 | 可调 | 可调 | 动态 | 不确定流量场景 |

### 4.1 中断延迟组成

```
PCIe MSI-X Write → IOAPIC → Local APIC → IDT Lookup → ISR Entry → EOI
├── 200ns ─┤├──── 100ns ──┤├─ 50ns ─┤├── 2μs-5μs (ISR body) ──┤

主要开销：
- 上下文切换（保存 regs / 恢复 regs）：~500 cy
- TLB/cache 污染（ISR 代码和数据）
- 中断屏蔽期间（cli/sti 或 IRQ disable）
- EOI 写回 APIC

实测：纯中断延迟 1-3μs（空 ISR）
       → 开始处理包：5-10μs（含 cache miss）
       → 轮询模式：0ns（不加额外延迟）
```

### 4.2 自适应中断 (DPDK L3FWD-Power)

```c
// DPDK empty poll 检测 + 按需切中断
// 低负载时：CPU 可进入 sleep / cstate
// 有包时：网卡中断唤醒

// rte_power_lib: 检测空转循环
// 连续 N 个空轮询 → pause core / 切中断
// 收到包中断 → resume polling

// 适用：控制面虚机（少量流量）或节能场景
// 不适用：线速转发场景（频繁切换反而更差）
```

## 5. IRQ 风暴与排查

```bash
# === 检测 IRQ 风暴 ===
# 看中断总数激增
watch -n1 'cat /proc/interrupts | awk "{sum+=\$2} END {print sum}"'

# 看哪个核中断最多
watch -n1 'cat /proc/interrupts | tail -1'

# 看哪个网卡队列中断最多
grep "mlx5" /proc/interrupts

# === 常见原因 ===
# 1. 广播/多播泛洪 → 网卡 broadcast 过滤
# 2. 网卡 RSS 不均 → 调整队列数或 indirection table
# 3. 中断合并 timeout 太小 → ethtool -C <dev> rx-usecs 50
# 4. 亲和不对 → 中断都打到同一个核

# === 中断合并调优 ===
ethtool -C enp179s0f0np0 \
    rx-usecs 1 \          # 收到包后等 1μs 再中断（0=关合并）
    rx-frames 1 \         # 1 帧即中断（不合并）
    tx-usecs 1 \
    tx-frames 1

# 数据面场景：关中断合并（DPDK 接管后自动关）
# 控制面场景：适当合并减少 CPU 开销
# adaptive-rx on: NetXtreme 自适应合并（不建议数据面）
```

## 6. 多队列 RSS 与 IRQ 映射

```
RX Queue 0 → MSI-X vec 0 → IRQ 134 → Core 0
RX Queue 1 → MSI-X vec 1 → IRQ 135 → Core 1
RX Queue 2 → MSI-X vec 2 → IRQ 136 → Core 2
...         → ...         → ...     → ...

# 查看 RSS indirection table
ethtool -x enp179s0f0np0
# RSS Hash 决定把包分到哪个队列
# indirection table 可调：偏向特定队列（特定核）

# 精确 RSS 控制
ethtool -X enp179s0f0np0 equal 8      # 8 队列均分
ethtool -X enp179s0f0np0 weight 0 0 0 1 1 1 1 1  # 不均分
ethtool -X enp179s0f0np0 start 0 equal 8         # 从队列 0 开始

# DPDK 不依赖 kernel RSS，PMD 自行管理
# VPP: rss node 做软件 RSS（灵活但稍慢）
```

## 7. ARM GIC 特有注意点

```bash
# ARM64 中断拓扑
cat /proc/interrupts | head -5

# ARM GIC ITS（MSI-X 翻译）限制：
# - LPI 中断不可路由到特定 core？需 ITS 配置
# - 部分 SoC 不支持 MSI-X（用 MSI 最多 32 vec）
# - SPI 中断可设置 affinity（/proc/irq/*/smp_affinity）

# 查看 GIC 类型
cat /proc/cpuinfo | grep "GIC:"*
# 或 dmesg | grep GIC
# GICv3 / GICv4 支持 MSI-X ITS
# GICv2 不支持 MSI-X（需 IOMMU 翻译）

# ARM64 下中断检查脚本
# 确认每个网卡队列 IRQ 是否均匀分布
for irq in $(grep -l "enp\|eth\|mlx" /proc/irq/*/name 2>/dev/null); do
    echo "$(cat $irq): $(cat ${irq}/smp_affinity_list)"
done
```

## 参考来源

- [[entities/CPU 隔离与实时调优]]
- [[concepts/CPU 核心架构]]
- Intel 64 and IA-32 Architectures Developer's Manual Vol.3A (APIC, MSI-X)
- ARM Generic Interrupt Controller Architecture Specification GICv3/v4
- DPDK EAL Interrupt Mode Documentation
- Linux kernel `Documentation/IRQ-affinity.rst`
