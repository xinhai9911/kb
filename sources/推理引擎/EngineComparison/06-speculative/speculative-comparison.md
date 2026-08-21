## vLLM vs SGLang 投机解码对比（一）：架构集成与草稿后端

对比两大引擎的投机解码（speculative decoding）。事实基准：vLLM V1（`vllm/v1/spec_decode/`、`vllm/v1/worker/gpu/spec_decode/`，KB 见 `vLLMSourceAnalysis/05-sampling/spec-decoding.md`、`15-v1-worker/spec-decode-v1.md`）与 SGLang SRT（`srt/speculative/`，KB 见 `SGLangSourceAnalysis/13-speculative/`）。EAGLE 树生成细节与调度/采样衔接见 [_part2](speculative-comparison_part2.md)。

### 一、架构集成：ModelRunner 内建 proposer vs spec worker 替换 model_worker

| 维度 | vLLM V1 | SGLang SRT |
|---|---|---|
| 集成位置 | 完全落在 `GPUModelRunner` 进程内：构造时按 `SpeculativeConfig.method` 创建 proposer + `RejectionSampler`（`v1/worker/gpu_input_batch.py`→`gpu_model_runner.py:630-709`） | 独立 spec worker 体系：`BaseSpecWorker` 子类**整体替换**调度器的 `model_worker`（`scheduler.py:1024-1027`），内部再挂一个草稿 `TpModelWorker` |
| 草稿模型载体 | `SpecDecodeBaseProposer`（`llm_base_proposer.py:71`）：draft 模型副本/draft hidden_size/权重共享 | `EagleDraftWorkerBase`（`base_spec_worker.py:57`）：独立 `TpModelWorker(is_draft_worker=True)`，独立 KV 池、独立 CUDA graph |
| 核心元数据 | `SpecDecodeMetadata`（`v1/spec_decode/metadata.py:10`）：`draft_token_ids`/`num_draft_tokens`/`cu_num_draft_tokens`/`target_logits_indices`/`bonus_logits_indices`/`logits_indices`，target 与 bonus logits 同批计算后按索引切分 | `SpecInputType`（`spec_info.py:309`）：`EAGLE_DRAFT / EAGLE_DRAFT_EXTEND / EAGLE_VERIFY / FROZEN_KV_MTP_DRAFT/VERIFY / DFLASH_DRAFT/VERIFY / NGRAM_VERIFY`，随 `batch.spec_info` 流动 |
| 每步编排 | 采样后 `proposer.propose` 产下一轮 draft（`propose_draft_token_ids`，`gpu_model_runner.py:5126`） | worker 内 `draft → verify → draft_extend` **三阶段显式编排**（`EAGLEWorkerV2.forward_batch_generation`，`eagle_worker_v2.py:1108`） |
| ForwardMode | 无独立 spec forward mode，复用常规 decode 前向 + metadata 标记 | 新增 `TARGET_VERIFY`（`is_extend`/可进 CUDA graph）与 `DRAFT_EXTEND_V2`（视为 prefill）（`forward_batch_info.py:100-114`） |
| 草稿 KV | EAGLE 复用 target KV（草稿与 target 同模型族） | draft worker 独立 `token_to_kv_pool`（与 target 共享 `req_to_token_pool`），`has_draft_kv()`（`spec_info.py:145`）控制预留 |
| 算法注册 | method 字符串分支 + `custom_class` 通道 | `SpeculativeAlgorithm` 枚举（`spec_info.py:31`）+ 插件注册表 `register_algorithm`（`spec_registry.py:222`） |
| 调度契约 | `SchedulerOutput.scheduled_spec_decode_tokens`（`req_id → draft ids`）+ `num_spec_tokens_to_schedule`；draft ids 经 `take_draft_token_ids()`（`gpu_model_runner.py:5005`，D2H）回填 | `batch.spec_info` 就地携带（`filter_batch`/`merge_batch` 切片拼接，`schedule_batch.py:3221/3290`）；`spec_prepare_for_decode`（`spec_utils.py:1032`）decode 前规格化 |

**关键差异**：
- vLLM 把投机解码做进 ModelRunner/采样器（proposer + rejection sampler），调度器只负责排 draft tokens；SGLang 用 spec worker **替换** model_worker，draft 与 verify 在同一 worker 的 `forward_batch_generation` 内分阶段编排。
- vLLM 每次前向只发一轮 draft（每 step `propose` 一次）；SGLang 引入 `draft_extend` 阶段，把验收结果回填草稿 KV、为下轮树根供 hidden states——这是两引擎 step 结构最大的形态差。

### 二、草稿后端清单

