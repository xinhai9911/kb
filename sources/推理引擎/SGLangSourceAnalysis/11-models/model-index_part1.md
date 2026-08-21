## 模型索引表（一）：文本 Dense / MoE·MLA

本文为 `sglang/srt/models/` 全量模型文件 → 架构类（architecture）→ 家族索引，与 [model-registry.md](model-registry.md)、[representative-models.md](representative-models.md) 配套。架构类即 HF `architectures` 中的字符串，由模块级 `EntryClass` 注册（`registry.py` 扫描 `hasattr(module, "EntryClass")`）。全仓 216 个顶层 `.py`：195 个注册文件共 246 个唯一架构类，21 个组件文件不注册（见 part2）。

### ① 文本 Dense

| 文件 | 架构类（architecture） |
|---|---|
| apertus.py | ApertusForCausalLM |
| arcee.py | ArceeForCausalLM |
| baichuan.py | BaichuanForCausalLM |
| chatglm.py | ChatGLMModel |
| commandr.py | CohereForCausalLM,Cohere2ForCausalLM |
| deepseek.py | DeepseekForCausalLM |
| exaone.py | ExaoneForCausalLM |
| exaone4.py | Exaone4ForCausalLM |
| falcon_h1.py | FalconH1ForCausalLM |
| gemma.py | GemmaForCausalLM |
| gemma2.py | Gemma2ForCausalLM |
| gemma3_causal.py | Gemma3ForCausalLM,EmbeddingGemmaModel |
| gemma3n_causal.py | Gemma3nForCausalLM |
| gemma4_causal.py | Gemma4ForCausalLM |
| glm4.py | Glm4ForCausalLM |
| gpt2.py | GPT2LMHeadModel |
| gpt_bigcode.py | GPTBigCodeForCausalLM |
| gpt_j.py | GPTJForCausalLM |
| granite.py | GraniteForCausalLM |
| grok.py | Grok1ForCausalLM,Grok1ModelForCausalLM |
| hrm_text.py | HrmTextForCausalLM |
| internlm2.py | InternLM2ForCausalLM |
| iquest_loopcoder.py | IQuestLoopCoderForCausalLM |
| jet_nemotron.py | JetNemotronForCausalLM |
| kimi_linear.py | KimiLinearForCausalLM |
| lfm2.py | Lfm2ForCausalLM,Lfm2BidirectionalModel |
| llama.py | LlamaForCausalLM,Phi3ForCausalLM,InternLM3ForCausalLM,IQuestCoderForCausalLM |
| llama4.py | Llama4ForCausalLM |
| longcat_flash.py | LongcatFlashForCausalLM |
| mellum.py | MellumForCausalLM |
| midashenglm.py | MiDashengLMModel |
| mimo.py | MiMoForCausalLM |
| mimo_v2.py | MiMoV2ForCausalLM,MiMoV2FlashForCausalLM |
| minicpm.py | MiniCPMForCausalLM |
| minicpm3.py | MiniCPM3ForCausalLM |
| minimax_m2.py | MiniMaxM2ForCausalLM |
| mindspore.py | MindSporeForCausalLM |
| ministral3.py | Ministral3ForCausalLM |
| mistral.py | MistralForCausalLM |
| mistral.py | Mistral3ForConditionalGeneration |
| mistral_large_3.py | MistralLarge3ForCausalLM |
| nemotron_h.py | NemotronHForCausalLM,NemotronHPuzzleForCausalLM |
| nemotron_nas.py | DeciLMForCausalLM |
| olmo.py | OlmoForCausalLM |
| olmo2.py | Olmo2ForCausalLM |
| opt.py | OPTForCausalLM |
| orion.py | OrionForCausalLM |
| persimmon.py | PersimmonForCausalLM |
| phi.py | PhiForCausalLM |
| phi3_small.py | Phi3SmallForCausalLM |
| qwen.py | QWenLMHeadModel |
| qwen2.py | Qwen2ForCausalLM |
| qwen3.py | Qwen3ForCausalLM |
| qwen3_next.py | Qwen3NextForCausalLM |
| solar.py | SolarForCausalLM |
| stablelm.py | StableLmForCausalLM |
| starcoder2.py | Starcoder2ForCausalLM |
| teleflm.py | TeleFLMForCausalLM |
| xverse.py | XverseForCausalLM |
| zaya.py | ZayaForCausalLM |

