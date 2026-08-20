## model_loader 模型加载

### 模块职责

`vllm/model_executor/model_loader/` 负责：把磁盘（或 HF Hub / ModelScope / 对象存储）上的权重文件读入模型实例，按并行策略切分、量化、重排参数，并校验加载完整性。`get_model()`（`model_loader/__init__.py`）是统一入口：

```text
get_model(vllm_config) -> get_model_loader(load_config) -> loader.load_model(vllm_config, model_config, prefix)
```

### 加载策略选择（load_format → Loader）

| load_format | 实现类 | 说明 |
|---|---|---|
| `auto`/`hf`/`safetensors`/`fastsafetensors`/`instanttensor`/`mistral`/`npcache`/`pt` | `DefaultModelLoader` | 默认加载器，按文件类型/库差异选择迭代器 |
| `dummy` | `DummyModelLoader` | 随机权重用于性能分析/`sleep` 重载，不读磁盘 |
| `sharded_state`/`runai_streamer_sharded` | `ShardedStateLoader` | 每 rank 只读自己的分片（`model-rank-{rank}-part-{part}.safetensors`） |
| `tensorizer` | `TensorizerLoader` | 基于 CoreWeave tensorizer 库的流式序列化 |
| `runai_streamer` | `RunaiModelStreamerLoader` | safetensors 流式加载（本地 FS / S3 / GCS / Azure Blob） |
| `modelexpress` | `ModelExpressModelLoader` | 薄封装，转发给第三方 `modelexpress` 包 |

- `register_model_loader(load_format)` 装饰器可向 `_LOAD_FORMAT_TO_MODEL_LOADER` 注册自定义加载器，须继承 `BaseModelLoader`。
- `model_loader_extra_config` 提供各 load format 专属选项，未知键会抛 `ValueError`（如 `DefaultModelLoader` 仅接受 `enable_multithread_load`、`num_threads`、`enable_weights_track`）。

### ModelLoader 抽象（`base_loader.py`）

| 成员 | 说明 |
|---|---|
| `download_model(model_config)` | 抽象方法，先下载模型让后续可立即加载 |
| `load_weights(model, model_config)` | 抽象方法，把权重载入（可对已初始化模型原位加载） |
| `load_model(vllm_config, ...)` | 通用骨架：初始化 → 加载权重 → 后处理 → `model.eval()` |
| `log_model_inspection(model)` | 当 `VLLM_LOG_MODEL_INSPECTION=1` 时打印模型结构 |

`load_model` 骨架流程：

```text
set_default_torch_dtype(model_config.dtype)
initialize_model(...)        # 构造 nn.Module（见下）
self.load_weights(model, ...)
if 存在 online quant 层: finalize_layerwise_processing(model, model_config)
process_weights_after_loading(model, model_config, target_device)
return model.eval()
```

### 模型构造（`utils.py`）

- `get_model_architecture(model_config)`：解析 HF config 的 `architectures` 列表，经 `model_config.registry.resolve_model_cls()` 得到模型类与架构名；结果按 `(model, convert_type, runner_type, trust_remote_code, model_impl, architectures)` 哈希缓存于 `_MODEL_ARCH_BY_HASH`。`trust_remote_code` 参与缓存键。
- `convert_type`：`none`/`embed`/`classify`，后两者用 `as_embedding_model`/`as_seq_cls_model` 包裹模型类。
- `initialize_model()`：新式模型类须接受 `vllm_config`、`prefix` 位置参数；旧式模型类按参数名猜测补 `config`/`cache_config`/`quant_config`/`lora_config`/`scheduler_config` 并告警 DeprecationWarning。
- `configure_quant_config()`：把 `packed_modules_mapping`、`hf_to_vllm_mapper` 传引用给量化配置（尚未全部迁移到 `SupportsQuant` mixin）。

### 权重加载与后处理

- 量化层专属后处理：遍历模块，对 `quant_method.process_weights_after_loading()`（重打包、FP8 重量化等）在 `device_loading_context` 内执行，随后 `update_param_tp_status()` 校正 TP 状态。
- 延迟注意力层、`HpcModule`、模型级 `process_weights_after_loading` 钩子、torchao 重载属性依次处理。
- `_has_online_quant()`：检测任一量化方法的 `uses_meta_device` 为真则走 layerwise reload 收尾。

### DefaultModelLoader 内部流程

