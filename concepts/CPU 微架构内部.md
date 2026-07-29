---
title: CPU 微架构内部
category: concepts
tags: [cpu, microarchitecture, rob, scheduler, execution-ports, uop-fusion, buffer, active]
created: 2026-07-29
updated: 2026-07-29
summary: >-
    CPU 微架构内部结构速查：ROB（Re-order Buffer）、调度器（Reservation
    Stations）、执行端口（Execution Ports）、Load/Store Buffer 深度、
    μOP Fusion/MacroFusion、Branch Predictor 内部（BTB/BHB/TAGE）、
    Prefetcher 内部状态机、Pipeline 气泡来源分析。
    面向性能调优的微架构概念——理解 PMC 事件触发的底层原因。
base_confidence: 0.8
lifecycle: draft
---

# CPU 微架构内部

> 前置 [[concepts/CPU 核心架构]]（流水线/Cache）。本文进入微架构更底层——ROB、调度器、端口压力、μOP Fusion 等。
> 理解这些概念才能真正读懂 PMC 事件（如 `uops_retired` → `idq_uops_not_delivered` 等）。

## 1. 现代 OoO 流水线（以 Intel Golden Cove P-core 为例）

```
取指     解码    μOP队列   分配/重命名   调度    执行     提交
┌────┐  ┌───┐  ┌──────┐  ┌─────────┐  ┌───┐  ┌───┐  ┌────┐
│ L1I │→│Dec │→│IDQ   │→│Alloc    │→│RS  │→│Port│→│ROB │
│ ITLB│  │6→8│  │(μOP  │ │(RAT)    │  │(97)│  │0-5│  │(512│
│ BPU │  │µFus│ │queue)│ │(ROB 512)│  │    │  │   │  │entry│
└────┘  └───┘  └──────┘  └─────────┘  └───┘  └───┘  └────┘
                                                     ↓
                                                  Store Buffer
                                                  ┌──────────┐
                                                  │L1D (32KB)│
                                                  └──────────┘
```

### 1.1 关键结构深度（Golden Cove）

| 结构 | 深度 | 说明 |
|------|------|------|
| ROB (Re-order Buffer) | 512 entries | 乱序执行的提交窗口 |
| Reservation Station (RS) | 97 entries | 等待发射的 μOP |
| Load Buffer | 72 entries | 未完成的 load |
| Store Buffer | 56 entries | 未提交的 store |
| IDQ (μOP Queue) | 108 entries | 解码后等待分配 |
| L1I Cache | 64KB | 指令 cache |
| L1D Cache | 48KB | 数据 cache（12-way） |
| μOP Cache | 2.25K entries | 解码后的 μOP 缓存（≈8K uops） |
| L2 TLB | 5K entries (4K) + 2K (2M) | 第二级 TLB |
| Branch Predictor | BTB ~5K entries | 分支预测目标缓冲区 |

### 1.2 各代 Intel 微架构比较

| 架构 | 发行 | ROB | RS | Load Buf | Store Buf | 端口 | 解码宽度 |
|------|------|-----|----|---------|----------|------|---------|
| Skylake (P-core) | 2015 | 224 | 97 | 72 | 56 | 8 | 4→6 |
| Sunny Cove | 2019 | 352 | — | 128 | 72 | 10 | 5→6 |
| Golden Cove | 2021 | 512 | 97 | 72 | 56 | 12 | 6→8 |
| Redwood Cove | 2023 | 512+ | — | — | — | 12+ | 6→8 |
| Crestmont (E-core) | 2023 | ~64 | — | — | — | ~6 | 3 |

## 2. μOP Fusion / MacroFusion

```
// === MacroFusion（宏融合）：两条指令合并为 1 条 μOP ===
// 条件分支跟在比较操作后
cmp  eax, 1    // 执行端口  0/1/5
jne  .label    // 执行端口  6 (分支)
// → 合并为一条 μOP（cmp + jne 成对运作）
// 提高解码效率和分支预测精度

// === μOP Fusion（微融合）：多个 μOP 执行时合并 ===
// 常用在 load + op 组合
add  eax, [mem]  // 拆为 load + add
// 在 RS 中作为 1 个 entry，发射时拆为 2 个 μOP
// 增加 RS 有效利用率

// === 数据面影响 ===
// - 热路径中宏融合可减少 10-15% 指令数
// - perf event: uops_retired.macro_fused
perf stat -e uops_retired.macro_fused,...
```

## 3. 执行端口竞争

### Golden Cove 端口图

```
Port 0: ALU, Shift, Branch2, Vector FMA, Vector Mul, Divide
Port 1: ALU, LEA, Vector FMA, Vector Add, Vector Shuffle
Port 2: Load (256-bit), Address Generation
Port 3: Load (256-bit), Address Generation
Port 4: Store Data
Port 5: ALU, Shuffle, Vector Logical, Fast LEA
Port 6: ALU, Shift, Branch1
Port 7: Store Address (AGU)
Port 8: ALU, Shift (新增 — 第二算术端口)
Port 9: Store Data (512-bit)
Port 10: Load (512-bit)
Port 11: Load (512-bit)
```

```c
// 端口瓶颈分析
// 场景 1：大量加法 → port 0/1/5/8 竞争
for (i = 0; i < n; i++) sum += data[i];  // add 在 port 0/1/5/8

// 场景 2：大量 load → port 2/3/10/11 竞争
for (i = 0; i < n; i++) {                // 每个 iter 至少 1 load
    tmp = data[i];                         // 占 load 端口
}

// 场景 3：混合 load+store + ALU
// 在数据面常见：解析包头（load）+ 修改（ALU）+ 写回（store）
// 三个流竞争不同端口，最佳情况是均匀分布
```

