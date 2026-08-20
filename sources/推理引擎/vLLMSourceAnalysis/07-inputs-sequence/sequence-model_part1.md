## 核心数据模型（一）：Request 请求对象与状态机

> 注意：本版本根目录 `vllm/sequence.py` 已无传统 `Sequence`/`SequenceGroup`/`SequenceStatus`/`BlockTable`，仅存 `IntermediateTensors`。请求数据模型迁至 `vllm/v1/request.py`（`Request`/`RequestStatus`），KV 块表迁至 `vllm/v1/worker/block_table.py`（见 [sequence-model_part2.md](sequence-model_part2.md)），调度相关结构见 03 模块。

### Request（vllm/v1/request.py:59）

`Request` 同时承担 v0 的 `Sequence` 与 `SequenceGroup` 职责：一个请求即一个对象，调度器按它调度、worker 按它记账。构造参数：

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `request_id` | `str` | 必选 | 请求唯一 ID |
| `prompt_token_ids` | `list[int] \| None` | 必选 | 已处理 prompt 的 token 序列 |
| `sampling_params` / `pooling_params` | 二者其一 | 必选 | 生成/池化二选一，都缺则 `ValueError` |
| `client_index` | `int` | `0` | 前端客户端索引 |
| `arrival_time` | `float \| None` | `None` | 缺省用 `time.time()` |
| `prompt_embeds` | `Tensor \| None` | `None` | 纯 embeds 输入 |
| `prompt_is_token_ids` | `list[bool] \| None` | `None` | 混合模式下逐位置掩码 |
| `mm_features` | `list[MultiModalFeatureSpec]` | `None` | 多模态特征规格，见 11 模块 |
| `lora_request` / `cache_salt` / `priority` / `trace_headers` | — | `None`/`0`/`None` | LoRA、prefix cache 盐值、优先级、trace 头 |
| `block_hasher` | `Callable` | `None` | 前缀缓存块哈希函数；以 partial 注入避免 `Request→partial→Request` 引用环 |
| `resumable` / `session_id` | — | `False`/`None` | 流式会话续接 |
| `reasoning_ended` / `reasoning_parser_kwargs` | — | `None` | 转发给结构化输出请求 |
| `abort_immediately` | `bool` | `False` | 入队后立即 abort（触发连接器 `request_finished` 钩子） |

关键初始化行为：

- 池化请求 `max_tokens = 1`；生成请求取 `sampling_params.max_tokens`。
- 由 `sampling_params` 生成 `StructuredOutputRequest`；存在则初始状态置 `WAITING_FOR_STRUCTURED_OUTPUT_GRAMMAR`。
- `sampling_params.extra_args` 中读取 `kv_transfer_params`、`ec_transfer_params`，`kv_cache_report_mode` 缺省 `"incremental"`。
- `num_prompt_tokens` 经 `length_from_prompt_token_ids_or_embeds` 计算（兼容纯 embeds）。
- `_all_token_ids` 三种情形：无 token ids → `[0]*num_prompt_tokens`；混合模式 → 占位 token 位置清零（避免 embed gather 越界）；否则拷贝 prompt ids。
- 对外只暴露 `ConstantList` 只读视图 `output_token_ids` / `all_token_ids`，写入必须走 `append_output_token_ids`（同时更新两列表与块哈希）。

核心方法/属性：

| 成员 | 行为 |
|---|---|
| `append_output_token_ids(id_or_list)` | 追加输出 token，随后 `update_block_hashes()` |
| `update_block_hashes()` | 将 `_block_hasher(self)` 产出的新满块哈希追加到 `block_hashes` |
| `num_tokens` / `num_tokens_with_spec` / `num_output_tokens` | `len(_all_token_ids)`、加投机 token 数、`len(_output_token_ids)` |
| `num_encoder_inputs` / `has_encoder_inputs` | `len(mm_features)` 及其非零判断 |
| `get_skip_reading_prefix_cache()` | 采样参数→池化参数→`False` |
| `get_num_encoder_embeds(input_id)` | 经 `mm_features[i].mm_position.get_num_embeds()` 取编码器嵌入数 |
| `record_event` / `take_events` | 记录/取走 `EngineCoreEvent`（`QUEUED`/`SCHEDULED`/`PREEMPTED`），供前端算时延 |
| `take_prefill_stats()` | 取走并清空 `PrefillStats` |
| `is_finished()` / `get_finished_reason()` | 委托 `RequestStatus` 与 `_FINISHED_REASON_MAP` |
| `__lt__` | 优先级排序键：`priority → arrival_time → request_id → id` |
| `from_engine_core_request(cls, request, block_hasher)` | 由进程间契约 `EngineCoreRequest` 构造本机对象 |

调度相关记账字段：`num_output_placeholders`、`num_stale_output_tokens`、`num_in_flight_tokens`（异步调度/PP 超前量）、`next_decode_eligible_step`（PP 节奏）、`last_sched_seq`（延迟释放块的围栏）、`num_preemptions`、`num_nans_in_logits`（logits 含 NaN 判定输出损坏）、`is_prefill_chunk`、`shared_prefix_boundary`（Mamba 共享前缀锚点）。

### RequestStatus 状态机

`RequestStatus`（IntEnum，`enum.auto()`）按值序递进：

| 状态 | 说明 |
|---|---|
| `WAITING` | 等待被调度 |
| `WAITING_FOR_STRUCTURED_OUTPUT_GRAMMAR` | 等待结构化输出语法编译 |
| `WAITING_FOR_REMOTE_KVS` | 等待远端 KV 传输 |
| `WAITING_FOR_STREAMING_REQ` | 流式输入，等待下一块输入 |
| `RUNNING` / `PREEMPTED` | 执行中 / 被抢占 |
| `FINISHED_*` | 终结态（见下） |

`is_finished(status)` 判定 `status > PREEMPTED`。终结态到 `FinishReason` 映射（`_FINISHED_REASON_MAP`）：`FINISHED_STOPPED→STOP`、`FINISHED_LENGTH_CAPPED→LENGTH`、`FINISHED_ABORTED→ABORT`、`FINISHED_IGNORED→LENGTH`（超长被忽略，按 OpenAI 语义仍报 length）、`FINISHED_ERROR→ERROR`、`FINISHED_REPETITION→REPETITION`、`WAITING_FOR_STREAMING_REQ→STOP`。

### StreamingUpdate

dataclass，流式续接的轻量载荷，仅含 `mm_features`、`prompt_token_ids`、`max_tokens`、`arrival_time`、`sampling_params`；`from_request` 在 `not resumable` 时返回 `None`。`Request.streaming_queue` 为 `deque[StreamingUpdate | None]`，`None` 条目表示流结束。

### IntermediateTensors（vllm/sequence.py）

根 `sequence.py` 唯一类。`@dataclass` 包装 `tensors: dict[str, torch.Tensor]`，供流水线并行**非末级**传递 hidden states/residuals：

- 刻意不用 `msgspec.Struct`（Dynamo 不支持），且手动写 `__init__` 以便 Dynamo 识别类来源文件。
- 支持按 str 取单个张量、按 slice 对所有张量切片（返回新 `IntermediateTensors`）；`__eq__` 用 `torch.equal` 逐张量比较；`empty_like` 静态方法生成同形空张量。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
