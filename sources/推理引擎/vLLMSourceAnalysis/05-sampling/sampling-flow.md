## 采样管线：Logits → 概率 → Token

核心实现为 `vllm/v1/sample/sampler.py` 的 `Sampler`（nn.Module 层），配合 `vllm/v1/sample/metadata.py` 的 `SamplingMetadata` 与 `vllm/v1/sample/logits_processor/` 的处理器链。

### 管线总览（Sampler.forward）

1. 若请求 logprobs：`raw_logprobs` 模式用 `logits.log_softmax` 从原始 logits 计算；`raw_logits` 模式直接克隆 logits（保留用于 top-k logprobs，先于惩罚与温度，与 V0 不同）。
2. logits 转 float32。
3. 应用 allowed token ids 白名单（masked_fill -inf）。
4. 应用 bad words 排除。
5. 应用非 argmax 不变 logits 处理器（min_tokens、logit_bias）。
6. 应用惩罚（repetition/frequency/presence）。
7. `sample()` 采样：
   - 非 all_random 先做贪心 argmax；all_greedy 直接返回。
   - 温度缩放。
   - 应用 argmax 不变处理器（默认 min_p）。
   - top_k/top_p 过滤。
   - 随机采样；非 all_random 时按温度<eps(1e-5) 选择贪心或随机结果。
8. 收集 top `max_num_logprobs` 与采样 token 的 logprobs；采样 token 在 top-k 内时最终为 max_num_logprobs 或 max_num_logprobs+1 个。
9. 返回 `SamplerOutput`。

### LogitsProcessor 工厂与链

- 工厂 `build_logitsprocs(vllm_config, device, is_pin_memory)`：内置处理器 `BUILTIN_LOGITS_PROCESSORS` = MinTokens → LogitBias → MinP，其后追加自定义处理器。
- 自定义处理器加载：入口点组 `vllm.logits_processors` 的插件 + 初始化时按 FQCN（`module:Class`）指定；经 `AdapterLogitsProcessor` 逐请求包装。
- `LogitsProcessors` 按 `is_argmax_invariant()` 分为两组：`non_argmax_invariant`（min_tokens、logit_bias，可改变贪心结果，采样前任意情况都应用）与 `argmax_invariant`（min_p，仅随机采样时应用）。
- 三个内置处理器：MinTokens 将 stop/EOS token 置 -inf 直至达到 min_tokens；LogitBias 按 `logits[row, token] += bias` 施加；MinP 用 `softmax` 后与 `max_prob * min_p` 比较并 mask。
- pooling 模型拒绝自定义处理器；推测解码启用时只保留 MinTokens，并告警 min_p/logit_bias 不生效。
- 每步前通过 `BatchUpdateBuilder`→`BatchUpdate`（removed/added/moved）同步请求增删搬移状态。

### SamplingMetadata 结构

| 字段 | 类型 | 说明 |
|------|------|------|
| `temperature` | Tensor | 逐请求温度 |
| `all_greedy` / `all_random` | boolean | 全贪心 / 全随机批优化标志 |
| `top_p` / `top_k` | Tensor | 逐请求 top-p/top-k（None 表示不启用） |
| `generators` | dict | req_index → torch.Generator（逐请求 seed） |
| `max_num_logprobs` | integer | None 不返回，0 仅采样 token，-1 全词表 |
| `no_penalties` | boolean | 全部请求无惩罚的快速路径 |
| `prompt_token_ids`、`frequency_penalties`、`presence_penalties`、`repetition_penalties` | Tensor | 惩罚输入 |
| `output_token_ids` | array | 已生成 token，惩罚/bad words 判重依据 |
| `allowed_token_ids_mask` | Tensor | 白名单掩码 |
| `bad_words_token_ids` | dict | req_index→禁止 token 序列 |
| `logitsprocs` | LogitsProcessors | 处理器链 |
| `logprob_token_ids` | dict | 指定 token id 的 logprobs 收集 |
| `spec_token_ids` | array | 推测解码草稿 token |
| `thinking_budget_state_holder` | object | 思考预算状态 |

### 采样实现要点

- 温度缩放 `apply_temperature`：非 all_random 时将 temp<1e-5 的行替换为 1.0（避免除零），再 `logits.div_(temp)`（原地）。
- 贪心：`logits.argmax(dim=-1)`。
- `TopKTopPSampler`：PyTorch-native 路径先 sort 出 -inf 掩码再 scatter 回来；CPU/小批量用 PyTorch 实现，CUDA/批量大走 Triton；FlashInfer 抽样（拒绝采样，不排序，需无 per-request generator 且非 processed 模式）；ROCm/XPU 有 aiter/xpu 内核。
- 随机采样 `random_sample`：避免 `torch.multinomial` 的 CPU-GPU 同步，用 Gumbel 技巧——生成指数噪声 q，`probs/q` 取 argmax；逐请求有 seed 时 `q[i].exponential_(generator=...)`。可选 `use_fp64_gumbel` 用 float64。
- 惩罚 `apply_penalties`（model_executor/layers/utils.py）：repetition 走自定义 kernel；frequency：`logits -= freq_penalty * output_bin_counts`；presence：`logits -= presence_penalty * output_mask`。
- logprobs 收集 `gather_logprobs`：topk + gather 采样 token，`batched_count_greater_than` 计 rank；int32 结果；`logprob_token_ids` 走按需 gather（genrative-scoring API）。
- 输出 `SamplerOutput`（v1/outputs.py）：`sampled_token_ids`（[num_reqs,1]，int32）+ `LogprobsTensors`（`logprob_token_ids`/`logprobs`/`selected_token_ranks` 三个 GPU Tensor，可选 `cu_num_generated_tokens`）。

### 旧/新两套采样器对比

V0 风格 `vllm/v1/sample/sampler.py`（nn.Module + SamplingMetadata）由 `vllm/v1/worker/gpu_model_runner.py` 调用，也供推测解码 rejection sampler 与 MTP 模型复用。较新的 `vllm/v1/worker/gpu/sample/sampler.py` 直接面向 `InputBatch`/`RequestState` 持久化状态，由 `vllm/v1/worker/gpu/model_runner.py` 使用：

| 维度 | v1/sample/sampler.py | v1/worker/gpu/sample/sampler.py |
|------|------|------|
| 输入 | SamplingMetadata（字典式） | InputBatch + 持久化状态对象 |
| 顺序 | allowed→bad_words→非 argmax 处理器→惩罚 | logit_bias_state（allowed+logit_bias+min_tokens）→ penalties → bad_words → thinking_budget → 温度 → min_p → top_k/top_p |
| 随机采样 | gumbel_sample（exponential noise）+ TopKTopPSampler | gumbel_sample（内置温度/seed）+ flashinfer_sample |
| 状态管理 | BatchUpdateBuilder 逐请求 partial | SamplingStates/PenaltiesState 等张量状态 + 分阶段写入 |
| 采样掩码 | 无 | `SamplingMaskTensors`（return_sampling_mask 时） |
| 用途 | gpu_model_runner（旧） | gpu/model_runner（新） |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)