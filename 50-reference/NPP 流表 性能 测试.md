---
aliases: ["npp-flowtable-perf-test"]
title: NPP 流表性能测试实例
tags: [npp, vpp, flowtable, performance, test, reference, active]
created: 2026-07-29
summary: >-
    针对 NPP 流表老化清理的性能测试实例：测试目标、观测口径（show cpu / show runtime / show errors）、四类用例（基线转发、空闲清理开销、满表压力、多核扩展）、具体 CLI 与采样步骤，以及示例结果表与判定标准。配套 [[50-reference/NPP 流表 清理 示例|清理代码实例]] 与 [[50-reference/NPP 定时器 机制|定时触发机制]]。
category: reference
updated: 2026-07-29
sources: []
base_confidence: 0.8
lifecycle: reviewed
---

# NPP 流表性能测试实例

> 配套：[[50-reference/NPP 定时器 机制|NPP 内部定时触发机制]]（架构与超时）、[[50-reference/NPP 流表 清理 示例|NPP 流表清理代码实例]]（被测代码）、[[50-reference/VPP 插件 性能|VPP 插件性能调优]]（调优方法论）。

本文给出一套**可执行的 NPP 流表性能测试方案**。核心被测对象是流表老化清理的两级协作（`flowtable-clear-process` + `flowtable_cleaner_node`），验证它"在数据面优先前提下不拖累转发、低负载才清理、满表能回收"。

## 1. 测试目标与口径

| 目标 | 关注点 | 通过标准（示例） |
|---|---|---|
| 基线转发不被清理拖垮 | 大流量下清理不应触发或应极轻 | 满速转发时 `flowtable_cleaner_node` 调用次数 ≈ 0 / 转发 pps 不下降 > 1% |
| 空闲清理开销可控 | 低负载时清理的 CPU 占比 | `show runtime` 中 cleaner 单次调用 < 几 μs 级、总占比 < 5% |
| 满表可回收 | fast_cleanup 能批量回收 | `session_count` 被压到 `slowclean_entries` 以下、无内存增长泄漏 |
| 多核无锁扩展 | per-thread 并行清理 | 多 worker 下各线程 `session_count` 均衡、总清理吞吐随核数近似线性 |

### 观测字段（全部来自 VPP CLI，无需改代码）

| 命令 | 看什么 |
|---|---|
| `show cpu` | 每 worker 实时 pps（转发第一观感） |
| `show runtime` | `flowtable-clear-process` / `flowtable_cleaner_node` 的 `calls`、`clocks`（累计时钟）、`vectors` |
| `show errors` | 丢包原因（区分 buffer 不足 / 策略丢） |
| `show interface` | 每接口 rx/tx/drops |
| `show flowtable sessions` | 当前会话数（需插件暴露该 CLI，或读 `session_count`） |
| `show threads` | worker 绑核情况 |

> 若插件未暴露 `show flowtable sessions`，可在 `flowtable_main.per_thread_data[ti].session_count` 上补一个 CLI（见 [[50-reference/VPP 插件 开发|插件开发]] §CLI）。

## 2. 测试环境准备

```bash
# 1) 启动 VPP（含 NPP/flowtable 插件，启用）
sudo vppctl "show plugins" | grep -i flowtable     # 确认插件已加载
sudo vppctl "show node" | grep -E "flowtable-clear-process|flowtable-cleaner"  # 确认 node 注册

# 2) 配置超时（用默认或显式设，便于复现）
sudo vppctl "set flowtable tcp-est-timeout 1800 tcp-fin-timeout 1 \
             tcp-init-timeout 1 udp-timeout 60 icmp-timeout 30"

# 3) 流量仪 / 发包器：用 TRex / pktgen / IXIA 打双向流
#    主机从 dpdk-input 收包（看 node 名），备机从 sffmgr-pkt-rx 收包
```

## 3. 测试用例

### 用例 A：基线转发（清理应几乎不触发）

**目的**：确认大流量时两级机制"让位"于数据面。

```bash
# 打接近线速的流量（如 10G 小包，pps 打满 worker）
# 持续 60s，期间每 5s 采样一次

for i in $(seq 1 12); do
  sudo vppctl "show cpu"      >> /tmp/testA_cpu.log
  sudo vppctl "show runtime"  >> /tmp/testA_runtime.log
  sudo vppctl "show errors"   >> /tmp/testA_err.log
  sleep 5
done
```

**判定**：`show runtime` 里 `flowtable-cleaner` 的 `calls` 在 60s 内应≈0（因为 `dpdk-input` 空闲判定不成立）；`show cpu` 转发 pps 稳定在预期线速；`show errors` 无丢包。

### 用例 B：空闲清理开销（低负载）

**目的**：确认低负载时清理能跑且开销可控。

```bash
# 停止打流（或降到 vectors < NODE_IDLE_SPEED=10/s）
# 持续 30s 采样

sudo vppctl "show runtime"        # 记录 cleaner 的 calls / clocks 起点
sleep 30
sudo vppctl "show runtime"        # 记录终点
```

