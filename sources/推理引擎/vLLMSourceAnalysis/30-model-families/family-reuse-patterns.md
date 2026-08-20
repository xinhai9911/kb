## 共性复用组件与特殊模型类型

### models/ 公共基础设施（非模型文件）

| 文件 | 行数 | 职责 |
|---|---|---|
| `registry.py` | 1532 | `ModelRegistry`：架构名 → 模块懒加载 → 类；`_ModelInfo` 缓存；`_TRANSFORMERS_BACKEND_MODELS` 回退路径 |
| `interfaces.py` | ~1900 | 全部能力协议（Protocol）：`SupportsMultiModal/Embeddings/LoRA/PP/MRoPE/XDRoPE/Quant/Realtime/Transcription/CrossEncoding/LateInteraction/MultiModalPruning/ScoreTemplate`、`HasInnerState/IsAttentionFree/IsHybrid/MixtureOfExperts/HasNoOps/SupportsMambaPrefixCaching/SupportsReplaySSM/SupportsEncoderCudaGraph`、`SupportsEagle/Eagle3`、`EagleModelMixin/LocalArgmaxMixin` |
| `interfaces_base.py` | — | 任务协议：`VllmModelForTextGeneration` / `VllmModelForPooling` + `is_text_generation_model` / `is_pooling_model` 判别 |
| `utils.py` | 1086 | `WeightsMapper`（权重重命名）、`AutoWeightsLoader`（统一加载入口）、`make_layers`/`PPMissingLayer`/`get_pp_missing_layer_names`（PP 切层）、`no_init_weights`、`maybe_prefix`、`sequence_parallel_chunk`、`init_vllm_registered_model`、`process_eagle_weight` |
| `adapters.py` | — | `as_embedding_model`（生成类 → 双向 embedding 类）、`as_seq_cls_model`（→ 序列分类类）、`SequenceClassificationConfig`、`load_weights_using_from_2_way_softmax` |
| `module_mapping.py` | — | `MultiModelKeys`（`language_model/connector/tower_model/generator` 四段），多模态权重加载分段依据 |
| `vision.py` | — | `VisionEncoderInfo` 抽象 + `get_vision_encoder_info` 工厂 + `get_num_selected_vision_tokens` + `FusedInputNorm` |
| `config.py` | — | `VerifyAndUpdateConfig`：架构级配置校验钩子（如 `DeepseekV32ForCausalLM` 强制 `cache_dtype="auto"`、`Ernie4_5_VLMoe` 关 `fast_moe_cold_start`） |

复用主链路：`ModelRegistry.load_model` → `models.<module>` import → 类实现 `VllmModel` 接口 → `AutoWeightsLoader.load_weights(weights, mapper=WeightsMapper(...))` 加载，`WeightsMapper` 做 stacked 映射（q/k/v→qkv、gate/up→gate_up）。多模态模型再叠加 `MultiModelKeys` 分段 + `vision.py` 的编码器解析。

### models/transformers 子目录（HF 通用后端）

```
transformers/
├── base.py          # Base 类：PreTrainedModelClasses 容器、__init__ 装配、is_backend_compatible() 校验
├── causal.py        # CausalMixin(VllmModelForTextGeneration) → TransformersForCausalLM
├── moe.py           # MoEMixin(MixtureOfExperts) → TransformersMoEForCausalLM，读取 HF MoE 状态
├── pooling.py       # EmbeddingMixin/SequenceClassificationMixin(VllmModelForPooling)
├── multimodal.py    # MultiModalMixin(SupportsMultiModal, SupportsMRoPE) + 通用 ProcessingInfo/Processor
├── legacy.py        # LegacyMixin：老接口兼容
├── layers.py        # 层定义辅助
├── fuser.py         # get_fuser：fx trace 匹配并缓存 fuser
├── fx_utils.py      # torch.fx 符号 trace、AST 改写工具
├── utils.py         # replace_linear_class、log_replacement 等
└── fusers/          # 6 种具体融合器
    ├── base.py      # BaseFuser/RewriteFuser/StackedFuser
    ├── qkv.py / packed_qkv.py   # QKV 投影合并（含 packed 不拆分）
    ├── glu.py       # gate/up 投影 → gate_up 融合
    ├── mla.py       # HF MLA 注意力 → vLLM layers/mla.py 的 MLA 层
    ├── moe.py       # HF MoE 块 → FusedMoE + GateLinear（vLLM 自有路由）
    └── rms_norm.py  # 裸张量 RMSNorm 叶模块融合
```

