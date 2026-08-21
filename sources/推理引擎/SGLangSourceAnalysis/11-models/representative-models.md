## 代表模型实现特征

按家族抽读 `sglang/srt/models/` 下的实现，归纳 SGLang 模型的共性骨架与 MLA / MoE / 多模态 / Transformers 回退的特化点。全部模型统一输出 `LogitsProcessorOutput`（或 `Pooler` 输出），forward 签名统一为 `(input_ids, positions, forward_batch, input_embeds=None, get_embedding=False, ...)`。

### 共性骨架（以 Llama 为基准）

`llama.py` 是「标准 decoder 模板」，大多数 Dense 模型照此结构改写：

| 组件 | 类 | 关键实现（llama.py 行号） |
|---|---|---|
| MLP | `LlamaMLP` | `MergedColumnParallelLinear`(gate_up) + `RowParallelLinear`(down) + `SiluAndMul`（:70） |
| 注意力 | `LlamaAttention` | `QKVParallelLinear` + `o_proj` + `get_rope` + `RadixAttention`（:138） |
| 残差层 | `LlamaDecoderLayer` | RMSNorm 带回传 residual、`quant_linear=` 挂钩（:283） |
| 主干 | `LlamaModel` | embed_tokens + `make_layers`(分层 PP) + norm（:372） |
| 输出 | `LlamaForCausalLM` | tie_word_embeddings 复用 embed；`LogitsProcessor` + `Pooler(LAST, normalize)`（:496） |

要点：
- **注意力与缓存解耦**：所有层不直接碰 KV 池，只调用 `RadixAttention(q, k, v, forward_batch)`（`llama.py:209`），由 ForwardBatch 元数据驱动（见 07-attention 模块）。
- **PP 与 split-prefill**：`pp_group.is_last_rank` 决定 logits 计算（`llama.py:584`）；`forward_split_prefill`（:599）配合 PD 分块；`LlamaModel` 用 `start_layer/end_layer` 切层。
- **一个文件多架构**：`llama.py` 底部 `Phi3ForCausalLM`、`InternLM3ForCausalLM`、`IQuestCoderForCausalLM` 直接继承 `LlamaForCausalLM`（:918-930），`EntryClass` 一并列出。
- **平台分支**：NPU 走 `forward_prepare_npu`（`sgl_kernel_npu` 的 fused split+qkv+rmsnorm+rope，:225），其余 `forward_prepare_native`。
- **权重加载**：`load_weights` 经 `AutoWeightsLoader` + `get_weight_remap`（FP8 后缀归一），`stacked_params_mapping` 把 `.q_proj/.k_proj/.v_proj` 拆进 `qkv_proj`（:543）。
- **量化内建**：类属性 `default_bitsandbytes_target_modules` / `bitsandbytes_stacked_params_mapping`（:498-516）供 BitsAndBytes 4bit 加载。

`qwen2.py`、`gemma.py` 与 llama 骨架的差异仅局部：Qwen2 注意力支持 qk_norm/partial_rotary；Gemma 用 `GeluAndMul("none")`（`gemma.py:69`）、无 bias、rope 全维 neox 风格；二者 `EntryClass` 分别只暴露 `Qwen2ForCausalLM` / `GemmaForCausalLM`。

### MLA：deepseek_v2.py

`DeepseekV2AttentionMLA`（:1708）是多 mixin 组合体，一个类覆盖 MHA / MLA / ROCm / CPU / NPU 五套 forward：

| 成员 | 说明 |
|---|---|
| `fused_qkv_a_proj_with_mqa` | `q_lora_rank` 存在时：`ReplicatedLinear(hidden, q_lora_rank+kv_lora_rank+qk_rope_head_dim)` 一次出三个低秩投影（:1778） |
| `q_a_layernorm` / `kv_a_layernorm` | RMSNorm 低秩归一（`kv_a_layernorm` 在后续构造中） |
| `q_b_proj` | `ColumnParallelLinear(q_lora_rank → num_heads×qk_head_dim)`，拆出 nope+rope 双段 |
| `kv_b_proj` / `o_proj` | 低秩 K/V 上投影 + 输出投影（:1849/:1859） |
| `RadixAttention` | 每层 `attn_mqa` 与 `attn_mha` 两个实例共享 `layer_id`，`v_head_dim` 与 `head_dim` 分离（MLA 用） |

