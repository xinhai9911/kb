## EngineArgs 与协议定义（arg_utils.py / protocol.py）

`vllm/engine/arg_utils.py`（2890 行）是两代引擎共用的 CLI 参数装配层，本文聚焦 `EngineArgs` 自身结构、默认值与校验，与 01-config 的 `VllmConfig` 装配互补。

### EngineArgs：dataclass 字段结构

`EngineArgs` 是约 230 个字段的 `@dataclass`（`arg_utils.py:423`）。默认值**不重复硬编码**，而是引用 `vllm/config` 各子配置类的类属性作为单一来源：

```python
@dataclass
class EngineArgs:
    model: str = ModelConfig.model
    tensor_parallel_size: int = ParallelConfig.tensor_parallel_size
    gpu_memory_utilization: float = CacheConfig.gpu_memory_utilization
    max_model_len: int = ModelConfig.max_model_len
    ...
```

| 默认值来源 | 代表字段 |
|---|---|
| `ModelConfig` | `model`/`tokenizer`/`dtype`/`seed`/`max_model_len`/`quantization`/`max_logprobs` 等 |
| `ParallelConfig` | `tensor_parallel_size`/`pipeline_parallel_size`/`nnodes`/`data_parallel_*` 等 |
| `CacheConfig` / `LoadConfig` / `SchedulerConfig` | `gpu_memory_utilization`/`kv_cache_dtype`；`load_format`/`download_dir`；`watermark`/`stream_interval` 等 |
| `VllmConfig`（经 `get_field`） | `compilation_config`/`attention_config`/`kernel_config`/`optimization_level` 等子配置对象 |
| 本地字面量 | `device_ids=None`、`enable_lora=False`、`shutdown_timeout=0` 等 |

关键设计：`block_size`/`max_num_batched_tokens`/`max_num_seqs`/`enable_chunked_prefill`/`enable_prefix_caching` 等字段默认为 `None`，**由 `create_engine_config` 按模型与使用场景回填**（见下文默认值推导）。

### __post_init__：入参归一化

- dict → 配置对象：`compilation`/`attention`/`mamba`/`kernel`/`ec_manager`/`eplb`/`weight_transfer`/`fault_tolerance`/`ir_op_priority` 等字段传入 dict 时自动构造对应 dataclass；`fault_tolerance_config` 会顺带自动开启 `enable_fault_tolerance`。
- `quantization_config` 经 `resolve_quantization_config()` 解析在线简写；随后 `load_general_plugins()` 加载插件；`HF_HUB_OFFLINE` 时（非云存储 URI）把 `model`/`tokenizer` 替换为本地路径。

### add_cli_args：反射式参数生成

`add_cli_args(parser)`（staticmethod）按配置类分组注册参数。分组与来源：

| argument group | 来源配置类 |
|---|---|
| 标准分组 | 15 个配置类各建一组：Model / Load / Attention / Mamba / StructuredOutputs / Parallel / Cache / Offload(UVA+Prefetch) / MultiModal / LoRA / Observability / Scheduler / Compilation / Kernel / VllmConfig |
| 其他参数 | `--disable-log-stats`/`--aggregate-engine-logging`/`--fail-on-environ-validation`/`--shutdown-timeout`/`--device-ids`/GDN 与 KDA 后端，及 DP 简写（`-dp/-dpn/-dpr/-dpl/-dpa/-dpp/-dpb`） |

`get_kwargs(cls)` → `_compute_kwargs(cls)`（`lru_cache`）反射 dataclass 字段类型生成 argparse kwargs，类型映射：

| 字段类型 | argparse 行为 |
|---|---|
| `bool` | `BooleanOptionalAction`（同时生成 `--x`/`--no-x`） |
| `bool \| str \| None` | 裸 flag 为 `True`，带值为字符串（`nargs="?"`, `const=True`） |
| `Literal[...]` | 生成 `choices`/`metavar` |
| `tuple/list/set` | 元素类型 + `nargs`（tuple 按 `Ellipsis` 区分） |
| `int` | `max_model_len` 用 `human_readable_int_or_auto`；部分字段用 `human_readable_int`（支持 1K/2M/1G）；其余 `int` |
| dataclass 类型 | `TypeAdapter(cls).validate_json`，help 附 API docs 链接 |
| `dict` | `json.loads`（`dict[str,str]` 用 `union_dict_and_str`，JSON 内数值支持 k/m/g 后缀展开） |
| 含 `None` | `optional_type` 包装，`""`/`"None"` → `None` |

### create_engine_config：装配与校验

`create_engine_config(usage_context=None, headless=False) -> VllmConfig`（`arg_utils.py:1943`）流程：

