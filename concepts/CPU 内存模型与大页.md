---
title: CPU 内存模型与大页
category: concepts
tags: [cpu, memory-model, tlb, hugepages, store-buffer, memory-ordering, active]
created: 2026-07-29
updated: 2026-07-29
summary: >-
    CPU 内存子系统深度：内存类型（UC/WC/WB）、Store Buffer 与 Invalidate Queue、
    Memory Ordering（x86 TSO vs ARM）、Write Combining、Non-temporal 指令、
    Non-temporal Store、TLB 层级与 Page Walk、大页（2MB/1GB）、THP 与 hugetlbfs。
    面向 DPDK/VPP 无锁编程与高性能数据面的内存模型速查。
base_confidence: 0.85
lifecycle: draft
---

# CPU 内存模型与大页

> 前置 [[concepts/CPU 核心架构]]（Cache/MESI）。本文聚焦内存类型、store buffer 一致性、内存序与大页机制。
> 实战见 [[entities/CPU 隔离与实时调优]]。

## 1. 内存类型（PAT/MTRR）

x86 通过 PAT（Page Attribute Table）或 MTRR 为每个内存区域指定类型，决定了 CPU 如何跟这块内存交互：

| 类型 | 缩写 | 缓存行为 | 合并行为 | 用途 |
|------|------|---------|---------|------|
| **Write Back** | WB | 全缓存 | 允许 | 普通 RAM（默认） |
| **Write Combining** | WC | 不缓存 | 允许写合并 | 显存、NIC 门铃寄存器 |
| **Uncacheable** | UC | 不缓存 | 不合并 | MMIO / 控制寄存器 |
| **Write Through** | WT | 缓存 + 直写 | 不允许 | 历史遗留 |

### 1.1 WC（Write Combining）—— 对数据面的意义

```c
// NIC 发送描述符环（TX ring）通常映射为 WC 内存
// WC 特性：CPU 对连续地址的多次写，在 WC buffer 中合并为一次 PCIe 事务
volatile struct tx_desc *tx_ring = (volatile void *)mmap(NULL, size,
    PROT_READ | PROT_WRITE, MAP_PRIVATE, fd, bar_addr);

// ❌ 乱序写入（导致多次 PCIe 事务）
tx_ring[0].addr = pkt_phys;  // PCIe 写 1
tx_ring[0].len  = pkt_len;   // PCIe 写 2
// WC buffer 没合并，发出 2 次 8B PCIe 写

// ✅ 合并写入（整个 16B 一次 PCIe 事务）
tx_ring[0].word64[0] = pkt_phys;
tx_ring[0].word64[1] = ((u64)pkt_len << 48) | flags;
// WC 将相邻写合并为一次 16B PCIe TLP
```

**关键点**：
- WC 不保证顺序（同地址除外）—— 合并后才 flush 到 PCIe
- 需要 flush 时用 `sfence` / `mfence`，或读 WC 区域（副作用 flush）
- DPDK `rte_write32` / `rte_write32_relaxed` 对 WC 映射的处理

### 1.2 检查与设置内存类型

```bash
# 查看 MTRR
cat /proc/mtrr

# 查看 PAT 对页的映射
# 页表条目中的 PAT 位决定该页是 WB/WC/UC
# 通过 BIOS / MTRR / page table PAT 设置

# DPDK EAL 对 PCIe BAR 的 mmap 自动设 WC
# 确认：cat /sys/bus/pci/devices/0000:18:00.0/resource0_wc 存在
```

## 2. Store Buffer 与 Invalidate Queue

### 2.1 写缓冲结构

```
Core 0                          Core 1
┌──────────────┐               ┌──────────────┐
│ Store Buffer │               │ Store Buffer │  ← 核内写缓冲
│   (未提交写)   │               │   (未提交写)   │
├──────────────┤               ├──────────────┤
│ L1d Cache    │ ← MESI →     │ L1d Cache    │
├──────────────┤               ├──────────────┤
│ Invalidate   │               │ Invalidate   │
│ Queue        │               │ Queue        │  ← 核间失效队列
└──────────────┘               └──────────────┘
```

- **Store Buffer**：每个核私有，存"已发射但未写入 L1"的写操作。写提交至 L1 前，后续读可先于写完成（Store Forwarding）
- **Invalidate Queue**：接收其他核的 MESI Invalidate 请求，可延迟处理

### 2.2 为什么需要 Memory Barrier

```c
// 典型无锁场景（生产者-消费者）
// Core 0（生产者）
data[0] = 42;              // 1. 写数据
WRITE_ONCE(ready, 1);      // 2. 写标记

// Core 1（消费者）
while (!READ_ONCE(ready)); // 3. 读标记
use(data[0]);              // 4. 读数据
```

硬件行为下可能发生：

| 重排序类型 | 可能性 (x86) | 可能性 (ARM) |
|-----------|-------------|-------------|
| 写 → 写重排 | 不可能 | 可能 |
| 写 → 读重排 | 可能（同一地址除外） | 可能 |
| 读 → 读重排 | 不可能 | 可能 |
| 读 → 写重排 | 可能 | 可能 |

