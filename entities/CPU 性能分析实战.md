---
title: CPU 性能分析实战
category: entities
tags: [cpu, performance, profiling, perf, pmc, tuning, active]
created: 2026-07-29
updated: 2026-07-29
summary: >-
    面向数据面开发者的 CPU 性能分析指南。perf 全方位用法、PMC（Performance Monitoring Counter）解读、
    热点定位案例（cache miss / 分支预测 / false sharing）、VPP/DPDK 专用分析方案、火焰图生成与解读。
base_confidence: 0.85
lifecycle: draft
---

# CPU 性能分析实战

> 先读 [[concepts/CPU 核心架构]] 了解 Cache/NUMA/SIMD 等微架构概念。
> 性能问题定位路径：`perf top` 看热点 → `perf stat` 看计数器 → `perf record -g` 取调用链 → 火焰图可视化。

## 1. perf 速查

```bash
# ===== 基础信息 =====
perf list                      # 列出所有支持的事件
perf list hw                   # 硬件事件
perf list cache                # Cache 事件

# ===== 实时热点 =====
perf top                       # 系统级实时热点（类似 htop 但按函数）
perf top -p $(pgrep vpp)       # 只看某个进程
perf top -e cache-misses       # 按 cache miss 排序（找谁在漏）
perf top -e branch-misses      # 按分支预测失败排序

# ===== 统计摘要 =====
perf stat -d ./your_app                    # 执行并统计关键指标
perf stat -e cycles,instructions,cache-misses,branch-misses \
  -p $(pgrep vpp) sleep 10                # 采样 10 秒

# ===== 采样 & 调用链 =====
perf record -g -p $(pgrep vpp) sleep 30   # 30 秒采样带调用链
perf report -g                            # 交互式浏览
perf report -g --stdio | head -100        # 文字输出

# ===== 特定事件 =====
perf stat -e LLC-load-misses,LLC-store-misses,LLC-prefetch-misses \
  -p $(pgrep vpp) sleep 5                 # LLC 层分析
perf stat -e dTLB-load-misses,dTLB-store-misses \
  -p $(pgrep vpp) sleep 5                 # TLB 分析
```

## 2. PMC 指标解读

### 2.1 黄金三指标（第一眼判断）

```bash
perf stat -e cycles,instructions,cache-misses,branch-misses \
  -p $(pgrep your_app) sleep 10

# 输出示例：
#   cycles:         3,241,987,654
#   instructions:   4,892,112,345
#   cache-misses:     12,344,567   # 占总访问的百分比
#   branch-misses:       345,678   # 占分支的百分比
```

| 派生指标 | 公式 | 健康范围 | 含义 |
|---------|------|---------|------|
| **IPC** | instructions / cycles | > 2 优, 1-2 中, < 1 差 | 每周期指令数：越高越好 |
| **CPI** | cycles / instructions | < 0.5 优 | 每指令周期数：越低越好 |
| **Cache Miss Rate** | cache-misses / cache-references | < 5% | L3 未命中率 |
| **Branch Miss Rate** | branch-misses / branches | < 5% | 分支预测准确率 |

### 2.2 配套观测链

```
IPC < 1
├── 高 cache-miss rate (>10%)
│   ├── 随机访问大结构体 → 紧凑数据布局 + 预取
│   └── 多核假共享 → per-CPU 结构 + cacheline 对齐
├── 高 branch-miss rate (>10%)
│   ├── 循环内复杂分支 → VPP 分流到不同 node
│   └── 数据驱动分支 → 查找表取代
├── 高 dTLB miss
│   ├── 大页未启用 → 启用 1GB/2MB 大页
│   └── 工作集 > TLB 覆盖 → 巨页 + THP
└── 无显著瓶颈 → 查看 I-cache / μOP cache / 取指瓶颈
```

### 2.3 Intel Xeon 特定 PMC

```bash
# 需要 root / 加载 intel-cmt-cat 驱动
perf stat -e \
  mem_load_retired.l1_hit,         # L1 命中率
  mem_load_retired.l2_hit,         # L2 命中率
  mem_load_retired.l3_hit,         # L3 命中率
  mem_load_retired.l3_miss,        # L3 未命中 → 内存
  -p $(pgrep vpp) sleep 5

perf stat -e \
  cycle_activity.stalls_mem_any,    # 因等待内存停顿的周期
  cycle_activity.stalls_l1d_miss,   # L1D miss 导致停顿
  cycle_activity.stalls_l2_miss,    # L2 miss 导致停顿
  -p $(pgrep vpp) sleep 5
```

