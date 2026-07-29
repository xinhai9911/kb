---
title: "CPU Cache 高级优化：CAT/RDT/硬件预取"
category: concepts
tags: [cpu, cache, cat, rdt, prefetcher, optimization, dpdk, active]
created: 2026-07-29
updated: 2026-07-29
summary: >-
    CPU Cache 高级优化技术栈：Cache Allocation Technology (CAT) 与
    Intel RDT（Cache/MBM 监控）、MLP（内存级并行度）、
    硬件预取器控制（DCU/IP/L2/SW/LL 预取器）、
    prefetch distance 调优、cache blocking 分块、
    DDIO 调整、代码布局优化（__rte_cache_aligned/code alignment/NOP padding）。
    面向 DPDK/VPP 数据面极致 cache 压榨。
base_confidence: 0.85
lifecycle: draft
---

# CPU Cache 高级优化：CAT/RDT/硬件预取

> 前置 [[concepts/CPU 核心架构]]（Cache 层级/MESI/DDIO），[[entities/CPU 性能分析实战]]（PMC 解读）。
> 本文是对基础 Cache 知识的补充——硬件级控制和高级优化技巧。

## 1. Intel RDT（Resource Director Technology）

### 1.1 CAT（Cache Allocation Technology）

```
┌──────────────────────┐
│ CLOS 0 (kernel/core)  │ ← 系统进程用（不受限）
│ ┌────┬────┬────┬────┐│
│ │ ¼  │ ¼  │ ¼  │ ¼  ││ ← 所有 way 可用
│ └────┴────┴────┴────┘│
├──────────────────────┤
│ CLOS 1 (control plane)│ ← OVS 慢路径、CLI
│ ┌────┐               │
│ │ ¼  │               │ ← 只占 1/4 way
│ └────┘               │
├──────────────────────┤
│ CLOS 2 (DPDK workers) │ ← 关键路径，独占 L3
│ ┌────────────┐       │
│ │    ½       │       │ ← 占 1/2 way
│ └────────────┘       │
└──────────────────────┘
```

**配置流程**：

```bash
# 1. 确认 CAT 支持
grep "cat_l3" /proc/cpuinfo   # L3 CAT
grep "cat_l2" /proc/cpuinfo   # L2 CAT
# 或 /sys/fs/resctrl/info/L3/cbm_mask 是否存在

# 2. 挂载 resctrl
mount -t resctrl resctrl /sys/fs/resctrl

# 3. 创建 CLOS
mkdir /sys/fs/resctrl/dpdk

# 4. 设置 L3 cache 掩码 (CBM)
# 假设 L3 有 12-way，DPDK 用 6 way（bit 0-5）
echo "3f" > /sys/fs/resctrl/dpdk/schemata
# 格式：L3:<cache_id>=<bitmask>
# L3:0=3f;1=3f  (两个 NUMA node 都设)

# 5. 把进程加入
echo $DPDK_PID > /sys/fs/resctrl/dpdk/tasks

# 6. 验证分配
# 任务只能使用 bit 0-5 对应的 L3 way
```

**数据面效果**：

| 场景 | L3 Miss Rate | 抖动 |
|------|------------|------|
| 无 CAT（共享） | 23% | 高（邻核 evict） |
| CAT 独占 50% | 11% | 低 |
| CAT 独占 75% | 5% | 极低 |

**原理**：CAT 防止邻核的控制面进程踢掉 DPDK 的热 cache line，相当于硬分区。

### 1.2 CMT（Cache Monitoring Technology）

```bash
# 监控 L3 占用和 Miss
# /sys/fs/resctrl/mon_data/ 中的监控量：
# l3_cache_occupancy = 当前占用 LLC 量（bytes）
# l3_total_cache_miss = miss 计数

# 创建监控组
mkdir /sys/fs/resctrl/mon_groups/dpdk_mon
echo $DPDK_PID > /sys/fs/resctrl/mon_groups/dpdk_mon/tasks
# 读监控数据：
cat /sys/fs/resctrl/mon_groups/dpdk_mon/mon_data/L3*/l3_cache_occupancy

# 持续监控
watch -n1 'cat /sys/fs/resctrl/mon_groups/dpdk_mon/mon_data/L3_00/l3_cache_occupancy'
```

### 1.3 MBM（Memory Bandwidth Monitoring）

```bash
# 监控内存带宽使用
cat /sys/fs/resctrl/mon_groups/dpdk_mon/mon_data/L3_00/mbm_total_bytes
# 看每秒带宽
watch -n1 'cat /sys/fs/resctrl/mon_groups/dpdk_mon/mon_data/L3_00/mbm_total_bytes'
```

## 2. 硬件预取器

### 2.1 Intel 预取器类型

