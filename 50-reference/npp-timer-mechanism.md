---
title: NPP 内部定时触发机制
tags: [npp, vpp, reference, active]
status: active
created: 2026-06-15
updated: 2026-06-15
source: "Q:/AI/code/hyperdrive/source/plugins/flowtable"
---

# NPP 内部定时触发机制说明书

## 概述

NPP（Network Processing Platform）基于 VPP/VLIB 框架实现了一套**协作式定时触发机制**，用于驱动流表（flowtable）会话的老化清理。该机制并非传统的 cron 或硬定时器，而是采用 **VLIB Process Node + Interrupt-driven Input Node** 的两级架构，在数据面低负载时安全地执行清理工作。

---

## 架构总览

```
┌─────────────────────────────────────────────────────────┐
│                  VLIB 主线程 (thread 0)                  │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │  flowtable-clear-process (PROCESS Node)          │   │
│  │                                                    │   │
│  │  while(1) {                                        │   │
│  │      wait_for_event_or_clock(timeout=1s); ──①     │   │
│  │      if (rx_node_idle) {                           │   │
│  │          set_interrupt_pending(cleaner) ───②      │   │
│  │      }                                             │   │
│  │  }                                                 │   │
│  └──────────────────────────────────────────────────┘   │
│                          │ ② interrupt pending            │
│                          ▼                               │
│  ┌──────────────────────────────────────────────────┐   │
│  │  flowtable-cleaner (INPUT Node, INTERRUPT state) │   │
│  │                                                    │   │
│  │  flowtable_cleaner_fn() { ────────────────③      │   │
│  │      session_try_cleanup(thread, now)             │   │
│  │  }                                                 │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│              各 Worker 线程 (thread 1..N)                │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │  flowtable-cleaner (INPUT Node, INTERRUPT state) │   │
│  │                                                    │   │
│  │  同样被 interrupt pending 触发 ──────────②       │   │
│  │  在本线程上下文执行 try_cleanup ──────────③      │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

**两级协作的关键含义**：
- **① 定时调度层**（PROCESS Node）：负责"何时触发"——周期性检查系统负载
- **② 中断信号层**：负责"通知谁"——向所有线程的 cleaner 节点发送中断
- **③ 执行层**（INPUT Node）：负责"做什么"——在各线程本地上下文执行清理

---

## 第一级：定时调度层 — flowtable-clear-process

### 节点注册

```c
// node.c:2783-2788
VLIB_REGISTER_NODE (flowtable_clear_process_node) = {
    .function = flowtable_clear_process,
    .type = VLIB_NODE_TYPE_PROCESS,         // 协作式进程，有自己的栈
    .name = "flowtable-clear-process",
    .process_log2_n_stack_bytes = 17,       // 128KB 栈空间
};
```

**VLIB_NODE_TYPE_PROCESS** 是 VLIB 中的协作式进程类型：
- 拥有独立的执行栈，可使用 `while(1)` 循环
- 通过 `vlib_process_wait_for_event_or_clock()` 主动让出 CPU
- 不会阻塞其他节点的执行
- 仅运行在主线程（thread 0）

### 核心逻辑

```c
// node.c:2697-2779
#define FLOWTABE_CLEAR_TIMEOUT  1     // 定时周期：1秒
#define NODE_IDLE_SPEED          10    // 空闲判定阈值：每秒处理的向量数 < 10
#define SFF_RX_NODE    "sffmgr-pkt-rx"
#define DPDK_RX_NODE   "dpdk-input"

