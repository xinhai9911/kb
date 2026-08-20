## 高层架构地图

### 源码包结构

vLLM 顶层 Python 包为 `vllm/`，核心区域：

| 目录 | 职责 |
|------|------|
| `entrypoints/` | 入口层：`LLM`（离线）、OpenAI 兼容 API server、CLI |
| `engine/` | 兼容别名（`LLMEngine`、`AsyncLLMEngine`、`EngineArgs`）；真正的引擎在 v1 |
| `v1/engine/` | V1 引擎前端：`LLMEngine`、`AsyncLLM`、`EngineCore`、`EngineCoreClient`、输入/输出处理 |
| `v1/core/` | 调度器、KV cache 管理器、KV cache 协调器 |
| `v1/executor/` | 执行器（单进程/Multiprocess/Ray）：驱动 worker 执行模型 |
| `v1/worker/` | worker 与 model runner：加载权重、准备输入、前向、采样 |
| `v1/sample/` | 采样器（`Sampler`）与 logits 处理器 |
| `v1/attention/` | 注意力后端选择 |
| `model_executor/models/` | 300+ 模型实现与 `ModelRegistry` |
| `distributed/` | 并行通信（NCCL、Ray、自定义 all-reduce、KV transfer） |
| `kernels/`（等） | 算子注册与内核管理 |
| `config/` | 配置体系（`VllmConfig` 聚合全部子配置） |
| `envs.py` | 环境变量体系 |
| `outputs.py` / `sampling_params.py` / `inputs/` | 顶层数据对象 |

### 组件分层

- **入口层**：`vllm.entrypoints.llm.LLM`（离线批推理，自动智能分桶）；OpenAI 兼容 server（`entrypoints/openai/api_server.py`，`vllm serve`）；CLI（`entrypoints/cli/`）。统一通过 `vllm.engine.arg_utils.EngineArgs` / `AsyncEngineArgs` 构造参数。
- **引擎前端**：`vllm.v1.engine.llm_engine.LLMEngine`（同步、离线）与 `vllm.v1.engine.async_llm.AsyncLLM`（异步、流式，在线 serving 用）。`vllm/engine/llm_engine.py` 与 `async_llm_engine.py` 仅是别名（backwards compatibility）。二者都实现 `EngineClient`（`vllm/engine/protocol.py`）。
- **引擎核心**：`EngineCore`（`v1/engine/core.py`）运行在独立进程，跑调度主循环：接收 `EngineCoreRequest` → `Scheduler.schedule()` → 分发到 `Executor.execute_model()` → 返回 `EngineCoreOutputs`。多进程模式下为 `EngineCoreProc`。
- **调度与 KV 缓存**：`v1/core/sched/scheduler.py` 的 `Scheduler.schedule()`；无独立 prefill/decode 阶段，按 `num_computed_tokens` 追赶 `num_tokens_with_spec` 统一分配 token。KV 缓存由 `KVCacheManager` / `SingleTypeKVCacheManager`（`FullAttentionManager`、`SlidingWindowManager`、`ChunkedLocalAttentionManager`、`MambaManager`、`CrossAttentionManager` 等）与 `HybridKVCacheCoordinator` 管理，支持 prefix caching。
- **注意力与采样**：`vllm/v1/attention/selector.py` 按模型/平台选后端；`vllm/v1/sample/sampler.py` 的 `Sampler(nn.Module)` 完成贪心/随机采样、logits 处理、penalty、logprobs。
- **模型执行**：`Executor`（`v1/executor/abstract.py`）→ `WorkerBase`（`v1/worker/worker_base.py`）→ `GPUModelRunner`（`v1/worker/gpu_model_runner.py`，准备 input tensor、构建 attention metadata、执行前向、采样）。
- **分布式**：`distributed/` 提供 TP/PP/DP/CP 通信原语与 `ParallelConfig`；executor 的 multiprocessing/ray 实现负责跨进程调度。
- **内核**：`vllm/ir/`、`compilation/`、`triton_utils/` 等承载 torch.compile/CUDA graph/自定义算子管理。

### 进程模型（V1）

- **API Server 进程**：处理 HTTP、输入渲染（tokenization、多模态加载），经 ZMQ 连到所有 EngineCore。默认 1 个；DP>1 时按 DP 规模伸缩（可 `--api-server-count` 覆盖）。
- **EngineCore 进程**：每个 DP rank 一个，跑调度忙循环，管理 KV cache，协调 GPU worker。
- **GPU Worker 进程**：每 GPU 一个，总数 `TP × PP × DP`；加载权重、执行前向、管 GPU 内存。
- **DP Coordinator 进程**（可选）：DP>1 时一个，负责 DP rank 间负载均衡与 MoE 同步前向。
- 进程连接方式：`EngineCoreClient` 子类 `InprocClient`（进程内，兼容模式）、`SyncMPClient`（ZMQ+后台进程，LLM 用）、`AsyncMPClient`（ZMQ+asyncio，AsyncLLM 用）。控制消息走 RPC（更推荐 data-plane 单独通信）。
- 示例：`-tp=4` 单机 → 1 API + 1 EngineCore + 4 Worker = 6 进程；`-tp=2 -dp=4` → 4+4+8+1 = 17 进程。

### v0 与 v1 架构演变

- V1 已统一为默认：`LLMEngine`/`AsyncLLMEngine` 直接别名到 `vllm.v1.*`；`VLLM_ENABLE_V1_MULTIPROCESSING` 默认 `1`，多进程引擎默认开启。
- 核心变化：调度器无 prefill/decode 阶段区分，统一按 token 分配；请求对象为 `vllm.v1.request.Request`；调度与模型执行拆到 EngineCore 独立进程；`EngineCoreRequest`/`EngineCoreOutput`（msgspec.Struct）为跨进程序列化契约。
- 旧的拆分式 `v0` 体系（`vllm/engine/llm_engine.py` 内部自包含）已移除，模块保留为前向兼容别名。废弃环境变量如 `VLLM_TRITON_ATTN_USE_TD` 仅告警。

### 配置体系

- `VllmConfig`（`config/vllm.py`）为引擎级全局配置聚合对象，所有类共享传递；子配置包括 `ModelConfig`、`ParallelConfig`、`CacheConfig`、`SchedulerConfig`、`SpeculativeConfig`、`LoRAConfig`、`DeviceConfig`、`CompilationConfig` 等。
- 模型构造器统一为 `__init__(self, *, vllm_config: VllmConfig, prefix: str = "")`，权重分片与量化在初始化期间完成（避免把完整大模型权重加载进每张卡再切片）。

### 环境变量体系（`vllm/envs.py`）

- 核心结构：`environment_variables: dict[str, Callable]` 逐个注册；通过模块级 `__getattr__` 惰性求值（如 `envs.VLLM_CPU_KVCACHE_SPACE`）。
- `enable_envs_cache()` 用 `functools.cache` 包住 `__getattr__` 并预取全部变量（服务初始化后调用）；`disable_envs_cache()` 还原；`is_set(name)` 判断显式设置；`validate_environ(hard_fail)` 检查未知 `VLLM_*` 变量。
- `compile_factors()` 返回参与 torch.compile 缓存键的环境变量哈希因子（忽略路径类、日志类等不影响编译结果的变量）。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)