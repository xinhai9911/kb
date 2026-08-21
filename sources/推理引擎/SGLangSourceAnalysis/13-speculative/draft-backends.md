## 其余草稿后端与配套机制

除 EAGLE 外，`srt/speculative/` 还覆盖 NGRAM、DFLASH、DSPARK、FROZEN_KV_MTP、STANDALONE 五类后端，以及自适应步数、disagg 草稿传输、HiCache 等配套。

### 草稿后端清单

| 算法 | 草稿来源 | 验证方式 | 特点 |
|---|---|---|---|
| NGRAM | CPU 侧 C++ 前缀树 `NgramCorpus`（`cpp_ngram/ngram_corpus.py:14`） | `TARGET_VERIFY` + `eagle_sample` | 无草稿模型（`draft_worker` 返回 None，`ngram_worker.py:143`），`has_draft_kv()=False`，decode-only、同步 |
| DFLASH | 草稿模型经普通 `TpModelWorker` 驱动（`dflash_worker_v2.py:405`） | 块式线性 verify（`DFlashVerifyInput`，`dflash_info.py:26`，`topk` 恒 1） | 并行起草（一步提出整块），`supports_target_verify_for_draft()=True` |
| DSPARK | 草稿模型 + 块提出器（`dspark_components/dspark_draft.py:166`） | `TargetVerifyExecutor`（`dspark_verify.py:80`）+ 规划器 `DSparkVerifyPlanner`（`dspark_planner.py:70`） | 动态验证预算/自适应验证；唯一支持 `ragged_verify`（per-req 变长 verify，`ragged_verify.py`） |
| FROZEN_KV_MTP | `FrozenKVMTPDraftWorker`（`frozen_kv_mtp_worker_v2.py:91`） | `FrozenKVMTPWorkerV2`（`:676`，继承 `EAGLEWorkerV2`） | MTP（multi-token prediction）式，`is_eagle()` 兼容分支；冻结 KV |
| STANDALONE | `StandaloneDraftWorker`（`standalone_worker_v2.py:35`，不共享 target embedding/lm_head） | 继承 EAGLE V2 verify | 独立完整草稿模型（无目标 hidden 输入，`hidden_states=None`，`eagle_info.py:156`） |

### NGRAM（`ngram_worker.py`）

- `_prepare_for_speculative_decoding`（`:310`）：decode-only；从每 req 最近 `max_trie_depth` 个 token 查 `ngram_corpus.batch_get`（`:299`）拿 `draft_tokens + tree_mask`（numpy，`non_blocking` 拷贝上 GPU），`reconstruct_indices_from_tree_mask`（sgl_kernel）重建 `retrieve_*` 与 positions；构造 `NgramVerifyInput`（`ngram_info.py:11`）。
- 验收后 `_update_ngram_corpus`（`:399`）`batch_put` 把本轮 token 写回语料库（仅接受段，`prev_accept_lens` 切片）。外部语料：`add_external_corpus / commit_corpus_load / remove_external_corpus`（`:160-170`，走 `external_corpus_manager.py`）。
- 无草稿 KV：每 decode 的 KV 分配不做 per-topk 页舍入（`get_alloc_len_per_decode`，见 `spec_info.py:145-149`）。

### DFLASH / DSPARK（dflash 族）

- 两者均以普通 `TpModelWorker` 当草稿（`BaseSpecWorker.draft_worker` 类型注解 `EagleDraftWorkerBase | TpModelWorker`，`base_spec_worker.py:181`），构建入口 `build_draft_tp_worker`（`draft_worker_common.py:65`，含草稿 attention 后端解析 `_resolve_draft_attention_backend_fallback`，`:43`）。
- DFLASH：草稿采样器 `_DflashDraftSampler` / `_SelectorDraftSampler`（`dflash_worker_v2.py:88/194`）接在草稿 forward 的 capture hook 上（`make_draft_sampler_capture_hook`，`draft_worker_common.py:147`）；验证为线性块（`DFlashVerifyInput.prepare_for_verify`，`dflash_info.py:59`），`generate_attn_arg_prefill` 支持 `ragged_verify_layout`（`:138`）。
- DSPARK：组件在 `dspark_components/`（规划、验证、块接受估计器 `dspark_block_accept_estimator.py:221`、可观测性 `dspark_observability.py`、KV 注入 `dspark_kv_inject.py:17`）；`supports_ragged_verify()`（`spec_info.py:131`）为 token-bucket 键控 verify graph 开门；adaptive budget 由 `HostConfidenceBudgetPlanner`（`dspark_planner.py:1011`）+ `on_verify_complete_cpu` / `note_request_finished` 钩子（`base_spec_worker.py:314-330`）闭环。
- 配置：`--speculative-dflash-block-size` / `--speculative-dspark-block-size`（后者 `gamma+1`，见 `server_args.py:2138/2143`）。

### 草稿专用 CUDA graph runner

| Runner | 文件 |
|---|---|
| `EAGLEDraftCudaGraphRunner` | `eagle_draft_cuda_graph_runner.py:76`（decode 多步树） |
| `EAGLEDraftExtendCudaGraphRunner` | `eagle_draft_extend_cuda_graph_runner.py:73` |
| `MultiLayerEagleDraftExtendCudaGraphRunner`（含 `OneGraph...` 变体） | `multi_layer_eagle_draft_extend_cuda_graph_runner.py:132/501/842` |
| `FrozenKVMTPCudaGraphRunner` | `frozen_kv_mtp_cuda_graph_runner.py:66` |

### 自适应投机解码

- `AdaptiveController`（`adaptive_runtime_state.py:61`）按 batch 大小在预构建的 `SpecRuntimeState`（`:19`）之间切换 `speculative_num_steps / num_draft_tokens`，每状态含草稿/target 的 attention 后端与 graph runner。
- `EAGLEWorkerV2.build_adaptive_runtime_state`（`eagle_worker_v2.py:1304`）在 `_override_worker_state`（`:1429`）上下文内临时改 server_args + worker 属性重捕获 graph；`apply_runtime_state`（`:1382`）运行时热切换。`adaptive_spec_params.py` 定义参数槽（`AdaptiveStepSlot:140` / `AdaptiveSpeculativeParams:262`）。

### 解耦/跨阶段草稿传输

- `decoupled_spec_io.py`：`DraftMeshMessageType` / `DraftSync` / `VerifyCommit` / `DraftControlBatch`（`:8-151`），draft 请求与 verify 提交的 IPC 协议（`DecoupledSpecIpcConfig:381`）。
- disagg：`eagle_disaggregation.py`（`build_eagle_disagg_draft_input`，`spec_info.py:179` 分支）、`dspark_disaggregation.py`、`dflash_disaggregation.py`——prefill→decode 阶段间经 `FutureMap` 传递草稿状态；`carries_draft_hidden_states()`（`spec_info.py:151`）只对 EAGLE 族生效。
- `build_disagg_draft_input` 默认实现返回 None（`spec_registry.py:152`）。
- HiCache：`HiCacheDraftMode`（`base_spec_worker.py:26`）`NONE/PACKED/SIDECAR`；`_build_hicache_draft_plan`（`:234`）决定草稿 KV 池打包进 target（MTP 可打包）还是侧挂（SIDECAR 只登记第一个草稿 runner）。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
