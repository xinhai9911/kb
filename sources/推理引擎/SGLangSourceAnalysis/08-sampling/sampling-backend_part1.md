## 采样后端流程与惩罚器

本文覆盖从 logits 产出到采样完成的完整链路：`LogitsProcessor`（`srt/layers/logits_processor.py`）→ penaltylib 惩罚器（`srt/sampling/penaltylib/`）→ `Sampler`（`srt/layers/sampler.py`）→ 采样内核。与 vLLM 的对照见 [sampling-backend_part2.md](sampling-backend_part2.md)。

### logits 处理阶段：LogitsProcessor

`LogitsProcessor(nn.Module)`（`logits_processor.py:283`）负责把模型 hidden states 变成下一 token 的 logits，输出 `LogitsProcessorOutput`（`logits_processor.py:96`）。关键路径：

| 步骤 | 行为 |
|---|---|
| 状态裁剪 `_get_pruned_states` | decode 用整批 hidden states；extend 按 `extend_seq_lens` 取每序列末位；带 input logprobs 的 extend 构造 `sample_indices`/`input_logprob_indices`/`token_to_seq_idx` 三组索引（支持 chunked prefill） |
| LM head `_compute_lm_head` | 经 `VocabParallelEmbedding` matmul；支持 LoRA 包装、量化方法（`should_apply_lm_head_quant_method`，`logits_processor.py:1035`）、FP32 head、GGUF |
| TP 汇聚 `_get_logits` | `do_tensor_parallel_all_gather` 时按 `use_attn_tp_group` 走 `_gather_attn_tp_logits` 或 `triton_symm_mem_ag.MultimemAllGatherer`；TP lm-head all-to-all 优化路径 `_tp_lm_head_all_to_all`（`logits_processor.py:844`）只交换目标 DP rank 的行块 |
| DP attention | `compute_dp_attention_metadata`（`logits_processor.py:250`）按 rank 计算 `dp_local_start_pos`/`dp_local_num_tokens`，`dp_gather_replicate` + `dp_scatter` |
| 后处理 | `final_logit_softcapping`（`softcap_inplace_logits`）、复制进共享 `next_token_logits_buffer`（`_copy_logits_to_buffer`，`logits_processor.py:869`，CUDA graph 缓冲） |

`LogitsMetadata`（`logits_processor.py:150`）是 forward 侧元数据载体，含 `forward_mode`、extend logprob 长度、DP 元数据与 `is_prefill_only` 等；`from_forward_batch` 从 `ForwardBatch` 派生。prefill-only 的 multi-item scoring（`compute_logprobs_for_multi_item_scoring`，`logits_processor.py:904`）在 delimiter 位置取样做 log_softmax 打分，不产出 `next_token_logits`。

### 惩罚器（penaltylib）

`BatchedPenalizerOrchestrator`（`penaltylib/orchestrator.py:13`）持有四个 penalizer 实例，每个按 `_is_required()` 惰性准备（`prepare_if_required`，`orchestrator.py:201`）。`apply(logits, repeat)` 支持投机解码：`repeat` 非 None 时把逐请求惩罚按 `repeat_interleave` 扩展到 draft token 布局（`orchestrator.py:55`）。惩罚分两类：

| 类别 | Penalizer | 张量形态 | 累积方式 | 施加公式 |
|---|---|---|---|---|
| 加性 additive | `BatchedFrequencyPenalizer`（`frequency_penalty.py:6`） | `cumulated_frequency_penalties` zeros `[bs, vocab]` + `frequency_penalties` `[bs,1]` | 每轮 `scatter_add_` | `logits -= freq_pen * count` |
| 加性 additive | `BatchedPresencePenalizer`（`presence_penalty.py:6`） | 同结构 zeros | 每轮 `scatter_`（出现即置值） | `logits -= presence_pen` |
| 乘性 multiplicative | `BatchedRepetitionPenalizer`（`repetition_penalty.py:18`） | `cumulated_repetition_penalties` ones `[bs, vocab]` | 每轮 `scatter_` | `apply_scaling_penalties`：`logits<0 → logits*pen`，否则 `logits/pen` |
| 加性 additive | `BatchedMinNewTokensPenalizer`（`min_new_tokens.py:6`） | `stop_token_penalties`（EOS/stop/additional stop 集合处 `-inf`）+ `len_output_tokens` | 每轮 `+=1` | `len < min_new_tokens` 时对 stop 集加 `-inf` |