### ② 文本 MoE / MLA / 稀疏·混合

| 文件 | 架构类（architecture） |
|---|---|
| afmoe.py | AfmoeForCausalLM |
| bailing_moe.py | BailingMoEForCausalLM,BailingMoeForCausalLM,BailingMoeV2ForCausalLM |
| bailing_moe_linear.py | BailingMoeV2_5ForCausalLM |
| cohere2_moe.py | Cohere2MoeForCausalLM |
| dbrx.py | DbrxForCausalLM |
| deepseek_v2.py | DeepseekV2ForCausalLM,DeepseekV3ForCausalLM,DeepseekV32ForCausalLM |
| deepseek_v4.py | DeepseekV4ForCausalLM |
| ernie4.py | Ernie4_5_MoeForCausalLM,Ernie4_5_ForCausalLM |
| exaone_moe.py | ExaoneMoEForCausalLM |
| glm4_moe.py | Glm4MoeForCausalLM,GlmMoeDsaForCausalLM,GlmMoeDsaForCausalLMNextN |
| glm4_moe_lite.py | Glm4MoeLiteForCausalLM |
| gpt_oss.py | GptOssForCausalLM |
| granitemoe.py | GraniteMoeForCausalLM |
| granitemoehybrid.py | GraniteMoeHybridForCausalLM |
| hunyuan.py | HunYuanMoEV1ForCausalLM,HunYuanDenseV1ForCausalLM |
| hunyuan_v3.py | HYV3ForCausalLM |
| inkling.py | InklingForConditionalGeneration,InklingForConditionalGenerationMTP |
| interns1.py | InternS1ForConditionalGeneration |
| interns1pro.py | InternS1ProForConditionalGeneration |
| interns2_mobius.py | InternS2MobiusForConditionalGeneration |
| interns2preview.py | InternS2PreviewForConditionalGeneration |
| kimi_k25.py | KimiK25ForConditionalGeneration |
| kimi_k3.py | KimiK3ForConditionalGeneration |
| laguna.py | LagunaForCausalLM |
| lfm2_moe.py | Lfm2MoeForCausalLM |
| llada2.py | LLaDA2MoeModelLM |
| minimax_m3.py | MiniMaxM3SparseForCausalLM |
| mixtral.py | MixtralForCausalLM |
| mixtral_quant.py | QuantMixtralForCausalLM |
| olmoe.py | OlmoeForCausalLM |
| phimoe.py | PhiMoEForCausalLM |
| qwen2_moe.py | Qwen2MoeForCausalLM |
| qwen3_moe.py | Qwen3MoeForCausalLM |
| qwen3_5_text.py | Qwen3_5MoeForCausalLM,Qwen3_5ForCausalLM |
| sarvam_moe.py | SarvamMLAForCausalLM,SarvamMoEForCausalLM |
| sdar.py | SDARForCausalLM |
| sdar_moe.py | SDARMoeForCausalLM |
| step3p5.py | Step3p5ForCausalLM |
| step3p7.py | Step3p7ForConditionalGeneration |
| xverse_moe.py | XverseMoeForCausalLM |

说明：`ForConditionalGeneration` 后缀在文本模型（InternS/Step/Kimi/Inkling）与多模态模型（part2）中均有使用，族归属按文件语义划分；`SarvamMLA` 为 MLA 系、`QuantMixtral` 为量化 MoE 特化入口（见 model-registry.md 选中链）。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
