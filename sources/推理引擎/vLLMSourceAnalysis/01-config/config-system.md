## VllmConfig 配置体系总览

本文基于 vLLM `vllm/config/` 源码,说明 `VllmConfig` 如何聚合全部子配置,以及配置的加载、合并、校验与哈希机制。

所有配置类使用 `utils.config()` 装饰器(pydantic dataclass),默认 `ConfigDict(extra="forbid")` 禁止额外字段;均可计算 `compute_hash()` 用于编译/缓存键。

### VllmConfig 聚合结构

`VllmConfig`(`vllm/config/vllm.py`,约 2700 行)是贯穿引擎的配置载体,经 `EngineArgs.create_engine_config()` 装配。字段如下(**默认构造**即 `Field(default_factory=...)` 的引用):

| 字段 | 类型 | 默认构造 | 必选 | 说明 |
|------|------|----------|------|------|
| `model_config` | `ModelConfig` | 无,默认 `None` | 是 | 模型配置;默认构造会触发下载模型,故必须显式传入 |
| `cache_config` | `CacheConfig` | `CacheConfig` | 否 | KV cache 配置 |
| `parallel_config` | `ParallelConfig` | `ParallelConfig` | 否 | TP/PP/DP/CP/EP 并行配置 |
| `scheduler_config` | `SchedulerConfig` | `SchedulerConfig.default_factory` | 否 | 调度器配置;InitVar 缺省 `max_model_len=8192`、`is_encoder_decoder=False` |
| `device_config` | `DeviceConfig` | `DeviceConfig` | 否 | 设备配置,`__post_init__` 由平台推断 `device_type` |
| `load_config` | `LoadConfig` | `LoadConfig` | 否 | 权重加载格式与策略 |
| `offload_config` | `OffloadConfig` | `OffloadConfig` | 否 | 权重 CPU offload 配置 |
| `attention_config` | `AttentionConfig` | `AttentionConfig` | 否 | 注意力后端/内核配置 |
| `mamba_config` | `MambaConfig` | `MambaConfig` | 否 | Mamba SSU 后端配置 |
| `kernel_config` | `KernelConfig` | `KernelConfig` | 否 | 内核选择与 warmup 配置 |
| `lora_config` | `LoRAConfig \| None` | `None` | 否 | LoRA 配置 |
| `speculative_config` | `SpeculativeConfig \| None` | `None` | 否 | 投机解码配置 |
| `diffusion_config` | `DiffusionConfig \| None` | `None` | 否 | 离散扩散(dLLM)模型配置 |
| `structured_outputs_config` | `StructuredOutputsConfig` | `StructuredOutputsConfig` | 否 | 结构化输出后端配置 |
| `observability_config` | `ObservabilityConfig` | `ObservabilityConfig` | 否 | 指标/OTLP trace 配置 |
| `quant_config` | `QuantizationConfig \| None` | `None` | 否 | 运行时量化配置(非 args 类) |
| `compilation_config` | `CompilationConfig` | `CompilationConfig` | 否 | torch.compile / CUDA graph 捕获配置,支持 `-cc.[field]=v` 简写 |
| `profiler_config` | `ProfilerConfig` | `ProfilerConfig` | 否 | torch/cuda/proton profiler 配置 |
| `kv_transfer_config` | `KVTransferConfig \| None` | `None` | 否 | 分布式 KV cache 传输配置 |
| `kv_events_config` | `KVEventsConfig \| None` | `None` | 否 | 事件发布配置 |
| `ec_transfer_config` | `ECTransferConfig \| None` | `None` | 否 | 分布式 encoder cache 传输配置 |
| `ec_manager_config` | `EncoderCacheManagerConfig` | `EncoderCacheManagerConfig` | 否 | 自定义 encoder cache 管理器配置 |
| `reasoning_config` | `ReasoningConfig \| None` | `None` | 否 | 推理(reasoning)模型配置 |
| `additional_config` | `dict \| SupportsHash` | `dict()` | 否 | 平台附加配置,参与哈希 |
| `instance_id` | `str` | `""` | 否 | `__post_init__` 设为 `time.time_ns()` |
| `optimization_level` | `OptimizationLevel` | `O2` | 否 | O0-O3,越高级启动越慢、性能越好 |
| `performance_mode` | `PerformanceMode` | `balanced` | 否 | `balanced`/`interactivity`/`throughput` |
| `weight_transfer_config` | `WeightTransferConfig \| None` | `None` | 否 | RL 训练期权重传输配置 |
| `shutdown_timeout` | `int` | `0` | 否 | 停机关机宽限期(秒),`>=0` |

