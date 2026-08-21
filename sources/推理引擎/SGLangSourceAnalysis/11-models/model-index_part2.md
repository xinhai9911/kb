## 模型索引表（二）：多模态 / 任务特化 / 投机解码 / 组件文件

承接 [model-index_part1.md](model-index_part1.md) 的 ② 文本 MoE 之后的全部注册文件（96 个）与 21 个不注册组件文件。

### ③ 多模态（VLM / OCR / Audio / ASR / Omni）

| 文件 | 架构类（architecture） |
|---|---|
| clip.py | CLIPModel |
| cohere2_vision.py | Cohere2VisionForConditionalGeneration |
| deepseek_janus_pro.py | MultiModalityCausalLM |
| deepseek_ocr.py | DeepseekOCRForCausalLM |
| deepseek_vl2.py | DeepseekVL2ForCausalLM |
| dots_ocr.py | DotsOCRForCausalLM |
| dots_vlm.py | DotsVLMForCausalLM |
| ernie45_vl.py | Ernie4_5_VLMoeForConditionalGeneration |
| gemma3_mm.py | Gemma3ForConditionalGeneration |
| gemma3n_mm.py | Gemma3nForConditionalGeneration |
| gemma4_mm.py | Gemma4ForConditionalGeneration |
| gemma4_unified.py | Gemma4UnifiedForConditionalGeneration |
| glm4v.py | Glm4vForConditionalGeneration |
| glm4v_moe.py | Glm4vMoeForConditionalGeneration |
| glm_image_vl.py | GlmImageForConditionalGeneration |
| glm_ocr.py | GlmOcrForConditionalGeneration |
| glmasr.py | GlmAsrForConditionalGeneration |
| internvl.py | InternVLChatModel |
| jet_vlm.py | JetVLMForConditionalGeneration |
| kimi_vl.py | KimiVLForConditionalGeneration |
| lfm2_vl.py | Lfm2VlForConditionalGeneration |
| lightonocr.py | LightOnOCRForConditionalGeneration |
| llava.py | LlavaLlamaForCausalLM,LlavaQwenForCausalLM,LlavaMistralForCausalLM,LlavaForConditionalGeneration |
| llavavid.py | LlavaVidForCausalLM |
| locate_anything.py | LocateAnythingForConditionalGeneration |
| minicpmo.py | MiniCPMO |
| minicpmv.py | MiniCPMV,MiniCPMV4_6ForConditionalGeneration |
| minimax_m3_vl.py | MiniMaxM3SparseForConditionalGeneration |
| mllama.py | MllamaForConditionalGeneration |
| mllama4.py | Llama4ForConditionalGeneration |
| moss_vl.py | MossVLForConditionalGeneration |
| muse_glimmer.py | MuseGlimmerForCausalLM,MuseGlimmerForConditionalGeneration |
| nano_nemotron_vl.py | NemotronH_Nano_VL_V2,NemotronH_Nano_Omni_Reasoning_V3 |
| nvila.py | NVILAForConditionalGeneration |
| nvila_lite.py | NVILALiteForConditionalGeneration |
| paddleocr_vl.py | PaddleOCRVLForConditionalGeneration |
| phi4mm.py | Phi4MMForCausalLM |
| pixtral.py | PixtralForConditionalGeneration,PixtralVisionModel |
| points_v15_chat.py | POINTSV15ChatModel |
| qwen2_5_vl.py | Qwen2_5_VLForConditionalGeneration |
| qwen2_vl.py | Qwen2VLForConditionalGeneration |
| qwen2_audio.py | Qwen2AudioForConditionalGeneration |
| qwen3_5.py | Qwen3_5MoeForConditionalGeneration,Qwen3_5ForConditionalGeneration |
| qwen3_asr.py | Qwen3ASRForConditionalGeneration |
| qwen3_omni_moe.py | Qwen3OmniMoeForConditionalGeneration |
| qwen3_vl.py | Qwen3VLForConditionalGeneration |
| qwen3_vl_moe.py | Qwen3VLMoeForConditionalGeneration |
| sarashina2_vision.py | Sarashina2VisionForCausalLM |
| step3_vl.py | Step3VLForConditionalGeneration |
| step3_vl_10b.py | StepVLForConditionalGeneration |
| unlimited_ocr.py | UnlimitedOCRForCausalLM |
| voxtral.py | VoxtralForConditionalGeneration |
| whisper.py | WhisperForConditionalGeneration |
| yivl.py | YiVLForCausalLM |
| mimo_v2_asr.py | MiMoV2ASRForCausalLM |

### ④ 任务特化（Embedding / Reward / Classification）

