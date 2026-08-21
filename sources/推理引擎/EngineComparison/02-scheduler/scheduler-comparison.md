## 02-scheduler 调度器对比：调度模型与批构建

本模块逐维度对比 vLLM V1 与 SGLang 的调度器。事实基准：vLLM V1 `Scheduler`/`AsyncScheduler`（`vllm/vllm/v1/core/sched/scheduler.py`、`interface.py`）与 SGLang `Scheduler`（`sglang/srt/managers/scheduler.py`）。KV 缓存/radix 缓存细节见本模块 [_part2](scheduler-comparison_part2.md) 与下一模块（03-kvcache）。调度策略、chunked prefill、抢占/淘汰见 [_part2](scheduler-comparison_part2.md)。

### 一、调度器架构定位

| 维度 | vLLM V1 | SGLang |
|---|---|---|
| 调度器位置 | `EngineCore` 独立进程内（`v1/engine/core.py::EngineCoreProc`），与前端 LLM/AsyncLLM 分离 | **Scheduler 独立子进程**（`scheduler.py:383`），每 `pp_size×tp_size` 一个 |
| 与模型执行的关系 | 分离：`Scheduler.schedule()` 产出决策 → `model_executor.execute_model`（独立 GPU Worker 进程） | **同进程**：Scheduler 内嵌 `TpModelWorker`，调度、KV 分配、前向驱动在同一循环内完成 |
| 调度时机 | `step()` 内 `schedule() → execute_model → update_from_output()` 双阶段分离，`batch_queue`（`max_concurrent_batches>1`）可异步重叠 | 单循环串行：收请求 → `get_next_batch_to_run` → `run_batch` → `process_batch_result` |
| 循环变体 | 引擎忙循环 `run_busy_loop`（`core.py`）+ 可选 `batch_queue` 异步重叠 | `event_loop_normal`（:1743）/ `event_loop_overlap`（:1778，双 CUDA stream 重叠）/ `event_loop_pp` / `event_loop_overlap_mlx` / PD 分离变体 |
| 调度步含义 | 每 `schedule()` 一次模型 forward | 每轮循环一次前向（prefill 批或 decode 批） |
| 并发模型 | `Scheduler`（同步）与 `AsyncScheduler`（`async_scheduler.py`，异步调度 + PP 步进围栏） | 同一 `Scheduler` 按 overlap 开关切换，`ScheduleBatch` 携带状态 |

> 关键差异 ①：vLLM V1 是「EngineCore 双层 + schedule/update 两阶段」，调度决策与结果回写各为独立 API；SGLang 是「单进程单循环」，调度与前向在同一个 while True 里按顺序推进，靠 `event_loop_overlap` 用 CUDA stream 在批边界上重叠 CPU 调度与 GPU 前向。

### 二、调度主循环对比

| 步骤 | vLLM V1 `schedule()`（`scheduler.py:496` 起） | SGLang `get_next_batch_to_run`（`scheduler.py:3064`） |
|---|---|---|
| ① | 先调度 **running**（`_schedule_running`）：逐请求算 `num_new_tokens`，受 `long_prefill_token_threshold`/`max_model_len` 封顶；`allocate_slots` 失败触发抢占 | 先处理中止/超时（`process_pending_chunked_abort`/`_abort_on_*_timeout`），合并上一 prefill 批（`stash_chunked_request` → `filter_batch` → `merge_batch`） |
| ② | 再调度 **waiting**（`_schedule_waiting`）：前缀缓存 `get_computed_blocks`（上限 `num_tokens-1`），KV connector 可异步加载进 `WAITING_FOR_REMOTE_KVS` | 选批：有 chunked/prefill 待调度走 `get_new_batch_prefill`（:3209），否则 `update_running_batch`（:3550）产 decode 批 |
| ③ | 编码器输入（多模态）`_try_schedule_encoder_inputs`，受 `encoder_compute_budget` 约束 | `_should_defer_prefill`（:1200）跳过 prefill；`dp_attn_adapter` 保证 DP 各 rank 模式一致 |
| ④ | 构造 `SchedulerOutput`；`_update_after_schedule` 推进 `num_computed_tokens`、标记 `is_prefill_chunk` | 返回 `NextBatchPlan(batch_to_run, running_batch)`（`schedule_batch.py:3423`） |
| 预算 | `token_budget=max_num_scheduled_tokens`、`input_budget=max_num_batched_tokens`、draft `num_lookahead_tokens`、running 数上限 `max_num_seqs` | `max_prefill_tokens`/`prefill_max_requests`/`chunked_prefill_size`/SWA 预算/`pp_max_micro_batch_size`（池容量截断） |
| 水位 | `watermark`（`kv_cache_manager`）为 WAITING/PREEMPTED 预留最小空闲块比例，避免频繁抢占 | `token_usage_low_watermark`（PrefillDelayer 低水位强制放行 prefill） |