| 后端 | vLLM（method 关键字 → 类，`v1/spec_decode/`） | SGLang（算法 → Worker，`srt/speculative/`） |
|---|---|---|
| EAGLE-1/2 | `eagle`/`eagle3` → `EagleProposer`（`eagle.py`） | `EAGLE`/`EAGLE3` → `EAGLEWorkerV2`（`eagle_worker_v2.py:1011`） |
| EAGLE 多层 | 无 | `--enable-multi-layer-eagle` → `MultiLayerEagleWorkerV2`（`multi_layer_eagle_worker_v2.py:918`） |
| Medusa | `medusa` → `MedusaProposer`（`medusa.py`） | 无 |
| 独立草稿模型 | `draft_model` → `DraftModelProposer`（`draft_model.py`，要求 draft TP 同 target、词表同构或 `VocabMapping`） | `STANDALONE` → `StandaloneWorkerV2`（`standalone_worker_v2.py:147`，不共享 target embedding/lm_head） |
| N-gram | `ngram`（CPU，`ngram_proposer.py`）/ `ngram_gpu`（GPU） | `NGRAM` → `NGRAMWorker`（`ngram_worker.py:71`，CPU 侧 C++ 前缀树 `NgramCorpus`） |
| DFlash | `dflash` → `DFlashProposer`（`dflash.py`，并行起草） | `DFLASH` → `DFlashWorkerV2`（`dflash_worker_v2.py:255`，块式线性 verify，topk 恒 1） |
| DSpark | `dspark` → `v1/worker/gpu/spec_decode/dspark/`（自适应验证，`adaptive_verification.py`） | `DSPARK` → `DSparkWorkerV2`（`dspark_components/dspark_worker_v2.py:76`，唯一支持 `ragged_verify`） |
| MTP 族 | `*_mtp` 系列（DeepseekMTP 等，`worker/gpu/spec_decode/mtp/`、`multi_module_mtp/`） | `FROZEN_KV_MTP` → `FrozenKVMTPWorkerV2`（`frozen_kv_mtp_worker_v2.py:676`，继承 EAGLE V2 verify，冻结 KV） |
| 其余 | `suffix`、`extract_hidden_states`、`gemma4_mtp`、`step3p5_mtp`、`custom_class`、`mlp_speculator` | — |

**关键差异**：
- vLLM 后端面更宽（suffix/extract_hidden_states/gemma4/step3p5/custom_class），SGLang 全部收敛到 7 个内置算法枚举，靠插件注册表扩展。
- 同一 EAGLE，SGLang 区分 `EAGLE`/`EAGLE3`/多层/`FROZEN_KV_MTP`（兼容 `is_eagle()` 分支）多个 worker；vLLM 仅 `EagleProposer` 一个类覆盖 eagle/eagle3。
- DFLASH/DSPARK 两引擎都有；N-gram 实现形态一致（CPU 侧匹配，target verify）；MTP 族 vLLM 走独立 mtp 目录，SGLang 以 FROZEN_KV_MTP 实现。

### 三、验证（验收采样）对比

| 维度 | vLLM `RejectionSampler` | SGLang `eagle_sample` |
|---|---|---|
| 位置 | `v1/sample/rejection_sampler.py`（triton kernel）+ 新批版 `v1/worker/gpu/spec_decode/rejection_sampler.py` | `eagle_utils.py:653` |
| greedy | `rejection_greedy_sample_kernel`：draft token == target argmax 即接受 | `verify_tree_greedy`（`eagle_utils.py:378`，各平台 kernel）：同判据 |
| 随机 | `rejection_random_sample_kernel`（Gumbel 技巧，`max(target_prob-draft_prob,0)` 补采） | `tree_speculative_sampling_target_only`（树）/ `chain_speculative_sampling_triton`（topk=1，`kernels/ops/speculative/reject_sampling.py`） |
| 结果结构 | `num_sampled`/`num_rejected` 供下轮预算；`parse_output` 以 `PLACEHOLDER_TOKEN_ID(-1)` 过滤 | `predict`/`accept_lens=num_correct_drafts+1`（含 bonus）/`accept_index`（`(bs, spec_steps+1)` 接受路径节点索引） |
| 采样方法配置 | `rejection_sample_method`：`standard`/`synthetic`/`block`；`draft_sample_method`：`greedy`/`probabilistic` | 随机采样需 `--speculative-use-rejection-sampling`（要求 topk=1）；`draft_probs` 仅拒绝采样模式下产生 |
| 约束兼容 | `min_p>1e-5`、`logit_bias`、自定义 logits processors 不支持 spec（仅 MinTokens）；输出 logprobs 与 DSpark 自适应互斥 | 惩罚/logit_bias 按 `draft_token_num` 展开；grammar mask 在 verify 内推进（`supports_grammar_overlap()`，`spec_info.py:137`，EAGLE/STANDALONE/DFLASH 族） |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
