## 多模态输入：数据结构与预处理管线

源码根：`sglang/srt/`（`managers/`、`multimodal/`、`mem_cache/` 三个包协同）。注意与 vLLM 不同：SGLang 没有独立的 `base.py`，核心数据结构与调度强耦合地定义在 `srt/managers/schedule_batch.py` 中，处理器注册在 `srt/managers/multimodal_processor.py`。

### 模块地图

| 文件/目录 | 职责 |
|---|---|
| `srt/managers/schedule_batch.py:292` 起 | `Modality`/`MultimodalInputFormat`/`MultimodalDataItem`/`MultimodalProcessorOutput`/`MultimodalInputs` 数据结构与 pad value 计算 |
| `srt/managers/multimodal_processor.py` | 处理器注册表 `PROCESSOR_MAPPING` 与工厂 `get_mm_processor` |
| `srt/multimodal/processors/` | 40+ 模型处理器（llava、internvl、qwen_vl、kimi_k3…）+ `base_processor.py` 基类 |
| `srt/multimodal/cache/` | `preprocess_cache.py`（CPU LRU + single-flight）+ `identity.py`（内容寻址哈希/指纹） |
| `srt/multimodal/transport/` | `cuda_ipc.py` 特性跨进程传输、`memory_pool.py` 池 |
| `srt/multimodal/evs/` | 视频 embedding 冗余消除（EVS） |
| `srt/multimodal/media_artifacts/` | `MediaArtifact`：模型相关、与 prompt 无关的预处理产物 |
| `srt/multimodal/vit_cuda_graph_runner.py` | ViT 的 CUDA Graph 封装（InternVL/Kimi 各有子类） |

### 核心数据结构（schedule_batch.py）

| 类型 | 说明 |
|---|---|
| `Modality`（:292） | `IMAGE`/`VIDEO`/`AUDIO` 枚举；`from_str`、`all()` |
| `MultimodalInputFormat`（:311） | `NORMAL` / `PROCESSOR_OUTPUT` / `PRECOMPUTED_EMBEDDING` 三种输入形态 |
| `MultimodalDataItem`（:318） | 一个 item = 一张图/一段视频/一段音频；`feature` 与 `precomputed_embeddings` 二选一 |
| `MultimodalProcessorOutput`（:498） | 处理器原始输出：`mm_items` + `input_ids` + 各类特殊 token id + `mrope_positions` |
| `MultimodalInputs`（:582） | Scheduler 侧形态，由 `from_processor_output()`（:622）物化 |

`MultimodalDataItem` 关键字段：`modality`、`hash`、`pad_value`、`offsets`（`[start,end]` 列表）、`format`、`feature`、`precomputed_embeddings`、`model_specific_data`（任意模型专属键值，经 `__getattr__` 透传）。

**pad_value 与 RadixAttention**：`set_pad_value()`（:374）先经 `resolve_multimodal_item_hash` 得到 item 哈希，再 `_compute_pad_value`（:218）映射到 vocab 之外：

```python
MM_PAD_SHIFT_VALUE = 1_000_000          # schedule_batch.py:147
return MM_PAD_SHIFT_VALUE + (hash % (1 << 30))
```

该 pad 值被写入 `input_ids` 占位区（`build_padded_input_ids`，:561），使 RadixAttention 能按内容哈希复用前缀；真正 embedding 时 `input_ids.clamp_(max=vocab_size-1)` 丢弃这些无用 token（见 mm_utils.py）。

### 处理器注册与工厂

`import_processors("sglang.srt.multimodal.processors")`（multimodal_processor.py:16）用 `pkgutil.iter_modules` 扫描包内模块，凡继承 `BaseMultimodalProcessor` 且带 `models` 属性的类，按 `arch`→`cls` 登记进 `PROCESSOR_MAPPING`（:13）。`get_mm_processor_cls`（:44）以 `hf_config.architectures` 匹配；`--model-impl transformers` 时回退到 `TransformersAutoMultimodalProcessor`。`get_mm_processor`（:74）实例化处理器。

### 预处理管线（base_processor.py）

`TokenizerManager` 侧入口为异步方法 `process_mm_data_async`（:730 抽象定义），实际流程：

