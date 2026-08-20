## 多模态注册与处理流程

源码根：`vllm/multimodal/`（含 `processing/`、`media/`、`video_prune/` 子包）。

### 模块结构

| 文件/目录 | 职责 |
|---|---|
| `__init__.py` | 导出全局实例 `MULTIMODAL_REGISTRY` |
| `registry.py` | `MultiModalRegistry` 调度、缓存工厂、`MultiModalTimingRegistry` |
| `processing/processor.py` | `BaseMultiModalProcessor` 处理管线、`PromptUpdate` |
| `processing/context.py` | `InputProcessingContext`、`BaseProcessingInfo`、`TimingContext` |
| `processing/dummy_inputs.py` | `BaseDummyInputsBuilder` 生成 profiling 假输入 |
| `inputs.py` | 张量模型：`MultiModalKwargsItem(s)`、`MultiModalFieldConfig`、`PlaceholderRange` |
| `parse.py` | `MultiModalDataItems` / `MultiModalDataParser` 数据归一化 |
| `media/` | `MediaIO`（bytes/base64/file 加载）、`MediaWithBytes`、`MediaConnector` |
| `hasher.py` | `MultiModalHasher` 计算缓存哈希 |
| `cache.py` | 处理器缓存（processor_only/lru/shm） |
| `video_prune/` | 视频裁切：EVS 与 VidCom2 |
| `image.py`/`video.py`/`audio.py` | 各模态归一化工具（`normalize_image`、`AudioResampler` 等） |

注意：源码中无 `base.py`；基础类（`BaseProcessingInfo` 等）位于 `processing/`。

### MultiModalRegistry

全局单例 `MULTIMODAL_REGISTRY` 由模型执行器（model runner）按目标模型分发数据处理。模型类通过装饰器注册三个工厂（`_ProcessorFactories`，懒加载）。

| 方法 | 说明 |
|---|---|
| `register_processor` | 装饰器，把 `info`/`dummy_inputs`/`processor` 工厂挂到模型类 `_processor_factory` |
| `supports_multimodal_inputs` | 判多模态能力；所有模态 `limit=0` 时退回纯文本模式（`enable_mm_embeds=True` 除外） |
| `create_processor` | 为指定模型+tokenizer 构建 `BaseMultiModalProcessor` |
| `get_dummy_mm_inputs` | 生成 profiling 假输入，不足 `max_model_len` 部分补 0 |
| `processor_cache_from_config` | 按 `--mm-processor-cache-type` 返回发送端缓存（processor_only/lru/shm） |
| `engine_receiver_cache_from_config` | 引擎进程接收端 LRU 缓存 |
| `worker_receiver_cache_from_config` | worker 进程共享内存接收端缓存（shm） |

缓存类型由 `mm_processor_cache_gb>0` 且 `data_parallel_size==1`（或外置负载均衡）决定；不支持 IPC 时退回 `processor_only`。

### 处理管线（media → 输入张量）

`BaseMultiModalProcessor.apply()` 主流程：

1. `_cached_apply_hf_processor`：调 HF processor 处理文本+多模态数据，产 token IDs 与处理张量。命中缓存时只处理缺失项并合并（`_merge_mm_kwargs`）。
2. `_maybe_apply_prompt_updates`：把占位符（如 `<image>`×N，N=编码器特征数）插入/替换进 token 序列；未命中再回落文本级匹配（`_apply_prompt_updates`）。
3. 扫描占位符位置，产出 `PlaceholderRange(offset,length)`；调用 `mm_input()` 组装 `MultiModalInput`。

返回结构：`prompt_token_ids` + `mm_kwargs`（按模态分组的张量字段）+ `mm_hashes` + `mm_placeholders`。

HF 处理封装于 `InputProcessingContext`：`call_hf_processor` 合并 `mm_processor_kwargs` 与模型配置、限制可用 kwargs、结果后处理（转 `model.dtype`、CPU 搬运——`torch_shm` IPC 时留在设备）。

### Prompt 更新（抢占/替换）

| 类 | 说明 |
|---|---|
| `PromptInsertion` | 在目标（`<s>`、`PromptIndexTargets.start/prefix/end`）后插入占位符 |
| `PromptReplacement` | 把输入占位符替换为特征占位符序列 |
| `PromptUpdateDetails` | 可带 `is_embed` 掩码，指定哪些位置喂 encoder 输出 embedding |
| `find_mm_placeholders` | 以 token 或文本匹配定位每个多模态项的占位符区间 |

`EncDecMultiModalProcessor`（编码器-解码器）改写流程：先 `create_encoder_prompt` 处理编码器，原 prompt 作为解码器输入，经 `mm_enc_dec_input` 组装。

### 数据 pack/unpack

`MultiModalDataParser`（parse.py）把 API 层的 `MultiModalDataDict` 归一为 `MultiModalDataItems`：

| 子类 | 说明 |
|---|---|
| `ProcessorBatchItems` | 列表型数据，`get_processor_data()` 产出 `{image/video/audio: [...]}` |
| `EmbeddingItems` | 预计算 embedding 张量（2D 或 3D），校验 `ndim` 与 hidden_size |
| `DictEmbeddingItems` | 由张量字典生成 kwargs 项 |
| `Audio/Image/VideoProcessorItems` | 各模态列表，可查询 `get_frame_size`、`get_num_frames` 等 |

处理结果按模态存为 `MultiModalKwargsItems`，每个 `MultiModalKwargsItem` 对应一个原始项。模型侧批处理由 `MultiModalFieldConfig` 定义：

| 字段类型 | unpack 语义 |
|---|---|
| `batched` | 按第 0 维取索引（pixel_values） |
| `flat` | 沿 dim 切片（`slices` 或 `size_per_item`） |
| `shared` | 所有项共享同份数据（如 grid 尺寸） |

`MultiModalKwargsItems.get_data()` 经 `group_and_batch_mm_items` 合并成 `BatchedTensorInputs` 传给模型。

### 媒体加载（media）

`MediaIO` 接口：`load_bytes` / `load_base64` / `load_file`。子类 `ImageMediaIO`（含 `VLLM_MAX_IMAGE_PIXELS` 像素上限、RGBA→RGB）、`VideoMediaIO`、`AudioMediaIO`。`MediaWithBytes` 保存原始字节与解码配置（参与哈希缓存，防止缓存损坏）。URL/HTTP 拉取由 `MediaConnector` 与 `MEDIA_CONNECTOR_REGISTRY` 完成，4xx（除 408/429）转 422。

### 哈希

`MultiModalHasher.hash_kwargs` 按算法（默认 blake3，兼容 sha256/sha512）序列化张量/数组/图像（含 EXIF UUID 短路）。`ProcessorInputs.get_mm_hashes` 优先使用用户提供的 `multi_modal_uuids`，仅当与 processor kwargs 一起哈希时才计算。

### 视频裁切（video_prune）

| 实现 | 说明 |
|---|---|
| `evs.py` | NVIDIA EVS：相邻帧 embedding 余弦相似度 → 不相似度排序，保留前 `(1-q)*total` token；首帧全保留，输出 bool 掩码；另含 `compute_mrope_for_media` |
| `vidcom2.py` | VidCom2（EMNLP 2025）：低方差通道子集打分、多尺度高斯带宽、softmax 温度 0.01，保留 `(1-q)*total_tokens`（每帧至少 1 token） |

两者均据 `tokens_per_frame × num_frames` 与裁切率 `q∈[0,1)` 计算保留 token 数，产出与占位符精确对应的掩码。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)