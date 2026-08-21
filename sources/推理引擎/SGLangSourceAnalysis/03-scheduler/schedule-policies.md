## SchedulePolicy 调度策略与准入/抢占

本文基于 `sglang/srt/managers/schedule_policy.py`，说明调度策略枚举、`calc_priority` 排序差异、`PrefillAdder` 准入预算与抢占淘汰机制。注意：本快照代码中**不存在** ship/marill 策略，`ServerArgs.schedule_policy` 合法值仅 `lpm/dfs-weight/fcfs/lof/random/routing-key/priority`（`server_args.py:839-854`）。

### 策略枚举与校验

`SchedulePolicy`（`schedule_policy.py:216`）把策略分成两类：

| 枚举 | 值 | 说明 |
|---|---|---|
| `CacheAwarePolicy` | `lpm`、`dfs-weight` | 感知 radix tree，需先做前缀匹配 |
| `CacheAgnosticPolicy` | `fcfs`、`lof`、`random`、`routing-key` | 不感知缓存 |

`_validate_and_adjust_policy`（:303）：`tree_cache.disable` 为真时 cache-aware 策略**自动降级为 fcfs**；非法值抛 `ValueError`。`_determine_active_policy`（:290）：**LPM 在等待队列 > 128 时退回 fcfs**，避免大规模前缀匹配/排序开销。

### calc_priority 各策略排序

`calc_priority`（:237）每轮 prefill 前调用，原地重排 `waiting_queue`：

| 策略 | 排序键 | 说明 |
|---|---|---|
| `fcfs` | 到达时间（priority 模式再乘 `priority_sign` 后优先） | 默认策略；`_sort_by_priority_and_fcfs` |
| `lpm` | `-num_matched_prefix_tokens`（临时降权者排 `inf` 尾部） | 长前缀命中优先，最大化复用 |
| `dfs-weight` | radix 树上按子树累计请求数的 DFS 序 | 聚集共享同一前缀的请求成批调度 |
| `lof` | `-max_new_tokens`（priority 优先） | 长输出优先，提高批内 token 密集度 |
| `random` | 洗牌 | 均衡/压测用 |
| `routing-key` | running 批内 `routing_key` 频率降序 | 提升多实例路由亲和 |

`priority_sign = 1 if schedule_low_priority_values_first else -1`（:232），控制 priority 数值大小与优先级方向的映射。

### 前缀匹配与批内前缀缓存

`match_prefix_for_req`（:138）调 `tree_cache.match_prefix`（`RadixKey` 含 `token_ids`/`extra_key`/`cache_salt`），回填 `prefix_indices`/`last_node`/`best_match_node`/`host_hit_length` 等。`_compute_prefix_matches`（:321）额外做**批内前缀缓存**：当多个候选请求的前缀都短（≤ `IN_BATCH_PREFIX_CACHING_CHECK_THRESHOLD`）且在等待队列内互相共享前缀（命中数 ≥ `IN_BATCH_PREFIX_CACHING_DEPRIORITIZE_THRESHOLD`）时，把该请求加入 `temporary_deprioritized`，让先调度的兄弟请求把公共前缀写进 radix 树，下一轮再批量命中。

### PrefillAdder：准入与预算

`PrefillAdder`（:511）在一次 prefill 决策中维护 token 预算并逐请求准入，产出 `can_run_list`/`preempt_list`/`new_chunked_req`。核心状态：

| 状态 | 含义 |
|---|---|
| `rem_total_tokens` | 池可用 token（扣除 running 批已占，含 mamba gap 预留） |
| `rem_input_tokens` | `max_prefill_tokens` 预算内剩余输入 token |
| `rem_chunk_tokens` | `chunked_prefill_size` 预算 |
| `rem_swa_tokens` | SWA（滑动窗口注意）专用预算 |
| `cur_rem_tokens` | 批内逐请求扣减的剩余预算 |

`add_one_req`（:1208）准入链（顺序即代码顺序）：

1. `prefill_max_requests` 限制批内请求数（`:1217`）；CP 序列切分时批内只允许 1 个请求（:1214）。
2. `total_tokens = cand_extend_input_len + max_new + page_size(+mamba gap)` ≥ `rem_total_tokens` → `NO_TOKEN`（:1243）。
3. SWA 混合池：`_swa_budget_for_req` 超 `rem_swa_tokens` 时尝试 SWA chunk 封顶或拒绝（:1256）。
4. 非 chunked 且批非空时 `real_input_tokens >= rem_input_tokens` → `OTHER`（:1270，保证首个请求总能进）。
5. `inc_lock_ref(last_node)` 锁住命中节点防驱逐；`init_load_back` 把 host 命中 KV 回载 GPU（:1321）。
6. 命中 `rem_chunk_tokens` 内 → 整段 prefill；否则按 page 对齐截断为 chunk 并设 `new_chunked_req`（:1386），`truncation_align_size`（确定性推理）强制截断长度为对齐倍数。
7. 预算扣减走 `_update_prefill_budget`（:864）：扣 `input_tokens`、预占 `max_new_tokens`（`ignore_eos` 时按新 token 比率，chunk 时预占 0）。