- 每层按 `AttnForwardMethod` 枚举分派（`MLA`/`MLA_ROCM`/`MLA_FUSED_ROPE_ROCM`/`MLA_FUSED_ROPE_CPU`/`MLA_NPU`，:2107-2200），核心是「absorb」低秩矩阵乘法路径（`forward_absorb_prepare` 产出 `inner_state`，`forward_absorb_core` 消费），把 Q 吸收进 W，避免把 KV 展开成完整头。
- `kv_cache_dtype` 取自全局 `get_model()`（:1770），`qk_head_dim = qk_nope_head_dim + qk_rope_head_dim`。
- **DSA 稀疏注意力**（DeepSeek V3.2）：`skip_topk`/`next_skip_topk` 让该层跳过 MoE top-k 复用上一层索引（:1816-1825）；`dsa_layer_skips_topk(config, layer_id)`、`mla_enable_prefill_cp`/`dsa_enable_prefill_cp` 开 prefill 上下文并行。
- **MoE**（`DeepseekV2MoE`，:552）：`MoEGate`（`noaux_tc` 时带 `e_score_correction_bias`，:458）+ `get_moe_impl_class(quant_config)` 产出专家实现；`num_fused_shared_experts` 把 shared expert 并入 MoE kernel，DeepEP/MegaMOE 下每 rank 扩展为 256+EP 槽位（如 EP=16 → 272 专家，top_k=8+1，:588-597）；TopK 分 `HashTopK`（hash 层）与 grouped noaux_tc（`use_grouped_topk`、`n_group`、`topk_group`）两条路。
- 家族：`DeepseekV3ForCausalLM`、`DeepseekV32ForCausalLM` 继承 `DeepseekV2ForCausalLM`（:3224），`EntryClass` 一并注册三个架构名。

### MoE 通用模式：qwen3_moe.py

`Qwen3MoeSparseMoeBlock`（:228）展示 SGLang MoE 的标准形态：

| 成员 | 实现 |
|---|---|
| `TopK` | `use_grouped_topk=False`、`renormalize=norm_topk_prob`（GGUF 关闭）（:252） |
| `experts` | `get_moe_impl_class(quant_config)`，`routing_method_type=RoutingMethodType.Renormalize`（:259） |
| `gate` | `ReplicatedLinear`（仅 modelslim 量化路径允许量化 gate，:280） |
| 双路径 forward | `forward_normal`（TP）vs `forward_deepep`（DeepEP / Ascend fused-EP，:302-308） |

`Qwen3MoeModel` 直接继承 `Qwen2MoeModel`（:912），体现「新 MoE 架构复用旧主干」的族内继承模式。

### 多模态：qwen2_vl.py

`Qwen2VLForConditionalGeneration`（:430）是「视觉塔 + LLM 主干」的模板，`EntryClass` 仅一个条件生成类：

| 部分 | 实现 |
|---|---|
| `visual` | `Qwen2VisionTransformer`（patch embed/merger/block/rotary，:474）；支持 BitsAndBytes 4bit |
| 语言主干 | `Qwen2Model` + `lm_head`（tie 时复用 embed_tokens，:483-495） |
| mrope | `"mrope_section" in rope_scaling` 开启，forward 时用 `forward_batch.mrope_positions`（3, seq_len）（:561） |
| token 对齐 | `pad_input_ids` 用 `MultiModalityDataPaddingPatternMultimodalTokens` 插入 `<image>/<video>` 占位（:501） |
| 特征抽取 | `get_image_feature` / `get_video_feature` / `_process_video_input` 统一走 `self.visual(pixel_values, grid_thw=...)`（:505-532） |
| 权重重映射 | `hf_to_sglang_mapper`（WeightsMapper）把 transformers v4.52 前后 checkpoint 前缀统一到 SGLang 命名（:451） |

多模态统一协议：decode 阶段或 `not contains_image_inputs()` 时跳过视觉计算（:564-567）；`should_apply_lora` 排除 `visual.` 前缀（:537）。

### Transformers 回退：transformers.py

`EntryClass` 一次注册 **12 个后端类**（`transformers.py:1672`），覆盖纯 Transformers 运行：

| 族 | 类 |
|---|---|
| Causal | `TransformersForCausalLM`、`TransformersMoEForCausalLM`、`TransformersMultiModalForCausalLM`、`TransformersMultiModalMoEForCausalLM` |
| Embedding | `TransformersEmbeddingModel`、`TransformersMoEEmbeddingModel`、`TransformersMultiModalEmbeddingModel`、`TransformersMultiModalMoEEmbeddingModel` |
| Sequence Classification | `TransformersForSequenceClassification`、`TransformersMoEForSequenceClassification`、`TransformersMultiModalForSequenceClassification`、`TransformersMultiModalMoEForSequenceClassification` |

`registry.py` 的 `_normalize_archs` 把未注册架构兜底到 `TransformersForCausalLM`；`resolve_transformers_arch`（`model_loader/utils.py`）先验证 HF 类存在且 `is_backend_compatible()`，兼容才回退，否则报「无 SGLang 实现且 HF 不兼容」。

### 特殊任务 / 投机家族

| 类型 | 代表文件 | 架构类 |
|---|---|---|
| Embedding/Reward/分类 | `llama_embedding.py`、`llama_reward.py`、`qwen2_classification.py` | `LlamaEmbeddingModel`、`LlamaForSequenceClassification`、`Qwen2ForSequenceClassification` 等 |
| 投机草稿（EAGLE/MTP/Draft） | `llama_eagle.py`、`qwen3_moe_mtp.py`、`dflash.py` | `LlamaForCausalLMEagle`、`Qwen3MoeForCausalLMMTP`、`DFlashDraftModel` 等 |
| 原生解码 | `torch_native_llama.py` | `TorchNativeLlamaForCausalLM`、`TorchNativePhi3ForCausalLM` |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