| 阶段 | 关键逻辑 |
|---|---|
| `_prepare_weights` | `auto` 检测到 `consolidated*.safetensors` 自动切 `mistral`；按 format 定 `allow_patterns`；本地目录直接 glob，否则 `download_weights_from_hf()`；safetensors 用 index 文件去重分片，非 safetensors 过滤 `optimizer.bin` 等推理无关文件 |
| `_get_weights_iterator` | 按 load_format 选迭代器：`safetensors_*`/`fastsafetensors`/`instanttensor`/`pt_*`/`np_cache`；`enable_multithread_load` 开启多线程版（默认 8 线程）；给权重名加 `source.prefix` |
| 流 | 主权重用 `model_config.model`，次要权重流来自模型类的 `secondary_weights` 属性 |

与加载相关的 `LoadConfig` 关键参数：`load_format`、`device`（覆盖目标设备）、`download_dir`、`ignore_patterns`、`use_tqdm_on_load`、`safetensors_load_strategy`（`lazy`/`eager`/`prefetch`/`torchao`）、`pt_load_map_location`、`safetensors_prefetch_*`。torchao checkpoint 时自动把策略切为 `"torchao"` 以在流内重建 tensor subclass。

### RNG 种子与 dummy 权重（`weight_utils.py`）

- `initialize_dummy_weights`：为每个参数用 `initialize_single_dummy_weight` 填 `[-1e-3, 1e-3]` 的均匀随机值。重点：**按参数 seed=1234 单独生成**，故 dummy 权重只依赖「元素个数 + dtype」，与设备分区无关、跨 rank 一致。
- meta 设备参数跳过（留给 online quant 最终化）；非浮点参数在 ROCm 上置零保证确定性；TPU 用 CPU generator（`uniform_` 会占用 TPU 内存）；<16bit 类型（FP8）经 fp16 中转再拷回。
- 加载完成后 `track_weights_loading`：对非量化模型（默认开启）严格比对 `named_parameters()` 与已加载名字，缺失即抛 `ValueError` 列出未初始化权重；online/后处理量化层的 scale 参数豁免（checkpoint 里可缺失）。

### MoE 专家并行权重过滤（`ep_weight_filter.py`）

EP 场景下每 rank 只需本组专家权重。`_init_ep_weight_filter` 在 `model_config.is_moe && enable_expert_parallel && enable_ep_weight_filter` 且未开 EPLB 时，按 `ep_size = dp_size * pcp_size * tp_size` 计算本 rank 的 `local_expert_ids`，`safetensors_weights_iterator` 据此在**读盘前**跳过非本地专家张量（专家权重约占 MoE 总字节 85-90%，可大幅削减存储 I/O）。

### 加载相关杂项

- 量化 config 解析（`get_quant_config`）：优先级为 HF `quantization_config`/`text_config`/`compression_config` → `hf_overrides` 的 `quantization_config_file`/`quantization_config_dict_json` → 在线量化 `OnlineQuantizationConfig` → checkpoint 目录内 `quant_cls.get_config_filenames()` 命中的配置文件。
- 兼容映射：`maybe_remap_kv_scale_name`（把弃用的 `.kv_scale` 映射到 `.attn.k_scale`，并处理 ModelOpt/Qwen3/Nemotron 等 8 种 scale 命名格式）、`maybe_remap_moe_expert_param_name`（`.experts.` 与 `.experts.routed_experts.` 新旧结构转换）。
- `use_fused_ops`：源码中「未确认」——`model_executor` 内无此参数，熔断算子开关实际由 `CompilationConfig.custom_ops`（见 custom-ops.md）控制。

### offloader 参数卸载（`offloader/`）

| 类 | 说明 |
|---|---|
| `BaseOffloader` | 抽象：`wrap_modules`/`post_init`/`sync_prev_onload`/`join_after_forward` |
| `NoopOffloader` | 默认单例，不改动模块 |
| `UVAOffloader` | 权重放 pinned CPU 内存，用 CUDA UVA 视图零拷贝直访（牺牲 PCIe 带宽）；`cpu_offload_gb>0` |
| `PrefetchOffloader` | 静态缓冲 + 事件流分叉的异步 H2D 预取（`offload_group_size>0`），兼容 torch.compile/CUDA graph |
| `create_offloader` | 按 `OffloadConfig` 选后端；`auto` 时 prefetch > uva > noop |

### warmup 核预热（`warmup/`）

`__init__.py` 为空；各子模块在模型执行前预热 JIT 内核（避免执行期边 JIT 边推理），如 `kernel_warmup.py`（b12x/cutedsl/deep_gemm/flashinfer/MHA 变体 TMA 预热）、`jit_warmup.py`、`flashinfer_autotune_cache.py` 等。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)