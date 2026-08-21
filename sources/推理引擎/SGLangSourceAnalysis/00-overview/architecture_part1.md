## SGLang 整体架构总览：进程模型与 IPC（_part1）

本文基于 SGLang 源码（`python/sglang/`，参考 commit `21c88f8625f2e699543a1c34f41d6894ef342903`）说明 SRT（SGLang Runtime）的多进程/多线程架构与 ZMQ 进程间通信。`sglang/srt/` 即服务端运行时本体。进程模型、四大 Manager 与请求端到端路径见 [_part2](architecture_part2.md)。

### 版本与定位

- `sglang/version.py` 用 `setuptools_scm` 动态取版本（`python/pyproject.toml` 中 `dynamic=["version"]`、`version_file="sglang/_version.py"`），无构建时兜底为 `0.0.0.dev0`；本知识库以 commit `21c88f86...` 为事实基准。
- SRT 即「SGLang Runtime」：HTTP server（FastAPI）+ 多进程推理引擎。入口 `sglang/launch_server.py` → `srt/entrypoints/http_server.py::launch_server`；离线 Python 入口为 `srt/entrypoints/engine.py::Engine`。
- `sglang/srt/` 目录分层：`managers/`（四大 manager 与调度）、`mem_cache/`（Radix 缓存与内存池）、`model_executor/`（ModelRunner 与 ForwardBatch）、`entrypoints/`（HTTP/Engine）、`distributed/`（NCCL/并行状态）、`server_args.py`（配置与 PortArgs）。

### 进程模型总览

`launch_server`（`http_server.py:2766`）调用 `Engine._launch_subprocesses`（`entrypoints/engine.py:1060`）拉起引擎，进程拓扑如下（`mp.set_start_method("spawn", force=True)`，`engine.py:1747`）：

| 进程 | 宿主组件 | 常驻数 | 启动处 | 说明 |
|---|---|---|---|---|
| 主进程 | FastAPI HTTP Server + `TokenizerManager` | 1 | `_setup_and_run_http_server` | 单 tokenizer 模式下三者同进程（`http_server.py:2766` docstring：「HTTP server, Engine, and TokenizerManager all run in the main process」） |
| Scheduler 子进程 | `Scheduler` + `TpModelWorker` | `pp_size × tp_size`（按 `_calculate_rank_ranges` 分配每节点） | `_launch_scheduler_processes`（`engine.py:856`） | 每个进程绑定一块 GPU，进程内 `Scheduler.init_tp_model_worker`（`scheduler.py:905`）就地创建 TP 模型 worker；**TPWorker 不是独立进程** |
| DetokenizerManager 子进程 | `DetokenizerManager` | 默认 1；`--detokenizer-worker-num>1` 时为 N 个 worker + 1 个 `MultiDetokenizerRouter` | `_launch_detokenizer_subprocesses`（`engine.py:974`） | 纯 CPU，做增量反分词 |
| DataParallelController 子进程 | `run_data_parallel_controller_process` | dp_size>1 或 MoE EP scale 时 1 | `engine.py:928` | 代理拉起并管理多个 scheduler 子进程 |
| MultiTokenizerRouter 子进程 | `MultiTokenizerRouter` + TokenizerWorker | `--tokenizer-worker-num>1` 时 1+N | `_launch_subprocesses` | 多 tokenizer 模式替代主进程内 TokenizerManager |
| SubprocessWatchdog | 监控线程 | 1 | `engine.py:1240` | 监测 scheduler/detokenizer 存活，崩溃时 SIGQUIT 清理进程树 |

子进程通过 `kill_itself_when_parent_died` 绑定父进程生命周期；scheduler 进程名形如 `sglang::scheduler_TP{n}`（`scheduler.py:5072`），detokenizer 为 `sglang::detokenizer`（`detokenizer_manager.py:522`）。

### 四大 Manager 职责

