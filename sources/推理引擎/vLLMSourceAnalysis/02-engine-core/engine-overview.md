## EngineCore 引擎核心总览

### 三大引擎的关系

vLLM V1 采用「前端进程 + EngineCore 后台进程」的两层架构：

| 引擎 | 文件 | 角色 |
|---|---|---|
| `LLM` | `vllm/entrypoints/llm.py` | 离线批量推理入口，同步驱动 `LLMEngine.step()`，提供 `generate`/`enqueue`/`chat`/`wait_for_completion`/池化 |
| `AsyncLLM` | `vllm/v1/engine/async_llm.py` | 在线服务用异步引擎（实现 `EngineClient` 协议），`generate()` 返回 `AsyncGenerator`，供 `vllm serve` 调用 |
| `EngineCore` | `vllm/v1/engine/core.py` | 引擎内核：调度 + 模型执行 + 输出产生，常驻独立进程；`EngineCoreProc`/`DPEngineCoreProc` 为其 ZMQ 封装 |

`LLM` 与 `AsyncLLM` 都只持有一个 `EngineCoreClient`。后者把请求发给 EngineCore，取回 `EngineCoreOutputs`。区别在驱动方式：`LLM` 同步 `step()`；`AsyncLLM` 由后台 asyncio `output_handler` 任务持续消费。

### 进程间契约类型

定义于 `vllm/v1/engine/__init__.py`，全部为 `msgspec.Struct`（msgpack 序列化）：

| 类型 | 方向 | 说明 |
|---|---|---|
| `EngineCoreRequest` | 前端→内核 | 请求体：`request_id`、`prompt_token_ids`、`mm_features`、`sampling_params`/`pooling_params`、`lora_request`、`data_parallel_rank`、`client_index` 等 |
| `EngineCoreOutput` | 内核→前端 | 单请求输出：`new_token_ids`、`new_logprobs`、`pooling_output`、`finish_reason`、`stop_reason`、`events` 等 |
| `EngineCoreOutputs` | 内核→前端 | 批量容器：`outputs`、`scheduler_stats`、`finished_requests`、DP wave 信号 |
| `EngineCoreReadyResponse` | 内核→前端 | 启动握手回执，含 `max_model_len`、`num_gpu_blocks`、并行规模等 |
| `UtilityOutput` | 内核→前端 | 工具调用返回（`call_id` + `result`/`failure_message`） |
| `EngineCoreRequestType` | 帧头字节 | `ADD`/`ABORT`/`START_DP_WAVE`/`UTILITY`/`EXECUTOR_FAILED`/`WAKEUP` |

### v1 相对 v0 的职责划分

`vllm/engine/` 下仍保留 v0 的代 `llm_engine.py`、`async_llm_engine.py`，但当前 `LLM`/`AsyncLLM` 实际使用 `vllm/v1/engine/llm_engine.py`（docstring 注明「Legacy LLMEngine for backwards compatibility」）。`EngineArgs`（`vllm/engine/arg_utils.py`）两代共用。

| 层次 | v0 | v1 |
|---|---|---|
| 请求/输出处理 | 均在引擎进程内 | 前端（`InputProcessor`/`OutputProcessor`）+ 内核（`EngineCore`）分离 |
| 调度、采样、KV 管理 | 引擎进程中「单层」 | 归入 `EngineCore` + 独立 `Scheduler`/Executor |
| 进程模型 | 可同进程 | 默认 EngineCore 独立后台进程，ZMQ 控制面 + msgpack 序列化 |
| DP 扩展 | 有限 | `DPCoordinator` 全局协调 wave 与负载 |

### 核心类职责表

| 类 | 文件 | 职责 |
|---|---|---|
| `LLM` | `entrypoints/llm.py` | 离线同步推理，内部 `self.llm_engine` 为 v1 `LLMEngine` |
| `AsyncLLM` | `v1/engine/async_llm.py` | 异步推理；后台 `output_handler` 循环把输出推入每请求 `RequestOutputCollector` |
| `LLMEngine` | `v1/engine/llm_engine.py` | 兼容接口：`add_request`/`step`/`abort_request`；组装 Input/OutputProcessor 与 client |
| `EngineCore` | `v1/engine/core.py` | 内核本体：`add_request`/`abort_requests`/`step`/`shutdown`/`sleep`/`collective_rpc` |
| `EngineCoreProc` | `v1/engine/core.py` | ZMQ 后台进程包装 + `run_busy_loop` + 输入/输出 socket 线程 |
| `DPEngineCoreProc` | `v1/engine/core.py` | DP（MoE）内核：wave 同步、两阶段暂停、`_has_global_unfinished_reqs` all-reduce |
| `EngineCoreActor`/`DPMoEEngineCoreActor` | `v1/engine/core.py` | Ray actor 形态的 EngineCore |
| `EngineCoreClient` | `v1/engine/core_client.py` | 抽象基类；`make_client` 工厂按模式选择实现 |
| `SyncMPClient`/`AsyncMPClient` | `v1/engine/core_client.py` | ZMQ 多进程 client 的同步/异步实现 |
| `InprocClient` | `v1/engine/core_client.py` | EngineCore 同进程、无 busy loop（v0 风格） |
| `DPAsyncMPClient`/`DPLBAsyncMPClient` | `v1/engine/core_client.py` | DP client；后者做基于负载分数的引擎选择 |
| `InputProcessor` | `v1/engine/input_processor.py` | EngineInput → `EngineCoreRequest` |
| `OutputProcessor` | `v1/engine/output_processor.py` | `EngineCoreOutputs` → `RequestOutput` |
| `DPCoordinator` | `v1/engine/coordinator.py` | DP>1 协调进程：负载统计发布 + 全局 wave/运行态 |
| `CoreEngineProcManager`/`CoreEngineActorManager` | `v1/engine/utils.py` | EngineCore 进程/actor 的创建、就绪、存活监控、关闭 |

