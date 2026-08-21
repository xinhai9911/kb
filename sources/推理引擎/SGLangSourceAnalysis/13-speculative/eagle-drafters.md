## Eagle 草稿头实现（EAGLE-1/2/3）

核心文件：`eagle_worker_v2.py`（`EAGLEWorkerV2` + `EagleDraftWorker`）、`eagle_info.py`（三个 SpecInput）、`eagle_utils.py`（树/采样）、`eagle_worker_common.py`（三阶段公共逻辑）、`draft_utils.py`（草稿 decode 后端工厂）。

### 两个类的分工

| 类 | 职责 |
|---|---|
| `EAGLEWorkerV2`（`eagle_worker_v2.py:1011`，`BaseSpecWorker` 子类） | 持有 target worker + `EagleDraftWorker`；实现 `forward_batch_generation` 阶段编排、`verify`、自适应协议 |
| `EagleDraftWorker`（`eagle_worker_v2.py:129`，`EagleDraftWorkerBase` 子类，`base_spec_worker.py:57`） | 草稿模型本体：独立 `TpModelWorker(is_draft_worker=True)`；`draft()`/`draft_forward()`/`_draft_extend_for_prefill()`/`_draft_extend_for_decode()`；草稿 CUDA graph 捕获 |

### 草稿模型加载（`EagleDraftWorker.__init__`，eagle_worker_v2.py:130）

- 独立实例化 `TpModelWorker`（`is_draft_worker=True`，`pp_rank=0`，以 target 的 `context_len` 跑绝对位置），置于 `draft_model_build_scope()` + `speculative_moe_backend_context()` + `speculative_moe_a2a_backend_context()`；EAGLE3 + DP attention 用 `draft_tp_context(attn_tp_group)`（`eagle_worker_v2.py:161-180`）。
- `init_lm_head`（`eagle_worker_v2.py:280`）——EAGLE 家族差异点：

| 变体 | 权重共享策略 |
|---|---|
| EAGLE-1/2 | `set_embed_and_head(embed, head)` 共享 target embedding + lm_head；若配 `--speculative-token-map`，`head.data = head.data[hot_token_id]` 收窄词表 |
| EAGLE-3 | 一般**不**共享 lm_head（`set_embed(embed)` 仅共享 embedding）；模型自带 `hot_token_id`；少数（如 nvidia/gpt-oss-120b-Eagle3）经 `load_lm_head_from_target` 走共享路径（`eagle_worker_v2.py:293-309`） |

- EAGLE-3 输入宽度：`get_draft_input_from_target_hidden_dim`（`eagle_utils.py:446`）——aux 模式草稿消费 `num_aux` 个 target 层拼接（`target_hidden_size * num_aux`），其余架构用 `spec_hidden_size`。

### 草稿 forward：多步树生成（`draft_forward`，eagle_worker_v2.py:560）

逐 step 循环 `speculative_num_steps` 次，复用同一 `ForwardBatch`：

1. 首步输入来自 `EagleDraftInput.topk_p / topk_index / hidden_states`（`eagle_info.py:142`，`topk_p` 形状 `(b, topk)`）；`hot_token_id` 映射后进入循环。
2. 每次前向用 `draft_attn_backend.attn_backends[i]`（按步取后端，`eagle_worker_v2.py:650`），上一步 `logits_output.hidden_states` 喂回草稿头（递归自回归）。
3. token 选择三条路径（`eagle_worker_v2.py:586-702`）：
   - `--speculative-use-rejection-sampling`（要求 topk=1，`eagle_worker_v2.py:151`）：`sample_draft_proposal`（`spec_utils.py:167`，温度缩放 + Gumbel 采样），收集 `draft_probs`；
   - topk=1 + CUDA：`draft_topk1_postprocess`（`sglang/kernels/ops/speculative/topk1.py`）写链式 `draft_tokens_topk1`；
   - topk>1：`renorm_draft_probs` + `fast_topk`（sgl_kernel）。
4. `per_step_draft_out_cache_loc`（`eagle_utils.py:64`）把 `(bs, topk, steps)` 缓存写目标按步切分写入草稿 KV。
5. topk=1 快速路径：`_rebuild_topk1_chain_buffers`（`base_spec_worker.py:112`）预分配 `parent_list`/`score_indices`，kernel 直接写链，免 `organize_draft_results`（`eagle_utils.py:107`，topk>1 时按 score 聚合成树）。

### draft → verify 的树形中间表示（`build_eagle_verify_input`，eagle_worker_common.py:316）

- `build_tree_kernel_efficient`（`eagle_utils.py:151`）：输入 `bonus_tokens + draft_tokens` 扁平 token 序列与 `parent_list / top_scores_index`，产出四件套：
  - `tree_mask`（`FULL_MASK`：`seq_lens_sum*n + n*n*bs` 展平布尔矩阵，GPU；`QLEN_ONLY`：n×n per-request，CPU；`QLEN_ONLY_BITPACKING`：bit 打包）；
  - `positions`（每个 draft token 的绝对位置 = seq_len + 深度）；
  - `retrieve_index / retrieve_next_token / retrieve_next_sibling`（树链式表示，供验收 kernel 遍历父链/兄弟链）。
