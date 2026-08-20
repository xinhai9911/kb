## 模型索引表（一）：Dense / MoE / MLA

本文为 `vllm/model_executor/models/` 全量模型文件 → 架构类（architecture）→ 家族索引（共 268 个模型文件），与 [model-family-taxonomy.md](model-family-taxonomy.md)、[model-registry.md](../19-model-definitions/model-registry.md) 配套。架构类即 HF `architectures` 中的字符串，注册/选中链见 19 模块；家族关键特性见 30 模块分类表。
### ① 文本 Dense

| 文件 | 架构类（architecture） |
|---|---|
| AXK1.py | AXK1Model,AXK1ForCausalLM |
| apertus.py | ApertusModel,ApertusForCausalLM |
| arcee.py | ArceeModel,ArceeForCausalLM |
| arctic.py | ArcticModel,ArcticForCausalLM |
| aria.py | AriaTextModel,AriaForConditionalGeneration |
| bagel.py | BagelForConditionalGeneration |
| bee.py | BeeForConditionalGeneration |
| bloom.py | BloomModel,BloomForCausalLM |
| chatglm.py | ChatGLMModel,ChatGLMBaseModel,ChatGLMForCausalLM |
| cheers.py | CheersVAEEncoder,CheersVAEModel,CheersForConditionalGeneration |
| commandr.py | CohereModel,CohereForCausalLM |
| config.py | DeepseekV32ForCausalLM |
| conformer_encoder.py | ConformerEncoder |
| deepencoder2.py | Qwen2Decoder2Encoder |
| ernie45.py | Ernie4_5ForCausalLM |
| exaone.py | ExaoneModel,ExaoneForCausalLM |
| exaone4.py | Exaone4Model,Exaone4ForCausalLM |
| exaone4_5.py | Exaone4_5_ForConditionalGeneration |
| extract_hidden_states.py | ExtractHiddenStatesModel |
| fairseq2_llama.py | Fairseq2LlamaForCausalLM |
| falcon.py | FalconModel,FalconForCausalLM |
| falcon_h1.py | FalconH1Model,FalconH1ForCausalLM |
| fireredlid.py | FireRedLIDModel,FireRedLIDForConditionalGeneration |
| flex_olmo.py | FlexOlmoForCausalLM |
| gemma.py | GemmaModel,GemmaForCausalLM |
| gemma2.py | Gemma2Model,Gemma2ForCausalLM |
| gemma3.py | Gemma3Model,Gemma3ForCausalLM |
| gemma4.py | Gemma4Model,Gemma4ForCausalLM |
| glm.py | GlmForCausalLM |
| glm4.py | Glm4Model,Glm4ForCausalLM |
| glm4_1v.py | Glm4vForConditionalGeneration,Glm4vMoeForConditionalGeneration |
| gpt2.py | GPT2Model,GPT2LMHeadModel,GPT2ForSequenceClassification |
| gpt_j.py | GPTJModel,GPTJForCausalLM |
| gpt_neox.py | GPTNeoXModel,GPTNeoXForCausalLM |
| granite.py | GraniteModel,GraniteForCausalLM |
| hrm_text.py | HrmTextModel,HrmTextForCausalLM |
| hyperclovax.py | HyperCLOVAXModel,HyperCLOVAXForCausalLM |
| interfaces_base.py | VllmModel |
| internlm2.py | InternLM2Model,InternLM2ForCausalLM,InternLM2ForRewardModel |
| interns1.py | InternS1ForConditionalGeneration |
| interns1_pro.py | InternS1ProMoeLLMModel,InternS1ProMoeLLMForCausalLM,InternS1ProForConditionalGeneration |
| interns2_mobius.py | InternS2MobiusModel,InternS2MobiusForCausalLM,InternS2MobiusMTP,InternS2MobiusForConditionalGeneration |
| interns2_preview.py | InternS2PreviewForConditionalGeneration |
| iquest_loopcoder.py | IQuestLoopCoderModel,IQuestLoopCoderForCausalLM |
| isaac.py | Siglip2Encoder,IsaacForConditionalGeneration |
| jais2.py | Jais2Model,Jais2ForCausalLM |
| kanana_v.py | KananaVForConditionalGeneration |
| keye.py | KeyeSiglipEncoder,KeyeSiglipVisionModel,KeyeForConditionalGeneration |
| kimi_k25.py | KimiK25ForConditionalGeneration |
| lfm2.py | Lfm2Model,Lfm2ForCausalLM |
| llama.py | LlamaModel,LlamaForCausalLM,LlamaBidirectionalForSequenceClassification,LlamaBidirectionalModel |
| llama4.py | Llama4Model,Llama4ForCausalLM |
| mellum.py | MellumModel,MellumForCausalLM |
| midashenglm.py | MiDashengLMModel |
| mimo.py | MiMoModel,MiMoForCausalLM |
| mimo_v2.py | MiMoV2Model,MiMoV2FlashForCausalLM,MiMoV2ForCausalLM |
| minicpm.py | MiniCPMModel,MiniCPMForCausalLM |
| minicpm3.py | MiniCPM3Model,MiniCPM3ForCausalLM |
| minicpmo.py | MiniCPMWhisperEncoder,MiniCPMOBaseModel |
| minimax_m2.py | MiniMaxM2Model,MiniMaxM2ForCausalLM |
| mistral.py | MistralModel,MistralForCausalLM |
| mistral_large_3.py | MistralLarge3ForCausalLM |
| mllama4.py | Llama4VisionEncoder,Llama4VisionModel,Llama4ForConditionalGeneration |
| moondream3.py | Moondream3VisionEncoder,Moondream3TextModel,Moondream3ForCausalLM |
| mpt.py | MPTModel,MPTForCausalLM |
| muse_glimmer.py | MuseGlimmerVisionEncoder,MuseGlimmerModel,MuseGlimmerForCausalLM |
| nemotron.py | NemotronModel,NemotronForCausalLM |
| nemotron_nas.py | DeciModel,DeciLMForCausalLM |
| olmo3.py | Olmo3Model,Olmo3ForCausalLM |
| openai_privacy_filter.py | OpenAIPrivacyFilterModel,OpenAIPrivacyFilterForTokenClassification |
| opencua.py | OpenCUAForConditionalGeneration |
| opt.py | OPTModel,OPTForCausalLM |
| orion.py | OrionModel,OrionForCausalLM |
| phi.py | PhiModel,PhiForCausalLM |
| phi3.py | Phi3ForCausalLM |
| plamo3.py | Plamo3Model,Plamo3ForCausalLM |
| qwen2.py | Qwen2Model,Qwen2ForCausalLM |
| qwen3.py | Qwen3Model,Qwen3ForCausalLM |
| qwen3_next.py | Qwen3NextModel,Qwen3NextForCausalLM |
| radio.py | RadioVisionEncoder,RadioInternVisionModel,RadioModel |
| registry.py | _BaseRegisteredModel,_RegisteredModel,_LazyRegisteredModel |
| rnj1.py | Rnj1Model,Rnj1ForCausalLM |
| skyworkr1v.py | SkyworkR1VChatModel |
| solar.py | SolarModel,SolarForCausalLM |
| stablelm.py | StableLMEpochModel,StablelmForCausalLM |
| step1.py | StepDecoderModel,Step1ForCausalLM |
| step3_text.py | Step3TextModel,Step3TextForCausalLM |
| step3p5.py | Step3p5Model,Step3p5ForCausalLM |
| step3p7.py | Step3p7ForConditionalGeneration |
| telechat2.py | TeleChat2Model,TeleChat2ForCausalLM |
| teleflm.py | TeleFLMModel,TeleFLMForCausalLM |
| voyage.py | VoyageQwen3BidirectionalEmbedModel |