static uword flowtable_clear_process (vlib_main_t * vm,
                                       vlib_node_runtime_t * rt,
                                       vlib_frame_t * f)
{
    f64 timeout = FLOWTABE_CLEAR_TIMEOUT;

    // ── 启动阶段：查找收包节点引用 ──
    u8 is_secondary = vm->buffer_main->issecondary;
    vlib_node_t *ndpdk = NULL, *nsff = NULL;
    vlib_node_t *clean_node = vlib_get_node_by_name(vm, "flowtable-cleaner");

    for (i = 0; i < vec_len(nm->nodes); i++) {
        n = nm->nodes[i];
        if (is_secondary && !strncmp(n->name, SFF_RX_NODE, ...))
            nsff = n;                          // 备机：sffmgr-pkt-rx
        else if (!strncmp(n->name, DPDK_RX_NODE, ...))
            ndpdk = n;                         // 主机：dpdk-input
    }

    // ── 加载外部扩展 API ──
    flowtable_exapi_init_func(vm);

    // ── 主循环 ──
    while (1) {
        vlib_process_wait_for_event_or_clock(vm, timeout);  // ① 等待1秒或事件

        // 判断收包节点是否"空闲"
        // 备机模式：检查 sffmgr-pkt-rx 节点
        if (is_secondary && nsff) {
            if (nsff->stats_total.vectors - last_vectors < NODE_IDLE_SPEED) {
                for (int ti = 0; ti < vec_len(vlib_mains); ti++)
                    vlib_node_set_interrupt_pending(vlib_mains[ti], clean_node->index);  // ②
            }
            last_vectors = nsff->stats_total.vectors;
        }

        // 主机模式：检查 dpdk-input 节点
        if (ndpdk) {
            if (ndpdk->stats_total.vectors - last_vectors < NODE_IDLE_SPEED) {
                for (int ti = 0; ti < vec_len(vlib_mains); ti++)
                    vlib_node_set_interrupt_pending(vlib_mains[ti], clean_node->index);  // ②
            }
            last_vectors = ndpdk->stats_total.vectors;
        }
    }
    return 0;
}
```

### 关键设计要点

| 要素 | 说明 |
|------|------|
| **定时周期** | 1秒（`FLOWTABE_CLEAR_TIMEOUT = 1`），不可配置 |
| **空闲判定** | 收包节点前后两次统计的 `vectors` 差值 < `NODE_IDLE_SPEED(10)` |
| **主/备机分支** | 备机看 `sffmgr-pkt-rx`，主机看 `dpdk-input`，两者都检查 |
| **触发范围** | 向 `vlib_mains[]` 中所有线程的 cleaner 节点设置 interrupt pending |
| **让出机制** | `vlib_process_wait_for_event_or_clock()` — 既等待超时也等待外部事件 |

### 空闲判定的意义

只在收包节点空闲时触发清理，避免：
- 清理操作占用 CPU 导致收包延迟/丢包
- 大流量时频繁触发清理加剧性能抖动
- 数据面优先级始终高于控制面/管理面操作

---

## 第二级：中断执行层 — flowtable-cleaner

### 节点注册

```c
// node.c:2622-2627
VLIB_REGISTER_NODE (flowtable_cleaner_node) = {
    .function = flowtable_cleaner_fn,
    .type = VLIB_NODE_TYPE_INPUT,             // 输入类节点，可被中断驱动
    .state = VLIB_NODE_STATE_INTERRUPT,       // 中断模式，不主动轮询
    .name = "flowtable-cleaner",
};
```

**VLIB_NODE_TYPE_INPUT + VLIB_NODE_STATE_INTERRUPT** 的组合含义：
- INPUT 节点可产生帧（frame）送入后续图节点
- INTERRUPT 状态意味着：**不主动运行，只在收到 interrupt pending 时被调度**
- 每个 worker 线程都有自己独立的 cleaner 节点实例
- 被调度时在**本线程上下文**执行，直接操作本线程的 per-thread 数据

### 核心逻辑

```c
// node.c:2605-2619
static uword flowtable_cleaner_fn (vlib_main_t * vm,
                                    vlib_node_runtime_t * rt,
                                    vlib_frame_t * f)
{
    flowtable_main_t *fm = &flowtable_main;
    f64 now = vlib_time_now(vm);

    if (fm->is_tenement && fm->flowtable_session_try_cleanup_f)
        fm->flowtable_session_try_cleanup_f(vm->thread_index, now);  // 多租户模式
    else
        flowtable_session_try_cleanup(fm, vm->thread_index, now);    // 标准模式

    return 0;
}
```

### per-thread 执行的必要性

`vm->thread_index` 标识当前线程。每个线程维护独立的：
- `sessions_pool` — 会话池
- `lru_list_pool` — LRU 链表池
- `lru_list_head_index` — LRU 链表头
- `session_count` — 会话计数
- `max_clean_count` — 最大清理数量

这保证了**无锁操作**：各线程只清理自己管理的会话，无需跨线程同步。

---

## 第三级：清理策略层 — session_try_cleanup

### 路径选择

```c
// flowtable_inlines.h:393-431
flowtable_session_try_cleanup(fm, thread_index, now)
{
    elt = LRU链表头->next;                  // 取最老（最可能过期）的会话
    if (elt->next == ~0) return;            // 无会话，跳过

    if (!ptd->fastcleanum && session_count < slowclean_entries)
        flowtable_slow_cleanup(...);         // 慢清理：逐条判断是否过期
    else
        flowtable_fast_cleanup(...);          // 快清理：流表压力下批量删除
}
```

### 慢清理（slow_cleanup） — 正常状态

```c
// flowtable_inlines.h:333-369
flowtable_slow_cleanup(fm, elt, thread_index, now)
{
    while (elt->value != ~0 && count < max_clean_count) {
        sess = pool_elt_at_index(sessions_pool, elt->value);
        elt = elt->next;

        if (sess->expire_time - now >= tcp_slow_age_timeout)
            → 更新 LRU 位置（距离过期还很远），continue
        else if (now < sess->expire_time)
            → break（后续会话更新，不可能过期）
        else
            → is_deleting = 1（已过期，标记删除）

        flowtable_session_cleanup(sess, ...);   // 执行删除
    }
}
```

**三个分支的含义**：

| 条件 | 动作 | 说明 |
|------|------|------|
| `expire_time - now >= slow_age_timeout` | 更新 LRU | 距过期 > 5×fin_timeout，移到 LRU 尾部延缓下次检查 |
| `now < expire_time` | 停止遍历 | LRU 按过期时间排序，后续更不可能过期 |
| `now >= expire_time` | 标记删除 | 已超时，执行清理 |

### 快清理（fast_cleanup） — 流表压力状态

```c
// flowtable_inlines.h:372-389
flowtable_fast_cleanup(fm, elt, thread_index, now)
{
    while (elt->value != ~0 && count < MAX_CLEANUP_COUNT) {
        sess = ...;
        sess->is_deleting = 1;                // 直接标记，不判断是否过期
        flowtable_session_cleanup(sess, ...);
        cleanup_count++;
    }
}
```

快清理**不判断是否过期**，直接批量删除最老的会话，用于流表即将满时的紧急回收。

### 触发条件对比

| 条件 | 策略 | 特点 |
|------|------|------|
| `session_count < slowclean_entries` 且无 fastclean 压力 | slow_cleanup | 逐条判断，只删过期流 |
| `session_count >= slowclean_entries` 或有 fastclean 压力 | fast_cleanup | 批量删除最老流，不判断过期 |

---

## 会话过期时间设定

每次会话创建或有新报文命中时，调用 `flowtable_session_set_expire()` 重设过期时间：

```c
// flowtable_inlines.h:434-479
sess->expire_time = now + <协议对应超时值>
```

| 协议 | 默认超时 | 来源 |
|------|---------|------|
| ICMP/ICMP6 | 30s | `fm->icmp_timeout` |
| UDP/IPSEC_ESP/IPSEC_AH | 60s | `fm->udp_timeout` |
| GRE | 30s | `fm->icmp_timeout` |
| TCP ESTABLISHED | 1800s | `fm->tcp_est_timeout`（或 ACL 自定义值） |
| TCP FIN/WAIT/CLOSE | 1s | `fm->tcp_fin_timeout` |
| TCP INIT (其他状态) | 1s | `fm->tcp_init_timeout` |
| slow_age 门槛 | 5s | `fm->tcp_fin_timeout × 5` |

ACL 可通过 `flowtable_session_set_expire_acl()` 覆盖 TCP EST 的超时值。

---

## 运行时超时配置

### CLI 命令

```
set flowtable tcp-est-timeout <val> tcp-fin-timeout <val> \
            tcp-init-timeout <val> udp-timeout <val> icmp-timeout <val>
