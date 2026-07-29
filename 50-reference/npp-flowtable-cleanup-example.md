---
title: NPP 流表清理代码实例
tags: [npp, vpp, flowtable, snippet, reference, active]
created: 2026-07-29
summary: >-
    基于 [[50-reference/npp-timer-mechanism|NPP 定时触发机制]] 的流表老化清理完整代码实例：三级协作（clear-process 定时调度 → cleaner 中断执行 → session_try_cleanup 策略）的可编译骨架，含 per-thread 无锁清理、slow/fast 双策略与 exapi del_handler 解耦回调。
category: reference
updated: 2026-07-29
sources: []
base_confidence: 0.8
lifecycle: reviewed
---

# NPP 流表清理代码实例

> 配套说明见 [[50-reference/npp-timer-mechanism|NPP 内部定时触发机制]]（架构、空闲判定、超时表）。
> 性能取舍见 [[50-reference/vpp-plugin-perf|VPP 插件性能调优]]。

本文把流表老化清理的两级协作（PROCESS 定时 + INTERRUPT 执行）整理成一份**可直接套用的代码骨架**，串起调度层、执行层、策略层三部分。源码索引里的真实文件/行号已在该说明书中列出，这里用精简骨架呈现可编译形态。

## 0. 数据结构（per-thread 无锁的前提）

```c
#include <vlib/vlib.h>
#include <vnet/vnet.h>
#include <vppinfra/bihash_8_8.h>

/* 每线程独立维护，保证清理无锁 */
typedef struct {
    u32               session_index;   /* 指向 sessions_pool 的索引 */
    u32               next;            /* LRU 双向链表 next (~0 表示尾) */
    u32               prev;
} flowtable_lru_elt_t;

typedef struct {
    /* 5 元组 + 方向作为流标识 */
    u32               key[4];
    f64               expire_time;     /* 绝对过期时刻 (vlib_time_now 基准) */
    u8                proto;
    u8                is_deleting;
    u16               thread_index;
    /* ...协议状态、统计等... */
} flowtable_session_t;

typedef struct {
    /* per-thread 数据，用 vec/池，按 thread_index 索引 */
    flowtable_session_t    *sessions_pool;          /* pool */
    flowtable_lru_elt_t    *lru_pool;               /* pool */
    u32                     lru_list_head_index;    /* LRU 头 (最老) */
    u32                     session_count;
    u32                     max_clean_count;        /* 单次清理上限 */
    u8                      fastcleanum;            /* 快清理压力标志 */
} flowtable_per_thread_t;

typedef struct {
    u8   is_tenement;
    u8   issecondary;
    /* 多租户清理函数指针（从 tenement_plugin.so 加载） */
    void (*flowtable_session_try_cleanup_f)(u32 thread_index, f64 now);

    /* 外部扩展 API：会话删除回调 */
    void (*del_handler)(flowtable_session_t *s);

    /* 超时配置（CLI/API 可改） */
    f64 tcp_est_timeout;    /* 1800s */
    f64 tcp_fin_timeout;    /* 1s */
    f64 tcp_init_timeout;   /* 1s */
    f64 udp_timeout;        /* 60s */
    f64 icmp_timeout;       /* 30s */

    u32  slowclean_entries; /* 慢清理阈值 */
    f64  tcp_slow_age_timeout; /* = tcp_fin_timeout * 5 */

    flowtable_per_thread_t *per_thread_data; /* 长度 = vec_len(vlib_mains) */
} flowtable_main_t;

static flowtable_main_t flowtable_main;
```

要点：所有可变状态按 `thread_index` 分片，清理时只碰本线程那份，无需加锁。

---

## 1. 第一级：定时调度层（PROCESS node）