- 树形状常量：`EagleVerifyInput.max_tree_depth = spec_steps + 1`、`tree_topk = topk`（`eagle_info.py:44-54`）。

### verify 阶段（`run_eagle_verify`，eagle_worker_common.py:461）

1. `eagle_prepare_for_verify`（`eagle_utils.py:497`）：设 `ForwardMode.TARGET_VERIFY`，`assign_extend_cache_locs_uniform_func` 分配 verify KV 位点，走 target 的 `decode_cuda_graph_runner.load_batch`（图路径）。
2. `target_worker.forward_batch_generation(batch=None, forward_batch=verify_forward_batch, is_verify=True)`——一次前向同时算所有 draft 位点 logits（**1 次 target 前向验证整棵草稿树**）。
3. `eagle_sample`（`eagle_utils.py:653`）：
   - penalty：`acc_additive_penalties / acc_scaling_penalties / logit_bias` 按 `draft_token_num` 重复展开（`eagle_utils.py:694-714`）；grammar mask 存在则 `grammar_mask.apply`。
   - greedy/CPU/NPU/HIP/XPU：`verify_tree_greedy_func`（`eagle_utils.py:378`，各平台有 kernel）——draft token == target argmax 即接受。
   - 随机采样：温度 softmax + top_k/top_p 重归一化后走 `tree_speculative_sampling_target_only`（树）或 `chain_speculative_sampling_triton`（topk=1 拒绝采样，`sglang/kernels/ops/speculative/reject_sampling.py`）；`draft_probs` 仅拒绝采样模式下产生（`eagle_info.py:30-32`）。
   - 可复现：`_verify_coins` / `_seeded_verify_coins`（`eagle_utils.py:583-650`）用 `murmur_hash32(seed, seq_lens, col)` 生成确定性拒绝币。
   - 产物：`predict`（per-node 预测 token）、`accept_lens = num_correct_drafts + 1`（含 bonus）、`accept_index`（`(bs, spec_steps+1)` 接受路径的全局节点索引）。
   - TP 一致性：ROCm/随机采样路径经 `tp_group.broadcast(predict/accept_index/num_correct_drafts, src=0)` 同步（`eagle_utils.py:745-871`）。
4. `fill_bonus_tokens_func`（`eagle_worker_common.py:616`）取接受链末端 target 预测为 bonus token，写入 `next_draft_input.bonus_tokens`（下轮树根）。
5. topk>1：`_finalize_accept_tree_path`（`eagle_worker_common.py:406`）压缩接受路径 KV/predict/hidden 到 req 块前端（`move_accept_tokens_to_target_kvcache`，`spec_utils.py:694`）；`compute_spec_logprobs`（`eagle_worker_common.py:627`）。
6. 混合架构（mamba）：`commit_mamba_states_after_verify`（`spec_utils.py:832`）。

### draft_extend：把验收结果填回草稿 KV（eagle_worker_v2.py:732 / 859）

- prefill 版（`_draft_extend_for_prefill`）：对 target prefill 输入做**左移旋转**（`input_ids[1:]+tail`，`eagle_utils.py:88`），以 `CaptureHiddenMode.LAST` 取末位 hidden 喂草稿头，产出首轮 `EagleDraftInput`。
- decode 版（`_draft_extend_for_decode`）：按 `num_correct_drafts = accept_lens - 1` / `num_accept_tokens` 决定每 req 回填数（`eagle_info.py:286-289`），`select_index` 只对每 req 最后接受行跑 lm_head；产出下轮 `EagleDraftInput`。
- `prepare_for_draft_extend`（`eagle_worker_common.py:105`）构造 `DRAFT_EXTEND_V2` forward：`extend_len = num_draft_tokens`（per-req 固定窗口），`prefix_len = seq_len - front_offset`，forward 后 `seq_lens + num_draft_tokens`。
- 草稿 decode 与 draft_extend 各有独立 CUDA graph runner；`_capture_cuda_graphs`（`eagle_worker_v2.py:346`）按设备选择 runner（cuda/xpu/musa → `EAGLEDraftCudaGraphRunner`，npu → NPU 版）。

### 多步注意力后端（`DraftBackendFactory`，draft_utils.py:27）

`create_decode_backend`（`:71`）按步建独立 attention 后端（flashinfer/triton/fa3/flashmla/dsa/dsv4 等 16 种，`:80-97`）；`create_draft_extend_backend`（`:106`）走 prefill 后端族。`steps <= 1` 时草稿 decode 后端为 None。

### MultiLayer Eagle（`--enable-multi-layer-eagle`）

`MultiLayerEagleWorkerV2`（`multi_layer_eagle_worker_v2.py:918`）持 `MultiLayerEagleDraftWorker`（`:110`），`draft_runners` 返回每层 runner 列表（`:189`），每步跑一层；draft-extend 有专用 multi-step runner（`multi_layer_eagle_draft_extend_cuda_graph_runner.py:132/501`）。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