后端兼容判定：`Base.is_backend_compatible()`（`base.py:96`）在模型加载前校验；`get_fuser(module)` 以 `(module 类型, 直接子模块名)` 为键做 `@cached` 缓存，先统计子层中 `nn.Linear` 数量（≥2 或叶模块）再 fx trace，按 `MLAFuser → GLUFuser → QKVFuser → PackedQKVFuser → RMSNormFuser` 顺序匹配；命中 `RewriteFuser` 时还会 `update_forward` 改写 forward 源码（`fuser.py` 注释明示「RMSNorm-shaped modules the tracer cannot match are warned about」）。`moe.py` 用 `ast` 检查 HF MoE forward 是否返回 tuple 以适配 `FusedMoE` 输出契约。

### 特殊模型类型

| 类型 | 代表 | 机制 |
|---|---|---|
| 内部状态（SSM/混合） | `mamba/mamba2/zamba2/jamba` | `HasInnerState` 协议声明 `get_initial_inputs`/`step` 等状态句柄；状态经 `self.mamba_cache` 管理（CUDA graph 捕获见 `copy_inputs_before_cuda_graphs`）；SSU 执行后端在 `layers/mamba/ops/ssu_dispatch.py`（`MambaSSUBackend`/`TritonSSUBackend`）；`SupportsMambaPrefixCaching` 允许前缀缓存（`interfaces.py:1079`） |
| 无注意力 | `mamba` 系 | `IsAttentionFree` 标记（`interfaces.py:860`），调度器按此跳过注意力预算计算 |
| 混合架构 | `jamba/zamba2/olmo_hybrid/granitemoehybrid` | `IsHybrid` + `layers_block_type` 交替排布注意力/Mamba/MoE 层 |
| 晚期交互检索 | `colbert/colpali/colqwen3/jina_for_ranking` | `SupportsLateInteraction`；`forward` 输出 token 级向量，与序列级 embedding 分流 |
| encoder-decoder | `whisper/whisper_causal/cohere_asr/nemotron_parse` | `SupportsTranscription` / `SupportsCrossEncoding`；输入处理走 `EncoderDecoderInputProcessor` |
| 实时（流式）推理 | `voxtral_realtime/qwen3_asr_realtime/granite_speech_plus` | `SupportsRealtime` 协议（`interfaces.py:1194`） |
| 推理/评分头 | `qwen2_rm/internlm2`（reward）、`qwen3_asr_forced_aligner`（对齐） | reward 注册于 `_REWARD_MODELS`；对齐器注册于 `_TOKEN_CLASSIFICATION_MODELS`；`SupportsScoreTemplate` 支持自定义评分模板 |
| 多模态编码器独立暴露 | `clip/siglip/intern_vit/moonvit/blip/idefics2_vision_model/kimi_k25_vit/gemma3n_audio_utils` | 视觉/音频塔既被多模态模型复用，也作为独立 embedding 架构注册（`CLIPEmbeddingModel`/`SiglipEmbeddingModel`） |
| 扩散生成 | `diffusion_gemma/cosmos3` | 需要 `DiffusionConfig`（VllmConfig 子配置，`vllm/config/vllm.py`）；block diffusion 逐块并行解码 |

### 与 19 模块的分工

19-model-definitions 已覆盖注册机制、协议族、`interfaces_base`、`utils`/`adapters` 以及 llama/qwen2/3/deepseek_v2/gpt2/glm4/phi3/mamba/jamba/kimi 等 12+ 代表架构的**实现细节**；本文（30）在家族维度补全：全量注册清单（registry 字典分组）、各族代表文件的复用关系、`transformers/` 后端与 fusers 机制、以及投机解码/MTP/MLA 变体等特殊模型类型。两文互补，共同构成 models/ 目录的完整地图。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