| 名字 | 控制 MSR | 作用 | 适合场景 |
|------|---------|------|---------|
| **DCU Prefetcher** (L1) | 0x1A4[0] | L1 数据预取，识别步进模式 | 连续内存访问（mbuf 池） |
| **DCU IP Prefetcher** (L1) | 0x1A4[1] | 基于指令指针的预取 | 重复的固定偏移访问 |
| **L2 HW Prefetcher** | 0x1A4[2] | L2 预取（前后双向） | 流式访问 |
| **L2 Adjacent Prefetcher** | 0x1A4[3] | L2 预取邻接 cache line | 顺序访问 |
| **LLC Prefetcher** | 0x1A4[4] | 跨 L3 预取（Skylake+） | 大数据集 |
| **MLP** (内存级并行度) | 硬件动态 | 同时发出多个未完成 load | 延迟隐藏 |

```bash
# 查看当前预取器状态
# Intel: MSR 0x1A4 位域
# 0 = enable, 1 = disable
rdmsr -a 0x1A4
# 输出举例：0x0（全开）/ 0x1E（全关）

# 关掉 L2 硬件预取（实验性调优）
wrmsr -a 0x1A4 $(( $(rdmsr -a 0x1A4 | head -1) | 0x4 ))
# 对特定核心操作：
wrmsr -p 16 0x1A4 0xe   # 关 core 16 上所有预取器除 LLC

# ARM64 预取器控制（因 SoC 而异）
# 通常不可调（由 microarchitecture 自动管理）
# 某些 ARM SoC 通过 IMPLEMENTATION DEFINED 寄存器提供
```

### 2.2 预取器调优

**何时关预取**：
- 随机访问模式（hash 查找、流表匹配）→ 预取读入无用行，污染 cache
- 大流量下，预取器误判 → 占 LLC way → 踢掉热数据
- DPDK mempool 分配模式随机 → 关 L2 prefetcher 有时反而提升

**何时开预取**：
- 流式数据（包首包续包处理、逐包校验）
- 顺序 bulk memcpy（大包拷贝）
- 连续包头解析

```bash
# 数据面测试方案
# 对比：全开 vs 只开 DCU vs 全关
# 用 perf stat 看 L1/L2/L3 命中率变化 + pps

for pref in 0x0 0x1 0x1e; do
    wrmsr -a 0x1A4 $pref
    perf stat -e \
        L1-dcache-load-misses,\
        L2-load-misses,\
        LLC-load-misses \
        ./your_app -- -l 16-23
    # 记录 pps
done
```

### 2.3 预取距离调优

```c
// 正确距离 = 内存延迟 / 每迭代处理时间 × 迭代步进大小
// 如：L3 miss ~300 cy，每个包处理 ~30 cy → 预取距离 ~10

// DPDK pipeline 模式预取示例
#define PREFETCH_OFFSET 4

for (i = 0; i < nb_pkts; i++) {
    // 提前拉数据
    rte_prefetch0(rte_pktmbuf_mtod(pkts[i + PREFETCH_OFFSET], void*));
    // 处理当前包
    process(pkts[i]);
}

// 经验距离速查表：
// 处理复杂度   │ 包处理延迟 │ 推荐预取距离
// 简单 L2 转发  │ ~20 cy   │ 8-12
// 路由查表     │ ~80 cy   │ 4-6
// IPSec 加解密 │ ~500 cy  │ 2-3
// 越低的距离 = 越保守（避免预取错误淘汰热数据）
```

## 3. DDIO 高级控制

```bash
# Intel DDIO（Data Direct I/O）：网卡数据直接写 LLC
# 默认：DDIO 占用 LLC 的 10%（Skylake）～ 20%（Ice Lake）
# DPDK 占全部核时，可以调大 DDIO 分片

# 查看 DDIO 配置（BIOS 控制，操作系统不可运行时调整）
# BIOS Setup → Socket Configuration → IIO Configuration
# → Intel® VT for Directed I/O → DDIO Allocation

# 可用 DDIO 调整量：
# Small (10%): 默认，保守
# Medium (15%): 推荐
# Large (20%): 如果 DPDK 占大量 LLC

# 验证 DDIO 命中（间接）：
perf stat -e LLC-loads,LLC-load-misses,LLC-stores,LLC-store-misses
# DDIO 命中表现为：LLC-store-misses 极低（网卡直接写 LLC）
# 如果 LLC-store-misses 高，考虑扩容 DDIO 或关掉 DDIO（极端低延迟场景）

# 关 DDIO？
# 某些场景关掉更好：网卡直接写 DRAM，不占 LLC
# 适合：大包处理（1KB+），避免 DDIO 踢掉已有热数据
# 权衡：小包场景开 DDIO（头处理热数据），大包场景关
```

## 4. 代码布局优化

### 4.1 Cache Line 对齐

