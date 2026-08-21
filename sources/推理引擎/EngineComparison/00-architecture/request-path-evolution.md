## vLLM V1 vs SGLang SRT：请求端到端路径、两代演进与设计理念

承接 [_part1](architecture-comparison.md)（进程模型与通信协议）。本部分把一次生成请求的完整生命周期逐环节对照，并对比 vLLM v0→v1 演进与两引擎的设计理念。事实基准：vLLM KB（00-overview/architecture.md、02-engine-core/*）、SGLang KB（00-overview/architecture_part1/_part2、02-managers/*）。

### 一、请求端到端路径逐环节对照

| 环节 | vLLM V1 | SGLang SRT |
|---|---|---|
| 1. 入口 | 离线 `LLM.generate`（`entrypoints/llm.py`，`_run_completion`→`_add_completion_requests`）；在线 `vllm serve` → `AsyncLLM.generate()` | `POST /generate`（`http_server.py:894`）→ `TokenizerManager.generate_request`（`tokenizer_manager.py:765`） |
| 2. 输入渲染/校验 | `Renderer.render_cmpl`（解析 prompt）→ `InputProcessor.process_inputs`（tokenize、`split_enc_dec_input`、构造 `mm_features`，`input_processor.py`） | `normalize_batch_and_arguments`（统一 text/input_ids/input_embeds）→ `_tokenize_one_request`（:995，含 mm_processor）→ `ReqState` 登记 |
| 3. 跨进程下行 | `EngineCoreClient` 发 `EngineCoreRequest`（`ADD` 帧，msgpack） | `_dispatch_to_scheduler`（:569）PUSH `TokenizedGenerateReqInput`/`BatchTokenizedGenerateReqInput` |
| 4. 内核收请求 | `process_input_sockets` → `preprocess_add_request`：`mm_receiver_cache` 特征复用 → `Request.from_engine_core_request`（含 block hasher 前缀哈希）→ 结构化输出预编译语法 | `SchedulerRequestReceiver.recv_requests`（`request_receiver.py:49`，仅 rank0 拉取）→ 经 NCCL/gloo `broadcast_pyobj` 广播同 TP/PP rank → `process_input_requests`（:1901） |
| 5. 前缀复用 | hash-based block 命中（`PrefixCachingBlockAllocator`） | `RadixCache.match_prefix`（`radix_cache.py:377`）：沿树找最长公共前缀，命中段内**分裂节点**暴露精确边界，`inc_lock_ref` 保护运行中路径 |
| 6. 调度 | `Scheduler.schedule()`：**无 prefill/decode 阶段区分**，按 `num_computed_tokens` 追赶 `num_tokens_with_spec` 统一分配 token | `get_next_batch_to_run`（:3064）：prefill 优先、decode 合并；overlap 模式 CPU 调度与 GPU 前向双 stream 重叠 |
| 7. 模型执行+采样 | `Executor.execute_model(non_block)` → `GPUModelRunner` 前向 → `Sampler`（`v1/sample/sampler.py`） | `TpModelWorker.forward_batch_generation`（`tp_worker.py:574`）→ `ModelRunner.forward` + `sample()`；CUDA graph 由 `init_cuda_graphs` 捕获 |
| 8. 输出下行 | `EngineCoreOutputs`（批量容器）PUSH 回前端 | `BatchTokenIDOutput` PUSH 给 Detokenizer（`ipc_channels.py:63`） |
| 9. 反分词 | 前端 `OutputProcessor.process_outputs`：`Detokenizer.update` 增量解码 + **stop 串检测**（命中改 `finish_reason=STOP`） | `DetokenizerManager._decode_batch_token_id_output`（:291）：`DecodeStatus` 增量窗口解码、`trim_matched_stop` 裁剪 stop 串，回 `BatchStrOutput` |
| 10. 组包分发 | `make_request_output` 按 `output_kind`/`stream_interval` 产出 `RequestOutput`；异步写入 `RequestOutputCollector` | `TokenizerManager.handle_loop`（:2199）→ `_handle_batch_output`（:2214）填 `meta_info`（`finish_reason`/`prompt_tokens`/`cached_tokens`）→ `_wait_one_response` yield 给 HTTP |
| 11. 中止 | `abort_requests` 走 `aborts_queue` 双写，step 后幂等批量处理；流式输入用 `input_chunk_queue` | `abort_request`（:1991）PUSH `AbortReq`；HTTP 断开 2s 后 `create_abort_task` 自动触发 |

> 逐环节关键差异：
> - **反分词归属不同**：vLLM 放前端进程（减少一次跨进程回传，但占用前端 CPU），SGLang 放独立 Detokenizer 子进程（CPU 与 GPU 引擎解耦，但多一跳 PUSH/PULL）。
> - **前缀复用实现不同**：vLLM 用 hash-based block（相等前缀→同 hash 命中），SGLang 用显式 radix 树（最长公共前缀匹配 + 节点分裂 + 叶子驱逐，可部分复用且支持 EAGLE bigram 视图）。
> - **调度模型不同**：vLLM V1 取消 prefill/decode 阶段概念，统一按 token 分配；SGLang 仍显式区分 prefill 批次与 decode 批次。
> - **流式回传粒度**：vLLM 用 `EngineCoreOutputs` 批量容器 + DELTA 增量；SGLang 用 `BatchStrOutput` 按 `stream_interval` 批量，增量流式经 `_coalesce_streaming_chunks` 合并积压块。

### 二、两代架构演进

| 维度 | vLLM v0 | vLLM v1（现状） |
|---|---|---|
| 进程模型 | 引擎可同进程运行（`InprocClient` 即 v0 风格兼容） | 默认 EngineCore 独立后台进程（`VLLM_ENABLE_V1_MULTIPROCESSING=1`），前端/内核/Worker 三类进程 |
| 调度 | prefill/decode 阶段分离 | 无阶段区分，统一按 token 分配（`num_computed_tokens`） |
| 请求契约 | 进程内对象直传 | `EngineCoreRequest`/`EngineCoreOutput(s)`（msgspec Struct）跨进程序列化 |
| 反分词 | 引擎内 | 前端 `OutputProcessor`（Fast/Slow `IncrementalDetokenizer`） |
| 旧代码 | `vllm/engine/llm_engine.py` 自包含引擎 | 仅保留为兼容别名（docstring 注明 "Legacy...backwards compatibility"） |
| DP 扩展 | 有限 | `DPCoordinator` + `DPLBAsyncMPClient`（负载感知选引擎）+ wave 同步 |

SGLang 无 v0/v1 分裂，SRT 进程模型自诞生即「主进程 + Scheduler 子进程 + Detokenizer 子进程」，现状演进点：`--detokenizer-worker-num` 多 Detokenizer、`--tokenizer-worker-num` 多 tokenizer worker + `MultiTokenizerRouter`、DP-attention（数据面/控制面分流广播）、`--enable-overlap-schedule` 默认开。

### 三、设计理念对比

| 理念 | vLLM V1 | SGLang SRT |
|---|---|---|
| 架构哲学 | **模块化 + 强解耦 + 稳定生产**：前端（Input/OutputProcessor）与内核（EngineCore）硬隔离，职责单一、契约显式（msgspec）、多执行器抽象（单进程/Multiprocess/Ray） | **运行时一体化**：四大 Manager 各司其职、ZMQ 单向环流水线化，Scheduler 与 TpModelWorker 同进程减少拷贝 |
| 性能主张 | 调度器统一 token 分配 + `batch_queue`/multi-batch 消除 pipeline bubble；CUDA graph / torch.compile 编译体系（`ir/`、`compilation/`） | **RadixAttention 极致前缀复用**：radix 树 + lock_ref 保护 + 叶子驱逐；overlap 双 stream；EAGLE 投机解码 native 支持 |
| 生成能力 | 通用生成 + pooling + 结构化输出（grammar 预编译）；LoRA/spec decode 插件式 | 生成/Embedding 同管，**多模态生成一体** + `sglang.lang` 结构化生成 DSL（`lang/`：`sgl.gen`/`sgl.select` 编译为 IR） |
| 稳定性/生产 | 进程隔离（调度崩溃不拖 Worker）、`EngineCoreSentinel` 容错包装、优雅 sleep/wake 分级、自动 fit `max_model_len`/`num_gpu_blocks` | SubprocessWatchdog 进程树清理、权重/LoRA 热更新 + `is_pause` 暂停门、`HealthCheckOutput` 健康检查 |
| 控制面 | 集中 `UtilityOutput`/`collective_rpc` | 89 种 tagged 消息 + FanOut 广播（`merge_results` 聚合 rank） |

### 四、小结

- **进程拓扑**：vLLM V1 三层（前端/EngineCore/Worker），隔离最强；SGLang 两层（主进程/Scheduler+Worker、Detokenizer），进程数少、路径短。
- **通信**：都是 ZMQ + msgspec(msgpack)；vLLM 以少量强类型契约 + Client 多实现，SGLang 以大量 tagged 类型 + TypeBasedDispatcher/FanOutCommunicator。
- **前缀复用**：vLLM hash-block（简单可靠），SGLang radix 树（极致复用 + EAGLE）。
- **调度**：vLLM 无 prefill/decode 阶段，SGLang 显式区分并做 overlap。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
