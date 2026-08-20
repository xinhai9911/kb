## ModelArchConfigConvertor 架构参数提取（_part2）

承接 config-mapping.md，详述 `vllm/transformers_utils/model_arch_config_convertor.py` 与 `vllm/config/model_arch.py`。入口：`ModelConfig.get_model_arch_config()`（model.py:882）按 `hf_config.model_type` 查 `MODEL_ARCH_CONFIG_CONVERTORS`，默认 `ModelArchConfigConvertorBase`。

### 基类字段提取（ModelArchConfigConvertorBase）

| 关键成员 | 行为 |
|---|---|
| `get_architectures/num_hidden_layers/total_num_attention_heads/vocab_size/hidden_size` | 从 `hf_text_config` 直接 `getattr`，缺省 0/[] |
| `get_total_num_kv_heads` | 依序探测 `n_head_kv`→`num_kv_heads`→`num_key_value_heads`→`multi_query_group_num`→`num_attention_groups`，默认取 attention heads |
| `get_head_size` | MLA 特例（`kv_lora_rank + qk_rope_head_dim`，受 `VLLM_MLA_DISABLE` 影响，deepseek_v4 用 `head_dim`）；`head_dim>0`→`hidden_size_per_head`→`hidden_size/heads` 兜底；含 transformers v5.4+ `qk_rope_head_dim` attribute_map bug 修复（回读原始 config.json 覆盖） |
| `get_num_experts` | `num_experts`→`moe_num_experts`→`n_routed_experts`→`num_local_experts`；list 取首项；空则从 `block_configs` 的 moe 块取 MAX（异构场景） |
| `get_num_experts_per_token` | `num_experts_per_tok`→`num_experts_per_token`→`top_k_experts`→`moe_topk`→`moe_top_k` |
| `get_torch_dtype` | config.dtype → `get_text_config()` → `vision_config`/`encoder_config` → safetensors 头部 dtype（`get_safetensors_params_metadata` + `common_broadcastable_dtype`）→ fp32 |
| `get_quantization_config` | 归一化 `quant_method`（`compressed_tensors`→`compressed-tensors`；ModelOpt 按 `quant_algo` 定 `modelopt`/`modelopt_fp4`）；根 config 无则查 `text_config` |
| `derive_max_model_len_and_key` | 9 个候选键（`max_position_embeddings`/`n_positions`/`max_seq_len`/`seq_length`/`model_max_length`/`max_target_positions`/`max_sequence_length`/`max_seq_length`/`seq_len`）取最小 max_len 并记键名 |
| `is_deepseek_mla` | 命中 20+ 个 MLA 系 model_type 且含 `kv_lora_rank`（eagle 透查底层架构） |
| `is_mm_prefix_lm` | 配置字段或已知列表（`bagel/gemma3/molmo2/moondream3/paligemma/umm`）；`supports_multimodal=False` 时强制 False |
| `rswa_window` | `rswa_window` 字段取整 |

### 异构（heterogeneous）模型处理

- `get_per_layer_hf_configs()`：仅当根或 text config 的 `is_heterogeneous=True` 时返回按层 `(hf_config, hf_text_config)` 对（text config 决定层数），否则 `None`。
- `convert()`：同质直接 `convert_layer()`；异构逐层转换后 `ModelArchitectureConfig.from_layers()` 合并——一致字段直取、仅数值字段按 `max` 折叠（buffer 按最大层定尺寸）并生成 `per_layer_overrides`（非数值字段不一致抛 `ValueError`）；异构 MLA 抛 `NotImplementedError`。
- `ModelArchitectureConfig.__getitem__(layer_idx)`（model_arch.py:77）：无差异时返回 `self`；有 override 时浅拷贝后套用 `per_layer_overrides[layer_idx]`，镜像 HF `per_layer_config[i]`。

### 特殊 convertor 表（MODEL_ARCH_CONFIG_CONVERTORS，按 model_type）

