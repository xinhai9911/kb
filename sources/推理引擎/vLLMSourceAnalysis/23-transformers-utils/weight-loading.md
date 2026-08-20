## transformers_utils 与模型权重流式加载

本文覆盖 HF 仓库侧权重发现/下载/流式迭代（`transformers_utils/repo_utils.py`、`model_executor/model_loader/weight_utils.py`、`default_loader.py`）。加载器骨架与并行切分见 [06-model-executor/loader.md](../06-model-executor/loader.md)。

### 分工边界

| 层 | 文件 | 职责 |
|---|---|---|
| 仓库交互 | `transformers_utils/repo_utils.py` | HfApi 单例、文件列举、下载、`with_retry`、revision 解析 |
| 权重下载/迭代 | `model_executor/model_loader/weight_utils.py` | `snapshot_download`、index 过滤、safetensors/pt/np_cache 等迭代器、兼容重映射 |
| 加载编排 | `model_executor/model_loader/default_loader.py` | `_prepare_weights` 定文件集、按 load_format 选迭代器、喂给 `model.load_weights()` |
| 文件锁/并发 | `weight_utils.get_lock` | SHA256 哈希文件名 + `filelock.FileLock`（0o666 跨用户共享），防多进程重复下载 |

`hf_api()` 返回带 `library_name="vllm"` 标注的共享 `HfApi`；`hf_fs()` 返回 `HfFileSystem`。启动时 `enable_xet_high_performance()` 打开 `HF_XET_HIGH_PERFORMANCE`。

### 仓库文件操作（repo_utils.py）

| 函数 | 行为 |
|---|---|
| `list_repo_files(repo_id, revision)` | `@cache` 缓存；本地目录直接 `rglob`；远程走 `hf_api().list_repo_files`（ModelScope 走 `modelscope_list_repo_files`）；离线模式返回 `[]`；`with_retry` 指数退避（2s→4s） |
| `list_filtered_repo_files` / `any_pattern_in_repo_files` | 按 `allow_patterns` 对**文件名**做 `fnmatch` 过滤 |
| `is_mistral_model_repo` | 仓库含 `consolidated*.safetensors` |
| `file_or_path_exists(model, config_name, revision)` | 本地存在 → True；否则 `try_to_load_from_cache`（HF 缓存，含 `_CACHED_NO_EXIST` 负缓存）→ 再 `file_exists`（Hub 查询） |
| `get_model_path` | 本地路径直返；否则 `snapshot_download(ignore_patterns="*")` 只取目录元数据 |
| `get_hf_file_to_dict(file, model, revision)` / `get_hf_file_bytes` | 本地缓存或 `hf_hub_download` 后读 JSON/字节 |
| `resolve_revision` | 把分支名解析为 commit hash（一次解析避免加载期间分支移动），失败回退原值 |
| `maybe_model_redirect` | `VLLM_MODEL_REDIRECT_PATH` 指向的 JSON 或空格分隔映射，重定向模型名 |

`transformers_utils/utils.py` 附带：`is_s3/is_gcs/is_azure/is_cloud_storage`、`convert_model_repo_to_path`（ModelScope 缓存根拼接）、`parse_safetensors_file_metadata`（读 safetensors 头部：8 字节长度 + JSON 元数据）。

### 权重下载（weight_utils.py）

`download_weights_from_hf(model_name_or_path, cache_dir, allow_patterns, revision, ...)`：

1. 非离线时用 `hf_fs().ls` 列仓库文件，尝试把 `allow_patterns` 收敛为**单个**模式以减少 `snapshot_download` 次数：safetensors + index 文件存在 → 直接下载 `model.safetensors.index.json`，把 `weight_map.values()` 去重后作为精确文件名列表；否则取首个命中 glob。
2. `get_lock` 加锁后逐模式 `hf_api().snapshot_download(...)`（`tqdm_class=DisabledTqdm`），命中即停。

配套：`download_safetensors_index_file_from_hf`（预下载 index）、`filter_duplicate_safetensors_files`（按 index 的 weight_map 去重——解决 Mistral-7B-v0.3 等同时存在 sharded 与 consolidated 文件的问题，缺索引文件报 `FileNotFoundError`）、`filter_files_not_needed_for_inference`（剔除 `training_args.bin`/`optimizer.bin` 等）。ModelScope 场景走 `maybe_download_from_modelscope`（同样加锁）。

### 权重迭代器（weight_utils.py，均为生成器）

