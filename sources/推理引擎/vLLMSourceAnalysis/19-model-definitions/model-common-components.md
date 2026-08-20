## 模型基类与公共组件（interfaces / utils / adapters）

模型文件虽然每个架构一个 `.py`，但公共机制集中在三个文件：`interfaces.py`（能力接口协议）、`interfaces_base.py`（三基类）、`utils.py`（权重加载/映射/PP 辅助）、`adapters.py`（embedding/seq-cls 在线转换）。

### interfaces.py：能力接口协议

全部为 `@runtime_checkable` 的 `Protocol` + 同名 `supports_*()` 探测函数（用 `getattr(model, "supports_xxx", False)` 或 `isinstance` 判定）。能力以 **ClassVar 布尔标志**暴露，供调度器/量化/LoRA 等机制静态探测：

| 协议 | 关键标志/成员 | 消费方 |
|---|---|---|
| `SupportsMultiModal` | `supports_multimodal`、`supports_multimodal_raw_input_only`、`supports_encoder_tp_data`、`requires_raw_input_tokens`、`_processor_factory`、`_language_model_names` | `MultiModalRegistry.supports_multimodal_inputs`（`multimodal/registry.py:103`）；`ModelConfig._model_info` |
| `SupportsMultiModalEmbeddings` | `embed_input_ids(input_ids, multimodal_embeddings, is_multimodal)` | 文本/多模态 embedding 合并（`_merge_multimodal_embeddings` 原位覆写占位 token） |
| `SupportsLoRA` | `supports_lora`、`packed_modules_mapping`、`embedding_modules`、`lora_skip_prefixes`、`lora_manager` | `lora/model_manager.py`（`SupportsLoRAModel = nn.Module, SupportsLoRA`） |
| `SupportsPP` | `supports_pp`、`make_empty_intermediate_tensors`；forward 须接收 `intermediate_tensors` | PP 切层（`_supports_pp_inspect` 用 `supports_kw` 检查 forward 签名） |
| `SupportsQuant` | `hf_to_vllm_mapper`、`packed_modules_mapping`、`quant_config`；`__new__` 从构造参数里找 `VllmConfig`/`QuantizationConfig` 并调 `_maybe_apply_model_mapping` | 量化配置初始化：把模型 `hf_to_vllm_mapper`（unstacked）与 `packed_modules_mapping` 合并进 `quant_config` |
| `MixtureOfExperts` | `num_moe_layers`、`num_expert_groups`、`num_logical/physical_experts`、`moe_layers`、`expert_weights`、`set_eplb_state()`、`update_physical_experts_metadata()` | EPLB（Expert Parallel Load Balancing）状态注入 |
| `SupportsEagle`/`SupportsEagle3`/`SupportsEagleBase` | `supports_eagle`/`supports_eagle3`、`has_own_lm_head`/`has_own_embed_tokens`；`EagleModelMixin._maybe_add_hidden_state` 输出 aux hidden state | 投机解码 draft/verifier 配对 |
| `SupportsMRoPE`/`SupportsXDRoPE` | `get_mrope_input_positions()`/`get_xdrope_input_positions()` | 多模态位置编码 |
| `HasInnerState`/`IsAttentionFree`/`IsHybrid`/`HasNoOps` | `has_inner_state`/`is_attention_free`/`is_hybrid`/`has_noops` | BlockManager / 注意力后端选择；`IsHybrid` 另有 `get_mamba_state_shape_from_config` |
| `SupportsTranscription`/`SupportsRealtime` | `supported_languages`、`get_generation_prompt`、`get_language_detection_prompt` | ASR/流式转写请求处理 |
| `SupportsEncoderCudaGraph` | `get_encoder_cudagraph_config`、`encoder_cudagraph_forward` 等 9 个方法 | 视觉编码器 CUDA graph 捕获/回放 |

其中 `_mark_language_model` / `_mark_tower_model`（`SupportsMultiModal` 的 contextmanager）配合 `utils.collect_children` + `no_init_weights`，实现 `--mm-encoder-only`（语言层换成 `StageMissingLayer`）与 `--limit-mm-per-prompt=0`（tower 层跳过初始化）。

### interfaces_base.py：三基类

| 类 | 必须实现 | 探测函数 |
|---|---|---|
| `VllmModel` | `__init__(vllm_config, prefix)`、`embed_input_ids`、`forward(input_ids, positions)` | `is_vllm_model`（签名检查） |
| `VllmModelForTextGeneration` | + `compute_logits(hidden_states)` | `is_text_generation_model` |
| `VllmModelForPooling` | + `is_pooling_model=True`、`pooler`、`default_seq/tok_pooling_type`、`attn_type`、`score_type` | `is_pooling_model`（读标志） |

装饰器 `default_pooling_type(...)` / `attn_type(...)` 用于便捷设置 ClassVar；`get_score_type` 沿 MRO 收集非 `"bi-encoder"` 的 `score_type`。这三类只做结构性约定，不带 ClassVar 标志，避免破坏既有 OOT 注册。