`add_chunked_req`（:1004）处理上一轮遗留 `chunked_req`：`_rem_tokens ≤ 0` 时仍强制准入防内存泄漏；截断未完成时返回 `req` 交由 `self.chunked_req` 记录。

### 优先级抢占（preempt_to_schedule, :1437）

`enable_priority_preemption` 且 `batch_is_full` 时，对排队的高优请求尝试抢占 running 请求：

1. 取 running 中未完成、未被占的请求，按 `(priority*(-priority_sign), -wait_queue_entry_time)` 升序（低优先先被抢）。
2. 需满足 `priority_diff > priority_scheduling_preemption_threshold` 且被抢 token 总和 ≥ 需求缺口（`min_tokens_to_remove` 降至 ≤0）。
3. 逐 `running_batch.release_req` 释放资源，`filter_batch(keep_indices=...)` 重过滤，被抢请求进 `preempt_list`（下一轮 `_add_request_to_queue` 重入队）。

### 抢占/淘汰三兄弟对比

| 机制 | 触发点 | 行为 |
|---|---|---|
| `preempt_to_schedule` | prefill 准入时 batch 满 + priority 模式 | 按优先级差主动释放 running，立即腾位 |
| `retract_decode`（`schedule_batch.py:2819`） | decode 前 `check_decode_mem` 失败 | 从最不受保护请求开始释放，放回等待队列（`is_retracted=True`） |
| `evict_from_tree_cache`（`schedule_batch.py:2816`） | decode 内存检查 | 先回收 radix 树可驱逐节点（LRU 化）再判断，减少请求级抢占 |

### 调度策略扩展

**PrefillDelayer**（`prefill_delayer.py:72`，`--enable-prefill-delayer`）：用跨 rank NCCL/gloo all-gather（缓冲 `(dp_size, attn_tp_size, 5)` 每 rank 打包 `prefillable/token_watermark/running_batch/max_prefill_bs/waiting_queue_len`）协商"本步是否允许 prefill"。触发条件：`slot_condition`（`max_running_requests - running_bs < max_prefill_bs`，避免 decode 被 prefill 合并顶满）或队列触发（`waiting_queue < running_bs * queue_min_ratio`），受 `max_delay_passes`/`max_delay_ms` 封顶；低水位 `token_usage_low_watermark` 时强制放行。`RecentPrefillBatchSizeTracker`（:22）维护最近 16 次 prefill 批大小高水位供预算参考。仅 `enable_overlap` 可用。

**MinFreeSlotsDelayer**（`min_free_slots_delayer.py:25`）：`min_free_slots_delay` 参数，`should_delay` 条件 `running_bs > 0 and num_allocatable_reqs < min_free_slots`——等运行槽位空出几个再一次性准入（DFlash 等准入成本高的场景）；显式值受 `max_running_requests` 截断，≤1 即禁用。

**SchedulerInputBlocker**（`scheduler_input_blocker.py:25`，`SGLANG_ENABLE_COLOCATED_BATCH_GEN`）：状态机 `UNBLOCKED → BLOCKED → GLOBAL_UNBLOCK_BARRIER → UNBLOCKED`，配合 `PollBasedBarrier` 让多 rank 同步"暂停接收/恢复接收"外部请求（`BlockReqInput` 指令流），实现 co-located batch generation 时全 TP rank 输入闸门一致。

### 与 vLLM V1 策略对照

| 维度 | SGLang | vLLM V1 |
|---|---|---|
| 策略载体 | `SchedulePolicy` + 每轮 `calc_priority` 重排 `waiting_queue` | `Request.__lt__`（`priority, arrival_time, request_id`）+ `create_request_queue` 选 FCFS/PRIORITY |
| cache 感知 | `lpm`/`dfs-weight` 显式按前缀排序 | 无独立 cache 策略，调度时逐请求 `get_computed_blocks` |
| 抢占对象 | 优先级差阈值 + token 缺口双条件 | 仅内存不足时 `running.pop()` 或 max-priority |
| 批内复用 | 批内前缀缓存降权机制（`_compute_prefix_matches`） | vLLM 通过 `cached_request` 增量化处理 |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
