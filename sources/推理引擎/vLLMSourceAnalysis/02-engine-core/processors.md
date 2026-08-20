## 输入/输出处理链路

### 管线总览

```
用户输入 → Renderer(渲染) → InputProcessor → EngineCoreRequest
        → (ZMQ/msgpack) → EngineCore 输入线程 preprocess_add_request
        → Scheduler / 模型执行
        → EngineCoreOutputs → (ZMQ) → 前端 OutputProcessor.process_outputs
        → Detokenizer + LogprobsProcessor → RequestOutput → 调用方
```

输入侧在生产 `EngineCoreRequest`；输出侧消费同一结构的引擎输出，合并为外层 `RequestOutput`/`PoolingRequestOutput`。

### InputProcessor（`v1/engine/input_processor.py`）

| 方法 | 职责 |
|---|---|
| `_validate_params` | 校验 `SamplingParams`/`PoolingParams`，并与 `supported_tasks`（generate/pooling 任务）比对 |
| `_validate_lora` | LoRA 请求与 `lora_config` 一致性检查 |
| `process_inputs` | 核心转换：tokenize（`InputPreprocessor.preprocess`）或直接接收已渲染 `EngineInput`；`split_enc_dec_input` 分开编码/解码输入；构造 `mm_features`；最终构造 `EngineCoreRequest` |
| `process_inputs_async` | `make_async` 包装，把阻塞的 tokenize/多模态处理分派到渲染器线程池，避免阻塞事件循环 |
| `assign_request_id` | 把外部 `request_id` 存入 `external_req_id`，内部 ID 追加 8 位随机后缀保证唯一 |
| `inject_into_mm_cache` | 前端已外部预处理的多模态数据注入处理器缓存 |

关键行为：

- `sampling_params.max_tokens` 未设置时，按 `max_model_len - 提示长度` 填充。
- 采样参数会从 generation config、EOS token、tokenizer 增量更新。
- prompt 长度/词表 ID 越界、`prompt_token_ids` 为空、多模态嵌入数超 `encoder_cache_size` 都抛 `VLLMValidationError`。

### EngineCore 输入线程预处理（`core.py`）

`process_input_sockets` 收到 `ADD` 帧后：

1. `MsgpackDecoder(EngineCoreRequest, oob_tensor_provider=tensor_ipc_receiver)` 解码（多模态张量走 IPC 队列）。
2. `preprocess_add_request`：
   - 用 `mm_receiver_cache.get_and_update_features` 复用多模态特征；
   - `Request.from_engine_core_request(...)` 生成内核 Request（含 `request_block_hasher` 前缀哈希）；
   - 结构化输出请求调 `structured_output_manager.grammar_init(req)` 预编译语法（异步，调度前必检查完成）。
3. `MultiModalCacheMissError`（P0/P1 缓存漂移）→ 返回可重试错误响应，前端丢弃失效 hash 后重发。

### OutputProcessor（`v1/engine/output_processor.py`）

状态核心是 `RequestState`（每请求一份），内含 `detokenizer`、`logprobs_processor`、`output_kind`、`stream_interval`、统计与流式队列。

`process_outputs` 是 vLLM V1 中**唯一遍历整批 EngineCoreOutputs 的循环**（开发者注释明确禁止另起全批量循环）：

1. 更新迭代统计（延迟、LoRA 状态）。
2. `new_token_ids` 非空时调 `detokenizer.update` 增量解码并做 stop 串检测；命中则把 `finish_reason` 改为 `STOP`、记录 `stop_reason`。
3. 调 `logprobs_processor.update_from_output` 更新样本/prompt logprobs。
4. `make_request_output` 按 `output_kind`/`stream_interval` 决定是否产出 `RequestOutput`：
   - `FINAL_ONLY`：未 finished 不输出；
   - 间隔控制：finished、首个 token 或达到 `stream_interval` 才发；
   - `DELTA`：只发自上次以来的增量 token。
5. 请求结束后释放；若 detokenizer 检出了 stop 但 EngineCore 尚不知情，把这些 ID 放进 `reqs_to_abort` 回送内核。

分发方式：

| 模式 | 去向 |
|---|---|
| `LLMEngine`（同步） | 追加进返回列表 `request_outputs` |
| `AsyncLLM`（异步） | 写入该请求的 `RequestOutputCollector`，由 `generate()` 协程消费 |

`RequestOutputCollector`：每请求一个 `asyncio.Event` 缓冲；DELTA 模式下消费者落后时合并输出。`abort_requests` 支持外部 ID→多个内部 ID 的映射，并级联中止子请求（`ParentRequest`）。流式输入（`resumable`）通过 `input_chunk_queue` 排队 `StreamingUpdate`，逐块推进 prompt 后重新进入 prefill。

### Detokenizer（`v1/engine/detokenizer.py`）

| 实现 | 选路条件 | 说明 |
|---|---|---|
| `FastIncrementalDetokenizer` | tokenizers≥0.22 且为 `TokenizersBackend` | 基于 `tokenizers.decoders.DecodeStream`，用 prompt IDs 原生预热；处理特殊 token 空格抑制；`Invalid prefix encountered`/溢出时重建流或返回 None |
| `SlowIncrementalDetokenizer` | 其它情况 | Python 侧 `detokenize_incrementally`，维护 `tokens`/`prefix_offset`/`read_offset` |
| `IncrementalDetokenizer` | 无 tokenizer | 跳过解码，仅记录 token IDs |

`update(new_token_ids, stop_terminated)` 返回命中的 stop 串或 `None`。`check_stop_strings` 支持多个 stop 串，取“最早完成者”，并列时按列表顺序。`include_stop_str_in_output` 控制 stop 串是否留在输出文本。`min_tokens` 满足前不做 stop 检查。

### LogprobsProcessor（`v1/engine/logprobs.py`）

| 数据 | 来源字段 | 说明 |
|---|---|---|
| 样本 logprob | `EngineCoreOutput.new_logprobs`（`LogprobsLists`） | token_ids/logprobs/ranks 三维 list；spec decode 一步多 token 时逐位置 append |
| prompt logprob | `EngineCoreOutput.new_prompt_logprobs_tensors`（`LogprobsTensors`） | 平铺张量恢复 `[num_tok, num_logprobs]` 形状后逐位生成 |

- `cumulative_logprob` 累计采样 token 的对数概率。
- `_verify_tokens`/`_correct_decoded_token`：byte-fallback tokenization 拆分多字节 UTF-8 产生 U+FFFD 时，用前文（最多 4 个）采样 token 重建正确文本。
- DELTA 语义：`pop_prompt_logprobs` 在 prefill 结束时一次性返回全部 prompt logprobs 并清空。

### 管线顺序要点

1. 输入：校验 → tokenize → 参数补全 → 多模态特征 → 序列化。
2. 内核：特征复用 → Request 构造 → 语法预编译 → 调度 → 执行 → 输出。
3. 输出：解码 → stop 检测 → logprob 累计 → 组包 → 分发/流式。
4. 顺序保证：`RequestState` 内沿 `new_token_ids` 增量推进；spec decode 的一次多 token 也在同一循环内逐 token 处理。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)