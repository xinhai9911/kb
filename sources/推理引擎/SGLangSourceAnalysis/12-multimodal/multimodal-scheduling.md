## 多模态输入：Scheduler 侧处理、Embedding 缓存与前向融合

核心文件：`srt/managers/tokenizer_manager.py`、`srt/managers/scheduler.py`、`srt/managers/mm_schedule.py`、`srt/managers/mm_utils.py`、`srt/mem_cache/multimodal_cache.py`。

### 请求流转总览

```text
TokenizeManager                 Scheduler                          ModelExecutor
  process_mm_data_async  →  MultimodalInputs(物化)  →  Req.multimodal_inputs
  mm_hashes / pad 预计算         pad_input_ids(可复用 padded)         ForwardBatch.mm_inputs
        │                         embedding_cache 命中/编码            general_mm_embed_routine
        └────────────── ZMQ PUSH ──────────────┘    mm_schedule         embed_mm_inputs → scatter
```

### TokenizerManager 侧（tokenizer_manager.py）

`_tokenize_one_request` 中 `should_run_mm_processor`（:1046）为真时调用 `mm_processor.process_mm_data_async`（:1089，image/audio/text 入参），产出 `MultimodalProcessorOutput`；随后：

- 覆盖 `input_ids`/`token_type_ids`（:1112-1117）。
- 外部 `mm_hashes`（KV 路由器下发）逐 item `set_hash(int(hash,16))`（:1129-1145），使外部路由决策与 SGLang 前缀缓存 key 对齐；解析失败回退内部 `hash_feature`。
- `SGLANG_MM_PRECOMPUTE_HASH` 开启时在此提前 `set_pad_value()`（:1147-1153）。
- language-only 拆分发（encoder 在其他机器）时经 `mm_receiver.recv_mm_data` 接收 encoder 回传的 embedding（:1076），缺省回退本地处理。

### Scheduler 侧（scheduler.py）

| 方法 | 行为 |
|---|---|
| `_get_multimodal_inputs`（:2310） | 已物化直接复用；否则 `MultimodalInputs.from_processor_output`（含 cuda-ipc 重建、GPU buffer 哈希） |
| `_process_and_broadcast_mm_inputs`（:2242） | TP>1 时仅 entry rank 物化一次，`broadcast_object_list` 经 `dp_tp_cpu_group` 广播给同组其他 rank，避免各 TP rank 重复 CPU 物化拖慢主线程 |
| `_try_apply_padded_mm_input_ids`（:2318） | 优先复用 `MultimodalInputs.padded_input_ids`（避免二次 pad），否则调用模型 `pad_input_ids` |
| `_maybe_compute_mrope_positions`（:2341） | gRPC 预处理路径缺 mrope 时补齐 |
| `_maybe_clear_mm_inputs`（:2385） | 请求结束后 `release_features()` 释放 GPU 特征；session 请求保留给下一轮 |

`pad_input_ids` 由模型侧提供（scheduler.py:1084 `tp_worker.get_pad_input_ids_func()`），基类实现两种策略（mm_utils.py）：`MultiModalityDataPaddingPatternTokenPairs`（:251，`<img>`…`</img>` 成对替换）与 `MultiModalityDataPaddingPatternMultimodalTokens`（:326，连续同 token 按 item offset 替换）。

### MMEmbeddingCache（mem_cache/multimodal_cache.py）

`MultiModalStaticCache`（:76）是服务级 embedding 缓存：`OrderedDict[hash, EmbeddingResult]` + 字节计账 LRU（`set` :102 按 `_get_tensor_size` 驱逐最旧）。两种查询粒度：

- `get(hashes)`（:91）：`combine_hashes` 后整请求级查询（`EmbeddingResult` 含 `embedding`）；
- `get_single(hash)`（:123）：逐 item 查询，供 per-image 编码路径使用。

模块级单例由 `init_mm_embedding_cache(max_size)`（mm_schedule.py:23）初始化。

### Embedding 调度（mm_schedule.py）

核心 `get_embedding_and_mask`（:628）三步：