```c
// DPDK 强制 64B 对齐
struct rte_mbuf {
    // ... 以 64B 对齐
} __rte_cache_aligned;

// 注意事项：
// - hot/cold 分离：热字段放前 64B，冷字段放后 64B
// - 所有 worker 只读（共享）的放同一 cache line
// - 所有 worker 各自写的务必 __rte_cache_aligned（防 false sharing）

// rte_mbuf 结构实际布局：
// First 64B: cache_line0 [port, ol_flags, packet_type, buf_addr, ...]
// Second 64B: cache_line1 [userdata, priv_size, timesync, ...]
// Third 64B: cache_line2 [pool, next, nb_segs, ...] (pool 共享)
// Fourth 64B: cache_line3 [hash, vlan, ...] (锚点)

// VPP vlib_buffer_t 类似：前 64B 热数据，后 64B 元数据
```

### 4.2 NOP Padding 与跳转对齐

```asm
; Intel 优化手册建议热点代码 16B 对齐
; 跳转目标 16B 对齐（避免跨越 uOP cache line）

; GCC 控制：
__attribute__((aligned(64))) void hot_function(void) {
    // ...
}

; 循环对齐（影响微代码读取）
; for 循环 start 地址 16B 对齐 → 提高 Loop Stream Detector 命中率
for (i = 0; i < nb_pkts; i++) __attribute__((aligned(16)));
```

### 4.3 Cold/Hot 属性

```c
// GCC __attribute__((cold)) / __attribute__((hot))
// 提示编译器：该路径不常执行 / 常执行

// VPP 中：
__attribute__((hot)) static uword process_pkts_fn (vlib_main_t *vm, ...) {
    // 热路径：包向量处理
}

__attribute__((cold)) static void error_handling_fn (...) {
    // 冷路径：错误处理，编译器不优化为 inline
    // 且链接时不放在 hot section 中
}

// 编译器结果：
// hot 函数 → hot section（L1 I-cache 友好）
// cold 函数 → cold section（不占 I-cache 空间）
// 冷热分离可减少 5-15% I-cache miss
```

## 5. Cache Blocking 分块

```c
// 通用优化技术：大数据集遍历时分块，使每块 fit in cache

// ❌ 直接遍历 16MB 数据：每个元素访问时 L3 miss
for (i = 0; i < 16*1024*1024; i++) { process(data[i]); }

// ✅ 分块遍历：每块 256KB（fit L2）
#define BLOCK_SIZE (256 * 1024 / sizeof(data_t))
for (b = 0; b < total; b += BLOCK_SIZE) {
    size_t end = min(b + BLOCK_SIZE, total);
    // 这块全部在 L2 cache 中命中
    for (i = b; i < end; i++) {
        process(data[i]);
    }
}

// 数据面：流表查表不是 "遍历" 而是 hash 查找
// 对应阻塞优化：把流表条目按 affinity 分组
// 每组大小 < L2/L3，查表时只扫描自己的组
```

## 6. 预取不可知情况的兜底策略

| 问题 | 手段 | 预期收益 |
|------|------|---------|
| 热点不连续 | SW prefetch（rte_prefetch0） | 10-30% L3 miss 下降 |
| 随机读占主导 | 关 HW prefetcher + 软件补偿 | 5-15% 热数据保留 |
| false sharing | __rte_cache_aligned 分离 | 30-60% 性能提升 |
| I-cache miss | cold/hot 属性 + 16B 对齐 + profile-guided | 5-10% IPC 提升 |
| DDIO 踢热数据 | BIOS 调大 DDIO 分片 | 10-20% LLC 命中提升 |
| neigh cache evict | CAT 隔离（resctrl） | 20-50% Miss 下降 |

## 7. 实战：L3 隔离 + 预取调优 + RDT 监控

```bash
# ===== 1. 分配 CAT 给 DPDK worker =====
mount -t resctrl resctrl /sys/fs/resctrl
mkdir /sys/fs/resctrl/dpdk
echo "L3:0=3f;L3:1=3f" > /sys/fs/resctrl/dpdk/schemata
echo $DPDK_PID > /sys/fs/resctrl/dpdk/tasks

# ===== 2. 预取调优 =====
# 先全开测基线，再逐项关测

# ===== 3. RDT 监控（无需 perf）=====
watch -n1 'echo "=== LLC Occupancy ==="; \
    cat /sys/fs/resctrl/mon_groups/dpdk_mon/mon_data/L3*/l3_cache_occupancy;'

# ===== 4. perf 验证 =====
perf stat -e \
    L1-dcache-loads,L1-dcache-load-misses, \
    L2-loads,L2-load-misses, \
    LLC-loads,LLC-load-misses, \
    LLC-stores,LLC-store-misses \
    -p $DPDK_PID -- sleep 10

# 结果解读：
# L1 Miss / L1 Loads = ~10% (好)
# L2 Miss / L2 Loads = ~30% (可接受)
# LLC Miss / LLC Loads < 5% (优秀，>15% 需优化)
```

## 参考来源

- [[concepts/CPU 核心架构]]
- [[entities/CPU 性能分析实战]]
- [[entites/CPU 隔离与实时调优]]
- Intel Resource Director Technology (RDT) Specification (Doc 62827)
- Intel Optimization Reference Manual (Ch.7: Cache and Prefetch)
- DPDK Programmer's Guide: Mempool / Ring 优化