| 迭代器 | 触发 load_format | 机制 |
|---|---|---|
| `safetensors_weights_iterator` | `safetensors`/`hf` 默认 | `safe_open` 惰性逐张量（lazy）；`eager` 全量 `load()`；`torchao` 用 `unflatten_tensor_state_dict` 重建 tensor subclass（跨分片 `leftover_state_dict` 暂存）；`local_expert_ids` 命中时**读盘前跳过**非本 rank 专家张量 |
| `multi_thread_safetensors_weights_iterator` | `enable_multithread_load` | `ThreadPoolExecutor` 并行 `load_file(device="cpu")`，`as_completed` 流式 yield，默认 8 线程 |
| `fastsafetensors_weights_iterator` | `fastsafetensors` | `ParallelLoader` 生产者/消费者流水线，`nogds=True` 规避 TP>1 的 GDS 问题，GDS 运行期失败可回退 |
| `instanttensor_weights_iterator` | `instanttensor` | InstantTensor 直接读盘到目标 device（NVIDIA only，`copy=True` 保证张量生命周期） |
| `runai_safetensors_weights_iterator` | runai_streamer | `SafetensorsStreamer` 流式 |
| `pt_weights_iterator` / `multi_thread_pt_weights_iterator` | `pt` | `torch.load(weights_only=True, map_location=pt_load_map_location)` |
| `np_cache_weights_iterator` | `npcache` | 首次把 .bin 转 numpy 落盘 `{hf_folder}/np/`（加锁防并发），之后直接 `np.load` |

预取：`safetensors_load_strategy="prefetch"` 或网络文件系统（NFS/Lustre 由 `/proc/mounts` 最长前缀匹配判定）且 checkpoint ≤90% 可用 RAM 时，后台 daemon 线程分块读文件预热 OS page cache（按 rank 均分文件、10% 进度日志）。

### DefaultModelLoader 衔接（default_loader.py）

`load_weights(model, model_config)`：torchao checkpoint 时把 `safetensors_load_strategy` 切为 `"torchao"`；`_init_ep_weight_filter` 计算本 rank `local_expert_ids`（EP 且 `enable_ep_weight_filter` 且非 EPLB 时）；然后把 `get_all_weights()` 的流喂给 `model.load_weights()`。

`get_all_weights`：主源为 `model_config.model`（`fall_back_to_pt`/`allow_patterns_overrides` 取模型类属性），次要源来自模型类 `secondary_weights` 属性，逐源 `_get_weights_iterator` 并在权重名前加 `source.prefix`。

`_prepare_weights` 定文件集：`auto` 检测 `consolidated*.safetensors` 自动切 `mistral`（index 为 `consolidated.safetensors.index.json`）；`hf` 允许 `*.safetensors`+`*.bin`；显式 safetensors 系格式不回退 .pt。`model_loader_extra_config` 仅接受 `enable_multithread_load`/`num_threads`/`enable_weights_track`，未知键抛 `ValueError`；多线程加载与 `safetensors_load_strategy` 非 `lazy` 组合被拒绝。

### 兼容与后处理工具（weight_utils.py）

- 权重写入函数：`default_weight_loader`（形状断言 + `copy_`，标量特判）、`row_parallel_weight_loader`（按 TP rank narrow 行）、`sharded_weight_loader(axis)`、`composed_weight_loader(loader, fn)`。
- `maybe_remap_kv_scale_name`：`.kv_scale`（弃用）→ `.attn.k_scale` 复制到 v_scale；ModelOpt/Qwen3/Nemotron/HYV3 等 8 种 scale 命名正则重映射（`attn_str` 依 MLA 特判）。
- `maybe_remap_moe_expert_param_name` / `remap_moe_expert_weights`：旧 `*.experts.*` ↔ 新 `*.experts.routed_experts.*` 结构互转（20 个后缀判定）。
- `convert_bin_to_safetensor_file`：`.pt → .safetensors` 转换（共享指针去重、size/张量校验）。
- `get_quant_config`：量化配置来源优先级——HF `quantization_config`/`text_config`/`compression_config` → `hf_overrides.quantization_config_file`/`quantization_config_dict_json` → 在线量化 `OnlineQuantizationConfig` → checkpoint 目录内 `quant_cls.get_config_filenames()` 命中文件（compressed-tensors 场景会注入 `total_num_heads`/`total_num_kv_heads` 供 TP 感知加载）。
- `initialize_dummy_weights`：按参数 seed=1234 独立生成 `[-1e-3,1e-3]`，只依赖元素数+dtype，跨 rank 一致（详见 [06 loader.md](../06-model-executor/loader.md)）。

### 与 config 层的耦合点

- `get_safetensors_params_metadata`（config.py:1181）：本地目录直接读头部；远程 `hf_api().get_safetensors_metadata`；Hub 失败回退 `snapshot_download(local_files_only=True)` 读缓存——被 `MistralConfigParser` 推断 dtype、`ModelArchConfigConvertorBase.get_torch_dtype` 使用。
- `get_quant_config` 中的 `model_config.model_arch_config.total_num_attention_heads` 即来自 config-mapping.md 所述的 convertor 产物。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