1. 统计当前 extend 区间内的 mm 占位 token 数 `_count_mm_tokens_in_extend`（:578，纯 host offset 计算，不回读 GPU mask）。
2. 取 embedding：全部 item 有 `precomputed_embeddings` 时走 `_get_precomputed_embedding`（:73，直接拼接+`get_embedding_chunk` 切分）；否则 `_get_chunked_prefill_embedding`（:465）。
3. `_get_multimodal_mask`（:572）用 `torch.isin(input_ids, placeholder)` 生成散射 mask；`_adjust_embedding_length`（:597）对齐 token 数（不匹配时警告并截尾，建议调大 `chunked_prefill_size`）。

**分块预填充编码（chunked prefill）**：`_get_chunked_prefill_embedding` 把请求分成两类：

| 路径 | 条件 | 行为 |
|---|---|---|
| per-image 批量路径 | 每个 item 恰好 1 个 offset | `_batch_encode_per_image_misses`（:285）跨请求收集所有 cache miss 并按哈希去重，**一次 ViT 调用**批量编码后 `torch.split` 回写缓存；`_assemble_per_image_chunk`（:437）按 overlap 切出本 chunk |
| full/EVS 路径 | 捆绑 item 或 EVS 结果 | `_get_chunked_embedding_full`（:216）整请求编码+整条目缓存 |

EVS 场景：编码结果为 `EVSEmbeddingResult` 时 `redistribute_pruned_frames_placeholders` 重写 input_ids 中占位区以匹配裁剪后 token 数（:250-260）。`DataEmbeddingFunc`（:142）约定返回 `[tokens,hidden]` 张量、逐 item 张量列表或 `EVSEmbeddingResult`；逐 item 形式（如 wav 自编码器）免去编码侧 concat、且每条缓存条目独占存储。CUDA 平台走批量路径，HIP/NPU/XPU 回退逐请求路径（:514）。

### 前向融合（mm_utils.py）

`general_mm_embed_routine`（:609）在模型 forward 中调用（如 `qwen2_5_vl.py:882`）：仅 prefill（`forward_batch.forward_mode.is_decode()/is_target_verify()` 为假）且 `contains_mm_inputs()` 时执行，decode 阶段直接 `embed_tokens(input_ids)`。

`embed_mm_inputs`（:368）要点：

1. 按模态取 embedder：优先 `data_embedding_func_mapping`（如 qwen2_5_vl 的 `get_image_feature`，qwen2_5_vl.py:767 内做 `pixel_values` concat + ViT `self.visual(...)`）；否则回落 `multimodal_model.get_{modality}_feature`（:420）。
2. `get_embedding_and_mask` 产出各模态 embedding 与 mask。
3. `input_ids.clamp_(0, vocab_size-1)` 后查表得文本 embedding——pad 值在 vocab 外，故先 clamp 再查表（:466-470）。
4. `masked_scatter_` 把 mm embedding 散射进 `input_embeds` 对应位置（:490-498），避免 `torch.where` 的 stream 同步；deepstack（qwen3_vl）模型额外维护 `input_deepstack_embeds`。
5. embedding 完成后把 item `feature` 迁回 CPU 释放显存（chunked prefill 后续 chunk 缓存 miss 时可回退，:698-717），`forward_batch.mm_inputs=None`、`mm_input_embeds=embeds`。
6. CUDA Graph 地址稳定性：`forward_batch.input_embeds` 存在时 `copy_` 到预分配缓冲（:723-725）。

disagg 场景：`enable_adaptive_dispatch_to_encoder` 时 `_embed_mm_inputs_with_split`（:505）按"整请求 precomputed / 非 precomputed"分组分别编码再拼回，保证 `get_embedding_and_mask` 只见到同质 batch。

ForwardBatch 侧字段（forward_batch_info.py）：`mm_inputs`（:461，按请求对齐的列表）、`input_embeds`（:420）、`mm_input_embeds`（:540）、`merge_mm_inputs`（:1003，把多请求 mm_inputs 合并供模型使用）。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