orchestrator 还提供 `accumulate_additive_penalties` / `accumulate_scaling_penalties`（`orchestrator.py:88/94`，乘性惩罚以张量逐元素相乘聚合成一个）供 overlap 预累积路径使用；`filter`/`merge`/`release` 与批对齐。`apply_scaling_penalties` 用 `torch.where` 而非布尔掩码索引，避免每步 D2H 同步（`repetition_penalty.py:9` 注释）。

### 采样阶段：Sampler 与后端分派

`Sampler(nn.Module)`（`sampler.py:71`）的 `forward`（`sampler.py:98`）流程：

```python
1. _preprocess_logits: apply_custom_logit_processor（按 batch_mask 应用） + sanitize_nan_logits
2. 若 is_all_greedy: torch.argmax（或 aiter greedy_sample）→ 直接返回
3. 否则:
   logits.div_(sampling_info.temperatures)
   logits[:] = torch.softmax(logits, dim=-1)     # 就地 softmax 省显存
   batch_next_token_ids = _sample_from_probs(...)
```

`_sample_from_probs`（`sampler.py:250`）按 `get_exec().kernel.sampling_backend` 分派，`SAMPLING_BACKEND_CHOICES = {"flashinfer", "pytorch", "ascend"}`（`server_args.py:113`）：

| 后端 | 条件 | 实现 |
|---|---|---|
| `flashinfer` | `need_min_p_sampling` | `top_k_renorm_prob` → `top_p_renorm_prob` → `min_p_sampling_from_probs`（sgl_kernel） |
| `flashinfer` | 否则 | `top_k_top_p_sampling_from_probs(probs, top_ks, top_ps, filter_apply_order="joint")`（flashinfer.sampling） |
| `pytorch` | — | `top_k_top_p_min_p_sampling_from_probs_torch`（`sampler.py:567`）：降序 sort → cumsum → top-k/top-p/min-p 掩零 → `torch.multinomial` 或 `multinomial_with_seed` |
| `ascend` | — | `_forward_ascend_backend`：直接从温度缩放后的 logits 采样，`torch_npu.npu_top_k_top_p`（top_k 需在 `[1,1024]`） |

注意约束：flashinfer 后端不支持 `sampling_seed`（断言，`sampler.py:271`）；简单采样情形（无 top-k/p/min-p）直接走 `sampling_from_probs_torch`（`sampler.py:732`），此时 seed 可用。

**确定性采样**：`multinomial_with_seed`（`sampler.py:687`，`@torch.compile`）用 Gumbel trick——`murmur_hash32(seed, positions, col_indices)`（triton kernel，`kernels/ops/sampling/murmur_hash.py`）生成逐行均匀数，转 Gumbel 噪声加到 float64 logprobs 后 `argmax`，是 `torch.multinomial` 的可复现替代。RL on-policy 路径（`rl_on_policy_target` 非 None）用 `log_softmax` 计算 logprob 对齐训练器，并从 logprobs 采样（`sampler.py:159`）。

**logprob 与 TP 同步**：`OutputLogprobProcessor`（`layers/logprob_processor.py`）计算 top-k/指定 token 的 logprob 写回 `LogitsProcessorOutput`；`SGLANG_RETURN_ORIGINAL_LOGPROB` 控制是否用温度缩放前的 logits 算 logprob（`sampler.py:66`）。`_sync_token_ids_across_tp`（`sampler.py:497`）仅在 `SYNC_TOKEN_IDS_ACROSS_TP` 或使用 grammar 时对 token id 做 `all_reduce MIN`——默认不同步，依赖采样内核确定性。

**自定义采样器**：`register_sampler_backend`（`sampler.py:531`）注册工厂并加入 `SAMPLING_BACKEND_CHOICES`；`create_sampler`（`sampler.py:545`）按 `sampling_backend` 构造，内置后端（`_BUILT_IN_SAMPLING_BACKENDS = {"flashinfer","pytorch","ascend"}`）统一返回默认 `Sampler()`。

### 采样内核组织

`sgl_kernel` 提供 AOT 采样算子 `top_k_renorm_prob`/`top_p_renorm_prob`/`min_p_sampling_from_probs`，经 `kernels/ops/sampling/__init__.py` 的 `register_kernel(KernelSpec(op="sampling.top_k_renorm_probs", ...))` 注册。ROCm 回退为 Triton 实现（`kernels/ops/sampling/renorm_triton.py`）：`top_k_renorm_probs_triton`/`top_p_renorm_probs_triton` 用 PyTorch 的 sort/cumsum 求 pivot（词表 10 万级不适合 Triton 寄存器排序），再用 `_mask_and_partial_sum_kernel` + `_normalize_kernel` 做掩码与重归一化。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