### 事件循环（EngineCoreProc.run_busy_loop）

```
while _handle_shutdown():
    _process_input_queue()          # 1) 轮询 input_queue，无工作时阻塞
    _maybe_publish_request_counts() # 发布 DP 负载统计（coordinator 模式）
    _process_engine_step()          # 2) step 内核，EngineCoreOutputs 入 output_queue
    _maybe_publish_request_counts()
```

- `_process_input_queue` 处理 `ADD`/`ABORT`/`UTILITY`/`WAKEUP`；空闲时释放 GIL 等待。
- `step()`（或启用 batch queue 时的 `step_with_batch_queue`）：`scheduler.schedule()` → `model_executor.execute_model(non_block=True)` →（可延迟）`sample_tokens(grammar)` → `scheduler.update_from_output()` 产生 `EngineCoreOutputs`。
- `batch_queue`（`max_concurrent_batches>1` 时启用，`deque` of Futures）允许调度与模型执行异步重叠，消除 pipeline bubble。
- 两条 daemon 线程与 ZMQ socket 通信：`process_input_sockets`（收帧→msgpack 解码→input_queue，必要时 `preprocess_add_request`）与 `process_output_sockets`（output_queue→PUSH 发送）。目的是让 ZMQ IO 与 GPU 计算重叠。
- abort 请求另走 `aborts_queue`（对 `ABORT` 双写两队列），在 step 结束后统一批量处理（幂等）。

### 请求状态机

| 状态（`RequestStatus`，`vllm/v1/request.py`） | 说明 |
|---|---|
| `WAITING` | 等待被调度 |
| `WAITING_FOR_STRUCTURED_OUTPUT_GRAMMAR` | 等结构化输出语法编译完成 |
| `WAITING_FOR_REMOTE_KVS` | 等远端 KV 传输（KV 连接器） |
| `WAITING_FOR_STREAMING_REQ` | 流式输入请求，等下一块输入 |
| `RUNNING` | 正在执行 |
| `PREEMPTED` | 被抢占 |
| `FINISHED_STOPPED` / `FINISHED_LENGTH_CAPPED` / `FINISHED_ABORTED` / `FINISHED_IGNORED` / `FINISHED_ERROR` / `FINISHED_REPETITION` | 终结态（`PREEMPTED` 之后均视为 finished） |

- `FinishReason`（IntEnum）：`STOP`/`LENGTH`/`ABORT`/`ERROR`/`REPETITION`，对外即 `RequestOutput.finish_reason` 字符串。
- `EngineCoreEvent`（`QUEUED`/`SCHEDULED`/`PREEMPTED`）+ 单调时间戳随输出下发，前端用它计算排队/调度/首 token 时延。
- 终结映射：`FINISHED_LENGTH_CAPPED`/`FINISHED_IGNORED`→`LENGTH`；`WAITING_FOR_STREAMING_REQ`→`STOP`。

### 启动握手与关闭

- 前端 `EngineCoreClient` 初始化时 `launch_core_engines` 拉起 EngineCore 进程（及 DP 模式下的 `DPCoordinator`），前端 `ROUTER` socket bind、引擎 `DEALER` connect。
- `startup_handshake`：`HELLO` → 前端回 `EngineHandshakeMetadata`（ZMQ 地址 + DP 配置）→ 引擎回 `READY` → 前端 `EngineCoreClient._apply_ready_response` 回写 auto-fit 后的 `max_model_len`/`num_gpu_blocks`。
- 关闭：`EngineShutdownState` `RUNNING → REQUESTED → SHUTTING_DOWN`；`shutdown_timeout=0` 立即 abort，否则 drain。
- `sleep(level)`：0 只暂停调度；1 权重卸载、丢弃 KV；2 释放全部 GPU 内存。`wake_up(tags=["scheduling"])` 恢复。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)