**内存停顿是数据面最大性能杀手**，通常一次 L3 miss = 300 周期 = 80-100 条指令的空等。

## 3. 火焰图

### 3.1 生成（FlameGraph 工具）

```bash
# https://github.com/brendangregg/FlameGraph
git clone https://github.com/brendangregg/FlameGraph.git

# 采样
perf record -F 99 -g -p $(pgrep vpp) sleep 30
perf script > out.perf

# 折叠调用栈 → 生成 SVG
./FlameGraph/stackcollapse-perf.pl out.perf > out.folded
./FlameGraph/flamegraph.pl out.folded > vpp-cpu.svg

# 差异火焰图（改前 vs 改后）
./FlameGraph/difffolded.pl before.folded after.folded > diff.folded
./FlameGraph/flamegraph.pl diff.folded > diff.svg
```

### 3.2 解读要点

- **宽条 = 热点**：顶部宽度大的函数就是 CPU 最多的
- **颜色不表示严重程度**：只是随机分配
- **I-cache 瓶颈特征**：栈顶函数频繁切换（宽度均匀、分布零散）
- **数据访问瓶颈**：`__clear_cache` / `memcpy` 等内存函数占宽条
- **锁竞争**：`__lll_lock_wait` / `futex` 等函数出现

## 4. Cache Miss 定位实战

### 4.1 找 cache-thrashing 代码

```bash
# 高 cache-misses → 定位到具体指令
perf record -e cache-misses -c 10000 -p $(pgrep vpp) sleep 10
perf report --stdio -n

# 输出会列出 cache-miss 占比最高的函数和指令偏移
# 反汇编带注释：
perf annotate --stdio -s your_hot_function
```

常见 cache miss 模式：

```c
// ❌ 模式 A：跳着访问大数组 → cache line 利用率低
// 假设 log_table[packet_hash] 随机访问 → 每次 cache miss
u32 drop = log_table[hash(packet->flow)];

// ✅ 改：把热数据紧凑放一起，或预取
for (int i = 0; i < n_left; i += 4) {
    rte_prefetch0(&log_table[hash(flows[i+2])]);  // 提前预取
    process_one(flows[i]);
}

// ❌ 模式 B：遍历大结构体链表 → cache miss 链式
for (flow_t *f = head; f; f = f->next) { ... }

// ✅ 改：用数组或 bihash（VPP/DPDK 自带的哈希表）
CLIB_BIHASH(flow_table, flow_key_t, flow_val_t);
```

### 4.2 查看 Cacheline 分布

```bash
# perf-c2c — 定位 false sharing 和 cacheline 竞争
# （Linux 5.10+）
perf c2c record -p $(pgrep vpp) sleep 10
perf c2c report

# 输出会标明哪些 cacheline 被多核乒乓访问
# HITM = Hit Modified（跨核写后读）是 false sharing 的标志
```

## 5. VPP/DPDK 场景的特定分析

### 5.1 VPP

```bash
# VPP 内建观测已可用（不依赖 perf）
vppctl show cpu              # 每 worker pps
vppctl show runtime           # 每 node 调用次数 + 时钟周期
vppctl show errors            # 丢包原因

# 当 node 耗时异常时 → perf 深入
perf top -p $(pgrep vpp)     # 看哪个函数最热

# 常见场景：node function 内 clib_mem_alloc → 高 cache-miss
# 解决方案：预分配 + buffer opaque
```

**VPP 节点耗时分析**：

```bash
vppctl show runtime
# Node                        Calls       Clocks     Avg(cyc)
# dpdk-input                  1234567    987654321  800
# ip4-input                   1234567    888888888  720
# your-node                     20000    200000000  10000   ← 远高于平均，需优化
```

`Avg(cyc)` 远超 1000 周期的 node 通常是热点。

### 5.2 DPDK

```bash
# DPDK 内建观测
./dpdk-testpmd -- --stats-period=1
# 看 pps / drop / mbuf 分配失败

# perf 分析 worker 线程
perf top -C 1-4               # 分析 DPDK worker 所绑的核
perf stat -e instructions,cycles -C 1-4 -- taskset -c 1 ./your_app
```

### 5.3 通用快速排查