### ② MoE

| 文件 | 架构类（architecture） |
|---|---|
| afmoe.py | AfmoeModel,AfmoeForCausalLM |
| bailing_moe.py | BailingMoeModel,BailingMoeForCausalLM,BailingMoeV2ForCausalLM |
| bailing_moe_linear.py | BailingMoeV25Model,BailingMoeV25ForCausalLM |
| bailing_moe_v3.py | BailingMoeV3Model,BailingMoeV3ForCausalLM |
| cohere2_moe.py | Cohere2MoeModel,Cohere2MoeForCausalLM |
| dbrx.py | DbrxModel,DbrxForCausalLM |
| ernie45_moe.py | Ernie4_5_MoeModel,Ernie4_5_MoeForCausalLM |
| exaone_moe.py | ExaoneMoeModel,ExaoneMoeForCausalLM |
| glm4_moe.py | Glm4MoeModel,Glm4MoeForCausalLM |
| glm4_moe_lite.py | Glm4MoeLiteModel,Glm4MoeLiteForCausalLM |
| gpt_oss.py | GptOssModel,GptOssForCausalLM |
| granitemoe.py | GraniteMoeModel,GraniteMoeForCausalLM |
| granitemoeshared.py | GraniteMoeSharedModel,GraniteMoeSharedForCausalLM |
| hunyuan_v1.py | HunYuanModel,HunYuanDenseV1ForCausalLM,HunYuanMoEV1ForCausalLM |
| lfm2_moe.py | Lfm2MoeModel,Lfm2MoeForCausalLM |
| mixtral.py | MixtralModel,MixtralForCausalLM |
| nemotron_h.py | NemotronHModel,NemotronHForCausalLM |
| olmoe.py | OlmoeModel,OlmoeForCausalLM |
| openpangu.py | OpenPanguModel,OpenPanguMoEModel,OpenPanguEmbeddedModel,PanguEmbeddedForCausalLM,PanguUltraMoEForCausalLM,PanguProMoEV2ForCausalLM |
| param2moe.py | Param2MoEModel,Param2MoEForCausalLM |
| phimoe.py | PhiMoEModel,PhiMoEForCausalLM |
| qwen2_moe.py | Qwen2MoeModel,Qwen2MoeForCausalLM |
| qwen3_moe.py | Qwen3MoeModel,Qwen3MoeForCausalLM |
| seed_oss.py | SeedOssModel,SeedOssForCausalLM |

### ③ MLA/混合线性

| 文件 | 架构类（architecture） |
|---|---|
| deepseek_v2.py | DeepseekV2Model,DeepseekV2ForCausalLM,DeepseekForCausalLM,DeepseekV3ForCausalLM,GlmMoeDsaForCausalLM |
| hy_v3.py | HYV3Model,HYV3ForCausalLM |
| laguna.py | LagunaModel,LagunaForCausalLM |
| longcat_flash.py | FlashModel,LongcatFlashForCausalLM |
| longcat_flash_ngram.py | FlashNgramModel,LongcatFlashNgramForCausalLM |
| qwen3_5.py | Qwen3_5Model,Qwen3_5ForCausalLM,Qwen3_5MoeForCausalLM,Qwen3_5ForConditionalGeneration,Qwen3_5MoeForConditionalGeneration |
| sarvam.py | SarvamMLAModel,SarvamMLAForCausalLM,SarvamMoEForCausalLM |


> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