1. `load_mm_data`（:1027）按 prompt 中特殊 token 与数据是否 1:1 对齐，分 `fast_load_mm_data`（:1107，直接并行加载、不扫描 prompt）与 `legacy_load_mm_data`（:1204，正则切分 prompt 后逐 token 匹配加载）两条路径；IO 提交到 `io_executor` 线程池（`submit_data_loading_tasks`，:891）。
2. `process_and_combine_mm_data`（:1570）调用 `process_mm_data`（:645，封装 transformers AutoProcessor）产出张量，`collect_mm_items_from_processor_output`（:1354）按 `ATTR_NAME_TO_MODALITY` 把 `pixel_values`/`audio_features` 等归入对应模态 item。
3. `get_new_expanded_mm_items`（managers/mm_utils.py:1090）把"一图多 offset"的捆绑 item 拆成逐 item，提升缓存粒度（图片按 `image_grid_thw`、视频按 `video_grid_thw` 切分 feature）。
4. 逐 item `set_pad_value()`；`SGLANG_MM_AVOID_RETOKENIZE` 开启时用 `_expand_input_ids`（:1535）保留用户原始 token 以规避 retokenize 漂移。

并发支持：`MultimodalProcessorExecutor`（processors/executor.py:24）以线程局部 deepcopy 的处理器克隆并行执行（`--mm-processor-worker-num` 控制），不支持并发处理的模型自动回退同步。

### 预处理缓存与内容寻址（cache/）

| 组件 | 说明 |
|---|---|
| `MultimodalPreprocessCache`（preprocess_cache.py:121） | CPU 字节计账 LRU + 每 key async single-flight（`get_or_compute` :255、`lookup_or_claim_many` :339）；`clear()` 用 generation 使旧计算无法回填（:246） |
| `MediaSnapshot`（identity.py:64） | 媒体不可变快照 + 严格内容摘要；路径/URL 不构成身份，每次按字节重哈希 |
| `build_processor_fingerprint`（identity.py:378） | 覆盖 transformers 版本、processor 类名、`model_revision`、`mm_process_config`、处理器自身 payload，防范跨配置复用 |
| `build_artifact_key`（identity.py:309） | `content_digest + modality + fingerprint + preprocess_kwargs` 的 SHA-256 |
| `resolve_multimodal_item_hash`（identity.py:327） | `SGLANG_MM_SKIP_COMPUTE_HASH` 时用 uuid；否则复用 `existing_hash`（外部 KV 路由器下发的 `mm_hashes`）或对 feature 算 `hash_feature` |

`media_artifacts/base.py` 定义 `MediaArtifact`：模型相关、prompt 无关的预处理产物（保留图片尺寸、token 数、encoder grid 等元数据，`cache_value()` 可省去 CUDA feature 只留元数据供 embedding 缓存命中时使用）。

### 跨进程传输

`mm_feature_transport` 三选一（base_processor.py:220）：`cpu`（默认）/ `cuda_ipc` / `cuda_vmm`。

| 模式 | 机制 |
|---|---|
| default（inline/pickle） | 直接 pickle 张量 |
| default + `ShmPointerMMData`（mm_utils.py:1262） | 非默认传输且开启 tokenizer 时，`wrap_shm_features`（:1381）把 CPU 张量写入共享内存、只传句柄；`/dev/shm` 满时回退 inline（`_wrap_shm_or_inline` :1348）；接收侧 `materialize()` 克隆后 unlink |
| cuda_ipc | `MmItemMemoryPool`（transport/cuda_ipc.py:92）按 `SGLANG_MM_FEATURE_CACHE_MB` 预算在 GPU 预分配，`CudaIpcTensorTransportProxy`（:170）池化切块共享；`acknowledge_consumption` 计数释放 |

另有 GPU 特征哈希加速：`SGLANG_MM_BUFFER_SIZE_MB>0` 时 `init_feature_buffer`（mm_utils.py:66）预分配 GPU 缓冲，`try_add_to_buffer` 把 feature 拷入再算哈希，避免多次小 H2D（schedule_batch.py `from_processor_output` :638）。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
