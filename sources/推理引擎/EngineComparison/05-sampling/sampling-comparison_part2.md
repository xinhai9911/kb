## vLLM vs SGLang 采样体系对比（二）：采样后端、logits 处理与惩罚器

承接 [sampling-comparison.md](sampling-comparison.md)（参数模型与批量张量化）。本文对比采样内核选择、logits 处理链与惩罚器。

### 一、采样后端对比

| 维度 | vLLM v1 `Sampler` | SGLang `Sampler` |
|---|---|---|
| 位置 | `vllm/v1/sample/sampler.py:73`（nn.Module，`Sampler.forward`），另有 `vllm/v1/worker/gpu/sample/sampler.py`（新 InputBatch 风格） | `srt/layers/sampler.py:98`（nn.Module，`Sampler.forward(logits_output, sampling_info)`） |
| 后端选择 | `TopKTopPSampler` 内部分派：PyTorch-native / Triton（CUDA 大批量）/ FlashInfer 拒绝采样 / aiter（ROCm）/ xpu | `sampling_backend` 参数三选一 `{"flashinfer","pytorch","ascend"}`（`server_args.py:113`）；可 `register_sampler_backend` 扩展（`sampler.py:531`） |
| 处理空间 | **logits 级**：温度/top-k/top-p/min-p 全在 logits 上操作 | **probs 级**：`logits.div_(temperatures)` 后**就地 softmax**（省显存），再在 probs 上 renorm |
| 采样步骤 | greedy argmax 兜底 → `apply_temperature`（temp<1e-5 置 1.0 防除零）→ argmax 不变式处理器（min_p）→ `TopKTopPSampler` | `_preprocess_logits`（自定义 processor + NaN 清洗）→ `is_all_greedy` 时 `torch.argmax`（或 aiter greedy）→ 否则 `div`+`softmax`+`_sample_from_probs`（`sampler.py:250`） |
| 贪心短路 | `all_greedy`/`all_random` 短路；非全随机时 `torch.where(temperature<eps, greedy, random)` 混合（`sampler.py:297`） | `is_all_greedy`（全部 `top_k<=1`）短路 `torch.argmax`；`is_any_greedy` 时逐请求选择 |
| 随机采样 | `torch.multinomial` 或 **Gumbel trick**（指数噪声 q，`probs/q` 取 argmax，避免 CPU-GPU 同步；`use_fp64_gumbel` 可选） | flashinfer `top_k_top_p_sampling_from_probs(..., filter_apply_order="joint")` 融合算子；pytorch 后端 `sort→cumsum→掩零→multinomial`；ascend 后端 `npu_top_k_top_p` |
| min_p 处理 | 内置 MinP logit processor（softmax 后与 `max_prob*min_p` 比较 mask），仅随机采样时应用 | flashinfer 走 `min_p_sampling_from_probs`（sgl_kernel AOT），按 `need_min_p_sampling` 分派；pytorch 后端统一 torch 路径 |
| 确定性采样 | 每请求 `torch.Generator`（`RANDOM_SEED` 类型），与后端无关 | `multinomial_with_seed`（`@torch.compile`，`sampler.py:687`）：`murmur_hash32`（triton kernel）生成逐行均匀数转 Gumbel，加 float64 logprobs 后 argmax；**flashinfer 不支持 `sampling_seed`**（断言，`sampler.py:271`） |
| logprobs 取点 | **采样前原始 logits** 算 top-k logprobs（`sampler.py:81` 注释，与 v0 差异）；`gather_logprobs` 返回 top-k+采样 token 及 rank（int32） | `OutputLogprobProcessor` 写回 `LogitsProcessorOutput`；`SGLANG_RETURN_ORIGINAL_LOGPROB` 切换原始/处理后 logits |
| 输出 | `SamplerOutput(sampled_token_ids[bs,1], LogprobsTensors)` | `batch_next_token_ids`（int32）写回 `GenerationBatchResult` |
| 投机解码 | `spec_token_ids` + 采样后 rejection sampler（`vllm/v1/sample/rejection_sampler.py`） | 惩罚 `apply(repeat)` 按 draft 布局展开（`orchestrator.py:55`）；processor 按 `num_tokens_in_batch` 展开（`sampler.py:768`） |
| TP 一致性 | 词表并行经 `get_top_tokens()` 免全 gather argmax（本地 argmax + all-gather 值/索引对归约） | `_sync_token_ids_across_tp`（`sampler.py:497`）仅 `SYNC_TOKEN_IDS_ACROSS_TP` 或 grammar 时 `all_reduce MIN`，默认不同步 |

**关键差异**：
- **logits vs probs**：vLLM 全程 logits 级处理（min_p 也是 logit processor）；SGLang 先 softmax 成 probs 再 renorm/采样，flashinfer 对 probs 做 `top_k_renorm_prob`→`top_p_renorm_prob`→`min_p_sampling_from_probs`。
- **后端形态**：vLLM TopKTopPSampler 按平台/批量内部分派；SGLang 用独立 `sampling_backend` 启动参数三选一，flashinfer 融合且 `filter_apply_order="joint"`。
- **确定性**：vLLM 的 Generator 方案无后端限制；SGLang 的 murmur_hash Gumbel 方案更可控但锁死后端。

