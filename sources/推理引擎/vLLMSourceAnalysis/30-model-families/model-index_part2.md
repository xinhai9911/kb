## 模型索引表（二）：SSM / Hybrid / Vision / Audio

本文承接 [model-index_part1.md](model-index_part1.md)。
### ④ SSM/Mamba

| 文件 | 架构类（architecture） |
|---|---|
| mamba.py | MambaModel,MambaForCausalLM |
| mamba2.py | Mamba2Model,Mamba2ForCausalLM |

### ⑤ 混合架构 Hybrid

| 文件 | 架构类（architecture） |
|---|---|
| granitemoehybrid.py | GraniteMoeHybridModel,GraniteMoeHybridForCausalLM |
| jamba.py | JambaModel,JambaForCausalLM,JambaForSequenceClassification |
| olmo_hybrid.py | OlmoHybridModel,OlmoHybridForCausalLM |
| zamba2.py | Zamba2Model,Zamba2ForCausalLM |

### ⑥ Vision 多模态

| 文件 | 架构类（architecture） |
|---|---|
| aimv2.py | AIMv2Model |
| blip.py | BlipEncoder,BlipVisionModel |
| blip2.py | Blip2QFormerEncoder,Blip2QFormerModel,Blip2ForConditionalGeneration |
| chameleon.py | ChameleonVQVAEEncoder,ChameleonModel,ChameleonForConditionalGeneration |
| cohere2_vision.py | Cohere2VisionForConditionalGeneration |
| deepseek_vl2.py | DeepseekVLV2ForCausalLM |
| ernie45_vl.py | VariableResolutionResamplerModel,Ernie4_5_VLMoeForConditionalGeneration |
| ernie45_vl_moe.py | Ernie4_5_VLMoeModel,Ernie4_5_VLMoeForCausalLM |
| gemma3_mm.py | Gemma3ForConditionalGeneration |
| gemma4_mm.py | Gemma4ForConditionalGeneration |
| glm4v.py | EVA2CLIPModel,GLM4VModel,GLM4VForCausalLM |
| granite4_vision.py | Granite4VisionLLMModel,Granite4VisionLLMForCausalLM,Granite4VisionForConditionalGeneration |
| h2ovl.py | H2OVLChatModel |
| hunyuan_vision.py | HunYuanVLForConditionalGeneration |
| hyperclovax_vision.py | HCXVisionForCausalLM |
| hyperclovax_vision_v2.py | HCXVisionV2ForCausalLM |
| idefics2_vision_model.py | Idefics2Encoder |
| idefics3.py | Idefics3Model,Idefics3ForConditionalGeneration |
| intern_vit.py | InternVisionPatchModel,InternVisionEncoder,InternVisionModel |
| interns1_vit.py | InternS1VisionEncoder,InternS1VisionModel |
| internvl.py | InternVLChatModel |
| keye_vl1_5.py | KeyeVL1_5ForConditionalGeneration |
| kimi_k25_vit.py | MoonViT3dEncoder,MoonViT3dPretrainedModel |
| kimi_vl.py | KimiVLForConditionalGeneration |
| lfm2_vl.py | Lfm2VLForConditionalGeneration |
| llava.py | LlavaForConditionalGeneration |
| llava_next.py | LlavaNextForConditionalGeneration |
| llava_next_video.py | LlavaNextVideoForConditionalGeneration |
| llava_onevision.py | LlavaOnevisionForConditionalGeneration |
| llava_onevision2.py | LlavaOnevision2ForConditionalGeneration |
| minicpmv.py | MiniCPMVBaseModel |
| minicpmv4_6.py | MiniCPMV4_6ForConditionalGeneration |
| mistral3.py | Mistral3ForConditionalGeneration |
| molmo.py | MolmoModel,MolmoForCausalLM |
| molmo2.py | Molmo2TextModel,Molmo2ForConditionalGeneration |
| moonvit.py | MoonVitEncoder,MoonVitPretrainedModel |
| nemotron_vl.py | LlamaNemotronVLChatModel,LlamaNemotronVLForSequenceClassification |
| nvlm_d.py | NVLM_D_Model |
| openpangu_vl.py | OpenPanguVLForConditionalGeneration |
| paligemma.py | PaliGemmaForConditionalGeneration |
| phi3v.py | Phi3VForCausalLM |
| pixtral.py | PixtralForConditionalGeneration,PixtralHFVisionModel |
| qwen2_5_vl.py | Qwen2_5_VLForConditionalGeneration |
| qwen2_vl.py | Qwen2VLForConditionalGeneration |
| qwen3_vl.py | Qwen3LLMModel,Qwen3LLMForCausalLM,Qwen3VLForConditionalGeneration |
| qwen3_vl_moe.py | Qwen3MoeLLMModel,Qwen3MoeLLMForCausalLM,Qwen3VLMoeForConditionalGeneration |
| rvl.py | RForConditionalGeneration |
| smolvlm.py | SmolVLMForConditionalGeneration |
| step3_vl.py | Step3VisionEncoder,Step3VLForConditionalGeneration |
| step_vl.py | PerceptionEncoder,StepVLForConditionalGeneration |

### ⑦ 音频/Omni 多模态

| 文件 | 架构类（architecture） |
|---|---|
| audioflamingo3.py | AudioFlamingo3Encoder,AudioFlamingo3ForConditionalGeneration |
| cohere_asr.py | ConformerEncoder,CohereASRModel,CohereAsrForConditionalGeneration |
| fireredasr2.py | FireRedASR2Encoder,FireRedASR2Model,FireRedASR2ForConditionalGeneration |
| funasr.py | SinusoidalPositionEncoder,FunASREncoder,FunASRModel,FunASRForConditionalGeneration |
| funaudiochat.py | FunAudioChatAudioEncoder,FunAudioChatDiscreteEncoder,FunAudioChatForConditionalGeneration |
| glmasr.py | GlmAsrEncoder,GlmAsrForConditionalGeneration |
| granite_speech.py | GraniteSpeechCTCEncoder,GraniteSpeechForConditionalGeneration |
| granite_speech_plus.py | GraniteSpeechPlusCTCEncoder,GraniteSpeechPlusForConditionalGeneration |
| kimi_audio.py | KimiAudioWhisperEncoder,KimiAudioForConditionalGeneration |
| mimo_audio.py | AudioEncoder,MimoAudioEncoder |
| mimo_v2_omni.py | MiMoV2OmniForCausalLM |
| moss_audio.py | MossAudioEncoder,MossQwen3Model,MossQwen3ForCausalLM,MossAudioModel |
| moss_transcribe_diarize.py | MossTranscribeDiarizeWhisperEncoder,MossTranscribeDiarizeForConditionalGeneration |
| qwen2_5_omni_thinker.py | Qwen2_5OmniThinkerForConditionalGeneration |
| qwen2_audio.py | Qwen2AudioForConditionalGeneration |
| qwen3_asr.py | Qwen3ASRForConditionalGeneration |
| qwen3_asr_forced_aligner.py | Qwen3ASRForcedAlignerForTokenClassification |
| qwen3_omni_moe_thinker.py | Qwen3OmniMoeAudioEncoder,Qwen3MoeLLMModel,Qwen3MoeLLMForCausalLM,Qwen3OmniMoeThinkerForConditionalGeneration |
| ultravox.py | UltravoxWhisperEncoder,UltravoxModel |
| voxtral.py | VoxtralForConditionalGeneration,VoxtralEncoderModel |
| whisper.py | WhisperEncoder,WhisperModel,WhisperForConditionalGeneration |
| whisper_causal.py | WhisperCausalEncoder |


> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