```bash
# 第一步：是不是 CPU 瓶颈？
# 看 %usr + %sys 是否接近 100%
top -p $(pgrep vpp)

# 第二步：是不是 cache miss？
perf stat -e cache-misses -p $(pgrep vpp) sleep 5

# 第三步：是不是虚假共享？
perf c2c record -p $(pgrep vpp) sleep 10 && perf c2c report

# 第四步：是不是大页问题？
cat /proc/meminfo | grep HugePage
# 或看 DPDK EAL 启动日志：EAL: Not enough hugepages ...

# 第五步：是不是 NUMA 跨域？
numactl --hardware
lspci -vv -s 0000:18:00.0 | grep NUMA  # 看网卡所在 NUMA
# DPDK EAL 启动日志里也打印 numa_node
```

## 6. 典型优化案例

### 例 1：Cache Miss 优化（DPDK l2fwd）

```
症状：perf top 显示 process_packets 占 70% CPU
      cache-miss rate = 18%

诊断：
  perf annotate 发现 packet_buf_pool 分配频繁触发 cache miss
  
方案：
  1. 预分配 mbuf pool 而不是 per-packet 分配
  2. mbuf 复用：处理完后放回 free ring 而不是 free 再 alloc

效果：
  cache-miss rate 从 18% → 6%
  pps 提升 40%
```

### 例 2：False Sharing（多核计数）

```
症状：增加 worker 核数，pps 不升反降

诊断：
  perf c2c report 显示 stats.total_packets cacheline 被多核竞争

方案：
  将计数器改为 per-CPU 数组，各核只写自己下标

效果：
  8 核从 8Mpps → 14Mpps
```

### 例 3：分支预测优化（VPP node）

```
症状：show runtime 显示某 node avg(cyc) = 3500，远高于同类

诊断：
  perf top -e branch-misses 确认此 node 分支预测失败率高
  代码中有多个 `if (type == A) ... else if (type == B) ...`

方案：
  拆分为 3 个独立 node，由前级 node 根据 type 分发
  各 node 无分支 → 分支预测失败归零

效果：
  avg(cyc) 从 3500 → 800
```

## 7. 监控大盘

```bash
# 采集 VPP 数据的周期性脚本示例
#!/bin/bash
while true; do
    echo "=== $(date) ===" >> /tmp/vpp-perf.log
    vppctl show runtime >> /tmp/vpp-perf.log
    vppctl show cpu >> /tmp/vpp-perf.log
    vppctl show errors >> /tmp/vpp-perf.log
    perf stat -e cycles,instructions,cache-misses \
      -p $(pgrep vpp) -- sleep 5 2>> /tmp/vpp-perf.log
    sleep 10
done
```

## 8. 常用 PMC 事件速查

| 事件名 | 含义 | 场景 |
|--------|------|------|
| `cycles` | CPU 时钟周期 | 总消耗 |
| `instructions` | 退休指令数 | IPC 计算 |
| `cache-references` | L3 缓存访问次数 | 命中率分母 |
| `cache-misses` | L3 未命中次数 | >5% 需优化 |
| `branch-instructions` | 分支指令 | 分支比 |
| `branch-misses` | 分支预测失败 | >5% 需优化 |
| `L1-dcache-load-misses` | L1D 未命中 | 数据局部性 |
| `L1-icache-load-misses` | L1I 未命中 | 代码局部性/内联 |
| `dTLB-load-misses` | 数据 TLB 未命中 | 大页配置 |
| `iTLB-load-misses` | 指令 TLB 未命中 | 代码量/大页 |
| `stalled-cycles-frontend` | 前端停顿（取指/解码） | 指令饥饿 |
| `stalled-cycles-backend` | 后端停顿（执行/内存） | 数据饥饿 |
| `faults` | 缺页异常 | 内存过量/首次访问 |
| `context-switches` | 上下文切换 | 绑核/隔离 |
| `cpu-migrations` | CPU 迁移 | 亲和性设置 |

## 参考来源

- [[concepts/CPU 核心架构|CPU 核心架构]]
- [[50-reference/vpp-plugin-perf|VPP 插件性能调优]]
- [[concepts/DPDK 核心架构|DPDK 核心架构（内存模型/NUMA 部分）]]
- Brendan Gregg: _Performance Analysis Super_ (perf 权威指南)
- Intel 优化手册 §PMC 事件列表
- `perf help` / `tldr perf`
