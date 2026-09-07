## 进程拓扑与启动冻结点（主进程 / EngineCore / Worker）

> 主题：引擎核心启动阶段（日志「引擎核心启动」）固化的三进程拓扑。关系视图见 `scratch/vllm-v1-process-topology.html`。
> 回链：[engine-overview.md](engine-overview.md)（消息契约与类职责）· [../08-distributed/worker-executor.md](../08-distributed/worker-executor.md)（Executor 选型）· [../15-v1-worker/worker-overview.md](../15-v1-worker/worker-overview.md)（Worker 类层次）

### 三进程两层拓扑

```text
[主进程]  进程A   API/收发（AsyncLLM / OpenAI Server）          GIL①
    │ ① spawn 拉起（launch_core_engines，一次性）  ⇅ ZMQ: EngineCoreRequest↓ EngineCoreOutputs↑
[EngineCore] 进程B  调度/排队/KV块管理/广播（run_busy_loop）     GIL②
    │ ② MultiprocExecutor spawn 拉起（按 world_size，一次性）  ⇅ ZMQ: 广播 SchedulerOutput↓ Future 按序聚合↑
[Worker × world_size] 进程C…  ModelRunner 跑前向（CPU 平台 CPUWorker）  GIL③
                        ▲ 主进程与 Worker 无任何直接连线（不创建、不通信）
```

| 关系 | 创建（spawn） | 通信 | 一句话 |
|---|---|---|---|
| 主进程 → EngineCore | ✅ 主进程 `launch_core_engines` 拉起 | ✅ ZMQ 每步传请求/收输出 | 前厅把单子递给大脑 |
| EngineCore → Worker | ✅ 它内部的 MultiprocExecutor 拉起 | ✅ 广播 `SchedulerOutput`、按序收 Future | 大脑把活分给车间 |
| 主进程 ↔ Worker | ✕ | ✕ | **互不知道对方存在**，一切经 EngineCore 转发 |
| Worker ↔ Worker | — | ✅ 集合通信（gloo/NCCL） | TP 切片交换；CPU 单机一般用不到 |

勘误提醒：通俗解读里常见「multiproc_executor 拉起 EngineCore」——方向反了。创建链是两层：**主进程拉起 EngineCore；MultiprocExecutor 是 EngineCore 进程内部的执行器，由它拉起 Worker**（见 `vllm/v1/engine/utils.py` 的 `CoreEngineProcManager` 与 `vllm/v1/executor/multiproc_executor.py` 的 `WorkerProc`）。

### 为什么拆进程：GIL 隔离

Python 同一进程内同一时刻只有一个线程执行字节码。调度循环想吃满一个核，若与 API 收发、输出处理同居一进程（v0 风格），三方抢同一把 GIL，调度被卡顿。V1 拆成三层各持独立 GIL：

- 主进程卡住只影响新请求接入，不影响正在跑的推理
- EngineCore 调度循环可**常驻满载**（两条 daemon 线程收发 ZMQ 与调度重叠）
- Worker 在 C++/算子内释放 GIL；调度崩溃不拖 Worker（`EngineCoreSentinel` 容错）

通信选 ZMQ IPC + msgpack（`msgspec.Struct` 契约）：控制面消息小而高频，开销低于 HTTP/gRPC。回退同进程调试：`VLLM_ENABLE_V1_MULTIPROCESSING=0`。

### world_size / rank / DP 与 gloo 约定

- `world_size`=执行侧总进程数、`rank`=每进程全局编号、DP 组=数据并行复制组；在此阶段定型（`ParallelConfig` 见 [../01-config/sub-configs_part2.md](../01-config/sub-configs_part2.md)）。
- **CPU 上 world_size=1 仍走 gloo 初始化**：NCCL 是 CUDA 专属不可用，gloo 做 CPU 元数据协调/barrier/对象广播（`GroupCoordinator.cpu_group`，`backend="gloo"`）；单进程也完整走一遍签到，保证 CPU/GPU 同一条代码路径——少一条分支少一类 bug。
- 后端退避：请求后端不可用（如无 NCCL）时警告并回退 gloo（见 [../08-distributed/parallel-state.md](../08-distributed/parallel-state.md)）。

### 启动日志「Config:」= 权威副本

参数在主进程组装成 `VllmConfig`，但 EngineCore 是另一进程，收到的是序列化后重建的副本。日志打印的 Config 段是 **EngineCore 实际收到、实际按此运行**的配置——核对参数生效看它，不是命令行。

### 冻结点：之后无法改并发/并行规模

本阶段完成后以下东西按 world_size/rank 物化，改拓扑只能重启：

- ZMQ socket 已绑定地址，进程间管道已建立
- gloo/NCCL 通信组已初始化（rank 编号已分配）
- Worker 进程已按并行规模拉起（OS 级资源）
- 后续 KV cache 池、编译缓存（CUDA Graph 档位）均按此拓扑分配

CPU 绑核（core id 分配）也在此前后发生。

### 排障核对清单

- **Config: 大段** → 核对真正生效的 `enforce_eager` / `tensor_parallel_size` / `max_model_len`；与命令行对不上 = 参数没传进去
- **world_size / rank** → 并行规模是否符合预期（CPU 应为 1）
- **READY 回执** → `max_model_len` / `num_gpu_blocks` 是 auto-fit 后的值，可能与配置不同（`startup_handshake` 流程见 [engine-overview.md](engine-overview.md)）
- **报错定位** → 主进程报错在 API 层；EngineCore 报错在调度/内存；Worker 报错在模型执行/内核

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
