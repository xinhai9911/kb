## vLLM V1 vs SGLang SRT：进程模型与通信协议对比

本模块对比两大推理引擎的**架构骨架**：进程拓扑、IPC 拓扑与跨进程序列化契约。事实基准：vLLM V1 引擎（`vllm/v1/engine/core.py`）与 SGLang SRT（`sglang/srt/`，commit `21c88f86...`）。请求端到端路径与两代演进见 [_part2](request-path-evolution.md)。

### 一、进程模型总览

| 维度 | vLLM V1 | SGLang SRT |
|---|---|---|
| 主进程职责 | API Server（HTTP + 输入/输出预处理） | FastAPI HTTP Server **+ TokenizerManager**（单 tokenizer 模式同进程） |
| 推理内核进程 | **EngineCore 独立进程**（每 DP rank 一个，`v1/engine/core.py::EngineCoreProc`） | **Scheduler 子进程**（`pp_size×tp_size` 个，每进程绑一块 GPU） |
| 模型执行进程 | **GPU Worker 独立进程**（每 GPU 一个，总数 `TP×PP×DP`） | **无独立执行进程**：`TpModelWorker` 与 Scheduler **同进程**（`scheduler.py:905` 就地创建） |
| 反分词位置 | 前端进程 `OutputProcessor` 内的 Detokenizer（`v1/engine/detokenizer.py`） | **DetokenizerManager 独立子进程**（默认 1，纯 CPU，`detokenizer_manager.py:92`） |
| 附加进程 | DP>1 时 `DPCoordinator`（负载均衡 + 全局 wave）；Ray 模式 `EngineCoreActor` | DP>1 时 `DataParallelController`；多 tokenizer 时 `MultiTokenizerRouter`+`TokenizerWorker` |
| 监控 | `CoreEngineProcManager`（`v1/engine/utils.py`）管理进程生命周期 | `SubprocessWatchdog` 监控线程，崩溃 SIGQUIT 清理 |
| 进程启动 | `EngineCoreClient.launch_core_engines`；握手 `HELLO→READY` | `mp.set_start_method("spawn", force=True)`（`engine.py:1747`）；子进程 `kill_itself_when_parent_died` |
| 进程数示例 | `-tp=4` → 1 API + 1 EngineCore + 4 Worker = 6 进程 | 单机 tp=4 → 主进程 + 4 Scheduler = 5 进程 |

> 关键差异 ①：vLLM 把「调度」与「模型执行」拆成**两类进程**（EngineCore / GPU Worker），SGLang 把二者**塞进同一进程**（Scheduler 内嵌 TpModelWorker），进程数更少、少一层 IPC 拷贝；vLLM 进程更多但隔离更强（调度崩溃不拖累 Worker）。

### 二、引擎内部职责对照

| 职责 | vLLM V1（文件） | SGLang SRT（文件:行） |
|---|---|---|
| 离线入口 | `LLM`（`entrypoints/llm.py`） | `Engine`（`entrypoints/engine.py`） |
| 在线入口 | `AsyncLLM`（`v1/engine/async_llm.py`） | FastAPI server（`entrypoints/http_server.py`） |
| 输入处理 | `InputProcessor`（`v1/engine/input_processor.py`） | `TokenizerManager`（`tokenizer_manager.py:386`） |
| 调度器 | `Scheduler`（`v1/core/sched/scheduler.py`） | `Scheduler`（`managers/scheduler.py:383`） |
| 前缀缓存 | BlockManager + hash-based `PrefixCachingBlockAllocator` | `RadixCache` 前缀树（`mem_cache/radix_cache.py:303`） |
| 模型执行 | `Executor`→`GPUModelRunner`（`v1/worker/gpu_model_runner.py`） | `TpModelWorker`（`managers/tp_worker.py:299`，同 Scheduler 进程） |
| 反分词 | `FastIncrementalDetokenizer`（前端） | `DetokenizerManager`（独立子进程，`DecodeStatus` 增量窗口） |
| 输出处理 | `OutputProcessor`（`v1/engine/output_processor.py`） | `TokenizerManager.handle_loop`（`tokenizer_manager.py:2199`） |
| 控制面广播 | `collective_rpc` / DP wave | `FanOutCommunicator`（`communicator.py:13`） |

### 三、IPC（ZMQ）拓扑对比

