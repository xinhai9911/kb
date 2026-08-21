## 采样体系与 vLLM 对照

续接 [sampling-backend_part1.md](sampling-backend_part1.md)（后端流程），本文给出 SGLang 与 vLLM 在采样体系上的对照，基线 vLLM 源码为 `vllm/sampling_params.py` 与 `vllm/v1/sample/`。

### 参数模型对照

| 维度 | SGLang `SamplingParams` | vLLM `SamplingParams` |
|---|---|---|
| 结构 | `srt/sampling/sampling_params.py:45`，`msgspec.Struct`（kw_only, array_like） | `vllm/sampling_params.py:215`，pydantic/msgspec dataclass |
| 采样分布 | `temperature`/`top_p`/`top_k=TOP_K_ALL`/`min_p`；贪心 = `top_k<=1` | 同字段但 `top_k=0` 表示禁用（`sampling_params.py:259`）；`SamplingType`（GREEDY/RANDOM/RANDOM_SEED）推断：`top_k==1` 且温度<eps 为贪心 |
| 长度 | `max_new_tokens=128`/`min_new_tokens`/`n=1` | `max_tokens=16`/`min_tokens` |
| 停止 | `stop`/`stop_token_ids`/`stop_regex`（内部归一化为 `stop_strs`/`stop_regex_strs`） | `stop`/`stop_token_ids`/`include_stop_str_in_output` |
| 约束 | `logit_bias`/`json_schema`/`regex`/`ebnf`/`structural_tag`（互斥） | `logit_bias`/`allowed_token_ids`/`bad_words`/`StructuredOutputsParams`（json/regex/choice/grammar/json_object/structural_tag） |
| 归一化时机 | 调度侧 `normalize(tokenizer)` 用 sre_parse 算 regex 上界、清空 API 别名 | `update_from_generation_config`（`sampling_params.py:656`）+ `verify`（`sampling_params.py:774`） |

### 批量张量化对照

| 维度 | SGLang `SamplingBatchInfo` | vLLM v1 `SamplingMetadata` |
|---|---|---|
| 来源 | `sampling_batch_info.py:29`，dataclass，`from_schedule_batch` 逐请求构张量 | `vllm/v1/sample/metadata.py:15`，由 `SampleArgs.from_sampler_state` 组装 |
| 粒度 | `temperatures[bs,1]`、`top_ps`、`top_ks`、`min_ps` 每**请求**一行 | `temperature`/`top_p`/`top_k` 每**token**一行（投机解码每位置一 token） |
| 标志 | `is_all_greedy`/`is_any_greedy`/`need_top_p_sampling`/`need_top_k_sampling`/`need_min_p_sampling` | `all_greedy`/`all_random` |
| 随机源 | `sampling_seed` 张量（确定性推理时）+ `murmur_hash32` Gumbel | `generators: dict[int, torch.Generator]` 逐请求生成器 |
| 惩罚张量 | penalizer 累积 `[bs, vocab]` 张量（frequency/presence/repetition/min_new_tokens 四类） | `frequency_penalties`/`presence_penalties`/`repetition_penalties`（每 token 一标量）+ `prompt_token_ids` |
| logprob 需求 | `top_logprobs_nums`/`token_ids_logprobs`（`ForwardBatch` 携带） | `max_num_logprobs`/`logprob_token_ids`（精确 token logprob，`metadata.py:47`） |

### 采样步骤对照

| 维度 | SGLang `Sampler.forward`（`layers/sampler.py:98`） | vLLM v1 `Sampler.forward`（`vllm/v1/sample/sampler.py:73`） |
|---|---|---|
| 预处理 | custom logit processor（dill 序列化，按请求掩码应用）→ `sanitize_nan_logits` | 允许 token 白名单 → bad words → 非 argmax 不变式 logit processor（min tokens/logit bias） |
| 惩罚 | 由 `apply_logits_bias` 在采样前施加（penaltylib 张量） | 采样内按序施加 repetition → frequency → presence |
| 分布处理 | `logits.div_(temperatures)` → 就地 `softmax` → 在 probs 上做 top-k/p/min-p 重归一化（`renorm`）后采样 | 保留 logits：`sample()` 内先温度，再 argmax 不变式 processor（min_p），再 `TopKTopPSampler` 做 top-k/top-p 掩码 |
| 贪心短路 | `is_all_greedy` 直接 `torch.argmax` | `all_greedy`/`all_random` 短路；`temperature<eps` 时用 `torch.where(temperature<eps, greedy, random)` 混合（`sampler.py:297`） |
| 随机采样 | flashinfer 融合算子（`filter_apply_order="joint"`）/ pytorch multinomial / Gumbel | `TopKTopPSampler`：`torch.multinomial` 或 gumbel（`use_fp64_gumbel` 可选）；采样结果 int32 与 int64 显式转换（`sampler.py:108` 注释，FlashInfer 返回 int32） |
| 确定性 | `multinomial_with_seed`（murmur_hash32 + Gumbel，float64） | 每请求 `torch.Generator`（seed 支持），`RANDOM_SEED` 采样类型 |
| logprob 取点 | `OutputLogprobProcessor`；`SGLANG_RETURN_ORIGINAL_LOGPROB` 切换原始/处理后的 logprob | 用**采样前原始 logits** 算 top-k logprobs（`sampler.py:81` 注释，与 v0 行为差异）；`gather_logprobs` 返回 top-k+采样 token 及 rank |
| 输出 | `batch_next_token_ids`（int32）写回 `GenerationBatchResult` | `SamplerOutput(sampled_token_ids.unsqueeze(-1), logprobs_tensors)` |
| 投机解码 | 惩罚 `apply(repeat)` 展开、自定义 processor 按 `num_tokens_in_batch` 展开（`sampler.py:768`） | `spec_token_ids` + 采样后 rejection sampler（`vllm/v1/sample/rejection_sampler.py`） |

### 关键差异小结

- **张量粒度不同**：SGLang decode 每请求采 1 个 token，张量按请求行；vLLM v1 采样在「token 空间」上做（投机解码一位置一 token），`SamplingMetadata` 的每行对应一个 token。
- **probs vs logits 采样**：SGLang 标准路径先 softmax 成 probs 再采样（pytorch 后端掩零后 `multinomial`；flashinfer 对 probs 做 renorm）；vLLM v1 从 logits 直接采样，温度/top-k/top-p/min-p 均为 logits 级处理（min_p 作为 logit processor，`sampler.py:283`）。
- **贪心判定**：SGLang 用 `top_k<=1` 聚合为 `is_all_greedy` 短路；vLLM 用 `SamplingType` 枚举 + `temperature<eps` 在结果处混合。
- **惩罚实现形态**：SGLang 惩罚是 `[bs, vocab]` 的完整张量（重复/频率/存在罚按词表累积）；vLLM v1 惩罚是每 token 标量配合 `prompt_token_ids` 在采样器内计数施加。
- **确定性采样**：SGLang 的 `sampling_seed` 依赖自定义 `murmur_hash32` + Gumbel 并限制后端（flashinfer 不支持）；vLLM 用标准 `torch.Generator`，与推理框架无关。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