| model_type | 类 | 覆写行为 |
|---|---|---|
| `falcon`/`RefinedWeb`/`RefinedWebModel` | `FalconModelArchConfigConvertor` | `new_decoder_architecture=False && multi_query=True` → KV heads=1 |
| `mpt` | `MPTModelArchConfigConvertor` | KV heads 取 `attn_config["kv_n_heads"]` |
| `dbrx` | `DbrxModelArchConfigConvertor` | 同上（`attn_config.kv_n_heads`） |
| `nemotron-nas` | `NemotronNasModelArchConfigConvertor` | 遍历 `block_configs`，首个非 no_op 块按 `heads//n_heads_in_group` 推导，否则 RuntimeError |
| `gemma4`/`gemma4_text`/`gemma4_unified`/`diffusion_gemma_text` | `Gemma4ModelArchConfigConvertor` | `use_bidirectional_attention=="vision"` 判定 mm_prefix；TS<5.15 时用 `gemma4_layer_config` 手工构造逐层 config（全注意力层 head_dim 更大） |
| `gemma4_mtp` | `Gemma4MTPModelArchConfigConvertor` | hidden_size 取 `backbone_hidden_size`（匹配主模型） |
| `cohere_asr` | `CohereAsrModelArchConfigConvertor` | 从 `transf_decoder["config_dict"]`/`encoder["n_heads"]` 取值，编解码 KV heads 须相等 |
| `moss_audio` | `MossAudioModelArchConfigConvertor` | 全部改从 `language_config` 取值 |
| `mamba`/`falcon_mamba`/`medusa`/`timm_wrapper` | Mamba/Medusa/Terratorch 系列 | head_size、KV heads 置 0 |
| `zamba2` | `Zamba2ModelArchConfigConvertor` | head_size 取 `attention_head_dim` |
| `mimo_v2`/`mimo_v2_flash` | `MimoV2ModelArchConfigConvertor` | 构造时剥除误设的 `attention_chunk_size`；有 `vision_config` 时改写 architectures |
| `*_mtp` 系列（`deepseek_mtp`/`mimo_mtp`/`glm4_moe_mtp`/`ernie_mtp`/`qwen3_next_mtp`/`bailing_hybrid*_mtp`/`step3p5_mtp`/`pangu_ultra_moe_mtp`/`longcat_flash_mtp`/`qwen3_5_mtp`/`gemma4_mtp`） | 对应 MTP 类 | 层数取 `num_nextn_predict_layers`（`qwen3_5_mtp` 取 `mtp_num_hidden_layers`，`longcat_flash_mtp` 缺省 1，`mimo_v2_mtp` 回退 `n_predict`） |

### ModelArchitectureConfig 结构（config/model_arch.py）

pydantic dataclass，字段：`architectures`、`model_type`、`text_model_type`、`hidden_size`、`total_num_hidden_layers`、`total_num_attention_heads`、`head_size`、`vocab_size`、`total_num_kv_heads`、`num_experts`、`num_experts_per_token`、`quantization_config`、`is_deepseek_mla`、`is_mm_prefix_lm`、`rswa_window`、`derived_max_model_len_and_key`、`per_layer_overrides`。`ModelConfig` 大量属性直接委托它（`total_num_attention_heads`、`vocab_size`、`hidden_size`、`head_size`、`total_num_kv_heads`、`num_experts(_per_token)`、`total_num_hidden_layers` 等，model.py:1371-1520），量化加载与 TP 切分也依赖 `total_num_*_heads`（见 weight-loading.md）。

### 其他公共工具（transformers_utils/config.py）

- `set_default_rope_theta` / `uses_mrope` / `uses_xdrope_dim` / `is_encoder_decoder`：供上层（attention 配置、调度器）探测 RoPE/编解码性质。
- `get_pooling_config` / `get_sentence_transformer_tokenizer_config` / `try_get_dense_modules`：sentence-transformers 仓库 `modules.json` 的 pooling / dense 层配置。
- `try_get_generation_config` / `try_get_tokenizer_config` / `get_hf_image_processor_config`：宽松读取，失败返回 `None`/空 dict（ModelScope 无 image_processor 接口）。
- `maybe_register_config_serialize_by_value`：`trust_remote_code` 时把 `transformers_modules` 动态类注册为 cloudpickle by-value 序列化（跨进程/多节点可 pickle，含 `multiprocessing.reducer` 与 ray.cloudpickle）。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