| 链路 | vLLM V1 | SGLang SRT |
|---|---|---|
| 请求下行 | 前端 `ROUTER`(bind) ↔ 引擎 `DEALER`(connect)，帧头 `EngineCoreRequestType`（`ADD`/`ABORT`/`UTILITY`/`WAKEUP` 等） | `Tokenizer→Scheduler` PUSH/PULL（`scheduler_input_ipc_name`）；RPC 走 DEALER（`rpc_ipc_name`） |
| 输出上行 | 引擎 `PUSH` output socket（`core.py:1780`） | `Scheduler→Detokenizer→Tokenizer` PUSH/PULL 单向环（`detokenizer_ipc_name`→`tokenizer_ipc_name`） |
| 序列化 | msgspec msgpack，全部契约类型在 `v1/engine/__init__.py` | msgspec `Struct(tag=True)`（`io_struct.py`），`msgpack.Decoder(Union)` 按 tag 解码 |
| 多模态张量 | `TensorIpcReceiver`（oob tensor IPC 队列，`tensor_ipc.py`） | `wrap_shm_features`/`cuda_vmm` 共享内存，ZMQ 只传句柄 |
| 收端分派 | 按请求类型（ADD/ABORT…） + `Request` 构造 | `TypeBasedDispatcher`：Scheduler 注册约 40 种、Tokenizer 26 类 FanOut 响应 |
| IO 与计算重叠 | `process_input_sockets`/`process_output_sockets` 两条 daemon 线程 | `--disable-overlap-schedule` 双 CUDA stream + `future_map`；`SchedulerRequestReceiver` 用 `zmq.NOBLOCK` 轮询 |

> 关键差异 ②：vLLM 采用 **ROUTER/DEALER 请求-应答 + PUSH 输出**（前端为中心），SGLang 采用 **PUSH/PULL 单向管道环**（数据单向流转）+ DEALER 控制面，天然适合流式；两者都默认 msgspec(msgpack)，SGLang 可用 `SGLANG_USE_PICKLE_IPC` 回退 pickle。

### 四、通信契约对比

| 契约 | vLLM V1 | SGLang SRT |
|---|---|---|
| 请求对象 | `EngineCoreRequest`（msgspec.Struct）：`request_id`/`prompt_token_ids`/`mm_features`/`sampling_params`/`lora_request`/`data_parallel_rank` 等 | `TokenizedGenerateReqInput`/`BatchTokenizedGenerateReqInput`（含 `input_ids`/`sampling_params`/时间戳） |
| 输出对象 | `EngineCoreOutputs` 批量容器（内含 `EngineCoreOutput`/`scheduler_stats`/`finished_requests`） | `BatchTokenIDOutput`（token id）→`BatchStrOutput`（已解码文本）/`BatchEmbeddingOutput` |
| 控制面 | `UtilityOutput`/`collective_rpc`/`EngineCoreReadyResponse`（启动握手回执） | 82 种成对 Request/Output（`AbortReq`/`FlushCacheReqInput/Output`/`UpdateWeightsFromTensorReqInput/Output` 等） |
| 广播原语 | DP 模式 `DPLBAsyncMPClient`（按负载分数选引擎）+ `DPCoordinator` | `FanOutCommunicator`：`queueing`（FIFO 串行）/`watching`（共享在途请求），`merge_results` 聚合各 rank |
| 客户端 | `EngineCoreClient` 抽象基类：`InprocClient`/`SyncMPClient`/`AsyncMPClient`/`DPAsyncMPClient` | Tokenizer 侧 `_dispatch_to_scheduler`（PUSH）+ `TokenizerControlMixin` 26 条 `_COMMUNICATOR_SPECS` 声明式规格 |

> 关键差异 ③：vLLM 把契约集中定义为**少量强类型 msgspec Struct**（`EngineCoreRequest`/`EngineCoreOutput(s)`），`EngineCoreClient` 多实现负责传输层差异；SGLang 契约是**大量带 tag 的联合类型**（io_struct 共 89 种 tagged 消息），靠 `TypeBasedDispatcher` 与 `FanOutCommunicator` 声明式扩展——控制面操作种类远多于 vLLM。

### 五、控制流（事件循环）对比

| 环节 | vLLM `EngineCoreProc.run_busy_loop`（`core.py:2153`） | SGLang `Scheduler.event_loop`（`scheduler.py:1691`） |
|---|---|---|
| 收请求 | `_process_input_queue` 轮询，空闲释放 GIL 阻塞 | `process_input_requests`（:1901）从 ZMQ PULL |
| 调度 | `scheduler.schedule()`（`step()` 或 `step_with_batch_queue`） | `get_next_batch_to_run`（:3064） |
| 执行 | `model_executor.execute_model(non_block=True)` → `sample_tokens` | `run_batch` → `TpModelWorker.forward_batch_generation`（:3832） |
| 发输出 | `EngineCoreOutputs` 入 output_queue → `process_output_sockets` PUSH | `BatchTokenIDOutput` PUSH 给 Detokenizer |
| 批量重叠 | `batch_queue`（`max_concurrent_batches>1`，deque of Futures）允许调度与执行异步重叠 | `event_loop_overlap` 用双 CUDA stream + `future_map` 重叠 |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
