## 模型索引表（三）：OCR / Embedding / 投机解码 / MTMD

本文承接 [model-index_part1.md](model-index_part1.md)。
### ⑧ OCR/文档理解

| 文件 | 架构类（architecture） |
|---|---|
| deepseek_ocr.py | DeepseekOCRForCausalLM |
| deepseek_ocr2.py | DeepseekOCR2ForCausalLM |
| dots_ocr.py | DotsOCRForCausalLM |
| glm_ocr.py | GlmOcrForConditionalGeneration |
| lightonocr.py | LightOnOCRForConditionalGeneration |
| nemotron_parse.py | NemotronParseForConditionalGeneration |
| paddleocr_vl.py | SiglipEncoder,SiglipVisionModel,PaddleOCRVLForConditionalGeneration |
| phi4mm.py | Phi4MMImageEncoder,Phi4MMForCausalLM |
| phi4mm_audio.py | ConformerEncoder |
| qianfan_ocr.py | QianfanOCRForConditionalGeneration |
| unlimited_ocr.py | UnlimitedOCRForCausalLM |

### ⑨ Embedding/池化/检索

| 文件 | 架构类（architecture） |
|---|---|
| bert.py | BertEncoder,BertModel,BertPoolingModel,BertEmbeddingModel,BertSpladeSparseEmbeddingModel,BertForSequenceClassification,BertForTokenClassification |
| bert_with_rope.py | BertWithRopeEncoder,NomicBertModel,GteNewModel,SnowflakeGteNewModel,JinaRobertaModel,GteNewForSequenceClassification |
| clip.py | CLIPEncoder,CLIPVisionModel,CLIPEmbeddingModel |
| colbert.py | ColBERTModel,ColBERTModernBertModel,ColBERTJinaRobertaModel,ColBERTLfm2Model |
| colmodernvbert.py | ColModernVBertForRetrieval |
| colpali.py | ColPaliModel |
| colqwen3.py | ColQwen3Model |
| colqwen3_5.py | ColQwen3_5Model |
| jina.py | JinaEmbeddingsV5DecoderModel,JinaEmbeddingsV5EncoderModel,JinaEmbeddingsV5Model |
| jina_vl.py | JinaVLForSequenceClassification |
| lfm2_siglip2.py | Siglip2Encoder,Siglip2Model |
| modernbert.py | ModernBertModel,ModernBertForSequenceClassification,ModernBertForTokenClassification |
| qwen2_rm.py | Qwen2RewardBaseModel,Qwen2ForRewardModel,Qwen2ForProcessRewardModel |
| roberta.py | RobertaEmbeddingModel,BgeM3EmbeddingModel,RobertaForSequenceClassification,RobertaForTokenClassification |
| siglip.py | SiglipEncoder,SiglipVisionModel,SiglipEmbeddingModel |
| siglip2navit.py | Siglip2Encoder,Siglip2NavitModel |

### ⑩ 投机解码/草稿

| 文件 | 架构类（architecture） |
|---|---|
| bailing_moe_mtp.py | BailingMoeV25MTPModel |
| bailing_moe_v3_mtp.py | BailingMoeV3MTPModel |
| cohere_eagle.py | CohereEagleModel,EagleCohereForCausalLM |
| deepseek_eagle.py | DeepseekV2Model,EagleDeepseekV3ForCausalLM |
| deepseek_eagle3.py | DeepseekV2Eagle3Model,Eagle3DeepseekV2ForCausalLM |
| deepseek_mtp.py | DeepSeekMTP |
| eagle2_5_vl.py | Eagle2_5_VLForConditionalGeneration |
| ernie_mtp.py | ErnieMTP |
| exaone4_5_mtp.py | Exaone4_5_MTP |
| exaone_moe_mtp.py | ExaoneMoeMTP |
| gemma4_dspark.py | Gemma4DSparkModel,Gemma4DSparkForCausalLM |
| gemma4_mtp.py | Gemma4MTP |
| glm4_moe_lite_mtp.py | Glm4MoeLiteMTP |
| glm4_moe_mtp.py | Glm4MoeMTP |
| glm_ocr_mtp.py | GlmOcrMTP |
| hy_v3_mtp.py | HYV3MTP |
| laguna_dflash.py | DFlashLagunaModel,DFlashLagunaForCausalLM |
| llama4_eagle.py | LlamaModel,EagleLlama4ForCausalLM |
| llama_eagle.py | LlamaModel,EagleLlamaForCausalLM |
| llama_eagle3.py | LlamaModel,Eagle3LlamaForCausalLM |
| longcat_flash_mtp.py | LongCatFlashMTP |
| mimo_mtp.py | MiMoMTP |
| mimo_v2_mtp.py | MiMoV2MTP,MiMoV2OmniMTP |
| minicpm_eagle.py | EagleMiniCPMModel,EagleMiniCPMForCausalLM |
| mistral_eagle.py | EagleMistralModel,EagleMistralForCausalLM |
| mistral_large_3_eagle.py | EagleMistralLarge3Model,EagleMistralLarge3ForCausalLM |
| nemotron_h_mtp.py | NemotronHMTP |
| openpangu_mtp.py | OpenPanguMTP |
| qwen3_5_mtp.py | Qwen3_5MTP,Qwen3_5MoeMTP |
| qwen3_dflash.py | DFlashQwen3Model,DFlashQwen3ForCausalLM |
| qwen3_dspark.py | Qwen3DSparkModel,Qwen3DSparkForCausalLM |
| qwen3_eagle3.py | Qwen3Eagle3Model,Eagle3Qwen3ForCausalLM |
| qwen3_next_mtp.py | Qwen3NextMTP |
| step3p5_mtp.py | Step3p5MTP |

### ⑪ MTMD/扩散

| 文件 | 架构类（architecture） |
|---|---|
| cosmos3.py | Cosmos3ForConditionalGeneration |
| cosmos3_edge.py | Cosmos3EdgeVisionEncoder,Cosmos3EdgeVisionModel,Cosmos3EdgeTextModel,Cosmos3EdgeForCausalLM,Cosmos3EdgeForConditionalGeneration |
| diffusion_gemma.py | DiffusionGemmaForConditionalGeneration |
| gemma3n.py | Gemma3nTextModel,Gemma3nForCausalLM |
| gemma3n_mm.py | Gemma3nForConditionalGeneration |
| gemma4_unified.py | Gemma4UnifiedForConditionalGeneration |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
