## 推测解码（Speculative Decoding）

以源码为准的机制概览。涉及 `vllm/v1/spec_decode/`（提案器）与 `vllm/v1/sample/rejection_sampler.py`、`vllm/v1/worker/gpu/spec_decode/`（验证器）。

### 并行采样 vs 推测采样

- 普通 decode：每步 1 次 target 模型前向，产生 1 个 token。
- 并行采样（parallel drafting）：一个前向同时采样多个 token（DFlash 等，全部草案一步提出），confidence-based 验证。
- 推测采样：先用便宜的草案模型（draft）自回归生成 K 个候选 token，再用 target 模型一次前向批量验证，接受一致的 draft token，其余按校准分布补采样——每步多位点验证，K 个 draft 只需 1 次 target 前向 + K 次小 draft 前向。

### 配置（SpeculativeConfig）

| 字段 | 说明 |
|------|------|
| `method` | 草案方法：`ngram`、`medusa`、`mlp_speculator`、`draft_model`、`suffix`、`custom_class`、`eagle`/`eagle3`、`extract_hidden_states`、`dflash`、`ngram_gpu`、`dspark` 及多种 `*_mtp`（DeepseekMTP 等） |
| `num_speculative_tokens` | 每步草案 token 数（单步上限 MAX_SPEC_LEN=128，未确认是否纳入所有路径） |
| `rejection_sample_method` | `standard`（论文拒绝采样）/ `synthetic`（预置接受率）/ `block`（块验证） |
| `draft_sample_method` | `greedy`（默认，argmax）或 `probabilistic`（按概率采样） |
| `enable_adaptive_verification` | 仅 DSpark 动态草案预算；开启时不能同时输出 logprobs |
| `use_heterogeneous_vocab` | 草案与 target 词表不同时的 VocabMapping 映射 |
| `model` / `draft_model_config` | 草案模型权重与配置 |

### 提案阶段（proposer）

- 基类 `SpecDecodeBaseProposer`（llm_base_proposer.py）：统一 eagle/draft_model/并行起草。`needs_extra_input_slots`（draft model 或并行起草需扩展输入槽），用 triton kernel 复制并扩展 input_ids/positions/slot_mapping，被拒 token 用 padding 占位后由 `token_indices_to_sample` 过滤。
- 子类：`DraftModelProposer`（独立草案模型，要求 draft TP 与 target 相同、词表同构或用 VocabMapping 约束）、`EAGLE`（eagle.py，接收 target hidden states）、`NgramProposer`（numba CPU，基于 prompt n-gram 匹配）、`ngram_proposer_gpu`、`Medusa`、`custom_class_proposer`、`dflash`（parallel drafting）、`step3p5`、`suffix_decoding` 等。
- draft token 默认贪心：`compute_logits(...).argmax`；`use_local_argmax_reduction` 可用局部 argmax 减少 TP 通信；`probabilistic` 时 `compute_probs_and_sample_next_token` 只按温度缩放（忽略其余采样参数，不影响拒绝采样后分布）。
- EAGLE/MTP 类草案复用 target 的 embedding 与 lm_head 权重（`_maybe_share_embeddings`/`_maybe_share_lm_head`）。

### 验证阶段（RejectionSampler，arXiv:2211.17192）

- `vllm/v1/sample/rejection_sampler.py`：输入 `draft_probs`（可选，ngram 无法提供）与 target `logits`（[num_tokens + batch, vocab]），输出 `SamplerOutput`。
- 术语：accepted（接受）、recovered（按校准分布补采）、bonus（全部接受后追加，由 target 单独采样，可带 top_p/top_k）；`output = accepted + recovered + bonus`。
- greedy 验证：draft token == target argmax 即接受，否则拒绝。
- 随机验证：`accepted = draft_prob>0 and target_prob/draft_prob >= uniform_prob`；拒绝后从 `max(target_prob - draft_prob, 0)`（Gumbel 技巧取 argmax）采样 recovered token。
- 实现为 triton kernel：`rejection_greedy_sample_kernel` 与 `rejection_random_sample_kernel`（逐位置循环，`use_fp64` 统一噪声），`generate_uniform_probs` 用 float64 防 0.0。
- `apply_sampling_constraints`：对草案位置应用温度 + top_k/top_p 展开（`expand_batch_to_tokens`）；min_tokens 用 `apply_with_spec_decode` 按草案位置掩码 stop token。
- 新版 `vllm/v1/worker/gpu/spec_decode/rejection_sampler.py`：面向 InputBatch，分块验证控制 FP32 缓冲（1GB 上限），支持 `block` 方法（块级验证，未确认细节）与 `synthetic`。
- 每步返回 `num_sampled` / `num_rejected`，供调度计算下轮草案预算；`parse_output` 用 PLACEHOLDER_TOKEN_ID(-1) 过滤被拒位置。

### 工作流（每步）

1. drafter 用上轮验证结果生成 K 个草案 token（含可能被拒位置的替换）。
2. target 一次前向：对草案位置 + bonus 位置同时算 logits（`SpecDecodeMetadata` 组织 `target_logits_indices`/`bonus_logits_indices`）。
3. 验证（见上），产出 accepted+recovered+(bonus)，过滤占位符。
4. 被拒位置进入下轮草案输入重建（Eagle 用 `is_rejected_token_mask` 打 padding）。

### 限制

- `min_p>1e-5` 与 `logit_bias` 暂不支持推测解码（VLLMValidationError）。
- 自定义 logits processors 不支持推测解码；默认只保留 MinTokens。
- `rejection_sample_method='synthetic'` 需且仅需 `synthetic_acceptance_rates` 与 `synthetic_acceptance_rates_by_length` 二者之一。
- 输出 logprobs 与 DSpark 自适应验证互斥。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)