**x86 TSO** 下只需 `smp_mb()`（实际 `mfence` / `lock` 前缀），而 ARM **每处共享访问都需 barrier**。

### 2.3 常用屏障指令

| 指令 | x86 | ARM64 | 语义 |
|------|-----|-------|------|
| 全屏障 | `mfence` | `dmb sy` | 所有前序访存完成前，后续访存不可开始 |
| 写屏障 | `sfence` | `dmb st` | 前序写完成后，后续写才可见 |
| 读屏障 | `lfence` | `dmb ld` | 前序读完成后，后续读才开始 |
| 单向屏障 | `smp_wmb()` | `dmb ishst` | 写-写顺序（release 语义） |

DPDK 封装：

```c
// DPDK memory barrier
rte_wmb();        // 写屏障（sfence / dmb ishst）
rte_rmb();        // 读屏障（lfence / dmb ishld）
rte_mb();         // 全屏障（mfence / dmb ish）
rte_smp_wmb();    // 多核写屏障（smp_mb()）
rte_io_wmb();     // IO 写屏障（对 WC 映射）

// DPDK ring（无锁 ring buffer）中大量使用单方向 barrier：
// enqueue 中：rte_smp_wmb() 保证数据写完后才更新 prod_tail
// dequeue 中：rte_smp_rmb() 保证 cons_tail 读后才读数据
```

## 3. Non-temporal 操作与预取非临时

### 3.1 NT Store

```c
// 非临时写：绕过 cache，直接写到内存
// 适合大块一次性数据处理（如 memcpy > L3）
#include <x86intrin.h>

void nt_memcpy(void *dst, const void *src, size_t n) {
    // 使用 NT store 绕过 cache，避免把已有热数据踢出 LLC
    for (size_t i = 0; i < n; i += 64) {
        __m512i data = _mm512_load_si512(src + i);
        _mm512_stream_si512(dst + i, data);  // 写绕过 cache
    }
    _mm_sfence();  // 确保 NT 写对外可见
}
```

**适用场景**：
- 大块数据拷贝（> LLC 大小），避免 cache pollution
- 从网卡收包后入队列（写好不用再读，不需要占 cache）
- 包数据拷贝到应用缓冲区（memcpy 替代方案）

**不适用的场景**：
- 小数据（< 2 cache lines），NT 开销 > 收益
- 即将被读的数据（NT 写后读会触发 cache fill，更慢）

### 3.2 NT Prefetch（NTA）

```c
// 缓存几行数据后就不再需要（如校验和计算流式数据）
rte_prefetch_non_temporal(addr);  // 拉到 L1，但淘汰优先级高
// _mm_prefetch(addr, _MM_HINT_NTA);
```

数据面中配合流式处理：从网卡收包 → 逐层解析 → 后续不再碰，用 NTA 避免污染 LLC。

## 4. TLB 与大页

### 4.1 TLB 层级

```
Intel Xeon Ice Lake:
L1 DTLB:    64 entries (4K) + 32 entries (2M/1G)    per-core
L1 ITLB:    64 entries (4K)                           per-core
L2 STLB:    2048 entries (4K/2M 混合)                  per-core
```

- **4K 页**：1 次页表遍历需 4 次内存访问（多级页表），TLB 覆盖仅 64×4K = 256KB
- **2MB 页**：2 级页表，TLB 覆盖 64×2M = 128MB
- **1GB 页**：1 级页表，TLB 覆盖 32×1G = 32GB

### 4.2 页大小的影响

| 页大小 | TLB 覆盖（L1 DTLB） | Page Walk 级数 | 适用场景 |
|--------|-------------------|---------------|---------|
| 4K | 256KB | 4 | 普通应用 |
| 2M | 128MB | 3 | DPDK mbuf 池、VPP 缓冲区 |
| 1G | 32GB | 2 | DPDK 大内存池、KVM 直通 |

```bash
# 查看当前大页
cat /proc/meminfo | grep -i huge
# AnonHugePages:    1003520 kB    (THP 透明大页)
# HugePages_Total:     128
# HugePages_Free:       32
# HugePagesize:       2048 kB

# 页表大小估算
# 64GB 内存，2M 页 → 32768 个页表条目 → TLB miss 概率极低
# 64GB 内存，4K 页 → 16M 个页表条目 → TLB miss 频繁
```

### 4.3 大页配置（DPDK 场景）

```bash
# ===== 2MB 大页 =====
# 运行时
echo 2048 | sudo tee /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages

# 持久化（/etc/default/grub）
GRUB_CMDLINE_LINUX="default_hugepagesz=1G hugepagesz=1G hugepages=8"

# ===== 1GB 大页 =====
# 需 CPU + BIOS 支持（Intel PDPE1GB / AMD Page Size 1G）
# 只在启动参数设置（运行时不可调）
default_hugepagesz=1G hugepagesz=1G hugepages=4

# 挂载 hugetlbfs
sudo mkdir -p /mnt/huge
mount -t hugetlbfs nodev /mnt/huge

# 查看 DPDK 使用的预留页
dpdk-hugepages.py -p 1G --setup 4G

# 验证大页分配
grep -i huge /proc/meminfo
lsecho /sys/devices/system/node/node*/hugepages/
# 每个 NUMA node 的数量：node0 和 node1 应均匀分配
```

