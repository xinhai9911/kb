## Scheduler 调度器：prefill 决策、结果处理与 radix 交互（part 2）

接 `scheduler-overview.md`（part 1），本文覆盖 `get_new_batch_prefill` 决策、decode 内存守卫、`run_batch`/`process_batch_result`，以及 radix cache 交互与 vLLM V1 对照。

### get_new_batch_prefill（:3209）→ _get_new_batch_prefill_raw（:3236）

| 步骤 | 逻辑 |
|---|---|
| grammar 就绪 | `grammar_manager.get_ready_grammar_requests` 重入队 |
| 提前返回 | `running_batch.batch_is_full` 或 `waiting_queue` 空（chunked_req 除外）；`min_free_slots_delayer.should_delay`（:3264） |
| 可分配槽位 | `get_num_allocatable_reqs = pp_max_micro_batch_size - running_bs`（截 `req_to_token_pool.available_size()`），≤0 且无 chunked_req 时置 `batch_is_full` |
| 策略排序 | `policy.calc_priority(waiting_queue, running_batch)`（见 schedule-policies.md） |
| chunk 尺寸 | `chunked_prefill_size`；`enable_dynamic_chunking`（PP）时用 `predict_next_chunk_size`（:3295） |
| 构造 adder | `PrefillAdder(...)`，带 token 预算 `max_prefill_tokens`、`prefill_max_requests`、`prefill_delayer_single_pass` |
| 逐请求准入 | 循环 `adder.add_one_req(req)`：返回 `AddReqResult.CONTINUE/NO_TOKEN/OTHER`（`schedule_policy.py:505`）；`batch_is_full` 且启 priority 抢占时 `adder.preempt_to_schedule` |
| 收尾 | 移除 `can_run_list` 出等待队列；`new_chunked_req` 存入 `self.chunked_req`；`ScheduleBatch.init_new(...).prepare_for_extend()`；混合 chunk（`is_mixed_chunk`）时 `mix_with_running` 并入 decode 请求 |

**chunked prefill**（`init_chunked_prefill`，:1160）：`chunked_prefill_size` 截断长请求为 `extend_range`，剩余部分记入 `new_chunked_req`，下一轮 `add_chunked_req`（`schedule_policy.py:1004`）继续，`extend_range.end > len(prefix_indices)` 时才 `stash_chunked_request` 缓存 KV（:3100）。`prefill_decode_interval` 让 prefill 后连续 N 轮只跑 decode。`chunked_prefill_size ≤ 0` 或 transformers 后端多模态模型自动禁用。

### update_running_batch（:3550）——decode 内存守卫

`filter_batch` 剔除已结束 → `check_decode_mem`（`schedule_batch.py:2812`，`evict_from_tree_cache` 回收可驱逐节点后查池余量）失败则 `retract_decode`（:2819）：按 `_get_decode_retraction_order`（priority 或 `(output_len, -input_len)`，:2883）从最不受保护者开始 `release_req` 回退内存、请求放回 `waiting_queue`（`is_retracted=True`）；仅剩 1 个仍放不下则 `FINISH_ABORT`。`new_token_ratio` 由 `NewTokenRatioTracker` 动态估计并回写。最后 `prepare_for_decode`（:3054）分配 1 token/req 的 KV 槽并 `seq_lens += 1`。

### run_batch 与 process_batch_result

`run_batch`（:3695）：`forward_ct += 1` 后按 overlap/spec 分支调 `model_worker.forward_batch_generation`（或 embedding 的 `forward_batch_embedding`），`copy_to_cpu` 在 `copy_stream` 上执行与下一前向重叠；spec_v2 下 `_forward_isolation`（:3651）快照/恢复批字段，`future_map` 中继下轮 `input_ids`。

`process_batch_result`（:3991）按 `forward_mode` 分发：

| 模式 | 处理器 |
|---|---|
| `decode` | `batch_result_processor.process_batch_result_decode` |
| `extend` | `process_batch_result_prefill` / `process_batch_result_dllm` / `process_batch_result_disagg_prefill` |
| `prebuilt` / `idle` | `process_batch_result_prebuilt` / `process_batch_result_idle` |

负责更新 radix cache、判定 finish、向 tokenizer 送 `BatchTokenIDOutput`。

### 与 radix cache 的交互

| 时机 | 调用 | 位置 |
|---|---|---|
| 调度前 | `policy.calc_priority` → `match_prefix_for_req` → `tree_cache.match_prefix`，填充 `prefix_indices`/`last_node`/`host_hit_length` | `schedule_policy.py:138` |
| 准入时 | `tree_cache.inc_lock_ref(last_node)` 临时锁防驱逐；`init_load_back` 把 host 命中前缀回载 GPU | `schedule_policy.py:1056/1321` |
| decode OOM | `evict_from_tree_cache(tree_cache, num_tokens)` 先回收 radix 节点再判定 | `schedule_batch.py:2816` |
| chunk 结束 | `maybe_cache_unfinished_req(req, tree_cache, chunked=True)` | `scheduler.py:2974` |
| 结果处理 | `batch_result_processor` 内按 token 插入/更新 radix 树 | `batch_result_processor.py` |

### 与 vLLM V1 Scheduler 粗对照

| 维度 | SGLang Scheduler | vLLM V1 Scheduler |
|---|---|---|
| 形态 | 独立进程单循环，调度+前向+结果处理串行驱动 | `EngineCore` 内 `Scheduler.schedule()` → `update_from_output()`，双阶段分离 |
| 批类型 | `ScheduleBatch` 显式区分 `ForwardMode.EXTEND/DECODE`，prefill 批与 decode 批逐轮切换 | 单一 `schedule()` 中每请求 `num_computed_tokens` 追赶目标，天然覆盖 chunk/缓存 |
| 队列 | `waiting_queue` + `running_batch` 两段 | `waiting`/`skipped_waiting`/`running` 三段，`RequestQueue` 抽象 |
| 抢占 | prefill 侧 `preempt_to_schedule`（优先级差阈值）+ decode 侧 `retract_decode`（内存不足） | `allocate_slots` 失败抢占 `running` 最低优先级/队尾，`num_computed_tokens=0` |
| 前缀缓存 | `tree_cache.match_prefix` 同步内嵌，调度直接拿 `prefix_indices` | `get_computed_blocks`，KV connector 支持异步加载（`WAITING_FOR_REMOTE_KVS`） |
| 策略 | `SchedulePolicy`（lpm/dfs-weight/fcfs/lof/random/routing-key）+ priority | `Request.__lt__` 的 `(priority, arrival_time, request_id)` + FCFS/PRIORITY 队列 |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
