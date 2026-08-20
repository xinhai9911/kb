## Scheduler 调度器：动态批处理与请求状态机

### 核心抽象 `SchedulerInterface`

`vllm/v1/core/sched/interface.py` 定义调度器抽象基类 `SchedulerInterface`（`Scheduler`、`AsyncScheduler` 均实现它）。每个调度步对应一次模型 forward，引擎忙循环反复调用：

| 方法 | 说明 |
|------|------|
| `schedule(throttle_prefills=False) -> SchedulerOutput` | 产生本步 `{req_id: num_tokens}` 调度决策 |
| `update_from_output(scheduler_output, model_runner_output) -> dict[int, EngineCoreOutputs]` | 依据前向输出更新状态、判定结束，按 client 返回输出 |
| `add_request(request)` | 请求入队；重复 request_id 视为 streaming 会话续传 |
| `finish_requests(request_ids, finished_status) -> list[Request]` | 外部中止（客户端断开/检测到结束串） |
| `update_draft_token_ids` / `update_draft_token_ids_in_output` | 写入/校验 spec decode 草稿 token（含 grammar 过滤） |
| `get_grammar_bitmask(scheduler_output)` | 结构化输出 grammar 位掩码 |
| `get_num_unfinished_requests` / `has_finished_requests` / `has_requests` / `get_request_counts` | 队列状态探测 |
| `reset_prefix_cache(reset_running_requests, reset_connector)` | 权重热更新后重置前缀缓存 |
| `make_stats() -> SchedulerStats` | 每步生成统计（仅 `log_stats=True`） |
| `pause_state` / `set_pause_state(PauseState)` | 暂停控制 |
| `shutdown()` | 关闭 KV connector / EC connector / 事件发布器 |

常用字段：`requests`（request_id→Request）、`waiting`/`skipped_waiting`（`RequestQueue`）、`running`（list）、`finished_req_ids`、`reset_preempted_req_ids`。

### 暂停状态 `PauseState`

| 状态 | 值 | 行为 |
|------|----|------|
| `UNPAUSED` | 0 | 正常调度 |
| `PAUSED_NEW` | 1 | 不再接入新请求，仅调度 running 中的请求 |
| `PAUSED_ALL` | 2 | 任何请求都不调度（`schedule` 将 token 预算置 0） |

### 调度策略 `SchedulingPolicy`

每请求携带 `priority: int = 0`（`vllm/v1/request.py`）。`Request.__lt__` 的比较键为 `(priority, arrival_time, request_id)`——**priority 值越小越先调度**，同优先级按到达时间，再按 request id。`request_queue.py` 提供：

| 策略 | 实现 | 说明 |
|------|------|------|
| `FCFS`（`"fcfs"`） | `FCFSRequestQueue(deque)` | 先到先出；`prepend_request` 置于队首（抢占后回队列） |
| `PRIORITY`（`"priority"`） | `PriorityRequestQueue`（`heapq`） | 按 `(priority, arrival_time)` 堆序 |

`create_request_queue(policy)` 工厂按策略选择队列。`skipped_waiting` 存放因阻塞状态（远程 KV / streaming / grammar）或异步依赖暂不能调度的请求；`PRIORITY` 模式下 `_select_waiting_queue_for_scheduling` 会比较两个队首谁的序更小。

### 请求状态机 `RequestStatus`

| 状态 | 转入条件 | 转出动作 |
|------|---------|---------|
| `WAITING` | 新请求入队 | 调度成功 → `RUNNING` |
| `WAITING_FOR_STREAMING_REQ` | resumable 请求本段生成完毕且仍有后续输入块 | 收到下一个 `StreamingUpdate` → `WAITING`；会话结束 → 完成态 |
| `WAITING_FOR_STRUCTURED_OUTPUT_GRAMMAR` | 请求使用结构化输出，grammar 尚未编译完成 | grammar 就绪 → `WAITING`；编译失败 → `FINISHED_ERROR` |
| `WAITING_FOR_REMOTE_KVS` | 调度到需要异步从远端加载 KV 的请求 | 传输完成 → `WAITING`/`PREEMPTED`（见 `_update_waiting_for_remote_kv`） |
| `RUNNING` | 正常调度执行中 | 停止/抢占 → 完成态或 `PREEMPTED` |
| `PREEMPTED` | 块分配不足被抢占（`_preempt_request`） | 重新调度 → `RUNNING` |
| `FINISHED_*` | `is_finished()` 判定：所有大于 `PREEMPTED` 的状态均为完成态 | 释放块与请求记录 |

