## 多模态输入与生成对比：vLLM `vllm/multimodal/` vs SGLang `srt/multimodal/`

对比两大引擎的多模态输入管线（注册/处理器/缓存/传输）与生成能力。事实基准：vLLM `vllm/multimodal/`（V1 时代经 `vllm/renderers/` 前端）与 SGLang `sglang/srt/managers/`+`srt/multimodal/`、`sglang/multimodal_gen/`。

### 一、架构定位总览

| 维度 | vLLM | SGLang SRT |
|---|---|---|
| 源码根 | `vllm/multimodal/`（`registry.py`/`processing/`/`media/`/`video_prune/`）+ 前端 `vllm/renderers/` | `sglang/srt/managers/`（`schedule_batch.py`/`multimodal_processor.py`）+ `srt/multimodal/`（`processors/`/`cache/`/`transport/`/`evs/`） |
| 注册中心 | 全局单例 `MULTIMODAL_REGISTRY`（`multimodal/registry.py`），模型类装饰器挂 `_ProcessorFactories`（info/dummy_inputs/processor 三工厂） | `PROCESSOR_MAPPING`（`managers/multimodal_processor.py:13`）：`pkgutil.iter_modules` 扫描 `srt/multimodal/processors/`，按 `arch`→`cls` 登记 40+ 处理器 |
| 处理器 | `BaseMultiModalProcessor`（`processing/processor.py`，`apply()` 管线）+ `EncDecMultiModalProcessor` | `BaseMultimodalProcessor`（`srt/multimodal/processors/base_processor.py`）+ `TransformersAutoMultimodalProcessor` 回退 |
| 数据结构 | `MultiModalDataDict`（`inputs/llm.py`）→ `MultiModalDataItems`（`parse.py`）→ `MultiModalKwargsItems`+`BatchedTensorInputs`（`inputs.py`） | `Modality`/`MultimodalInputFormat`/`MultimodalDataItem`（`managers/schedule_batch.py:292-318`）→ `MultimodalProcessorOutput`（:498）→ `MultimodalInputs`（:582） |
| 占位符机制 | `PlaceholderRange(offset,length)`+`PromptInsertion/Replacement`（token/文本双匹配） | `pad_value`（`MM_PAD_SHIFT_VALUE=1_000_000`+hash）写入 input_ids 占位区（`schedule_batch.py:147`） |
| 缓存 | 发送端/引擎端/worker 端三级缓存（`--mm-processor-cache-type`：processor_only/lru/shm） | `MultimodalPreprocessCache`（CPU LRU+single-flight）+ `MultiModalStaticCache` 即 MMEmbeddingCache（`mem_cache/multimodal_cache.py:76`） |
| 哈希 | `MultiModalHasher`（`hasher.py`，blake3 默认，兼容 sha256/512） | `build_artifact_key`（SHA-256，`cache/identity.py:309`）+ `MediaSnapshot` 内容摘要 |
| 跨进程传输 | V1 `TensorIpcReceiver` oob tensor IPC（`v1/engine/tensor_ipc.py`）；GPU IPC 池 `mm_ipc_gpu_memory_gb` | `mm_feature_transport` 三选一：`cpu`/`cuda_ipc`/`cuda_vmm`（`base_processor.py:220`）+ `ShmPointerMMData` 共享内存句柄 |
| 多模态生成 | **无**（推理引擎内不生成图像/视频） | `sglang/multimodal_gen/`（SGLang Diffusion）独立运行时 |

> 关键差异 ①：vLLM 用**装饰器式注册**（模型类声明）+ 三级**可插拔缓存**，数据结构按「API 层→parser 层→kwargs 层→batched 层」四级归一；SGLang 用**包扫描式注册**，核心数据结构与调度器强耦合定义在 `schedule_batch.py`，pad_value 直接挂钩 RadixAttention 前缀复用。

### 二、核心数据结构对比