```

修改后会自动重算 `tcp_slow_age_timeout = tcp_fin_timeout × 5`。

### API 配置

通过 `flowtable.api` 定义的消息接口，远程设置各超时参数，效果同 CLI。

---

## 多租户（Tenement）扩展

当 `fm->is_tenement = 1` 时，清理逻辑替换为 tenement 插件提供的函数指针：

```c
fm->flowtable_session_try_cleanup_f = vlib_get_plugin_symbol(
    "tenement_plugin.so", "tenement_flowtable_session_try_cleanup");
```

这允许多租户场景下使用租户隔离的清理策略。

---

## 外部扩展 API（exapi）

`flowtable_clear_process` 启动时调用 `flowtable_exapi_init_func()`，从 `flowtable_exapi_plugin.so` 加载扩展函数，包括 `del_handler`（会话删除回调），用于协议识别、falcon 引擎等外部模块在会话老化时执行清理。

---

## HA 刷新机制（补充）

除定期清理外，还有**HA（高可用）刷新间隔**机制：

```c
fm->ha_refinterval = 10;  // 默认 10秒

// 在流处理路径中检查：
if ((sess->ha_last_refreshed + fm->ha_refinterval) < now) {
    sess->ha_last_refreshed = now;
    → 触发 HA 同步
}
```

这是**附随触发**，不是独立定时器——在报文处理流程中顺便检查，无需额外定时进程。

---

## 整体触发链路总结

```
每1秒唤醒
    │
    ▼