**计算**：
```
cleaner_calls = calls_end - calls_start          # 理论 ≈ 30（每秒一次）
cleaner_clocks_total = clocks_end - clocks_start
per_call_us = cleaner_clocks_total / cleaner_calls / cpu_freq_hz * 1e6
```

**判定**：`cleaner_calls ≈ 30`（每 1s 一次），`per_call_us` 在微秒级；`show cpu` 主线程占用接近 0（confirm 协作式让出生效）。

### 用例 C：满表压力 + fast_cleanup

**目的**：验证流表将满时 `fast_cleanup` 能批量回收、不泄漏。

```bash
# 1) 打大量短生命期流（如 UDP 60s 超时 / TCP fin 1s），让 session_count 飙升
#    用流量仪制造 N 条流（N 远大于 slowclean_entries）
# 2) 观察 session_count 曲线
sudo vppctl "show flowtable sessions" > /tmp/sess_start.txt
# 3) 停流，进入空闲 → 触发清理
sleep 60
sudo vppctl "show flowtable sessions" > /tmp/sess_end.txt
```

**判定**：
- 停流后 60s 内 `session_count` 从峰值回落到 `slowclean_entries` 以下。
- `slow_cleanup` 优先（逐条判断过期）；若期间触发 `fastcleanum`，`show runtime` 应看到 cleaner `vectors` 单次批量大（`MAX_CLEANUP_COUNT=1024` 上限）。
- `show errors` 与 RSS 内存无持续增长 → 无泄漏（pool_put 正确）。

### 用例 D：多核无锁扩展

**目的**：验证 per-thread 清理可并行、无锁竞争。

```bash
# 多 worker（startup.conf 配 workers N），打多流让 RSS 分散到各核
sudo vppctl "show threads"        # 确认 N 个 worker
sudo vppctl "show runtime"        # 看每个 worker 的 cleaner 调用是否均衡
```

**判定**：`show runtime` 中每个 worker 的 `flowtable-cleaner` `calls` 大致相等（流亲和良好、无跨核争锁）；总清理吞吐随 worker 数近似线性。若某 worker 明显偏高 → 检查 RSS 是否把多流打到同一核（见 [[50-reference/VPP 插件 性能|调优]] §流绑定）。

## 4. 示例结果表（模板）

| 用例 | 指标 | 基线值 | 实测值 | 判定 |
|---|---|---|---|---|
| A 基线转发 | 转发 pps | 12.0 Mpps | 11.9 Mpps | PASS（降幅 <1%） |
| A | cleaner calls / 60s | ≈0 | 2 | PASS |
| A | `show errors` drops | 0 | 0 | PASS |
| B 空闲清理 | cleaner calls / 30s | ≈30 | 30 | PASS |
| B | per_call 耗时 | <5 μs | 3.1 μs | PASS |
| C 满表回收 | session_count 峰值 | — | 1.2M | — |
| C | 回收后 session_count | < slowclean_entries | 82k | PASS |
| C | 内存增长 | 0 | 0 | PASS（无泄漏） |
| D 多核 | worker0/1/2/3 calls | 均衡 | 31/30/31/30 | PASS |

## 5. 调优闭环（发现问题后）

1. **基线 pps 下降 / cleaner calls 异常多** → 空闲阈值 `NODE_IDLE_SPEED` 太低或收包节点名不匹配（检查 `SFF_RX_NODE` / `DPDK_RX_NODE`）。
2. **per_call 耗时高** → 见 [[50-reference/VPP 插件 性能|调优]]：slow_cleanup 里是否有 per-session 分配、LRU 操作是否缓存友好。
3. **满表不回收 / 内存涨** → 检查 `fastcleanum` 触发条件、`pool_put` 是否配对 `pool_get`、del_handler 是否抛错中断清理。
4. **多核不均** → 检查 RSS / 流哈希、NUMA 亲和（[[50-reference/VPP 插件 性能|调优]] §多核）。

**循环**：测基线 → `show runtime` 找异常节点 → 改代码/配置 → 重测（同用例）。

## 6. 注意事项

- **空闲判定依赖收包节点名**：主机 `dpdk-input`、备机 `sffmgr-pkt-rx`，测试环境要对应，否则清理永不触发或误触发。
- **时钟口径**：`show runtime` 的 `clocks` 是累计 CPU 周期，换算耗时需除以 `show cpu` 里的 CPU 频率（或 `vlib_cpu_freq`）。
- **不要在被测时开 `trace add`**：trace 会显著降低转发速率，污染性能数据。
- **`sleep` 抖动**：采样脚本用 `sleep` 足够；若要高精度，用 `vppctl "show runtime"` 的两次差值为准，不依赖 wall-clock。

## 延伸

- 清理实现：[[50-reference/NPP 流表 清理 示例|NPP 流表清理代码实例]]
- 触发机制：[[50-reference/NPP 定时器 机制|NPP 内部定时触发机制]]
- 调优方法：[[50-reference/VPP 插件 性能|VPP 插件性能调优]]
