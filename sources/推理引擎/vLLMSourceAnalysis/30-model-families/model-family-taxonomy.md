## 模型家族分类学总览

`vllm/model_executor/models/` 共 310 个文件（含 `transformers/` 子目录），对应约 300 个 HF 架构名。本文按**技术族**归纳全部注册模型，补充 19-model-definitions 已覆盖的 12+ 代表架构之外的剩余家族。

### 注册入口与分类来源

所有架构 → (文件模块, 类名) 映射集中在 `registry.py` 的**按任务分组字典**中，`_VLLM_MODELS` 汇总后由 `ModelRegistry` 消费：

| 字典 | 行号 | 任务族 |
|---|---|---|
| `_TEXT_GENERATION_MODELS` | 72-219 | 纯文本生成（decoder-only / MoE / MLA / SSM） |
| `_EMBEDDING_MODELS` | 221-273 | embedding（文本 + 多模态） |
| `_LATE_INTERACTION_MODELS` | 275-289 | 晚期交互检索（ColBERT / ColPali / ColQwen3） |
| `_REWARD_MODELS` | 291-295 | reward / process reward |
| `_TOKEN_CLASSIFICATION_MODELS` | 297-316 | token 级分类 |
| `_SEQUENCE_CLASSIFICATION_MODELS` | 318-345 | 序列分类 / 排序 |
| `_MULTIMODAL_MODELS` | 347-616 | 多模态（视觉/音频/OCR/Omni） |
| `_SPECULATIVE_DECODING_MODELS` | 618-689 | 投机解码草稿（Eagle / MTP / Medusa / DFlash） |
| `_TRANSFORMERS_SUPPORTED_MODELS` | 691-708 | 少量白名单直接进 transformers 后端 |
| `_TRANSFORMERS_BACKEND_MODELS` | 710-743 | 通用回退后端（`transformers/*`） |
| `_PREVIOUSLY_SUPPORTED_MODELS` / `_OOT_SUPPORTED_MODELS` | 764 / 806 | 弃用（报错提示）与第三方模型 |

`_ModelInfo.architecture` 取类名本身（`registry.py:842`）；`register_model()` 支持类对象或 `"<module>:<class>"` 懒加载字符串。

### 家族分类总表（12 族）

| 家族 | 代表文件 | 关键特性 | 实现策略 |
|---|---|---|---|
| ① 文本 Dense | `gemma2/gemma3/gemma4/mistral/falcon/bloom/opt/mpt/gpt_j/gpt_neox/stablelm/solar/orion/exaone/telechat2/nemotron/olmo3/phi/minicpm/mellum/jais2/plamo3/step1` | GQA 注意力、RoPE（多种风格）、RMSNorm；无 MoE | 多数继承 `llama.py` 或自建 decoder layer，复用 `Attention`/`QKVParallelLinear`/`AutoWeightsLoader` |
| ② MoE | `mixtral/qwen2_moe/qwen3_moe/gpt_oss/phimoe/dbrx/olmoe/afmoe/granitemoe/bailing_moe/exaone_moe/nemotron_h/hunyuan_v1/openpangu/param2moe/seed_oss/lfm2_moe/sarvam/cohere2_moe/glm4_moe` | 路由专家（top-k）、`FusedMoEFactory`、EPLB 冗余、共享专家 | 稠密基座 + `FusedMoE` 块；`gpt_oss.py` 另含 OCP-MX 量化专家 |
| ③ MLA/混合线性 | `deepseek_v2/deepseek_v3_2/sarvam/kimi_k3/laguna/longcat_flash/hy_v3/qwen3_5/minimax_m3` | 低秩 KV 潜在态、深度稀疏 indexer、混合线性注意力 | 复用 `layers/mla.py` 的 `MLAModules`；V3.2 加 `SparseAttnIndexer` + `RSWAAttention` |
| ④ SSM/Mamba | `mamba/mamba2`（另 `falcon_mamba` 映射到 mamba） | 纯状态空间层（`layers/mamba/mamba_mixer.py`/`mamba_mixer2.py`）、无注意力 | `MambaForCausalLM` 实现 `IsAttentionFree` + `HasInnerState`；`SupportsMambaPrefixCaching` 支持 SSM 前缀缓存 |
| ⑤ 混合架构（Hybrid） | `jamba/zamba2/olmo_hybrid/granitemoehybrid` | 注意/Mamba/MoE 层按 `layers_block_type` 交替；SSM 与 Transformer 共存的 **无独立 RNN 族**，RNN 类模型（teleflm 等实为 Llama 子类）归入 Dense 族 | `IsHybrid` 协议（`interfaces.py:887`）；`zamba2` 用 `itertools.cycle` 交替 `MambaMixer2` 与 `Attention` |
| ⑥ Vision 多模态 | `qwen2_vl/internvl/llava/llava_next/gemma3_mm/gemma4_mm/phi3v/glm4v/idefics3/paligemma/pixtral/minicpmv/molmo/ovis/smolvlm/mistral3/mllama4/chameleon/kimi_vl/step_vl/h2ovl/deepseek_vl2/nvlm_d/openvla` | 视觉塔 + connector + 语言背板；`MultiModalKeys` 分语言/connector/tower/generator 四段 | 背板复用 `qwen2.py`/`gemma3.py` 等；视觉塔复用 `clip.py`/`siglip.py`/`intern_vit.py`；`SupportsMRoPE` 支持 3D 位置 |
| ⑦ 音频/Omni 多模态 | `whisper/qwen2_audio/glmasr/cohere_asr/granite_speech/parakeet/funasr/ultravox/voxtral/kimi_audio/mimo_audio/moss_audio/funaudiochat/qwen3_asr/qwen2_5_omni_thinker` | 音频编码器（Whisper 等）+ 投影 + LM；部分 encoder-decoder | `whisper.py` 为 encoder-decoder 代表（`SupportsTranscription` 协议族见 `interfaces.py:1229`） |
| ⑧ OCR/文档理解 | `deepseek_ocr/glm_ocr/dots_ocr/unlimited_ocr/paddleocr_vl/lightonocr/qianfan_ocr/nemotron_parse/phi4mm` | 高分辨率视觉 + 文本识别头 | 复用视觉塔组件；`phi4mm.py` 同时处理图像+音频（`Phi4MMForCausalLM`） |
| ⑨ Embedding/池化/检索 | `bert/roberta/modernbert/bert_with_rope/jina/gritlm/colbert/colpali/colqwen3/clip/siglip/terratorch/qwen2_rm` | 双向注意力、`EncoderOnlyAttention`、`DispatchPooler`、晚期交互 `SupportsLateInteraction` | `adapters.py` 的 `as_embedding_model`/`as_seq_cls_model` 动态包装生成类；`bert.py` 家族实现 `SupportsCrossEncoding` |
| ⑩ 投机解码/草稿 | `llama_eagle/llama_eagle3/qwen3_eagle3/deepseek_eagle/mistral_eagle/medusa/deepseek_mtp/glm4_moe_mtp/gemma4_mtp/qwen3_dflash/qwen3_dspark` | 草稿头（Eagle 自回归 / MTP 单步 / Medusa / DFlash / DSpark） | 注册于 `_SPECULATIVE_DECODING_MODELS`；`EagleModelMixin`/`SupportsEagle3` 协议（`interfaces.py:1499/1549`） |
| ⑪ MTMD/扩散 | `diffusion_gemma/cosmos3/gemma3n_mm/gemma4_unified` | 离散/块扩散、统一多模态（MTMD） | `DiffusionGemmaForConditionalGeneration` 需 `DiffusionConfig`；`cosmos3` 为视频扩散 |
| ⑫ Transformers 通用后端 | `transformers/base/causal/moe/pooling/multimodal/legacy/layers/fuser.py` + `fusers/` | 无原生实现模型的 HF 直跑回退，`is_backend_compatible()` 校验 | `get_fuser` 用 fx trace 匹配 6 种 fuser 把 HF 模块融合进 vLLM 层 |