```c
#define FLOWTABLE_CLEAR_TIMEOUT  1      /* 周期 1 秒 */
#define NODE_IDLE_SPEED          10     /* 空闲阈值：每秒向量数 < 10 */
#define SFF_RX_NODE   "sffmgr-pkt-rx"
#define DPDK_RX_NODE  "dpdk-input"

static uword
flowtable_clear_process (vlib_main_t * vm,
                         vlib_node_runtime_t * rt,
                         vlib_frame_t * f)
{
    flowtable_main_t *fm = &flowtable_main;
    vlib_node_t *clean_node = vlib_get_node_by_name (vm, "flowtable-cleaner");
    vlib_node_t *rx_node = NULL;
    u64 last_vectors = 0;

    /* 主机看 dpdk-input，备机看 sffmgr-pkt-rx */
    const char *rx_name = fm->issecondary ? SFF_RX_NODE : DPDK_RX_NODE;
    rx_node = vlib_get_node_by_name (vm, rx_name);

    /* 加载外部扩展 API（del_handler 等） */
    flowtable_exapi_init_func (vm);

    while (1) {
        /* ① 协作式等待：让出 CPU，醒来时是超时或被外部事件唤醒 */
        vlib_process_wait_for_event_or_clock (vm, FLOWTABLE_CLEAR_TIMEOUT);

        if (!rx_node || !clean_node)
            continue;

        /* 空闲判定：前后两次统计的 vectors 增量 < 阈值 */
        u64 cur = rx_node->stats_total.vectors;
        if (cur - last_vectors < NODE_IDLE_SPEED) {
            /* ② 向所有线程的 cleaner 发 interrupt pending */
            for (int ti = 0; ti < vec_len (vlib_mains); ti++)
                vlib_node_set_interrupt_pending (vlib_mains[ti], clean_node->index);
        }
        last_vectors = cur;
    }
    return 0;
}

VLIB_REGISTER_NODE (flowtable_clear_process_node) = {
    .function = flowtable_clear_process,
    .type = VLIB_NODE_TYPE_PROCESS,
    .name = "flowtable-clear-process",
    .process_log2_n_stack_bytes = 17,   /* 128KB 栈 */
};
```

---

## 2. 第二级：中断执行层（INPUT node, INTERRUPT state）

```c
static uword
flowtable_cleaner_fn (vlib_main_t * vm,
                      vlib_node_runtime_t * rt,
                      vlib_frame_t * f)
{
    flowtable_main_t *fm = &flowtable_main;
    f64 now = vlib_time_now (vm);
    u32 ti = vm->thread_index;            /* 本线程上下文 */

    /* 多租户：走租户隔离的清理函数；否则走标准清理 */
    if (fm->is_tenement && fm->flowtable_session_try_cleanup_f)
        fm->flowtable_session_try_cleanup_f (ti, now);
    else
        flowtable_session_try_cleanup (fm, ti, now);

    return 0;
}

VLIB_REGISTER_NODE (flowtable_cleaner_node) = {
    .function = flowtable_cleaner_fn,
    .type = VLIB_NODE_TYPE_INPUT,          /* 可被中断驱动 */
    .state = VLIB_NODE_STATE_INTERRUPT,    /* 不主动轮询，仅 interrupt 时跑 */
    .name = "flowtable-cleaner",
};
```

---

## 3. 第三级：清理策略层

### 3.1 入口：选 slow / fast

```c
static void
flowtable_session_try_cleanup (flowtable_main_t *fm, u32 thread_index, f64 now)
{
    flowtable_per_thread_t *ptd = &fm->per_thread_data[thread_index];

    /* LRU 头是最老会话，优先从此处回收 */
    u32 head = ptd->lru_list_head_index;
    flowtable_lru_elt_t *elt = pool_elt_at_index (ptd->lru_pool, head);
    if (elt->next == ~0)
        return;   /* 空表 */

    /* 流表未满 → 慢清理（逐条判断是否真的过期）
       流表压力大 (fastcleanum) 或超阈值 → 快清理（批量删最老） */
    if (!ptd->fastcleanum && ptd->session_count < fm->slowclean_entries)
        flowtable_slow_cleanup (fm, elt, thread_index, now);
    else
        flowtable_fast_cleanup (fm, elt, thread_index, now);
}
```

### 3.2 慢清理：逐条判断过期

```c
static void
flowtable_slow_cleanup (flowtable_main_t *fm,
                        flowtable_lru_elt_t *elt,
                        u32 thread_index, f64 now)
{
    flowtable_per_thread_t *ptd = &fm->per_thread_data[thread_index];
    u32 count = 0;

    while (elt->value != ~0 && count < ptd->max_clean_count) {
        flowtable_session_t *sess =
            pool_elt_at_index (ptd->sessions_pool, elt->value);
        u32 next_elt = elt->next;
        elt = pool_elt_at_index (ptd->lru_pool, next_elt);
        count++;

        f64 slack = sess->expire_time - now;

        if (slack >= fm->tcp_slow_age_timeout) {
            /* 距过期还很远：移到 LRU 尾部，延缓下次被扫到 */
            flowtable_lru_move_to_tail (ptd, sess->lru_index);
            continue;
        } else if (now < sess->expire_time) {
            /* LRU 按过期时间排序，后序更不可能过期，停止遍历 */
            break;
        } else {
            /* 已过期：标记删除并执行清理 */
            sess->is_deleting = 1;
            flowtable_session_cleanup (fm, sess, thread_index);
        }
    }
}
```

### 3.3 快清理：批量删最老（不判断过期）

