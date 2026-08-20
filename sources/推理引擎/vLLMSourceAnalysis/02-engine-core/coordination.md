## Coordinator / 多进程与并发机制

### 同步 vs 异步执行

| 形态 | 入口 | Client 实现 | 特征 |
|---|---|---|---|
| 同步离线 | `LLM` → `LLMEngine` | `InprocClient`（v0 兼容，同进程无 busy loop）或 `SyncMPClient` | `step()` 阻塞推进；`get_output` 从队列取整批输出 |
| 异步在线 | `AsyncLLM` | `AsyncMPClient`（DP: `DPAsyncMPClient`/`DPLBAsyncMPClient`） | asyncio：`get_output_async` 由后台任务持续消费 |
| 引擎内核进程 | 独立/后台进程 | — | `EngineCore`/`EngineCoreProc` 常驻，EventLoop 见 engine-overview |

`EngineCoreClient.make_client(multiprocess_mode, asyncio_mode, ...)` 工厂决定组合：

| multiprocess | asyncio | 结果 |
|---|---|---|
| 否 | 否 | `InprocClient` |
| 是 | 否 | `SyncMPClient` |
| 是 | 是 | `AsyncMPClient` |
| 是，DP | 是 | `DPAsyncMPClient`（外部 LB）或 `DPLBAsyncMPClient`（内部 LB） |

### 线程模型

EngineCore 侧（`EngineCoreProc`）：

| 线程/任务 | 职责 |
|---|---|
| `process_input_sockets` | ZMQ `DEALER` 收帧 → msgpack 解码 → 入 `input_queue`；`preprocess_add_request` 也在此线程（与模型 forward 并行） |
| `process_output_sockets` | 从 `output_queue` 取 `EngineCoreOutputs` → ZMQ `PUSH` 到对应前端；缓冲区复用、zero-copy 发送 |
| 主线程 | `run_busy_loop` 只消费 `input_queue`/调度/step |
| `aborts_queue` | abort 单独线程安全队列，step 后统一批量处理 |

前端侧：

| 实现 | 消费线程 | 说明 |
|---|---|---|
| `SyncMPClient` | `EngineCoreOutputQueueThread`（daemon） | 轮询 output socket，utility 结果回填 `utility_results`，普通输出入 `outputs_queue` |
| `AsyncMPClient` | `EngineCoreOutputQueueTask`（asyncio task） | 同样逻辑，消除 GIL 依赖；异常置 `EngineDeadError` |
| `MPClientEngineMonitor` 线程 | `monitor_engine_liveness` | 进程 sentinel/Ray run ref 失活检测；任一 EngineCore 意外退出 → 标记 `engine_dead` → 关闭 client，后续操作抛 `EngineDeadError` |
| `SignalCallback` | 专用信号线程 | SIGTERM/SIGINT 处理器中安全唤醒 busy loop |

### ZMQ 拓扑

| Socket | 角色 | 说明 |
|---|---|---|
| 前端 `input_socket`（`ROUTER`,bind） | 收请求 | 引擎 `DEALER` connect 后发 `EngineCoreReadyResponse` |
| 引擎 output `PUSH` | 发输出 | 前端 `PULL` 接收；帧由 `MsgpackEncoder` 生成 |
| DP `coordinator_input` / `coordinator_output` | DP 引擎 ↔ Coordinator | `XSUB`/`PUSH`，订阅消息、READY 通知、wave 广播 |
| 前端 `stats_update_socket`（`XSUB`） | 前端订阅 DP 统计 | 轮询 `(counts, current_wave, engines_running)` |

### DPCoordinator（`v1/engine/coordinator.py`）

仅 DP>1 时启动，独立进程（`DPCoordinatorProc`，进程名 `VLLM_DP_Coordinator`）。职责：