### 三、批类型与 prefill/decode 分离

| 维度 | vLLM V1 | SGLang |
|---|---|---|
| 阶段模型 | **无显式阶段**：每请求以 `num_tokens_with_spec = len(prompt)+len(output)+len(spec)` 为目标，`num_computed_tokens` 逐步追赶，天然覆盖 chunked prefill/前缀缓存/投机解码（`scheduler.py:58` 附近注释） | **显式两相**：prefill 批（`ForwardMode.EXTEND`）与 decode 批（`ForwardMode.DECODE`）逐轮切换，`batch.forward_mode` 驱动不同处理器 |
| 混合批 | 同一批内可同时含 prefill 与 decode 请求（连续批处理本质） | 默认 prefill 批与 decode 批分离；`enable_mixed_chunk` 时 `mix_with_running` 把 decode 请求并入 prefill 批 |
| decode 守卫 | running 请求继续分配，块不足即抢占 | `update_running_batch` → `check_decode_mem`（`schedule_batch.py:2812`）失败先 `evict_from_tree_cache` 再 `retract_decode` |
| prefill 节流 | DP 下 `throttle_prefills=True` 推迟新 prefill 到对齐 cadence | `_should_defer_prefill`（`prefill_decode_interval` 计数）让 prefill 后连续 N 轮只跑 decode；`PrefillDelayer` 跨 rank 协商 |

### 四、批构建契约：SchedulerOutput vs NextBatchPlan/ScheduleBatch

| 维度 | vLLM V1 `SchedulerOutput`（`interface.py`） | SGLang `NextBatchPlan` + `ScheduleBatch`（`schedule_batch.py:3423`） |
|---|---|---|
| 请求描述 | `scheduled_new_reqs`（`NewRequestData`）+ `scheduled_cached_reqs`（`CachedRequestData`，**仅传增量** `num_computed_tokens` 之后的部分） | `ScheduleBatch`（`reqs`、`batch_is_full`、`forward_mode`、`extend_range`、`seq_lens`、`prefill_indices` 等字段），`prepare_for_extend`/`prepare_for_decode` 装配 |
| 增量/全量 | cached 请求走增量；new 请求全量 | 每轮重算整批 `input_ids`/`seq_lens` 快照（overlap 时 `batch.copy()` 进 `result_queue`） |
| 附加决策 | `num_scheduled_tokens`、`preempted_req_ids`、`finished_req_ids`、`num_common_prefix_blocks`（cascade attention） | `running_batch`（下一轮运行批）+ `batch_to_run`（本轮前向批）分离，`new_chunked_req` 记录未完成 chunk |
| 结果回写 | `update_from_output(scheduler_output, model_runner_output) -> dict[int, EngineCoreOutputs]` 按 client 返回 | `process_batch_result`（:3991）按 `forward_mode` 分发到 `process_batch_result_prefill/decode` 等，更新 radix、判定 finish、送 `BatchTokenIDOutput` |

### 五、队列组织与请求状态

| 维度 | vLLM V1 | SGLang |
|---|---|---|
| 队列结构 | 三段：`waiting`/`skipped_waiting`（`RequestQueue`，`request_queue.py`）+ `running`（list）；阻塞请求进 `skipped_waiting` | 两段：`waiting_queue`（list，每轮 `calc_priority` 原地重排）+ `running_batch`（`ScheduleBatch`）；retracted 请求带 `is_retracted=True` 回队 |
| 状态显式化 | `RequestStatus` 枚举：`WAITING`/`WAITING_FOR_STREAMING_REQ`/`WAITING_FOR_STRUCTURED_OUTPUT_GRAMMAR`/`WAITING_FOR_REMOTE_KVS`/`RUNNING`/`PREEMPTED`/`FINISHED_*` | 无等价状态枚举；用 `waiting_queue` 位置 + `chunked_req` + `is_retracted` 标记表达 |
| 阻塞来源 | 远程 KV、streaming 输入、grammar 编译、异步依赖 | grammar 就绪重入队（`grammar_manager.get_ready_grammar_requests`）、abort 超时 |

> 关键差异 ②：vLLM 把「阶段」隐式化——任何请求都是"已计算 token 追目标 token"的连续过程，prefill/chunk/decode 只是同一主循环内的预算切片；SGLang 把「阶段」显式化为 `ForwardMode` 与独立批构建路径（`get_new_batch_prefill`/`update_running_batch`），决策点更直观但结构更分裂。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