| 文件 | 架构类（architecture） |
|---|---|
| bert.py | BertModel,Contriever,BertForSequenceClassification |
| gemma2_reward.py | Gemma2ForSequenceClassification |
| internlm2_reward.py | InternLM2ForRewardModel |
| llama_classification.py | LlamaForClassification |
| llama_embedding.py | LlamaEmbeddingModel,MistralModel |
| llama_reward.py | LlamaForSequenceClassification,LlamaForSequenceClassificationWithNormal_Weights |
| qwen2_classification.py | Qwen2ForSequenceClassification |
| qwen2_rm.py | Qwen2ForRewardModel |
| qwen3_classification.py | Qwen3ForSequenceClassification |
| qwen3_embedding.py | Qwen3Model |
| qwen3_rm.py | Qwen3ForRewardModel |
| roberta.py | XLMRobertaModel,XLMRobertaForSequenceClassification |

### ⑤ 投机解码（EAGLE / MTP / NextN / Draft）与原生解码

| 文件 | 架构类（architecture） |
|---|---|
| bailing_moe_nextn.py | BailingMoeForCausalLMNextN |
| deepseek_nextn.py | DeepseekV3ForCausalLMNextN |
| deepseek_v4_nextn.py | DeepseekV4ForCausalLMNextN |
| deepseek_v4_dspark.py | DeepseekV4ForCausalLMDSpark |
| dflash.py | DFlashDraftModel,DFlashLagunaForCausalLM,MuseGlimmerAssistantModel,DFlash2DraftModel |
| dspark.py | Qwen3DSparkModel,DSparkDraftModel |
| ernie4_eagle.py | Ernie4_5_MoeForCausalLMMTP |
| exaone_moe_mtp.py | ExaoneMoEForCausalLMMTP |
| gemma4_mtp.py | Gemma4AssistantForCausalLM,Gemma4UnifiedAssistantForCausalLM |
| glm4_moe_lite_nextn.py | Glm4MoeLiteForCausalLMNextN |
| glm4_moe_nextn.py | Glm4MoeForCausalLMNextN |
| glm_ocr_nextn.py | GlmOcrForConditionalGenerationNextN |
| hunyuan_v3_nextn.py | HYV3ForCausalLMNextN |
| kimi_k25_eagle3.py | Eagle3DeepseekV2ForCausalLM |
| llama_eagle.py | LlamaForCausalLMEagle |
| llama_eagle3.py | LlamaForCausalLMEagle3 |
| longcat_flash_nextn.py | LongcatFlashForCausalLMNextN |
| mimo_mtp.py | MiMoMTP |
| mimo_v2_nextn.py | MiMoV2MTP |
| mistral_eagle.py | MistralForCausalLMEagle |
| mistral_large_3_eagle.py | MistralLarge3ForCausalLMEagle |
| nemotron_h_mtp.py | NemotronHForCausalLMMTP |
| qwen2_eagle.py | Qwen2ForCausalLMEagle |
| qwen3_moe_mtp.py | Qwen3MoeForCausalLMMTP |
| qwen3_next_mtp.py | Qwen3NextForCausalLMMTP |
| qwen3_5_mtp.py | Qwen3_5ForCausalLMMTP |
| step3p5_mtp.py | Step3p5MTP |
| torch_native_llama.py | TorchNativeLlamaForCausalLM,TorchNativePhi3ForCausalLM |

### ⑥ Transformers 后端回退

| 文件 | 架构类（architecture） |
|---|---|
| transformers.py | TransformersForCausalLM,TransformersMoEForCausalLM,TransformersMultiModalForCausalLM,TransformersMultiModalMoEForCausalLM,TransformersEmbeddingModel,TransformersMoEEmbeddingModel,TransformersMultiModalEmbeddingModel,TransformersMultiModalMoEEmbeddingModel,TransformersForSequenceClassification,TransformersMoEForSequenceClassification,TransformersMultiModalForSequenceClassification,TransformersMultiModalMoEForSequenceClassification |

### ⑦ 组件文件（无 EntryClass，不注册，被 ①-⑥ import 引用）

| 文件 | 用途 |
|---|---|
| siglip.py / siglip2.py / clip 系 | SigLIP 视觉编码器（Qwen2.5-VL、Gemma3 等复用） |
| parakeet.py / gemma3n_audio.py / gemma4_audio.py / mimo_audio.py / phi4mm_audio.py | 音频编码器 |
| idefics2.py / minicpmv_vit.py / gemma4_vision.py / dots_vlm_vit.py / kimi_vl_moonvit.py / minimax_vl_common.py | 视觉塔组件 |
| ernie45_moe_vl.py / kimi_k3_vl.py / mimo_vl.py | 多模态组件（被对应主文件引用） |
| nemotron_h_utils.py / phi4mm_utils.py / utils.py | 权重映射 / 工具函数 |
| radio.py | Radio 视觉编码器组件 |
| registry.py | 注册表本身（见 model-registry.md） |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
