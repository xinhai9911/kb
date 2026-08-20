## 代表架构对比与复用关系

`vllm/model_executor/models/` 含 292 个文件，绝大多数架构以「继承基座 + 覆盖层/注意力/加载」方式实现。下面按复用血缘分组对比。

### 架构→文件→关键特性总表

| 架构名（HF） | 文件 | vLLM 类 | 关键特性 |
|---|---|---|---|
| `LlamaForCausalLM` | `llama.py` | `LlamaForCausalLM` | GQA、RoPE（neox 式）、SwiGLU（`gate_up_proj`）、RMSNorm、可选 sliding window；带 `hf_to_vllm_mapper`（q/k/v→qkv、gate/up→gate_up stacked） |
| `Phi3ForCausalLM` | `phi3.py` | `Phi3ForCausalLM(LlamaForCausalLM)` | 仅 18 行：纯继承，覆盖 `packed_modules_mapping`（`qkv_proj` 不拆、`gate_up_proj` 不拆） |
| `Qwen2ForCausalLM` | `qwen2.py` | `Qwen2ForCausalLM` | GQA、RoPE（默认 theta=1e6，`set_default_rope_theta`）、可选 `qk_norm`、可选 `dual_chunk_attention_config`、`is_causal=False` 转双向编码器注意力 |
| `Qwen3ForCausalLM` | `qwen3.py` | `Qwen3ForCausalLM` | 继承 Qwen2 模型骨架；注意力内置 `q_norm`/`k_norm`（RMSNorm per-head），支持 `per_layer_sliding_window` |
| `GPT2LMHeadModel` | `gpt2.py` | `GPT2LMHeadModel` | 绝对位置 embedding（`wpe`）、LayerNorm、无 RoPE；`_transpose_conv1d` 处理 HF Conv1D 转置权重；`_add_transformer_prefix` 补前缀 |
| `Glm4ForCausalLM` | `glm4.py` | `Glm4ForCausalLM` | 继承 `LlamaModel`（仅换 `layer_type=Glm4DecoderLayer`）；partial RoPE（`partial_rotary_factor=0.5`，neox=False）、四段 LayerNorm（`post_self_attn_layernorm`/`post_mlp_layernorm`）、权重跳过 MTP 层 |
| `DeepseekV2ForCausalLM` | `deepseek_v2.py` | `DeepseekV2ForCausalLM` | MLA（Multi-Head Latent Attention）+ 共享/路由 MoE（`DeepseekV2MoE`→`FusedMoEFactory`，grouped top-k、EPLB）；`DeepseekForCausalLM`/`DeepseekV3ForCausalLM`/`GlmMoeDsaForCausalLM` 为其空子类 |
| `DeepseekV32ForCausalLM` | `deepseek_v2.py` | 同文件 + `Indexer`/`DeepseekV32IndexerCache` | V3.2 混合线性注意力：深度稀疏注意力 indexer + `RSWAAttention`，`DeepseekV32IndexerBackend` |
| `Qwen2MoeForCausalLM` | `qwen2_moe.py` | `Qwen2MoeForCausalLM` | 继承 Qwen2 注意力 + `Qwen2MoeSparseMoeBlock`（FusedMoE） |
| `Qwen3MoeForCausalLM` | `qwen3_moe.py` | `Qwen3MoeForCausalLM` | Qwen3 注意力 + MoE |
| `Qwen3_5ForCausalLM` | `qwen3_5.py` | `Qwen3_5ForCausalLM` | 新一代混合线性注意力 |
| `MambaForCausalLM`/`FalconMamba` | `mamba.py` | `MambaForCausalLM` | SSM 状态空间模型（无注意力，`IsAttentionFree`），`HasInnerState` |
| `JambaForCausalLM` | `jamba.py` | `JambaForCausalLM` | 注意力+Mamba 混合（`IsHybrid`），`layers_block_type` |
| `MoonshotKimiaForCausalLM` | `kimi_audio.py` | `KimiAudioForConditionalGeneration` | 注：`models/` 下**无** `moonshot.py`，该架构由 registry 映射到 `kimi_audio`（音频多模态） |
| `TransformersForCausalLM` 等 | `models/transformers/*.py` | 后端类 | 无原生实现模型的通用回退：直接跑 HF 模型，`is_backend_compatible()` 校验 |

### 复用血缘（子类化 → 只改增量）

```
llama.py  ─┬─ phi3.py（18 行覆盖 LoRA mapping）
          ├─ glm4.py（LlamaModel + 定制 decoder layer）
          ├─ mistral.py / internlm2.py / telechat2.py ...
          └─ adapters 转换（LlamaBidirectionalModel / ForSequenceClassification）

qwen2.py  ─┬─ qwen3.py（Qwen2Model 骨架 + QK-Norm 注意力）
           ├─ qwen2_moe.py（Qwen2Attention + MoE 块）
           ├─ qwen2_rm.py（reward：ForCausalLM + score 头）
           └─ qwen2_vl.py 等（多模态：语言背板复用 Qwen2Model）

deepseek_v2.py ── DeepseekForCausalLM / DeepseekV3ForCausalLM / GlmMoeDsaForCausalLM（空子类，按 config 分支）

gpt2.py ── GPT2ForSequenceClassification（+SupportsCrossEncoding 池化）
```