### 二、logits 处理链对比

| 维度 | vLLM | SGLang |
|---|---|---|
| 上游 | `vllm/model_executor/layers/logits_processor.py`：LM head（`_apply_head`，fp32 out_dtype）→ TP 时 all-gather → 截 vocab padding → soft_cap（Gemma2）→ scale | `srt/layers/logits_processor.py:283`：`_compute_lm_head`（LoRA/量化/FP32/GGUF）→ `_get_logits`（`triton_symm_mem_ag` 或 `_tp_lm_head_all_to_all` 只交换目标 rank 行块）→ DP attention → `final_logit_softcapping` → 复制进 CUDA graph 缓冲 |
| 采样侧处理器链 | `build_logitsprocs` 工厂，`BUILTIN_LOGITS_PROCESSORS` = MinTokens → LogitBias → MinP；后接插件（入口点 + FQCN）；按 `is_argmax_invariant()` 分两组（non_argmax：min_tokens/logit_bias 采样前必应用；argmax_invariant：min_p 仅随机采样） | 采样前 `apply_logits_bias`（`sampling_batch_info.py:283`）：非 overlap 用 orchestrator.apply、overlap 用预累积缓冲双路径，把惩罚/文法掩码/logit_bias 施加到 logits |
| 自定义处理器 | `AdapterLogitsProcessor` 逐请求包装，无 dill | 自定义 logit processor **dill 序列化**随请求传输，`apply_custom_logit_processor` 按请求掩码批量应用（`sampler.py:90`） |
| 文法/结构化约束 | `structured_outputs` 六选一由引擎约束机制转换（KB 未含约束后端细节）；SamplingMetadata 无 grammar 掩码字段 | `grammars`/`grammar_mask` 显式携带文法掩码，采样前随 `apply_logits_bias` 一并施加 |
| NaN 处理 | 无专门说明 | `sanitize_nan_logits`（`_preprocess_logits` 内） |

### 三、惩罚器实现对比

| 惩罚 | vLLM | SGLang |
|---|---|---|
| 通用形态 | 每 token 标量 penalty 参数（`frequency_penalties` 等）+ `prompt_token_ids`/`output_token_ids` 序列，`apply_all_penalties` 内计数施加（`model_executor/layers/utils.py`） | `BatchedPenalizerOrchestrator`（`penaltylib/orchestrator.py:13`）持有四类 Penalizer，各按 `_is_required()` 惰性准备；惩罚为 `[bs,vocab]` 累积张量 |
| frequency | `logits -= freq_penalty * output_bin_counts` | `BatchedFrequencyPenalizer`（`frequency_penalty.py:6`）：`[bs,vocab]` 每轮 `scatter_add_`，`logits -= freq_pen*count` |
| presence | `logits -= presence_penalty * output_mask` | `BatchedPresencePenalizer`（`presence_penalty.py:6`）：每轮 `scatter_`（出现即置值），`logits -= presence_pen` |
| repetition | **自定义 CUDA kernel**（不走通用张量运算） | `BatchedRepetitionPenalizer`（`repetition_penalty.py:18`）：乘性 scaling，初始 ones、每轮 `scatter_`；`torch.where` 分 `logits<0→logits*pen, 否则 logits/pen`，避免 D2H 同步（`repetition_penalty.py:9`） |
| min_tokens | MinTokens **logit processor**：stop/EOS 置 -inf 直至达到 min_tokens（非 penalizer 形态） | `BatchedMinNewTokensPenalizer`（`min_new_tokens.py:6`）：`stop_token_penalties`（EOS/stop 集 -inf）+ `len_output_tokens` 每轮 `+=1` |
| 施加顺序 | repetition → frequency → presence（`apply_all_penalties`） | 分加性/乘性两类；overlap 模式经 `accumulate_additive_penalties`/`accumulate_scaling_penalties`（乘性逐元素相乘聚合，`orchestrator.py:88,94`）预累积 |
| 投机兼容 | 同一采样器内处理 | `apply(logits, repeat)` 支持展开到 draft token 布局 |
| 批维护 | 由 `BatchUpdate` 同步每请求状态 | orchestrator 提供 `filter`/`merge`/`release` 与批对齐 |

**关键差异**：
- **存储形态**：vLLM 惩罚参数是每 token 标量、采样时按 token 序列实时计数；SGLang 维护 `[bs,vocab]` 完整累积张量（frequency/presence 加性、repetition 乘性），贴 GPU 批量运算但占用 O(bs×vocab) 显存。
- **repetition_penalty**：vLLM 走专用 kernel；SGLang 用 `torch.where` 乘除变换避免布尔索引 D2H 同步。
- **min_tokens 归属**：vLLM 归为 logit processor（可提前融合），SGLang 归为第四类 Penalizer（计入 orchestrator）。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