| Manager | 类（文件:行） | 进程形态 | 线程模型 | 核心职责 |
|---|---|---|---|---|
| TokenizerManager | `TokenizerManager`（`managers/tokenizer_manager.py:386`） | 主进程（或多 tokenizer worker） | asyncio(uvloop) 单事件循环 | 持有 tokenizer/mm_processor、请求校验、tokenize、`_dispatch_to_scheduler` 发请求、`rid_to_state` 记状态、`handle_loop`（:2199）收 Detokenizer 回包并组装 HTTP 响应；健康检查 `ServerStatus`（:3578） |
| Scheduler | `Scheduler`（`managers/scheduler.py:383`） | 子进程（每 TP rank 一个） | 同步主线程事件循环（`run_event_loop` :1691 → `event_loop_normal`/`event_loop_overlap`） | 收请求（`process_input_requests` :1901）、RadixCache 前缀匹配、`get_next_batch_to_run`（:3064）调度、`run_batch` 驱动前向、采样、输出 token 推给 Detokenizer；持有 `tree_cache`（:558）、KV 池 |
| DetokenizerManager | `DetokenizerManager`（`managers/detokenizer_manager.py:92`） | 子进程（默认 1） | 同步 `event_loop`（:167） | 将 `BatchTokenIDOutput` 增量解码为 `BatchStrOutput`（`_decode_batch_token_id_output` :291，维护 `DecodeStatus`/`decode_status` 字典），Embedding 直通（:209） |
| TpModelWorker | `TpModelWorker`（`managers/tp_worker.py:299`） | 与 Scheduler 同进程 | 被 Scheduler 同步调用 | 持有 `ModelRunner`，执行 `forward_batch_generation`（:574）→ ModelRunner.forward + `sample()`；CUDA stream 由 Scheduler 侧统一管理（`schedule_stream`/`forward_stream`） |

Scheduler 的 overlap 调度（`--disable-overlap-schedule` 关闭）用双 CUDA stream + `future_map` 让 CPU 调度与 GPU 前向重叠，decode 批次的 CUDA graph 捕获由 `TpModelWorker.init_cuda_graphs` 完成。

### 进程间通信（ZMQ）

所有 IPC 基于 ZMQ（`PortArgs`，`server_args.py:9901`）：单机普通模式地址为 `ipc://<tmpfile>`，DP-attention/多机模式退化为 TCP。消息默认 msgspec(msgpack) 序列化（`io_struct.py:2463`），`SGLANG_USE_PICKLE_IPC` 可切 pickle。

| 链路 | Socket 类型 | 地址字段 | 方向 |
|---|---|---|---|
| Tokenizer→Scheduler | PUSH/PULL | `scheduler_input_ipc_name` | 请求下行（`tokenizer_manager.py:553` PUSH；`ipc_channels.py:38` PULL） |
| Scheduler→Detokenizer | PUSH/PULL | `detokenizer_ipc_name` | 输出下行（`ipc_channels.py:63`；`skip_tokenizer_init` 时改发 tokenizer_ipc_name 直连） |
| Detokenizer→Tokenizer | PUSH/PULL | `tokenizer_ipc_name` | 结果上行（`detokenizer_manager.py:121` PUSH；`tokenizer_manager.py:550` PULL） |
| Engine→Scheduler(RPC) | DEALER | `rpc_ipc_name` | 控制面（`engine.py:300`；`ipc_channels.py:49`） |
| Scheduler→Metrics | PUSH | `metrics_ipc_name` | 指标上报 |

消息类型全部为 `msgspec.Struct(tag=True)`（`io_struct.py`），收端用 `msgpack.Decoder(Union[全部类型])` 按 tag 反序列化、再经 `TypeBasedDispatcher` 分派：

| 类型 | 链路 | 说明 |
|---|---|---|
| `TokenizedGenerateReqInput` / `TokenizedEmbeddingReqInput` | 下行 | 单请求（含 input_ids、sampling_params、时间戳） |
| `BatchTokenizedGenerateReqInput` / `BatchTokenizedEmbeddingReqInput` | 下行 | 批量请求（`_send_batch_request` :1619） |
| `BatchTokenIDOutput` / `BatchStrOutput` / `BatchEmbeddingOutput` | 上行 | 输出（token id / 已解码文本 / embedding 向量） |
| `AbortReq` / `FlushCacheReqInput` / `UpdateWeightFromDiskReqInput` / `FreezeGCReq` 等 | 双向/下行 | 控制消息 |
| 多模态张量 | 旁路 | `wrap_shm_features`/`cuda_vmm` 走共享内存，ZMQ 只传句柄 |

`communicator.py::FanOutCommunicator`（:13）是 tokenizer 侧的一发多收原语：一次 send 扇出给 `fan_out` 个接收方并等齐全部响应，`queueing`（FIFO 串行）/`watching`（并发共享同一在途请求）两种模式；TokenizerManager 用它向所有 scheduler 广播权重更新等控制请求。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
