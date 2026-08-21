## 权重加载链路与参数服务

权重加载入口为 `ModelRunner.load_model`（`model_runner.py:1049`），核心委托 `model_loader/loader.py` 与 `weight_utils.py`；`weight_cache/` 提供 IPC 参数服务器，`checkpoint_engine/` 提供训练侧在线更新。

### 加载主链路

```text
ModelRunner.load_model (model_runner.py:1049)
  └─ build_load_config(...)                    # → LoadConfig
  └─ maybe_enable_ipc_weight_cache(...)        # weight_cache_mode != off → IPC_CACHE
  └─ load_model_with_memory_saver(...)         # load_model_utils.py:268
       ├─ memory_saver_adapter.region(GPU_MEMORY_TYPE_WEIGHTS, enable_cpu_backup=...)
       ├─ loader = get_model_loader(load_config, model_config)   # loader.py:4273
       ├─ loader.load_model(model_config, device_config)         # 构造模型 + 装权重
       └─ 或 StartupWeightLoadManager（--is-startup-weight-load-overlap 异步装载）
  └─ load_kv_cache_scales / resolve_sliding_window_size
```

- `load_model_with_memory_saver`（`load_model_utils.py:268`）：先 `monkey_patch_vllm_parallel_state()`，在 memory saver 的 `WEIGHTS` 区域（可配 CPU backup）内加载，随后 `empty_cache` 并反向打补丁。
- `build_load_config`（`load_model_utils.py:192`）装配 `LoadConfig`：`load_format`、`download_dir`、`model_loader_extra_config`、`tp_rank`、remote-instance 参数、`modelopt_config`、`weight_cache_mode/socket`。
- 加载后 `dist_barrier_after_load`（`load_model_utils.py:343`）：`dist.monitored_barrier`（480s 超时）检测不均衡加载。

### get_model_loader 工厂（load_format → Loader）

`loader.py:4273`，按 `load_config.load_format` 返回加载器：

| load_format | 实现类 | 说明 |
|---|---|---|
| `auto`/`safetensors`/`fastsafetensors`/`mistral`/`pt`/`npcache` | `DefaultModelLoader`（`loader.py:379`） | 默认路径，按文件类型选迭代器 |
| `dummy` | `DummyModelLoader` | 随机权重（按参数 seed=1234 生成，跨 rank 一致） |
| `sharded_state` | `ShardedStateLoader` | 每 rank 读自己的分片 |
| `presharded` | `PreshardedModelLoader` | 首次加载后落盘 per-rank 分片，带结构签名校验 |
| `bitsandbytes` | `BitsAndBytesModelLoader` | 4/8bit 量化权重流式加载 |
| `gguf` | `GGUFModelLoader` | GGUF 格式（`gguf_name_maps.py` 名称映射） |
| `layered` | `LayeredModelLoader` | 逐层加载以便逐层在线量化 |
| `flash_rl` | `QuantizedRLModelLoader` | RL 训练 FP8 原生量化 |
| `remote` / `remote_instance` | `RemoteModelLoader` / `RemoteInstanceModelLoader` | 远端加载（FS/KV / NCCL/TransferEngine） |
| `runai_streamer` | `RunaiModelStreamerLoader` | safetensors 流式加载 |
| `ipc_cache` | `IpcModelLoader`（`weight_cache/ipc_loader.py`） | 从 daemon 经 CUDA IPC 零拷贝共享权重 |
| `private` | `sglang.private.private_model_loader` | 私有扩展点 |
| `modelopt_fp8/fp4/mixed` | `ModelOptModelLoader` | NVIDIA ModelOpt 检查点（calibration/restore/export） |

自定义 `load_format` 传 `type` 时直接实例化；`auto-round-int8` 走 `IncModelLoader`。

### DefaultModelLoader 内部流程

| 阶段 | 方法 | 关键行为 |
|---|---|---|
| 权重准备 | `_prepare_weights`（`loader.py:475`） | `SGLANG_USE_MODELSCOPE` 时走 ModelScope；非本地目录经 `download_weights_from_hf`；按 format 定 `allow_patterns` 并 glob；safetensors 用 index 文件去重，非 safetensors 过滤推理无关文件 |
| 迭代器 | `_get_weights_iterator`（`loader.py:585`） | 多线程 safetensors（默认 8 线程，`buffered_multi_thread_safetensors_weights_iterator`，支持 mmap 禁用/预取）；pt 用 `multi_thread_pt_weights_iterator`；加 `source.prefix` |
| 权重流 | `_get_all_weights`（`loader.py:731`） | 主权重流 + 模型 `secondary_weights` 属性定义的次要流；多层 EAGLE 时 `_filter_mtp_weights` 按 `draft_model_idx` 过滤 MTP 层并重映射到 layer 0 |
| 模型构造 | `_initialize_model`（`loader.py:318`） | `get_model_architecture` 解析 HF config → 模型类；`install_shared_experts_fusion_decision`；传 `config`+`quant_config`（+`draft_model_idx`） |
| 加载骨架 | `load_model`（`loader.py:967`） | `set_default_torch_dtype(dtype)` → `_initialize_model` → `load_weights_and_postprocess` → `eval()` |
| 装权重+后处理 | `load_weights_and_postprocess`（`loader.py:998`） | `model.load_weights(weights)`（按名路由进参数，量化 scale 走 `param.weight_loader`）；对含 `quant_method` 的模块在 `device_loading_context` 内执行 `quant_method.process_weights_after_loading`（重打包/FP8 重量化） |

