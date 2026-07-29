---
title: Linux 内存管理
category: concepts
tags: [linux, memory, mm, slab, page-allocator, buddy, numa, cma, active]
created: 2026-07-29
updated: 2026-07-29
summary: >-
    Linux 内存管理子系统内核视角。物理内存管理（Buddy 分配器/PageBlock/
    Migration Types/Watermarks/Kswapd）、Slab/Slub 分配器（kmem_cache/
    per-CPU slab/vmalloc/slub 调试）、内存碎片整理（Compaction/THP/Migration）、
    虚拟内存（VMA/Page Fault/MMU notifier）、CMA 预留内存、
    内存 cgroup 与 OOM Killer、NUMA-aware 分配策略。
    面向 DPDK 大页分配和内核旁路场景的理解。
base_confidence: 0.85
lifecycle: draft
---

# Linux 内存管理

> 前置 [[concepts/CPU 内存模型与大页]]（页表/大页），[[concepts/CPU 核心架构]]（NUMA）。
> 本文侧重内核内存管理器结构，与 DPDK 用户空间分配器对照。

## 1. 物理内存管理：Buddy 分配器

### 1.1 Order 层级

```
order 0:     4K 页     (2^0 × 4K)
order 1:     8K 页     (2^1 × 4K)
order 2:    16K 页     (2^2 × 4K)
...
order 9:     2M 页     (2^9 × 4K)   ← 大页
order 10:    4M 页     (2^10 × 4K)
...
order MAX_ORDER-1 (通常 10-11)
```

```bash
# 查看当前各 order 的空闲页数
cat /proc/buddyinfo
# Node 0, zone   Normal   2180  1740  732  120  48  12  2  1  0  0  0
#               order0  order1 ...                               order10
# 解读：Node 0 的 Normal zone 有 2180 个 4K 连续块...

# Buddy 分裂代价
# order 2 分配 → 没有 → order 3 分裂为两个 order 2
# 其中一个返回，一个挂到 order 2 链表
# 分裂操作：链表操作 + bit 操作，约 20-50 cy
# 合并相反（释放时和相邻块合并）
```

### 1.2 Migration Types

```bash
# Per-migrate-type 统计
cat /proc/pagetypeinfo | grep "^Node" | tail -10

# Linux 将物理页分类：
# Unmovable: 内核分配（slab、page table）不可移动
# Reclaimable: 文件缓存可回收
# Movable: 用户页（可迁移——压缩的前提）
# Reserve: 预留页
# Isolate: 隔离页（迁移进行中）

# 避免碎片的关键：Movable 集中在 zone 的一端
# Unmovable 不被 Movable 打散
```

## 2. Watermarks 与 Kswapd

```bash
# 查看各 zone watermarks
cat /proc/zoneinfo | grep -E "Node|min|low|high|pages free|protection"

# Watermark 含义：
# min:  最底线（atomic 分配必须保留）
# low:  kswapd 唤醒水位
# high: kswapd 休眠水位
# 
# 当空闲页 < low → kswapd 开始回收
# 当空闲页 < min → 直接回收（direct reclaim — 阻塞！）

# Direct Reclaim 对数据面意味着：
# 分配内存时等待 100μs-10ms → 丢包！
# 数据面场景必须避免：
# vm.min_free_kbytes 调高（预留足够）
# 预分配（DPDK 启动时分配所有内存）
```

### 2.1 Kswapd 与数据面干扰

```bash
# kswapd 在 NUMA 系统中额外问题：
# - kswapd 可能运行在隔离核上（即使设置了 isolcpus！）
# - kswapd 后台扫描 LRU → 占用 CPU + 内存带宽
# - 导致 1-5ms 的延迟抖动

# 缓解：
# isolcpus 配合 cpuset 将 kswapd 限制到 non-isolated 核
# vm.watermark_scale_factor 调大（让 kswapd 更早启动、更温柔）
echo 200 | sudo tee /proc/sys/vm/watermark_scale_factor  # default=10

# DPDK 场景：所有内存预分配 → kswapd 不应该被唤醒
# 监控：
grep kswapd /proc/stat
atop | grep kswapd
```

## 3. Slab/Slub 分配器

```bash
# Slab 用于小对象（< 8KB）的内核分配
# 常见 slab cache:
# kmalloc-256, kmalloc-512  -> 通用 kmalloc
# skbuff_head_cache         -> sk_buff
# cred_jar                  -> 凭据
# sighand_cache             -> 信号处理
# inode_cache               -> inode
# dentry_cache              -> dentry

# slub_info
cat /proc/slabinfo | head -20

# Slab 分配性能
# 从 per-CPU freelist 分配：~10-20 cy（无锁）
# 从 slab 页面取：~50 cy
# 从 Buddy 新分配页面：~100+ cy

# 给 DPDK 的启示：
# sk_buff 分配代价 ~200 cy（slab + 初始化）
# DPDK mbuf 从 mempool 取：~10 cy（无锁 ring/stack）
# 这是 DPDK 比内核快的原因之一
```