### 4.4 THP 透明大页

```bash
# 状态
cat /sys/kernel/mm/transparent_hugepage/enabled
# [always] madvise never

# 数据面场景建议关掉
echo never | sudo tee /sys/kernel/mm/transparent_hugepage/enabled

# 原因：THP 是内核后台 khugepaged 线程做碎片整理和页合并
# 在数据面高负载时可能引入延迟抖动（khugepaged 抢 CPU / 内存锁）
# DPDK/VPP 要求自己管理大页（hugetlbfs），不需要 THP
```

### 4.5 大页性能影响实测

| 配置 | TLB Miss 率 | 数据面延迟抖动 |
|------|-----------|--------------|
| 4K 页 | ~15% | 高（page walk 不稳定） |
| 2M 页+ THP | ~3% | 中（THP 碎片整理抖动） |
| 1G 页 hugetlbfs | <0.5% | 极低（稳定） |

## 5. 无锁编程的内存模型约束

### 5.1 DPDK 无锁 Ring 的内存序保证

```c
// DPDK rte_ring（多生产者/多消费者无锁队列）
// 核心依靠三组 barrier 保证正确性：

// 生产者入队：
rte_smp_wmb();    // 1. 数据写入对消费者可见 → 再写 prod_tail
rte_io_wmb();     // 2. 对 WC 映射的门铃寄存器写入顺序

// 消费者出队：
rte_smp_rmb();    // 3. 读 cons_tail → 再读数据指针
```

- 生产者侧：先写数据，再更新生产指针（smp_wmb 防止重排）
- 消费者侧：先读生产指针确认数据就绪，再读数据（smp_rmb 防止重排）
- ARM64 下额外的 barrier 隐于 `dmb`，而 x86 下 smp_wmb 退化为 `compiler barrier`（x86 TSO 保证写-写顺序）

### 5.2 原子操作

```c
// DPDK 原子操作封装
rte_atomic32_add(&counter, 1);         // lock add（x86） / ldadd（ARM64）
rte_atomic32_cmpset(&flag, 0, 1);      // lock cmpxchg / casal（ARM64）

// 带 memory order 标记的原子操作（C11）
__atomic_store_n(&ptr, val, __ATOMIC_RELEASE);
__atomic_load_n(&ptr, __ATOMIC_ACQUIRE);
__atomic_add_fetch(&cnt, 1, __ATOMIC_RELAXED);

// x86 TSO 下：
// RELAXED ≈ 无 barrier（已保证 TSO 顺序）
// RELEASE/ACQUIRE ≈ compiler barrier（硬件已保证）
// ARM64 下：RELEASE 需 dmb ish（写屏障），ACQUIRE 需 dmb ish（读屏障）
```

### 5.3 False Sharing（防踩坑）

```c
// 核间共享写状态时，cache line 在 M,E,S,I 间乒乓传递
// 典型场景：DPDK worker 的统计计数器

// ❌ 所有 worker 写同一个 struct
struct stats { u64 rx_pkts; u64 tx_pkts; } stats;

// ✅ 每个 worker 写自己的 struct + cacheline 对齐
struct stats_per_core {
    u64 rx_pkts;
    u64 tx_pkts;
} __rte_cache_aligned;

// ❌ 全局锁保护（DPDK 热路径严禁）
pthread_mutex_lock(&lock);   // 导致 syscall + 上下文切换
```

## 6. 实用技巧速查

```bash
# 查看页表内存占用
grep PageTables /proc/meminfo

# 查看某进程的实际页大小分布
sudo perf stat -e dTLB-load-misses,dTLB-store-misses \
  -p $(pgrep vpp) sleep 5

# 查看大页使用
cat /sys/kernel/mm/hugepages/hugepages-2048kB/free_hugepages
cat /sys/kernel/mm/hugepages/hugepages-1048576kB/free_hugepages

# 确认 MMIO 区域内存类型
sudo cat /proc/mtrr

# WC 映射验证
hexdump -C /sys/bus/pci/devices/0000:18:00.0/resource0_wc | head

# DPDK 启动日志看大页分配
sudo ./your_app --log-level lib.eal:debug | grep -i huge
```

## 参考来源

- [[concepts/CPU 核心架构]]
- [[entities/CPU 性能分析实战]]
- Intel 64 and IA-32 Arch. SW Developer's Manual Vol.3A (Memory Ordering / MTRR/PAT)
- DPDK Programmer's Guide: Ring Library / Mempool Library
- Linux kernel Documentation/admin-guide/mm/hugetlbpage.rst
