## vLLM vs SGLang 投机解码对比（二）：EAGLE 实现差异与调度/采样衔接

承 [_part1](speculative-comparison.md)。聚焦 EAGLE 树生成与验收、draft token 在 batch/logits/KV 中的处理。事实基准：vLLM `vllm/v1/spec_decode/eagle.py`（KB `15-v1-worker/spec-decode-v1.md`）与 SGLang `srt/speculative/eagle_*.py`（KB `13-speculative/eagle-drafters.md`）。

### 一、EAGLE 实现差异

| 维度 | vLLM `EagleProposer` | SGLang `EAGLEWorkerV2` + `EagleDraftWorker` |
|---|---|---|
| 文件 | `v1/spec_decode/eagle.py` | `eagle_worker_v2.py`（`EAGLEWorkerV2:1011`、`EagleDraftWorker:129`）、`eagle_info.py`、`eagle_utils.py`、`eagle_worker_common.py` |
| 权重共享 | `_maybe_share_embeddings`/`_maybe_share_lm_head` 复用 target embedding 与 lm_head（MTP 类同） | EAGLE-1/2：`set_embed_and_head` 共享 embedding+lm_head（`--speculative-token-map` 可收窄词表）；EAGLE-3：一般只共享 embedding、模型自带 `hot_token_id`（少数走 `load_lm_head_from_target`，`eagle_worker_v2.py:280-309`） |
| 草稿输入 | 接收 target hidden states + 上轮 sampled tokens | `EagleDraftInput.topk_p/topk_index/hidden_states`（`eagle_info.py:142`）；EAGLE-3 aux 模式消费 `num_aux` 个 target 层拼接（`get_draft_input_from_target_hidden_dim`，`eagle_utils.py:446`） |
| 树生成 | `propose()` 单次产 K 个 token，逻辑在 proposer 内 | `draft_forward`（`eagle_worker_v2.py:560`）逐 step 循环 `speculative_num_steps` 次，复用同一 `ForwardBatch`，上步 hidden 递归喂回草稿头；`fast_topk`/`draft_topk1_postprocess`（`kernels/ops/speculative/topk1.py`）选 topk |
| tree mask | 无显式树（线性链式布局，靠 `SpecDecodeMetadata` 索引） | `build_tree_kernel_efficient`（`eagle_utils.py:151`）产出 `tree_mask`（`FULL_MASK`/`QLEN_ONLY`/`QLEN_ONLY_BITPACKING` 三种形态）+ `positions` + `retrieve_index/retrieve_next_token/retrieve_next_sibling`（树链式表示，供验收 kernel 遍历父链/兄弟链） |
| 树形状 | `max_spec_len`（MAX_SPEC_LEN=128）线性草稿 | `EagleVerifyInput.max_tree_depth = spec_steps+1`、`tree_topk = topk`（`eagle_info.py:44-54`） |
| 验收路径 | `RejectionSampler` 按位置逐个验收（linear） | `eagle_sample` 沿接受路径遍历：`verify_tree_greedy`（greedy）/ `tree_speculative_sampling_target_only`（随机）；`accept_index` 记录 `(bs, spec_steps+1)` 接受路径 |
| 补采样（bonus） | 全部接受后 target 单独采样 bonus（可带 top_p/top_k） | `fill_bonus_tokens_func`（`eagle_worker_common.py:616`）取接受链末端 target 预测写入下轮树根 |
| 回填草稿 KV | 复用 target KV，无独立 draft_extend | `draft_extend`（`eagle_worker_v2.py:732/859`）：prefill 版左移旋转取末位 hidden（`eagle_utils.py:88`）；decode 版按 `num_correct_drafts` 只对最后接受行跑 lm_head 产下轮 `EagleDraftInput` |
| 验收后压缩 | 被拒位置以 padding 占位（`is_rejected_token_mask`），下轮重建输入 | topk>1 时 `_finalize_accept_tree_path`（`eagle_worker_common.py:406`）压缩接受路径 KV/predict/hidden 到 req 块前端（`move_accept_tokens_to_target_kvcache`，`spec_utils.py:694`） |

**关键差异**：
- vLLM 的 EAGLE 是**线性草稿 + 逐位置验收**，无显式树结构；SGLang 是**topk 树草稿**（`tree_topk` 树宽、`max_tree_depth` 树深），tree mask 决定一次 target 前向覆盖整棵树，accept 路径沿树链遍历。
- SGLang 有独立的 `draft_extend` 阶段维护草稿 KV 与下轮树根输入；vLLM EAGLE 与 target 共用 KV，无此阶段。

### 二、与调度（scheduler）衔接

