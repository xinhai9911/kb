## multimodal_gen：图像/视频生成运行时架构

`sglang/multimodal_gen/`（SGLang Diffusion）是与 `srt` 并列的同级包，服务于扩散模型（图像/视频/3D）生成。基于 FastVideo（2025-09-24 fork），并行库复用 xDiT，管线设计参考 diffusers，端到端加速由 `sgl-kernel`、运行时调度与各类缓存完成。

### 与 srt 的关系

| 维度 | 说明 |
|---|---|
| 运行时 | 完全独立：自有 `Scheduler`/`GPUWorker`/`PipelineExecutor`，不使用 srt 的 LLM scheduler、KV cache、RadixAttention |
| 依赖 | 仅复用 `sglang.srt.observability.trace`（如 pipelines_core/schedule_batch.py:42）、`sglang.kernels` 与 `sglang.utils` 命名空间 |
| 并行 | xDiT 风格并行组：tp、classifier-free guidance（cfg）、ulysses、ring、sequence parallel（sp） |
| 入口 | `DiffGenerator`（Python SDK）、`sglang generate/serve` CLI、OpenAI 兼容 API、realtime session |

### 包结构

| 目录/文件 | 职责 |
|---|---|
| `registry.py` | 多模态模型中心注册表：`get_model_info` 按模型路径解析管线类与采样参数 |
| `configs/pipeline_configs/` | `PipelineConfig` 基类 + 各模型配置（`flux`、`wan_*`、`qwen_image`、`zimage`、`sana`、`hunyuan3d`…） |
| `configs/sample/` | `SamplingParams`、Spectrum 采样参数 |
| `runtime/entrypoints/` | `diffusion_generator.py`（`DiffGenerator`）、`http_server.py`、`openai/`、`cli/`（generate/serve） |
| `runtime/launch_server.py` | 服务端进程启动（`launch_server`） |
| `runtime/scheduler_client.py` | 同步客户端（`sync_scheduler_client`） |
| `runtime/server_warmup.py` | 首包预热（`SchedulerWarmupMixin`、`run_sync_client_warmup`） |
| `runtime/registry.py`、`runtime/managers/`、`runtime/pipelines_core/`、`runtime/pipelines/` | 见下 |
| `runtime/cache/`、`runtime/loader/`、`runtime/layers/`、`runtime/models/` | 缓存加速、组件加载、自定义层、模型实现 |
| `third_party/`、`csrc/`、`benchmarks/`、`apps/`、`testtools/` | 三方依赖、C++ 扩展、基准、示例、测试 |

### 执行模型（runtime/managers）

`Scheduler`（managers/scheduler.py）跑在 rank 0：`zmq.ROUTER` 绑定 `scheduler_endpoint_for(dp_replica)` 接收外部请求，按 DP 副本分块；`_MAX_RECV_REQS_PER_POLL=1024` 批量收包，经 `dynamic_batch_admission.BatchAdmissionController` 准入后交给 worker。

- `GPUWorker`（gpu_worker.py）：`spawn` 启动的 GPU 进程，初始化 sp/tp/cfg/ulysses/ring 并行组，执行 `ComposedPipelineBase` 的阶段流水。
- `CPUWorker`（cpu_worker.py）：CPU 平台替代。
- `memory_managers/`：组件驻留策略（resident / component-offload / layerwise-offload，`ComponentResidencyManager`）+ `MemoryOccupationController`。
- `disaggregation/`：去耦生成（调度/去噪分角色，`RoleType`、`SchedulerDisaggMixin`）。

### 管线内核（runtime/pipelines_core）

`ComposedPipelineBase`（composed_pipeline_base.py）定义多阶段组合管线的框架：无状态、持有 `modules` 与 `executor`；`build_pipeline`（pipelines_core/__init__.py）仅接受合法 HF diffusers `model_index.json`，输出 `PipelineWithLoRA`（`LoRAPipeline` + 组合管线双继承）。

| 部件 | 职责 |
|---|---|
| `stages/base.py` `PipelineStage` | 单阶段抽象；实例：`InputValidationStage`、`TextEncodingStage`、`ImageEncodingStage`、`LatentPreparationStage`、`TimestepPreparationStage`、`DenoisingStage`（含 DMD/causal/progressive 变体）、`DecodingStage`、`ImageVAEEncodingStage` |
| `executors/` | `PipelineExecutor`（抽象基类）+ `parallel_executor.py`（并行）+ `sync_executor.py`（同步） |
| `schedule_batch.py` | `Req`/`OutputBatch`/`BatchMetricsWindow` 等函数式传递状态，受 srt `forward_batch_info.py` 启发（文件头注明） |
| `composed_pipeline_base.py` | 阶段编排、模块装载顺序（`order_component_load_specs`）、组件驻留管理 |

`runtime/pipelines/` 放具体模型管线（flux、wan_*、qwen_image、zimage、sana、hunyuan3d 等），各自组合上述 stage 并声明 `is_video_pipeline`。

### 生成加速缓存（runtime/cache）

| 实现 | 原理 |
|---|---|
| `teacache.py` | TeaCache：相邻扩散步调制输入 L1 距离累积超阈值才强制计算，正向/负向 CFG 分支独立缓存（arXiv 2411.14324） |
| `spectrum.py` | Spectrum：对 denoiser block 输出做 Chebyshev 多项式岭回归，训练无关的跳步预测（arXiv 2603.01623） |
| `cache_dit_integration.py` | cache-dit 集成：DiT 块级缓存（DBCache、TaylorSeer），`enable_cache_on_transformer` 等钩子 |

### 关键流（DiffGenerator）

`DiffGenerator`（entrypoints/diffusion_generator.py）统一入口：`from_pretrained(model_path, num_gpus, ...)` → 装配 `ServerArgs` → `launch_server` 拉起 `Scheduler`+workers → `sync_scheduler_client` 建立同步客户端；`generate(sampling_params_kwargs)` 提交 `Req`，Scheduler 按阶段流水推进，最终 `OutputBatch` 回传并经 `post_process_sample`/`save_outputs` 落盘。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