```c
#define MAX_CLEANUP_COUNT  1024

static void
flowtable_fast_cleanup (flowtable_main_t *fm,
                        flowtable_lru_elt_t *elt,
                        u32 thread_index, f64 now)
{
    flowtable_per_thread_t *ptd = &fm->per_thread_data[thread_index];
    u32 count = 0;

    while (elt->value != ~0 && count < MAX_CLEANUP_COUNT) {
        flowtable_session_t *sess =
            pool_elt_at_index (ptd->sessions_pool, elt->value);
        u32 next_elt = elt->next;
        elt = pool_elt_at_index (ptd->lru_pool, next_elt);

        sess->is_deleting = 1;                 /* 直接标记，不判断 */
        flowtable_session_cleanup (fm, sess, thread_index);
        count++;
    }
}
```

### 3.4 真正删除 + exapi 解耦回调

```c
static void
flowtable_session_cleanup (flowtable_main_t *fm,
                           flowtable_session_t *sess, u32 thread_index)
{
    flowtable_per_thread_t *ptd = &fm->per_thread_data[thread_index];

    /* 1) 外部模块解耦清理：协议识别 / falcon 引擎在删除时回调
          不在热路径同步做重活 —— 见 NPP 说明书 exapi 段 */
    if (fm->del_handler)
        fm->del_handler (sess);

    /* 2) 从 LRU 摘链 */
    flowtable_lru_remove (ptd, sess->lru_index);

    /* 3) 归还 pool 条目 */
    pool_put (ptd->sessions_pool, sess);
    ptd->session_count--;
}
```

### 3.5 过期时间设定（报文命中/新建时）

```c
static void
flowtable_session_set_expire (flowtable_main_t *fm,
                              flowtable_session_t *sess, u8 proto, f64 now)
{
    switch (proto) {
    case IP_PROTOCOL_ICMP:
    case IP_PROTOCOL_ICMP6:
    case IP_PROTOCOL_GRE:
        sess->expire_time = now + fm->icmp_timeout;          /* 30s */
        break;
    case IP_PROTOCOL_UDP:
    case IP_PROTOCOL_IPSEC_ESP:
    case IP_PROTOCOL_IPSEC_AH:
        sess->expire_time = now + fm->udp_timeout;           /* 60s */
        break;
    case IP_PROTOCOL_TCP:
        /* 实际按 TCP 状态细分：EST 1800s / FIN/INIT 1s */
        sess->expire_time = now + fm->tcp_est_timeout;
        break;
    default:
        sess->expire_time = now + fm->udp_timeout;
        break;
    }
}
```

---

## 4. 多租户 / 外部 API 加载

```c
/* 启动时从 tenement_plugin.so 载入租户隔离清理函数 */
void flowtable_exapi_init_func (vlib_main_t *vm)
{
    flowtable_main_t *fm = &flowtable_main;
    fm->flowtable_session_try_cleanup_f =
        vlib_get_plugin_symbol ("tenement_plugin.so",
                                "tenement_flowtable_session_try_cleanup");
    fm->del_handler =
        vlib_get_plugin_symbol ("flowtable_exapi_plugin.so",
                                "flowtable_session_del_handler");
}
```

---

## 5. 串起来的触发链路

```
每 1 秒 wake
  │
  ▼ flowtable-clear-process
   收包节点空闲?（vectors 增量 < 10）
    ├─ 否 → 跳过，等下一轮
    └─ 是 → 对所有线程 cleaner 发 interrupt pending
              │  (各 worker 本线程上下文)
              ▼ flowtable-cleaner
        flowtable_session_try_cleanup(thread, now)
              ├─ 流表未满 → slow_cleanup（逐条判断是否过期）
              └─ 压力大   → fast_cleanup（批量删最老）
                    │
                    ▼ flowtable_session_cleanup
                 del_handler 回调（解耦清理）→ 摘 LRU → pool_put
```

## 6. 要点回顾（与调优衔接）

- **数据面优先**：只在收包空闲时清理，避免抢转发 CPU。
- **per-thread 无锁**：清理只动本线程 `per_thread_data`，多核可并行。
- **两级解耦**：process 节点管"何时"，cleaner 节点管"做"，`show runtime` 能分别统计。
- **slow/fast 双策略**：正常逐条判断过期，压力大时批量回收，保住转发。
- **exapi 解耦**：重活（协议识别/falcon）通过 `del_handler` 延后到删除点，不在清理热路径同步执行。

## 延伸

- 架构与超时表：[[50-reference/npp-timer-mechanism|NPP 内部定时触发机制]]
- 性能取舍：[[50-reference/vpp-plugin-perf|VPP 插件性能调优]]
- 插件写法：[[50-reference/vpp-plugin-dev|VPP 插件开发]]