### utils.py：权重映射与加载

**`WeightsMapper`**（权重名映射，dataclass）——回答"HF 权重名 → vLLM 内部名"如何工作，按顺序应用六类规则：

| 规则字段 | 语义 | 示例（Llama） |
|---|---|---|
| `orig_to_new_renaming` | transformers `WeightRenaming` 逐条重命名 | — |
| `orig_to_new_regex` | 正则替换 | — |
| `orig_to_new_substr` | 子串替换 | — |
| `orig_to_new_stacked` | 子串→`(新名, shard_id)`；多张 HF 权重合并成一张 vLLM 权重并附分片元数据 | `".q_proj" → (".qkv_proj", "q")`、`".gate_proj" → (".gate_up_proj", 0)` |
| `orig_to_new_prefix` / `orig_to_new_suffix` | 前缀/后缀替换 | — |

映射值为 `None` 表示丢弃该权重；`shard_id` 会写到 `tensor.shard_id`，交给 `weight_loader` 做分片加载。`apply()` 对 `(name, tensor)` 流做映射；`get_unstacked_mapper()` 去掉 stacked 规则，供 LoRA 名解析与量化配置保留 `q_proj` 等原名。`__or__` 合并两个 mapper（量化 scale 映射等）。

**`AutoWeightsLoader`**——单遍权重加载器，递归下钻 `load_weights`（子模块可 override）或参数级 `weight_loader`：

- `_groupby_prefix` 按第一段模块名分组，避免多遍扫描 checkpoint；
- `skip_prefixes` / `skip_substrs`（默认跳过 `rotary_emb.inv_freq` 等非权重张量）、`ignore_unexpected_prefixes/suffixes`（默认忽略 `.bias`）控制忽略；
- `load_weights(weights, mapper=...)` 先并入 `quant_config.get_cache_scale_mapper()` 与 `_ignore_unexpected_suffixes`，再统一 apply mapper；
- 用 `@support_quantized_model_reload_from_hp_weights` 装饰，支持量化模型从 HP 权重热重载。

**PP 辅助**：`make_layers(num_hidden_layers, layer_fn, prefix)` 按 `get_pp_indices` 把非本 rank 的层替换为 `PPMissingLayer`（Identity 透传），并套 `get_offloader().wrap_modules`；`make_empty_intermediate_tensors_factory(keys, hidden_size)` 生成 `SupportsPP` 需要的 profiling 空张量；`get_pp_missing_layer_names`/`is_pp_missing_parameter` 供权重加载跳过缺失层。

**多模态辅助**：`_merge_multimodal_embeddings`（按 `is_multimodal` 掩码原位写入 mm embedding）、`flatten_bn`、`_flatten_embeddings`、`scatter_output_slices`（编码器 CUDA graph 输出按 token 数散回）。

### adapters.py：embedding / 分类模型在线转换

`as_embedding_model(cls)` / `as_seq_cls_model(cls)` 通过**动态子类化**把生成模型就地变成池化模型（幂等：已是 pooling 模型则原样返回）：

1. `_create_pooling_model_cls` 生成 `class ModelForPooling(orig_cls, VllmModelForPooling)`：
   - 用 `no_init_weights(..., targets=(LogitsProcessor, ParallelLMHead))` 把 LM 头替换为 `StageMissingLayer("output")`（省显存、权重加载时跳过）；
   - `_load_pooling_model_weights` 支持从 `*ForCausalLM` 或 `*Model` 两种前缀加载权重（探测 `""`/`"model."` 前缀，懒链式转发）。
2. embedding 变体 `_init_pooler` → `DispatchPooler.for_embedding(pooler_config)`（默认 LAST token）；
3. seq-cls 变体混入 `SupportsCrossEncoding`，`_init_pooler` 建 `ReplicatedLinear` score 头 + `DispatchPooler.for_seq_cls`；`load_weights` 支持在线转换：`SEQ_CLS_LOAD_METHODS`（`from_2_way_softmax`、`no_post_processing`）把 lm_head 权重直接截成 score 头（Qwen3-Reranker、bge-reranker-v2-gemma 等）。
4. 类名改写：`LlamaForCausalLM` → `LlamaBidirectionalModel`/`LlamaForSequenceClassification` 等（经 `_get_pooling_model_name`）。

### 公共层组件位置

`models/` 下没有 `layers.py`；通用层（Attention、QKV/Row/Column/MergedParallelLinear、RMSNorm、fused_moe、mla、LogitsProcessor、VocabParallelEmbedding 等）位于 `vllm/model_executor/layers/`。`models/transformers/layers.py` 是 Transformers 后端专用：`VLLM_USE_HW_AGNOSTIC=1` 时从 `vllm.model_executor.hw_agnostic.layers.<module>` 解析符号，失败则回退 vLLM 原生层。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
