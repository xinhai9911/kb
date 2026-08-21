## SGLang 投机解码架构总览

源码：`srt/speculative/`（约 36 个 .py + 2 子目录，核心：`spec_info.py`、`spec_registry.py`、`base_spec_worker.py`、`eagle_worker_v2.py`、`ngram_worker.py`）。与 vLLM「proposer + RejectionSampler 全在 ModelRunner 进程」不同，SGLang 将投机解码组织成**独立的 spec worker 体系**：一个 `BaseSpecWorker` 子类整体替换调度器的 `model_worker`，内部再挂一个**草稿 TpModelWorker**（独立 KV 池、独立 CUDA graph），draft 与 verify 在同一个 worker 的 `forward_batch_generation` 里分阶段编排。

### 算法注册与 worker 映射

- 内置算法枚举 `SpeculativeAlgorithm`（`srt/speculative/spec_info.py:31`）：`DFLASH / DSPARK / EAGLE / EAGLE3 / FROZEN_KV_MTP / STANDALONE / NGRAM / NONE`。
- 插件机制 `SpeculativeAlgorithm.register`（`spec_info.py:63`）→ `register_algorithm`（`spec_registry.py:222`），存 `_REGISTRY`；`from_string` 未知名字回落到注册表，二者鸭子类型统一（`is_*()`/`supports_*()`/`create_worker`，`spec_info.py:47`）。
- worker 工厂 `create_worker`（`spec_info.py:254`）：

| 算法 | Worker 类 | 文件 |
|---|---|---|
| EAGLE / EAGLE3 | `EAGLEWorkerV2` | `eagle_worker_v2.py:1011` |
| EAGLE + `--enable-multi-layer-eagle` | `MultiLayerEagleWorkerV2` | `multi_layer_eagle_worker_v2.py:918` |
| FROZEN_KV_MTP | `FrozenKVMTPWorkerV2` | `frozen_kv_mtp_worker_v2.py:676` |
| STANDALONE | `StandaloneWorkerV2` | `standalone_worker_v2.py:147` |
| DFLASH | `DFlashWorkerV2` | `dflash_worker_v2.py:255` |
| DSPARK | `DSparkWorkerV2` | `dspark_components/dspark_worker_v2.py:76` |
| NGRAM | `NGRAMWorker` | `ngram_worker.py:71` |

### 进程内集成：spec worker 取代 model_worker

调度器（`srt/managers/scheduler.py`）：

- `maybe_init_draft_worker`（`scheduler.py:923`）经 `self.spec_algorithm.create_worker(...)`（`scheduler.py:941`）实例化 draft worker，NGRAM 额外挂 `ExternalCorpusManager`。
- 初始化顺序：`alloc_memory_pool`（draft 与 target 共享 `req_to_token_pool`，draft 有独立 `token_to_kv_pool`）→ `init_attention_backends` → `init_cuda_graphs`（`scheduler.py:967-991`）。
- 关键分发：`if self.spec_algorithm.is_none(): self.model_worker = self.tp_worker else: self.model_worker = self.draft_worker`（`scheduler.py:1024-1027`）。此后调度器对 `model_worker.forward_batch_generation(...)` 的调用全部落在 spec worker 上。
- 内存/统计（`scheduler.py:1337-1392`）：`primary_draft_kv_pool`、`carries_draft_hidden_states()`（仅 EAGLE 族）决定 disagg prefill→decode 是否携带 draft hidden states。

### 每步三阶段流程（decode 路径）

`EAGLEWorkerV2.forward_batch_generation`（`eagle_worker_v2.py:1108`）：

```
target prefill（新请求，CaptureHiddenMode.FULL）
        ↓ next_token_ids / hidden_states
draft_extend（prefill 版）→ 填草稿 KV、产出首批 EagleDraftInput
        ↓ 之后每步 decode：
draft（EagleDraftWorker.draft，多步自回归树生成）          → EagleVerifyInput
target verify（TARGET_VERIFY 前向 + eagle_sample 验收）   → predict/accept_lens
draft_extend（decode 版，按 accept 长度重跑草稿前向填 KV） → 下轮 EagleDraftInput
```

- 每阶段用 `spec_stage_span("draft"/"draft_extend")`（`spec_utils.py:687`，NVTX）打点。
- `speculative_num_steps == 0` 时跳过 draft，走 `_build_trivial_verify_input`（`eagle_worker_v2.py:1205`）退化为普通 decode，但保留 draft KV 预热。
- `on_publish` 在 verify 结束、draft_extend 之前发布，用于 overlap 调度的 fence。

### SpecInput 与 ForwardMode