`StackedParamsDispatch`（`model_loader/auto_loader.py:62`）集中处理 fused 参数路由（`qkv_proj` ← `q/k/v_proj`，`gate_up_proj` ← `gate/up_proj`，含 shard_id）。`filter_pp_weights`（`auto_loader.py:156`）在 PP 下按 `[start_layer, end_layer)` 丢弃非本 stage 层的权重。

### 量化检查点

- `_get_quantization_config`（`loader.py:213`）：由 `model_config.quantization` 经 `get_quant_config`（`weight_utils.py:263`）解析；校验 GPU capability 与支持的激活 dtype；`quark` 扩充 `packed_modules_mapping`；FP8 config 注入 DSV4 FP4 专家元数据。
- 在线量化（FP8/FP4）：加载后 `report_online_quantization` 记录 `quant_config.quantized_layers`；NVFP4 在线转换对 FlashInfer FP4 相关环境变量临时设值（`loader.py:1028`）。
- KV cache scales：`load_kv_cache_scales`（`load_model_utils.py:107`）在 `kv_cache_dtype == "fp8_e4m3"` 时从 `quantization_param_path` 调 `model.load_kv_cache_scales`，否则回退 1.0。
- ModelOpt：`ModelOptModelLoader` 用 `AutoModelForCausalLM.from_pretrained(device_map="auto")` 装载 base 模型做 calibration。

### weight cache：IPC 参数服务器

`weight_cache/` 构成「daemon 进程共享权重」体系，在多实例（PD 分离 / 同模型多副本）场景消除重复加载：

| 组件 | 文件 | 职责 |
|---|---|---|
| `WeightCacheDaemon` | `daemon.py:76` | 每 (gpu, tp_rank) 一个守护进程：`load()`（`daemon.py:186`）加载并 TP 切分、量化后处理，`_export_state`（`daemon.py:346`）导出 CUDA IPC handle，`serve()`（`daemon.py:404`）起 socket 服务 |
| `protocol.py` | — | `CacheConfig`（model/arch/tp/pp/dp/ep/quant/hash 指纹）、`compute_global_rank`、`get_socket_path` |
| `ipc_loader.py` | — | `IpcModelLoader`：客户端经 socket 映射 daemon 的 IPC 权重（零拷贝），`load_format=IPC_CACHE` 时使用 |
| `daemon.launch_weight_cache_daemons` | `daemon.py:592` | 多进程拉起 daemon 组 |

`maybe_enable_ipc_weight_cache`（`load_model_utils.py:234`）把 `load_format` 覆盖为 `IPC_CACHE` 并记住原格式为 `fallback_load_format`；每 rank 由 `global_rank = tp_size*pp_rank + tp_rank` 推导唯一 socket。零拷贝 IPC 下禁用 weights CPU backup。**注意：源码未在本模块内定义参数服务器消息协议细节，本表仅依据协议/加载器入口归纳职责。**

### checkpoint_engine 与 weight_sync

| 组件 | 文件 | 说明 |
|---|---|---|
| `SGLangCheckpointEngineWorkerExtensionImpl` | `checkpoint_engine/checkpoint_engine_worker.py:92` | 向 checkpoint_engine 训练侧暴露 worker 扩展：`get_model_loader`/`get_post_hook`/`update_weights_from_ipc(zmq_handles)` |
| `checkpoint_engine/update.py` | — | 独立 torchrun 入口：parameter server 广播训练权重到推理实例（配 `--checkpoint-engine-wait-weights-before-ready`） |
| `weight_sync/tensor_bucket.py` | — | `FlattenedTensorBucket`：张量展平打包，供跨进程权重/LoRA 传输 |
| `WeightUpdater` | `model_runner_components/weight_updater.py` | 运行期权重更新：磁盘/分布式 group/tensor/IPC，支持 `recapture_cuda_graph` |
| `WeightExporter` | `model_runner_components/weight_exporter.py` | 向远端实例发送本实例权重（NCCL group），支撑跨实例迁移 |

运行时权重更新 RPC 由 `TpModelWorker` 暴露（`tp_worker.py:131-220`，`io_struct` 请求），更新后按需重捕获 decode CUDA graph。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