1. `current_platform.pre_register_and_update()`；构造 `DeviceConfig`；`envs.validate_environ(fail_on_environ_validation)`。
2. 非云存储模型经 `maybe_override_with_speculators()` 改写 `model`/`tokenizer`/`speculative_config`。
3. `create_model_config()`（约 80 参数直传 `ModelConfig`）并回写 `model`/`model_weights`/`tokenizer`；`_check_feature_supported()` 校验 PP>1 的 executor 支持。
4. 默认值回填：`_set_default_chunked_prefill_and_prefix_caching_args`（按模型支持，RISC-V 强制关闭）、`_set_default_reasoning_config_args`、`_set_default_max_num_seqs_and_batched_tokens_args`。
5. DP 校验：`hybrid_lb`/`external_lb` 互斥；`nnodes` 须整除 world size；非 MoE 禁用 external LB；external LB 要求 `data_parallel_rank`（可经 `node_rank` 推导）；fault tolerance 仅支持 external LB。
6. 组装 `CacheConfig`（`kv_cache_dtype` 先解析 "auto"，`turboquant_*` 追加 skip layers）、`ParallelConfig`（`assigned_physical_gpu_ids=_resolve_device_ids()`，Ray 下告警、禁止混用 int/UUID）、`SchedulerConfig`、`LoRAConfig`（仅 `enable_lora` 时构造）、`AttentionConfig`（`attention_backend` 互斥、TurboQuant 强制 FA2）、`MambaConfig`（字符串转枚举）、`KernelConfig`（`moe_backend`/`linear_backend` 覆盖）。
7. 返回 `VllmConfig(...)`（`VllmConfig.__post_init__` 内做跨配置校验，见 01-config）。

### 批量默认值分档（get_batch_defaults）

`get_batch_defaults(world_size)` 按显存/设备/UsageContext 给出 `max_num_batched_tokens`/`max_num_seqs` 默认值：

| 设备条件 | LLM_CLASS（离线） | OPENAI_API_SERVER |
|---|---|---|
| 显存 ≥160GB（B200/B300） | 16384 / 1024 | 16384 / 1024 |
| 显存 ≥70GB 且非 A100（H100/H200） | 16384 / 1024 | 8192 / 1024 |
| 其他 GPU | 8192 / 256 | 2048 / 256 |
| TPU（V6E/V5E/V5P 分档） | 2048~512 | 1024~256 |
| CPU（按 world_size 缩放） | 4096·ws / 256·ws | 2048·ws / 128·ws |

`performance_mode="throughput"` 时未显式指定的值 ×2；非 chunked prefill 时取 `max(model_max_len, 默认值)`；`max_num_batched_tokens` 再以 `max_num_seqs * max_model_len` 封顶。

### AsyncEngineArgs

```python
@dataclass
class AsyncEngineArgs(EngineArgs):
    enable_log_requests: bool = False
```

仅新增 `enable_log_requests`；`add_cli_args(parser, async_args_only=False)` 非 `async_args_only` 时先调 `EngineArgs.add_cli_args`，再补 `--enable-log-requests`，最后 `pre_register_and_update(parser)`。

### protocol.py：EngineClient 协议

`protocol.py` 定义两类对象：

**`StreamingInput`**（dataclass）：`prompt: EngineInput` + `sampling_params: SamplingParams | None = None`，用于 `generate()` 多轮流式会话（输入经 async generator 逐块提供）。

**`EngineClient`**（`ABC`，"Protocol class for Clients to Engine"）——前端与引擎的统一契约，v1 `AsyncLLM` 即其实现：

| 成员 | 类别 | 说明 |
|---|---|---|
| `vllm_config`/`model_config`/`renderer`/`input_processor` | 类属性 | 引擎对象 |
| `is_running`/`is_stopped`/`errored`/`dead_error` | abstract property | 运行状态 |
| `generate`/`encode` | abstract | 生成/池化请求，返回 `AsyncGenerator[RequestOutput/PoolingRequestOutput]`；`generate` 接受 `EngineCoreRequest`/`PromptType`/`EngineInput`/`AsyncGenerator[StreamingInput]` |
| `abort` | abstract | `(request_id: str \| Iterable[str])` 异步中止 |
| `notify_kv_transfer_request_rejected` | abstract | KV 传输被拒时通知引擎做 connector 清理 |
| `check_health`/`do_log_stats`/`is_tracing_enabled` | abstract | 健康/统计/追踪 |
| `start_profile`/`stop_profile`/`reset_mm_cache`/`reset_encoder_cache`/`reset_prefix_cache` | abstract | 性能与缓存管理 |
| `sleep`/`wake_up`/`is_sleeping` | abstract | 休眠（`level`+`PauseMode`） |
| `add_lora` | abstract | 动态加载 LoRA 适配器 |
| `pause_generation`/`resume_generation`/`is_paused` | abstract | 暂停/恢复请求准入 |
| `shutdown` | abstract | `(timeout: float \| None)` 关闭 |
| `scale_elastic_ep`/`collective_rpc`/`handle_fault`/`get_status`/`get_supported_tasks`/RL 权重传输系列 | 非 abstract | 默认 `raise NotImplementedError`（弹性 EP、集体 RPC、容错、权重传输等可选能力） |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