- `SpecInputType`（`spec_info.py:309`）：`EAGLE_DRAFT / EAGLE_DRAFT_EXTEND / EAGLE_VERIFY / FROZEN_KV_MTP_DRAFT / FROZEN_KV_MTP_VERIFY / DFLASH_DRAFT / DFLASH_VERIFY / NGRAM_VERIFY`；`SpecInput.is_draft_input()/is_verify_input()`（`spec_info.py:351-365`）供 attention backend / ForwardBatch padding 统一分派。
- `SpecInput` 携带 `num_tokens_per_req / num_tokens_for_logprob_per_req`（统一每请求 token 宽度，兼作 DP attention 的 `global_num_tokens` 乘数，见 `spec_scale_global_num_tokens`，`spec_info.py:368`），以及 `ragged_verify_layout`（仅 DSPARK 支持，`supports_ragged_verify()`，`spec_info.py:131`）。
- 新 ForwardMode（`srt/model_executor/forward_batch_info.py:100-114`）：`TARGET_VERIFY`、`DRAFT_EXTEND_V2`。`TARGET_VERIFY` 属于 `is_extend`/`is_cuda_graph`（按扩展语义前向、可进 CUDA graph）；`DRAFT_EXTEND_V2` 视为 prefill（`is_prefill(include_draft_extend_v2=True)`）。
- 每请求 token 宽度统一推导：`resolve_num_tokens_per_req`（`spec_utils.py:97`）——draft_decode=topk、draft_extend=num_draft_tokens、target_verify 走算法钩子 `get_num_tokens_per_req_for_target_verify`（DSPARK 的 draft worker 为 `num_draft_tokens - 1`，`spec_info.py:228`）。

### 与 03-scheduler / 06-model-executor 的衔接

- `ScheduleBatch.spec_info`（`srt/managers/schedule_batch.py:2190`）随 batch 流动：`filter_batch`（`:3221`）/ `merge_batch`（`:3290`）切片/拼接各算法的 draft/verify 张量（如 `EagleDraftInput.filter_batch`，`eagle_info.py:208`）。
- `spec_prepare_for_decode`（`spec_utils.py:1032`）在 `schedule_batch.py:3066` 由调度器调用，做 decode 前的规格化准备（EVICT_SWA、penalty 累积、KV 分配 `alloc_for_spec_decode`，`eagle_utils.py:962`）。
- 验收统计回流：`on_verify_complete_cpu` / `note_request_finished` / `activate_step_by_batch` 钩子（`base_spec_worker.py:314-338`），由调度器的 batch-result 处理器调用，喂给 `AdaptiveController`（`adaptive_runtime_state.py:61`）做自适应步数切换（`build_adaptive_runtime_state`/`apply_runtime_state`，`eagle_worker_v2.py:1304/1382`）。
- forward 侧：`TARGET_VERIFY` 复用 target 的 `decode_cuda_graph_runner`（`eagle_prepare_for_verify`，`eagle_utils.py:497`，按 `speculative_num_steps/num_draft_tokens` 捕获的专用 graph）；draft 侧有独立 `EAGLEDraftCudaGraphRunner` / `EAGLEDraftExtendCudaGraphRunner`（`eagle_draft_cuda_graph_runner.py:76`、`eagle_draft_extend_cuda_graph_runner.py:73`）。

### 与 vLLM spec_decode 对照

| 维度 | vLLM | SGLang |
|---|---|---|
| 集成位置 | ModelRunner 内建 proposer + RejectionSampler | spec worker 替换 model_worker，内挂 draft TpModelWorker |
| draft 编排 | 每 step 采样后 `proposer.propose` 产下一轮 draft | worker 内 `draft → verify → draft_extend` 三阶段显式编排 |
| 验收采样 | `rejection_sampler`（greedy/随机，triton kernel） | `eagle_sample`（`eagle_utils.py:653`）：greedy 走 `verify_tree_greedy`，随机走 `tree_speculative_sampling_target_only` / `chain_speculative_sampling_triton` |
| 树结构 | `SpecDecodeMetadata`（target/bonus logits 索引） | `EagleVerifyInput` + `retrieve_index/retrieve_next_token/retrieve_next_sibling` + tree mask |
| 与调度器契约 | `SchedulerOutput.scheduled_spec_decode_tokens` | `batch.spec_info` 就地携带，`model_worker` 整体替换 |
| 草稿 KV | EAGLE 用 target KV 复用 | draft worker 独立 `token_to_kv_pool`，`has_draft_kv()`（`spec_info.py:145`）控制预留 |
| 约束解码 | 不支持 grammar 并行 | `supports_grammar_overlap()`（`spec_info.py:137`，EAGLE/STANDALONE/DFLASH 族）在 verify 内推进 grammar FSM |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