`OptimizationLevel` 为 `IntEnum`:O0 无优化、O1 Dynamo+Inductor 编译与 Piecewise CUDA graph、O2 增加 Full/Piecewise CUDA graph、O3 同 O2。`OPTIMIZATION_LEVEL_TO_CONFIG` 把级别映射到 `compilation_config`/`kernel_config` 的默认字典。

### 配置加载与 CLI 装配

CLI 参数定义于 `EngineArgs`(`vllm/engine/arg_utils.py`),加载流程:

1. `EngineArgs.create_engine_config()` 解析 `--xxx` 参数,逐类构造子配置 dataclass(如 `ModelConfig`、`CacheConfig`、`ParallelConfig`)。
2. 记 `ModelConfig` 中保存的 `tokenizer`、`model` 回写到 `EngineArgs`,供后续复用。
3. 组装 `VllmConfig(...)`,随后在 `VllmConfig.__post_init__` 中做跨配置校验。
4. 环境变量由 `vllm.envs` 模块承载:以模块级 `environment_variables` dict(变量名 → 读取函数)声明,通过模块 `__getattr__` 懒加载;`validate_environ(hard_fail)` 拒绝未知 `VLLM_*` 变量;服务初始化后 `enable_envs_cache()` 做缓存。

### 合并与覆盖机制

- `utils.replace(dc, **kwargs)`:兼容 pydantic dataclass 的 `dataclasses.replace`,仅保留 `init` 字段重建实例。
- `utils.update_config(config, overrides)`:递归合并,字段不存在或类型不符时抛 `ValueError`;子配置为 dataclass 时要求 override 值必须是 Mapping 或目标类型。
- `VllmConfig.with_hf_config(hf_config, architectures=None)`:用实际加载的 HF config 深拷贝重建 `model_config`(含 `tie_word_embeddings` 传递),返回新实例,供模型加载后对齐 config。
- `VllmConfig._apply_optimization_level_defaults`/`_set_config_default`:按优化级别把默认值写入 `compilation_config` 等子配置(`-cc.param=val` 简写基于 `replace`)。

### 校验与哈希

- `VllmConfig.__post_init__` 调 `try_verify_and_update_config()`:按 `architecture` 查 `MODELS_CONFIG_MAP` 执行架构级 `verify_and_update_config`,再校验 `ModelConfig.verify_with_parallel_config`、hybrid 配置、Run.ai 加载格式等;`config_updated` 标志防止重复执行。
- 跨配置校验示例:`--enable-return-routed-experts` 与 PP>1 / 上下文并行(DCP/PCP>1)冲突时报错。
- 哈希:`utils.normalize_value()` 将枚举(带 FQN)、torch.dtype、Path、dataclass、容器等规范化为可 JSON 序列化结构,`get_hash_factors` + `hash_factors` 输出 SHA-256。每个子配置 `compute_hash()` 声明"影响计算图结构"的字段集合,`VllmConfig.compute_hash()` 聚合版本号与各子哈希,作为 torch.compile / CUDA graph 缓存键。`compute_hash_cached` 按对象身份缓存。

### 全局 current config

`set_current_vllm_config(vllm_config, check_compile, prefix)` 为上下文管理器,把当前 `VllmConfig` 存线程局部变量并挂载编译层面钩子;`get_current_vllm_config()` 与 `get_current_vllm_config_or_none()` 读取;`get_layers_from_vllm_config` 按层类型提取层配置。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)