| 层 | vLLM | SGLang |
|---|---|---|
| API 输入 | `MultiModalDataDict: Mapping[str, ModalityData]`，内建 image/video/audio/**vision_chunk** 模态 | API 层直接传 `MultimodalDataItem`（`feature` 或 `precomputed_embeddings` 二选一） |
| 归一化 | `MultiModalDataParser` 子类：`ProcessorBatchItems`/`EmbeddingItems`/`DictEmbeddingItems` 等 | `MultimodalInputFormat` 三形态：`NORMAL`/`PROCESSOR_OUTPUT`/`PRECOMPUTED_EMBEDDING`（`schedule_batch.py:311`） |
| 批处理 | `MultiModalFieldConfig`：`batched`/`flat`/`shared` 定义 unpack 语义（`inputs.py`） | `offsets`（`[start,end]` 列表）+ `pad_value` + `model_specific_data`（任意模型专属 KV） |
| 增量索引 | `PlaceholderRange.embeds_cumsum`/`get_embeds_indices_in_range` 按区间取 encoder 输出行 | `get_embedding_and_mask`（`mm_schedule.py:628`）按 `torch.isin` 生成散射 mask |

### 三、处理管线对照

| 环节 | vLLM `BaseMultiModalProcessor.apply()` | SGLang `TokenizerManager.process_mm_data_async` |
|---|---|---|
| 数据加载 | `MediaIO`（bytes/base64/file）+ `MediaConnector` HTTP 拉取（4xx 除 408/429 转 422） | `load_mm_data` 分 `fast_load_mm_data`（1:1 对齐直载）/`legacy_load_mm_data`（正则切 prompt），IO 走 `io_executor` 线程池 |
| HF 处理 | `_cached_apply_hf_processor` 调 HF processor，缓存命中只处理缺失项（`_merge_mm_kwargs`） | `process_mm_data` 封装 transformers AutoProcessor，`collect_mm_items_from_processor_output` 按 `ATTR_NAME_TO_MODALITY` 归类 |
| 占位符 | `_maybe_apply_prompt_updates`：PromptInsertion/Replacement 插入/替换特征占位符，产出 `PlaceholderRange` | `get_new_expanded_mm_items`（`mm_utils.py:1090`）拆「一图多 offset」捆绑 item，逐 item `set_pad_value()` |
| 并发 | `_mm_executor` 单 worker 线程保 P0/P1 顺序（`renderers/base.py:73`） | `MultimodalProcessorExecutor`（`processors/executor.py:24`）线程局部 deepcopy 克隆并行（`--mm-processor-worker-num`） |
| 规避重分词 | —（renderer 统一处理） | `SGLANG_MM_AVOID_RETOKENIZE` 时 `_expand_input_ids` 保留用户原始 token |

### 四、Embedding 缓存与前向融合

| 维度 | vLLM | SGLang |
|---|---|---|
| 缓存命中查询 | 发送端缓存+引擎/worker 接收端 LRU；`multi_modal_uuids` 用户指定时优先 | `MultiModalStaticCache.get(hashes)` 整请求级 / `get_single(hash)` 逐 item（`multimodal_cache.py:91/123`） |
| 编码批处理 | 无显式分块（V1 `mm_features` 统一携带） | `_get_chunked_prefill_embedding`（`mm_schedule.py:465`）：per-image 批量路径跨请求按哈希去重**一次 ViT 调用**；full/EVS 路径整请求编码 |
| 前向融合 | — | `general_mm_embed_routine`（`mm_utils.py:609`）：仅 prefill 执行，`masked_scatter_` 散射 embedding（避免 `torch.where` stream 同步），decode 阶段直接 `embed_tokens` |
| GPU 显存 | tensor IPC 直传，GPU IPC 池 | `cuda_ipc` 用 `MmItemMemoryPool` 预算池化；`SGLANG_MM_BUFFER_SIZE_MB` GPU 缓冲算哈希 |

> 关键差异 ②：SGLang 把「**分块预填充 + per-image 批量编码 + 前向融合**」做进 mm 调度（`mm_schedule.py`），chunk 间 embedding 缓存放大缓存命中；vLLM V1 多模态张量走独立 tensor IPC，预处理与前向解耦更彻底。

### 五、视频裁切（EVS 类）对比

| 维度 | vLLM `video_prune/` | SGLang `multimodal/evs/` |
|---|---|---|
| 实现 | `evs.py`（NVIDIA EVS 余弦相似度排序）+ `vidcom2.py`（VidCom2 低方差通道+多尺度高斯带宽） | `srt/multimodal/evs/` 视频 embedding 冗余消除 |
| 掩码 | 产出与 `PlaceholderRange` 精确对应的 bool 掩码 | `EVSEmbeddingResult` → `redistribute_pruned_frames_placeholders` 重写 input_ids 占位区（`mm_schedule.py:250`） |

### 六、多模态生成：仅 SGLang

`sglang/multimodal_gen/`（SGLang Diffusion）是与 `srt` 并列的同级包，vLLM 无对应能力。

| 维度 | 说明 |
|---|---|
| 关系 | 独立运行时：自有 `Scheduler`/`GPUWorker`/`PipelineExecutor`，不复用 srt 的 LLM scheduler/KV cache/RadixAttention（仅复用 trace/kernels/utils） |
| 入口 | `DiffGenerator`（`runtime/entrypoints/diffusion_generator.py`）、`sglang generate/serve` CLI、OpenAI 兼容 API、realtime session |
| 管线 | `ComposedPipelineBase`（`runtime/pipelines_core/`）：InputValidation→Text/ImageEncoding→Latent/TimestepPreparation→Denoising→Decoding 阶段流水 |
| 并行 | xDiT 风格：tp/cfg/ulysses/ring/sequence parallel；去耦生成（`disaggregation/`） |
| 加速 | `runtime/cache/`：TeaCache（调制输入 L1 距离跳过步）、Spectrum（Chebyshev 岭回归跳步）、cache-dit（DiT 块级缓存） |
| 基线 | 基于 FastVideo fork（2025-09-24），sgl-kernel 加速 |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