### 各家族代表实现要点（19 模块未覆盖者）

| 文件 | 类 | 关键行为 |
|---|---|---|
| `gemma.py`（553 行） | `GemmaForCausalLM` | 专属 `GemmaRMSNorm`；`_get_gemma_act_fn` 以 `@cache` 修正早期 Gemma 配置误写 exact GeLU（改 `gelu_pytorch_tanh`） |
| `mistral.py` | `MistralForCausalLM` | docstring 即「Mistral adaptation of the LLaMA architecture」；直接 import `llama.py` 的 `LlamaAttention/LlamaDecoderLayer/LlamaModel/LlamaForCausalLM`，仅自写 `MistralMLP` |
| `gpt_oss.py`（1249 行） | `GptOssForCausalLM` | `OAIAttention.rope_is_neox_style` 类变量控制 RoPE 风格；MoE 走 `FusedMoEFactory` + `GateLinear`，支持 OCP-MX 块量化专家；权重经 `remap_moe_expert_weights` |
| `gemma3_mm.py` | `Gemma3ForConditionalGeneration` | 视觉塔直接复用 `.siglip.SiglipVisionModel`；语言背板复用 `gemma3.py` 的 `Gemma3Model`；`Gemma3MultiModalProjector` 为动态分辨率 patch 重组 |
| `internvl.py`（1069 行） | `InternVLChatModel` | 复用 `.intern_vit.InternViT` 视觉塔 + `init_vllm_registered_model` 懒加载语言背板；processor 处理图片+视频两类输入 |
| `glm4v.py` | `GLM4VForCausalLM` | 语言背板复用 `chatglm.py` 的 `ChatGLMBaseModel/ChatGLMModel/GLMTransformer`；视觉塔用 `Conv2dLayer` + `MMEncoderAttention` |
| `bert.py`（981 行） | `BertEmbeddingModel/BertForMaskedLM/BertForTokenClassification/BertForSequenceClassification/BertSpladeSparseEmbeddingModel` | 双向编码器用 `EncoderOnlyAttention`；池化走 `DispatchPooler` + `pooler_for_token_classify` 等；实现 `SupportsCrossEncoding` |
| `clip.py` | `CLIPVisionModel/CLIPEmbeddingModel` | 视觉塔通用件：`Conv2dLayer` 下采样 + `MMEncoderAttention`（编码器注意力）；`VisionEncoderInfo` 由 `vision.py:get_vision_encoder_info` 按 config 分发 |
| `whisper.py`（1070 行） | `WhisperForConditionalGeneration` | encoder-decoder 结构代表；`whisper_utils.py` 承载输入处理，`whisper_causal.py` 为因果变体 |
| `colpali.py` | `ColPaliModel` | 继承 `PaliGemmaProcessingInfo/PaliGemmaMultiModalProcessor`；`forward` 返回 token 级视觉向量（`_is_proj_weight` 区分投影权重）；实现 `SupportsLateInteraction` |
| `zamba2.py`（968 行） | `Zamba2ForCausalLM` | 注意力层与 `MambaMixer2` 层按 `cycle` 交替（hybrid）；`IsHybrid` + `SupportsMambaPrefixCaching` + `HasInnerState` 三协议齐备 |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