结束状态及 finish reason：`FINISHED_STOPPED`→stop、`FINISHED_LENGTH_CAPPED`→length、`FINISHED_ABORTED`→abort、`FINISHED_IGNORED`→length、`FINISHED_ERROR`→error、`FINISHED_REPETITION`→repetition。

### `schedule()` 连续批处理主循环

调度没有独立的 prefill/decode 阶段：每个请求以 `num_tokens_with_spec = len(prompt_token_ids) + len(output_token_ids) + len(spec_token_ids)` 为目标，逐步让 `num_computed_tokens` 追赶上去，天然覆盖 chunked prefill、前缀缓存、投机解码。预算约束：`token_budget = max_num_scheduled_tokens`、`input_budget = max_num_batched_tokens`、draft 槽位 `num_lookahead_tokens`，running 数上限 `max_num_seqs`。

1. **先调度 running**：按队序计算 `num_new_tokens`（含 output placeholders），受 `long_prefill_token_threshold`（无 `-1` 时限制单段 prefill 长度）、`max_model_len` 封顶；`allocate_slots` 分配 KV 块失败则触发抢占。
2. **再调度 waiting**：先做前缀缓存查询 `get_computed_blocks`（命中上限 `num_tokens - 1`，末 token 必须重算取 logits），有 KV connector 时叠加外部命中并可能异步加载（进入 `WAITING_FOR_REMOTE_KVS`）；满足 `max_num_running_reqs`、`max_loras` 等约束后入 `running`。
3. 编码器输入（多模态）调度 `_try_schedule_encoder_inputs` 受 `encoder_compute_budget` 与编码器缓存容量约束。
4. 构造 `SchedulerOutput`：`scheduled_new_reqs`（`NewRequestData`）、`scheduled_cached_reqs`（`CachedRequestData`，仅传增量）、`num_scheduled_tokens`、`preempted_req_ids`、`finished_req_ids`、`num_common_prefix_blocks`（cascade attention 用）等。
5. `_update_after_schedule` 推进 `num_computed_tokens`、标记 `is_prefill_chunk`，随后清空本周期的 `finished_req_ids`/`reset_preempted_req_ids`。

DP（数据并行）prefill 均衡：`throttle_prefills=True` 且此前 prefill 未饱和时，将新 prefill 计算推迟到对齐 cadence 的步，decode 仍照常运行。

### 抢占（Preemption）

`allocate_slots` 返回 `None`（空闲块不足）时抢占最低优先级请求：

| 策略 | 受害者选择 |
|------|-----------|
| `PRIORITY` | `max(running, key=(priority, arrival_time))`，即 priority 值最大（最低优先级）者；若其本步已被调度则撤销并回退预算 |
| `FCFS` | `running.pop()`（队尾，最近追加者） |

`_preempt_request`：释放 KV 块与编码器缓存、`status=PREEMPTED`、`num_computed_tokens=0`、清空 spec tokens、`num_preemptions += 1`、放回 `waiting` 队首。AsyncScheduler 下在途输出标记 stale。`reset_prefix_cache(reset_running_requests=True)` 会对全部 running 强制抢占后重置缓存。

### 请求停止判定 `check_stop`（`sched/utils.py`）

顺序判定：未达 `min_tokens` 不停止 → 末 token 为 `eos_token_id` 或命中 `stop_token_ids` → `FINISHED_STOPPED` → 达到 `max_model_len`/`max_tokens` → `FINISHED_LENGTH_CAPPED` → 检测到尾缀重复模式（`RepetitionDetectionParams`）→ `FINISHED_REPETITION`。

### AsyncScheduler 与 Scheduler 的区别

`AsyncScheduler`（`async_scheduler.py`）继承 `Scheduler`，用于异步调度（允许下一批与其输出重叠计算，配合 PP/V2 runner），差异：

| 维度 | `Scheduler` | `AsyncScheduler` |
|------|-------------|------------------|
| 在途 token 记账 | `num_in_flight_tokens` | 用 `num_output_placeholders` 预占本步将产生的 token（`+ num_sampled_tokens_per_step + spec tokens`） |
| 草稿 token | 下步由 `update_draft_token_ids` 写回 | 占位符 `[-1] * n` 由 worker 侧更新 |
| PP 步进约束 | 无 | v2 runner 下设置 `next_decode_eligible_step = current_step + pp_size`，限制同请求解码节奏 |
| 块释放 | 立即 | 通过 `last_sched_seq`/`processed_step_seq` 围栏延迟释放，防止在途前向仍写块 |
| 暂停对外输出 | 正常交付 | 抢占后在途输出标记 `drop_stale_output`/`num_stale_output_tokens` 记账 |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)