```bash
# 端口压力分析
perf stat -e uops_dispatched_port.port_0,\
    uops_dispatched_port.port_1,\
    uops_dispatched_port.port_2,\
    uops_dispatched_port.port_3,\
    uops_dispatched_port.port_4,\
    uops_dispatched_port.port_5,\
    uops_dispatched_port.port_6 \
    -p $DPDK_PID -- sleep 5

# 解读：
# port_2 + port_3 占比高 → 内存读取瓶颈
# port_4 占比高 → 大量写操作（有 false sharing？）
# port_0/1/5/6 占比均匀 → ALU 分布好
# 单个端口超过 40% → 可能成为瓶颈
```

## 4. ROB 与 RS 压力

```bash
# === ROB 利用率 ===
# uops_retired.slots  vs  uops_issued.any
# 高差值 → 前端取指跟不上执行

perf stat -e uops_retired.slots,uops_issued.any \
    -p $DPDK_PID -- sleep 5

# === RS 满导致 stall → IDQ_UOPS_NOT_DELIVERED ===
# 后端执行慢 → RS 不释放 → 解码 stall
# 表示后端才是瓶颈（而非前端取指）
perf stat -e idq_uops_not_delivered.core \
    -p $DPDK_PID -- sleep 5

# === ROB 全满 → ALLOC_STALL ===
# = 没有 ROB entry 可用
# 表示乱序窗口不够（通常是因为长延迟指令堵住 ROB）
# 如：L3 miss → 等待 300cy → 占 ROB 300cy
perf stat -e resource_stalls.any,resource_stalls.rob \
    -p $DPDK_PID -- sleep 5
```

## 5. Load / Store Buffer 压力

```bash
# === Load Buffer 满 ===
# 无法发出新的 load → 流水线 stall
# 原因：cache miss 的 load 长期占用 LB
perf stat -e ld_blocks.store_forward,load_hit_pre.sw_pf \
    -p $DPDK_PID -- sleep 5

# === Store Buffer 满 ===
# 无法提交新 store → ROB 不释放
# 原因：Store Buffer 等待 cache line 的 MESI 写权限
perf stat -e resource_stalls.sb \
    -p $DPDK_PID -- sleep 5

# === Store Forwarding ===
# Store 还未写到 L1D 时，后续 load 直接从 Store Buffer 拿数
# perf 事件：ld_blocks.store_forward > 0 → store-forwarding 冲突
# 延迟约 10cy（比 L1 hit 4cy 慢）
# 原因：load 地址与 store 地址部分重叠
```

## 6. Branch Predictor 内部

```
Branch 指令
    ↓
┌──────────────────┐
│ BTB (Branch      │ ← 根据 PC 查目标地址
│ Target Buffer)   │     Golden Cove: ~5K entries
├──────────────────┤
│ BHB (Branch      │ ← 用历史分支地址索引（解决别名冲突）
│ History Buffer)  │
├──────────────────┤
│ TAGE (Tagged     │ ← 多表预测器，用不同长度历史做预测
│ Geometric)       │     -> ITTAGE (无条件跳转)
├──────────────────┤
│ Loop Detector    │ ← 检测小循环（<64 iter）
├──────────────────┤
│ Stat Corr (SC)   │ ← 静态预测
└──────────────────┘
    ↓
预测方向 + 目标地址
```

**数据面相关**：
- VPP 中将 `if-else` 拆成独立 node 后，每个 node 的 TAGE 预测器可以专门学习该 node 的 pattern
- 循环中的分支：Loop Detector 在 <64 次迭代时可完全消除分支预测代价
- BTB 别名冲突：当热路径分支指令过多时，BTB 可能互相覆盖

## 7. Pipeline Bubble 最终溯源

| 问题 | PMC 事件 | 根源 |
|------|---------|------|
| 前端 stall | `idq_uops_not_delivered` | I-cache miss / ITLB miss / 解码瓶颈 |
| 后端 stall | `resource_stalls.any` | ROB 满 / RS 满 / LB 满 / SB 满 |
| 内存瓶颈 | `mem_load_retired.l3_miss` | L3 miss 等待 DRAM |
| 分支预测错误 | `branch_mispredict_retired` | 预测器 pattern 改变 |
| 数据依赖 | `resource_stalls.sb` | Store Buffer 满（等待写权限） |
| 执行端口饱和 | `uops_dispatched_port.port_*` 高 | 代码中某种操作太密集 |

```bash
# 全量微架构健康检查
perf stat -e \
    cycles,instructions,\
    idq_uops_not_delivered.core,\
    resource_stalls.any,\
    resource_stalls.rob,\
    resource_stalls.sb,\
    ld_blocks.store_forward,\
    mem_load_retired.l3_miss,\
    branch_mispredict_retired,\
    uops_executed.core,\
    uops_retired.slots,\
    uops_retired.macro_fused \
    -p $DPDK_PID -- sleep 5

# 快速诊断：
# instructions/cycles = IPC
# idq_uops_not_delivered/cycles = 前端 stall 占比
# resource_stalls.any/cycles = 后端 stall 占比
```

## 参考来源

- [[concepts/CPU 核心架构]]
- [[entities/CPU 性能分析实战]]
- Intel Optimization Reference Manual (Appendix B: Microarchitecture)
- Intel 64 and IA-32 Architecture Developer's Manual Vol.3C (PMC events)
- Agner Fog's Microarchitecture documentation
- WikiChip: Golden Cove / Zen 5 microarchitecture