1. **负载统计发布**：收集每引擎 `[waiting, running, kv_cache_usage]`（`SchedulerStats`），按 `min_stats_update_interval_ms`（默认 100ms）或变化后 5 秒发布给前端，供内部 LB 决策。
2. **全局 wave / 运行态跟踪**：引擎在“全局运行”与“全局暂停”两态间切换，wave 号 = 集体运行→暂停的次数。rank 0 引擎经 `wave_complete` 通知；锁步 DP（MoE）由 `DPEngineCoreProc._has_global_unfinished_reqs` 每 32 步 all-reduce 达成暂停共识。
3. **`START_DP_WAVE` 广播**：前端发来新请求而引擎暂停时，或某个引擎收到旧 wave 请求时，唤醒其它引擎。

外部 LB 模式下引擎不发布统计，前端仅在 wave/运行态变化时收到更新。

### 并行采样（`v1/engine/parallel_sampling.py`）

`SamplingParams.n > 1` 时，`LLMEngine.add_request`/`AsyncLLM.add_request` 由 `ParentRequest` 扇出 n 个子请求：

| 要点 | 说明 |
|---|---|
| 子请求 ID | `"{index}_{parent_id}"`，所有子请求共享同一 prompt |
| 采样参数 | `_get_child_sampling_params`：`n=1`；`seed` 为空则缓存复用，非空则每子请求 `seed+index` 唯一种子 |
| 输出聚合 | 流式（非 `FINAL_ONLY`）：每个子完成即转出；`FINAL_ONLY`：聚合到 `output_aggregator` 列表，全部子请求完成才输出 |
| 完成判定 | `get_outputs`：`child_requests` 集空即 finished；已返回过的子输出不再下发 |
| abort 关联 | `OutputProcessor.abort_requests`（internal）命中 parent 时级联 abort 全部 child |
| 统计 | `observe_num_generation_tokens` 记录全体子请求最大生成长度 |

### tensor IPC（`v1/engine/tensor_ipc.py`）

多模态张量在 API server 与 engine core 之间零拷贝共享：

- 通道：单个 `torch.multiprocessing.Queue`（仅 DP=1 支持；`configure mm_tensor_ipc=="torch_shm"` 时由 `launch_core_engines` 创建）。
- `TensorIpcSender`（前端，作 `MsgpackEncoder` 的 `oob_tensor_consumer`）：把张量 `share_memory_()` 后放入队列，返回 `(sender_id, message_id, tensor_id)` 元数据句柄写入 msgpack 帧；失败则回落标准序列化。
- `TensorIpcReceiver`（引擎输入线程，作解码器 `oob_tensor_provider`）：**drain-and-buffer** 模式——持续排空队列缓存所有张量，直到找到句柄匹配者；丢弃过期 message（处理多发送者乱序）。
- 数据单元 `TensorIpcData`：`sender_id`/`message_id`/`tensor_id`/`tensor`。

### 多进程部署与生命周期（`v1/engine/utils.py`）

| 管理器 | 后端 | 说明 |
|---|---|---|
| `CoreEngineProcManager` | `multiprocessing` | 每 DP rank 一个 `context.Process(target=EngineCoreProc.run_engine_core)`；`monitor_engine_liveness` 用进程 sentinel 检测异常退出 |
| `CoreEngineActorManager` | Ray | 每 DP rank 一个 actor（`EngineCoreActor`/`DPMoEEngineCoreActor`）；`create_dp_placement_groups` 按 `strict`/`fill`/`span` 策略建 placement group，支持跨节点 |

`launch_core_engines`（context manager）统一：起 DPCoordinator（rank 0）、建 tensor queue、按模式拉起 proc/actor，并在 `wait_for_engine_startup` 中完成 `HELLO→init→READY` 握手；MoE+DP 模式校验各 worker `parallel_config_hash` 一致。

工具调用：`UTILITY` 请求类型把 `call_utility(method, *args)` 映射为 EngineCore 的**任意方法**远端执行（`collective_rpc`/LoRA/缓存重置等都走此通道），`_invoke_utility_method` 支持返回 `Future` 的异步方法。

弹性 EP（`DPLBAsyncMPClient`）：`prepare_elastic_ep`/`commit_elastic_ep` 跨 DP 在线扩缩容；预配 `ElasticEPScalingState`，`reinitialize_distributed`/`commit_prepared_elastic_ep` 使引擎切换新并行配置。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)