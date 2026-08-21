## 01-config 配置体系对比：配置载体与参数装配

本模块对比 vLLM 与 SGLang 的配置体系。依据：`Q:\AI\kb\sources\推理引擎\vLLMSourceAnalysis\01-config\`（config-system.md、model-config.md、sub-configs_part1/2.md）与 `Q:\AI\kb\sources\推理引擎\SGLangSourceAnalysis\01-config\`（config-system.md、server-args-groups.md、env-constants-configs.md）；源码：`vllm/vllm/config/vllm.py`、`vllm/engine/arg_utils.py`、`sglang/srt/server_args.py`。

### 1. 顶层设计对照

| 维度 | vLLM | SGLang |
|---|---|---|
| 配置载体 | `VllmConfig`（pydantic dataclass，`vllm/config/vllm.py` 约 2700 行）聚合 20+ 子配置 | `ServerArgs`（普通 dataclass，`server_args.py:454`，约 10073 行）单类承载全部参数 |
| 类型体系 | `@utils.config()` 装饰器，默认 `ConfigDict(extra="forbid")` 禁额外字段 | 普通 `@dataclasses.dataclass` + `typing.Annotated` 挂元数据 |
| 元数据注解 | 无（字段即参数） | `A[T, help]` 简写 / `Arg(help, aliases, ...)` 完整 CLI 元数据 / `NS("exec.kernel")` 配置命名空间路径 |
| CLI 生成 | `EngineArgs`（`vllm/engine/arg_utils.py`）手工 `add_argument` | `add_cli_args_from_dataclass`（`arg_utils.py:218`）扫描注解自动派生；字段名 `tp_size`→`--tp-size`，`Arg.aliases` 提供 `--tensor-parallel-size` |
| 子配置组织 | `ModelConfig`/`CacheConfig`/`ParallelConfig`/`SchedulerConfig`/`DeviceConfig`/`LoadConfig`/`KernelConfig`/`CompilationConfig` 等独立文件 | 单一 `ServerArgs` + 40+ 参数组（`server_args.py:495-3615` 注释横幅）+ `srt/configs/` 下少量独立类 |
| 运行时投影 | `set_current_vllm_config` 线程局部 + 编译钩子（`get_current_vllm_config()`） | `RuntimeContext` 只读配置袋：`get_exec()/get_memory()/get_schedule()/get_model()/get_serving()` 等按 `NS()` 路径投影 |
| 覆盖机制 | `utils.update_config` 递归合并 + `with_hf_config(hf_config)` 深拷贝重建 model_config | `arg_groups/overrides.py`（2733 行）声明式解析：`_resolved` 只读视图 + `materialize_declarations` |
| 哈希 | `compute_hash()` 作 torch.compile/CUDA graph 缓存键 | 无 `compute_hash` |

### 2. VllmConfig 聚合结构（vllm/config/vllm.py）

`VllmConfig` 经 `EngineArgs.create_engine_config()`（`arg_utils.py:1943`）装配，默认构造即 `Field(default_factory=...)`：

| 字段 | 子配置类 | 必选 | 说明 |
|---|---|---|---|
| `model_config` | `ModelConfig` | 是 | 默认构造触发下载模型，必须显式传入 |
| `cache_config` | `CacheConfig` | 否 | KV cache：`block_size=16`、`gpu_memory_utilization=0.92`、`enable_prefix_caching=True` |
| `parallel_config` | `ParallelConfig` | 否 | TP/PP/DP/PCP/DCP/EP 全并行维度 |
| `scheduler_config` | `SchedulerConfig` | 否 | 缺省 `max_model_len=8192`、`is_encoder_decoder=False` |
| `device_config` | `DeviceConfig` | 否 | `__post_init__` 由平台推断 `device_type` |
| `load_config` / `offload_config` | `LoadConfig` / `OffloadConfig` | 否 | 权重加载格式 / CPU offload |
| `attention_config` / `kernel_config` | `AttentionConfig` / `KernelConfig` | 否 | 注意力后端 / 内核选择与 warmup |
| `lora_config` / `speculative_config` | `LoRAConfig` / `SpeculativeConfig` | 否 | 默认 `None` |
| `structured_outputs_config` / `observability_config` | 对应类 | 否 | 结构化输出 / 指标 trace |
| `compilation_config` | `CompilationConfig` | 否 | torch.compile/CUDA graph，支持 `-cc.[field]=v` 简写 |
| `quant_config` / `mamba_config` / `kv_transfer_config` | 各自类 | 否 | 运行时量化 / Mamba / 分布式 KV 传输 |
| `instance_id` | `str` | 否 | `__post_init__` 设为 `time.time_ns()` |
| `optimization_level` / `performance_mode` | 枚举 | 否 | `O0-O3` / `balanced/interactivity/throughput` |

`OptimizationLevel`（IntEnum）经 `OPTIMIZATION_LEVEL_TO_CONFIG` 映射到 `compilation_config`/`kernel_config` 默认字典；`additional_config` 为平台附加配置，参与哈希。

### 3. ServerArgs 参数分组（server_args.py:495-3615）

40+ 语义分组，主要分组与代表性字段：

| 分组 | 代表性字段 |
|---|---|
| Model and tokenizer（495） | `model_path`、`tokenizer_mode/backend`、`load_format`、`context_length`、`model_impl` |
| Quantization / data type（643） | `dtype`、`quantization`、`kv_cache_dtype`、`enable_tf32_matmul` |
| Memory and scheduling（777） | `mem_fraction_static`、`chunked_prefill_size`、`schedule_policy`、`max_total_tokens`、`page_size` |
| Distributed topology（998） | `tp_size/pp_size/dp_size/dcp_size/attn_cp_size`、`nnodes/node_rank`、`load_balance_method` |
| HTTP server（1285）/ API（1367） | `host/port/enable_http2`；`api_key`、`served_model_name` |
| Constrained decoding（1692） | `grammar_backend`、`reasoning_parser`、`tool_call_parser` |
| Kernel backend（1706） | `attention_backend`、`sampling_backend`、`fp8_gemm_runner_backend` |
| Cuda graphs（1875） | `cuda_graph_config`（decode/prefill 分相） |
| Speculative / EP（2094/2358） | `speculative_algorithm`；`moe_runner_backend`、`eplb_*` |
| LoRA（2908）/ PD disaggregation（3130） | `enable_lora`；`disaggregation_mode`、`disaggregation_transfer_backend` |

### 4. 参数装配路径对比

| 路径 | vLLM | SGLang |
|---|---|---|
| CLI | `EngineArgs` 解析 `--xxx` → `create_engine_config()` 逐类构造子配置 dataclass → 组装 `VllmConfig(...)`，`ModelConfig` 中 tokenizer/model 回写 EngineArgs | `sglang serve` → `ServerArgs.from_cli_args(args)`（`server_args.py:9010`）从 Namespace 取有值字段组装实例 |
| kwargs | `VLLMEngine(engine_args)` 或 `AsyncLLMEngine.from_engine_args` | `sglang.Engine(**kwargs)`（`entrypoints/engine.py:251`）kwargs 与 ServerArgs 字段一一对应 |
| YAML | 不支持 | `--config` 由 `ConfigArgumentMerger`（`server_args_config_parser.py`，187 行）合并，优先级 **CLI > Config > 默认**，仅支持 `store_true`/`store` action |
| 直传对象 | `EngineArgs` 构造后再注入 VllmConfig | `Engine(server_args=...)` 跳过 kwargs 构造 |

SGLang `__post_init__` 后进入 `_run_resolution_pipeline()`（`server_args.py:3620`）：约 60 步有序 `_handle_*` dispatcher（模型→并行→内核→CUDA graph→内存→语法/投机→环境变量→校验→`materialize_declarations`）；完成后 `__setattr__` 守卫令字段只读，报错提示 `get_context().override(...)`。`model_path in ["none","dummy"]` 时提前短路。

### 5. 环境变量体系对比

| 维度 | vLLM（`vllm/envs.py`） | SGLang（`sglang/srt/environ.py`，1677 行） |
|---|---|---|
| 前缀 | `VLLM_*` | `SGLANG_*`（少数历史 `SGL_*` 自动重写） |
| 实现 | 模块级 `environment_variables` dict（变量名→读取函数）+ 模块 `__getattr__` 懒加载 | 类级描述符 `EnvField`/`EnvStr`/`EnvBool`/`EnvInt`/`EnvFloat`/`EnvTuple`/`EnvJSON` + `Envs` 单例（约 550 字段） |
| 注册 | 模块内声明 | `Envs` 类声明，`EnvField._allow_set_name=False` 禁止追加 |
| 未知变量 | `validate_environ(hard_fail)` 拒绝未知 `VLLM_*`（启动即报错） | 无全局拒绝；`EnvBool` 等解析失败 `warnings.warn` 并回退默认 |
| 缓存 | 服务初始化后 `enable_envs_cache()` | 描述符 `get()` 直接读 `os.getenv` |
| 废弃管理 | 无集中机制 | `_DeprecatedEnv` 注册表 + `_handle_deprecated_envs()`：改名转发（`SGLANG_QUEUED_TIMEOUT_MS→SGLANG_REQ_WAITING_TIMEOUT`）、极性翻转（`SGLANG_DISABLE_*→SGLANG_ENABLE_*`）、前缀重写 |
| 第三方缓存 | — | `redirect_third_party_caches()` 把 Triton/Inductor/NV/FlashInfer JIT 缓存重定向到 `SGLANG_CACHE_DIR` |
| 反向传播 | 少 | `_handle_environment_variables()`（`server_args.py:8150`）把 CLI 参数写回环境变量（如 `enable_torch_compile→SGLANG_ENABLE_TORCH_COMPILE`）供子进程继承 |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