`phi3.py` 是"最小继承"的极端样例：完整实现只有 10 行代码 + 8 行 `packed_modules_mapping`。

### 代表性注意力实现对比

| 架构 | 注意力结构 | QK-Norm | RoPE | 其他 |
|---|---|---|---|---|
| Llama | GQA（`QKVParallelLinear` + `Attention`） | 无 | neox 式，`get_rope(..., rope_parameters)` | 支持 `sliding_attention` per-layer |
| Qwen2 | GQA | 可选 `qk_norm`（BAGEL 等） | theta 默认 1e6 | `dual_chunk_attention_config` 双块注意力 |
| Qwen3 | GQA | 内置 `q_norm`/`k_norm`（RMSNorm） | 同上 | per-layer sliding window |
| Glm4 | GQA | 无 | partial（0.5）非 neox 式 | 四段 LayerNorm 布局 |
| DeepseekV2/V3 | MLA：`fused_qkv_a_proj`(q_lora+kv_lora) → `kv_a_layernorm` → `kv_b_proj` 展开；`DeepseekV2MLAAttention`（`layers/mla.py` `MLAModules`/`MultiHeadLatentAttentionWrapper`） | — | deepseek_yarn / deepseek_llama_scaling | 低秩 KV 缓存（只存 `kv_lora_rank` 的潜在态） |
| DeepseekV3.2 | MLA + 深度稀疏 indexer（`SparseAttnIndexer`、`fused_indexer_q_rope_quant`）+ `RSWAAttention` | — | — | 每层前 N 个 token 稀疏注意力 + 滑动窗口 |

### MoE 公共实现

- 模型层 MoE 块（如 `DeepseekV2MoE`）由 `GateLinear`（router，可带 `e_score_correction_bias`）+ `FusedMoEFactory` 组装；支持 grouped top-k、sequence parallel MoE（`sequence_parallel_chunk` + all-gather）、EPLB 冗余专家（`n_logical/n_physical/n_local_physical/n_redundant_experts`）、共享专家（`shared_experts`，或 AITER fused-shared-experts 时打包进 routed 槽）。
- `FusedMoEFactory` 及各类 kernel 实现在 `vllm/model_executor/layers/fused_moe/`（`configs/`、`experts/`、`router/`、`runner/` 子包，约 1.2 万行）。
- 模型顶层混入 `MixtureOfExperts`：`DeepseekV2ForCausalLM.set_moe_parameters` 扫描 `model.layers` 收集 `moe_mlp_layers`，`extract_moe_parameters` 把专家数等元数据写入实例属性，供 EPLB 与专家并行（EP）调度探测。

### 权重加载模式对比

| 架构 | 加载方式 | 特殊处理 |
|---|---|---|
| Llama/Qwen2 系 | `AutoWeightsLoader.load_weights(weights, mapper=WeightsMapper(...))` | stacked 映射把 5 张 HF 权重并为 3 张 vLLM 权重；`tie_word_embeddings` 时跳过 `lm_head.` |
| GPT2 | `AutoWeightsLoader` + `_transpose_conv1d` + `_add_transformer_prefix` | HF Conv1D 权重转置（`.weight` 且名字含 `c_attn/c_proj/c_fc`）；跳过 `.attn.bias/.attn.masked_bias` |
| Glm4 | `AutoWeightsLoader` + `skip_prefixes` | 跳过 `lm_head.` 与 `model.layers.{num_hidden_layers+i}.`（MTP 草稿层） |
| DeepseekV2/V3 | `AutoWeightsLoader` | `get_expert_mapping` 经 `fused_moe_make_expert_params_mapping` 生成专家权重/scale 映射；`fuse_qkv_a_proj` 时 `packed_modules_mapping["fused_qkv_a_proj"] = ["q_a_proj","kv_a_proj_with_mqa"]` |
| GPTQ 等量化模型 | 通用 | `AutoWeightsLoader.load_weights` 自动并入 `quant_config.get_cache_scale_mapper()`，忽略 `.bias` 等后缀 |

### Embedding / Pooling 复用

- 纯文本 embedding：registry 直接映射专用类（`BertEmbeddingModel`、`RobertaEmbeddingModel`），或经 `as_embedding_model(LlamaForCausalLM)` 动态子类化（`LlamaBidirectionalModel`）。
- 多模态 embedding：`CLIPEmbeddingModel`、`SiglipEmbeddingModel`、`ColPaliModel` 等单独实现，仍实现 `SupportsMultiModalEmbeddings` 的 `embed_input_ids`。
- 池化任务：`VllmModelForPooling` 协议声明 `default_seq_pooling_type`/`default_tok_pooling_type`/`pooler`，`DispatchPooler`（`layers/pooler.py`）按 `PoolerConfig` 分发；`GPT2ForSequenceClassification` 用 `DispatchPooler.for_seq_cls(pooler_config, classifier=self.score)`。
- 新模型接入要点：`__init__(vllm_config, prefix)` + `embed_input_ids` + `forward(input_ids, positions, ...)`（`VllmModel`）；生成类补 `compute_logits`；能力标志（`supports_lora`/`supports_multimodal`/`supports_pp` 等）按需继承协议类即可被 registry 自动探测进 `_ModelInfo`。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