flowtable-clear-process 检查收包节点是否空闲
    │
    ├─ 不空闲 → 跳过，等下一轮
    │
    └─ 空闲 → 向所有线程的 flowtable-cleaner 发 interrupt pending
              │
              ▼ (各 worker 线程上下文)
        flowtable-cleaner 执行 flowtable_session_try_cleanup
              │
              ├─ 流表未满 → slow_cleanup（逐条判断过期）
              │
              └─ 流表压力大 → fast_cleanup（批量删除最老流）
```

**设计哲学**：数据面优先、低负载才清理、per-thread 无锁、两级协作解耦调度与执行。

---

## 源码索引

| 组件 | 文件 | 关键行 |
|------|------|--------|
| clear-process 注册 | `node.c` | 2783-2788 |
| clear-process 实现 | `node.c` | 2697-2779 |
| cleaner 注册 | `node.c` | 2622-2627 |
| cleaner 实现 | `node.c` | 2605-2619 |
| slow_cleanup | `flowtable_inlines.h` | 333-369 |
| fast_cleanup | `flowtable_inlines.h` | 372-389 |
| session_try_cleanup | `flowtable_inlines.h` | 393-431 |
| session_set_expire | `flowtable_inlines.h` | 434-479 |
| timeout 默认值 | `flowtable.c` | 3241-3250 |
| CLI timeout 命令 | `flowtable.c` | 1918-1948, 3176-3179 |
| ACL expire 覆盖 | `flowtable.c` | 1717-1741 |
| HA refresh | `flowtable.c` | 1543-1549, 825, 982 |
| session_expired 判断 | `flowtable.c` | 1673-1695 |
| API timeout 处理 | `flowtable_api.c` | 94-107 |
| timeout 字段定义 | `flowtable.h` | 265-270, 301 |
| session expire 字段 | `flowtable_api.h` | 49-52, 61 |
| exapi 注册 | `session_share.h` | 888-940 |