| 维度 | vLLM V1 | SGLang SRT |
|---|---|---|
| 调度产出 | `SchedulerOutput.scheduled_spec_decode_tokens`（req_id → draft ids）+ `num_spec_tokens_to_schedule`；worker 据此建 `SpecDecodeMetadata` | `ScheduleBatch.spec_info`（`schedule_batch.py:2190`）随 batch 流动，`filter_batch`/`merge_batch` 切片拼接各算法 draft/verify 张量 |
| worker 挂载 | 调度器调普通 model_worker，spec 全在 runner 内 | `if spec_algorithm.is_none(): model_worker=tp_worker else: model_worker=draft_worker`（`scheduler.py:1024-1027`）；`maybe_init_draft_worker`（`:923`）建 draft worker，NGRAM 挂 `ExternalCorpusManager` |
| 初始化 | runner `__init__` 内建 drafter + RejectionSampler（仅 `get_pp_group().is_last_rank`） | `alloc_memory_pool`（draft 独立 `token_to_kv_pool`）→ `init_attention_backends` → `init_cuda_graphs`（`scheduler.py:967-991`） |
| 每 step 数据流 | `execute_model` 建 metadata → `_sample` 验收 → `propose_draft_token_ids` → `post_step` 中 `take_draft_token_ids()`（D2H）回填调度器 `update_draft_token_ids()` | `spec_prepare_for_decode`（`spec_utils.py:1032`，`schedule_batch.py:3066`）：EVICT_SWA、penalty 累积、`alloc_for_spec_decode`（`eagle_utils.py:962`） |
| 异步路径 | async 时 `update_async_spec_token_ids` 在 worker 进程内写回真实 draft（penalty/bad_words 依赖） | `on_publish` 在 verify 后、draft_extend 前发布，供 overlap 调度 fence |
| 验收统计回流 | `num_sampled`/`num_rejected` 供调度算下轮预算 | `on_verify_complete_cpu`/`note_request_finished`/`activate_step_by_batch`（`base_spec_worker.py:314-338`）喂 `AdaptiveController`（`adaptive_runtime_state.py:61`）做自适应步数切换（`apply_runtime_state`，`eagle_worker_v2.py:1382`） |
| disagg | 无专门跨引擎草稿传输（EAGLE 在引擎内） | `eagle_disaggregation.py`/`dspark_disaggregation.py`/`dflash_disaggregation.py` 经 `FutureMap` 传草稿状态；`carries_draft_hidden_states()`（`spec_info.py:151`）仅 EAGLE 族；`decoupled_spec_io.py` 提供 IPC 协议 |

### 三、与采样（sampler/logits/KV）衔接

| 维度 | vLLM V1 | SGLang SRT |
|---|---|---|
| logits 组织 | target logits 与 bonus logits 同批算（`target_logits_indices`/`bonus_logits_indices`），按索引切分；draft 位置 + bonus 位置 | `TARGET_VERIFY` 一次 target 前向算整棵草稿树位点（`eagle_prepare_for_verify`，`eagle_utils.py:497`，复用 `decode_cuda_graph_runner` 专用 graph） |
| 采样输入 | `SamplingMetadata` 每 token 一行；`rejection_sampler(spec_decode_metadata, draft_probs, logits, sampling_metadata)` | `ForwardBatch` + `batch.spec_info`；verify 用 `eagle_sample`，惩罚按 `draft_token_num` 展开（`eagle_utils.py:694-714`） |
| draft 采样方式 | 默认贪心 `argmax`；`probabilistic` 仅按温度缩放；`use_local_argmax_reduction` 减少 TP 通信 | 三路径：拒绝采样（topk=1，`sample_draft_proposal` 温度+Gumbel）/ `draft_topk1_postprocess` 写链式 token / `renorm_draft_probs`+`fast_topk`（topk>1） |
| KV 分配 | draft 位置与 target 共用位置空间，逐 token 槽位 | `resolve_num_tokens_per_req`（`spec_utils.py:97`）统一每请求 token 宽度（draft_decode=topk、draft_extend=num_draft_tokens、target_verify 走算法钩子），兼作 DP attention 的 `global_num_tokens` 乘数；无草稿 KV 后端（NGRAM）不做 per-topk 页舍入 |
| CUDA graph | 无独立 draft graph（EAGLE 与 target 同进程同图） | 独立 `EAGLEDraftCudaGraphRunner`（`eagle_draft_cuda_graph_runner.py:76`）/`EAGLEDraftExtendCudaGraphRunner`（`:73`）/`MultiLayerEagleDraftExtendCudaGraphRunner`/`FrozenKVMTPCudaGraphRunner` |
| 约束解码 | grammar 与 spec 不并行（结构化输出场景仅跳过无效 spec token，pad 为 -1） | `supports_grammar_overlap()`（EAGLE/STANDALONE/DFLASH 族）在 verify 内推进 grammar FSM，`grammar_mask.apply`（`eagle_utils.py:714`） |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