```bash
# Slub 调试（性能开销大，仅开发环境）
# slub_debug=FZ  (F=free poison, Z=redzone)
# slub_debug=U   (full debug — 非常慢)
slub_debug=FZ 加入 /etc/default/grub

# 查看 slub 分配统计
slabtop -s c
```

## 4. 内存碎片整理（Compaction）

```bash
# 背景压缩（后台 kcompactd）
# 直接压缩（同步/异步）

# 查看压缩统计
cat /proc/vmstat | grep compact
# compact_migrate_scanned   已扫描可迁移页
# compact_free_scanned      已扫描空闲页
# compact_isolated          已隔离页数
# compact_stall             直接压缩导致的 stall

# 碎片检查
cat /proc/buddyinfo
# 如果 order>=3 的块很少 → 碎片严重

# 生产环境关闭紧凑（减少延迟抖动）
echo 0 | sudo tee /proc/sys/vm/compact_memory  # 手动执行一次
# 关后台 compact:
echo 0 | sudo tee /proc/sys/vm/compact_unevictable_allowed
# 或在启动参数加: transparent_hugepage=never
# (THP 的 khugepaged 也做 compact)
```

## 5. CMA（Contiguous Memory Allocator）

```bash
# CMA 预留大块连续物理内存（给 GPU/VPU/Camera 等 DMA 设备）
# 启动参数：
cma=256M @0-4G          # 在 4GB 以下预留 256MB

# 查看 CMA
cat /proc/meminfo | grep Cma
# CmaTotal:     262144 kB
# CmaFree:      262144 kB

# CMA 与 DPDK 的关系：
# DPDK 通过 hugepages 预留内存（用户空间 mmap）
# CMA 是内核空间的连续内存预留
# 两者通常不冲突，但共享同一物理内存
# 如果 DPDK 用 1GB 大页 + CMA 抢占低端连续内存 → 需协调
```

## 6. NUMA-Aware 分配策略

```bash
# NUMA 策略（mbind / set_mempolicy）
# --membind: 只从指定 node 分配
# --interleave: 交替分配（大数据集推荐）
# --preferred: 优先从某 node 分配

# DPDK EAL 默认：--socket-mem 1024,0  → node0 占 1GB
# VPP startup.conf:
# dpdk {
#   socket-mem 1024,1024  # 两 node 各 1GB
# }

# NUMA 负载均衡（AutoNUMA）：
# 内核自动迁移页面和 task 到更近的 node
# 缺点：迁移代价高（页表更新 + TLB shootdown）
# 数据面建议关掉
echo 0 | sudo tee /proc/sys/kernel/numa_balancing

# 检查 NUMA 分配不均衡
numastat -c           # 看 per-process NUMA miss
```

## 7. OOM Killer

```bash
# OOM 触发条件：
# - 所有 zone 低于 min watermark
# - 无可回收页（swap 满 + cache 耗尽）
# - 分配 GFP_KERNEL 不可阻塞

# 评分逻辑：
# badness() 函数：
#   points = rss + swap + page_table_pages / 2
#   root 进程评分 × 0.8
#   子进程数越多评分越高

# DPDK 场景 OOM 预防：
# - vm.overcommit_memory=2 （严格模式）
# - vm.overcommit_ratio=0  （不允许 overcommit）
# - 明确告诉系统 DPDK 已占用
# echo 2 | sudo tee /proc/sys/vm/overcommit_memory
# echo 0 | sudo tee /proc/sys/vm/overcommit_ratio

# 查看某进程 OOM 评分
cat /proc/<pid>/oom_score
cat /proc/<pid>/oom_score_adj
```

## 8. DPDK 的内存预分配策略

```bash
# DPDK EAL 初始化时的内存分配：
# 1. 从 hugetlbfs 预留大页（2M/1G）
# 2. rte_memseg_primary 把大页切分
# 3. memzone 管理
# 4. mempool 从 memzone 分配
# 5. rte_malloc 从 mempool 分配 mbuf

# 完成后内核伙伴系统不再管理这部分内存
# 因此 kswapd/kcompactd 不会干扰 DPDK
# 但系统其他进程的分配/回收仍可能触发

# 看 DPDK 内部分配情况
grep -i mem /proc/vmallocinfo  # 虚存中 DPDK mmap
# 对比 /proc/meminfo 的 HugePages_*
```

## 参考来源

- [[concepts/CPU 内存模型与大页]]
- [[concepts/CPU 核心架构]]
- Linux kernel: Documentation/admin-guide/mm (全系列)
- Linux kernel: Source (mm/page_alloc.c, mm/slub.c, mm/compaction.c)
- DPDK EAL Memory Subsystem Docs
- Brendan Gregg: Linux MM (slides, 2020)
