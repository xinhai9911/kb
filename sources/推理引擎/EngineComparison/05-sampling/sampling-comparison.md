## vLLM vs SGLang 采样体系对比（一）：SamplingParams 与批量张量化

本模块对比两大引擎的采样子系统。事实基准：vLLM V1（`vllm/sampling_params.py`、`vllm/v1/sample/`，KB 见 `vLLMSourceAnalysis/05-sampling/`、`21-model-layers/sampler-pooling.md`）与 SGLang SRT（`srt/sampling/`、`srt/layers/sampler.py`，KB 见 `SGLangSourceAnalysis/08-sampling/`）。采样后端/logits 处理见 [_part2](sampling-comparison_part2.md)。

### 一、SamplingParams 参数模型对比

| 维度 | vLLM `SamplingParams` | SGLang `SamplingParams` |
|---|---|---|
| 定义位置 | `vllm/sampling_params.py:215`，pydantic + msgspec | `srt/sampling/sampling_params.py:45`，`msgspec.Struct(kw_only, array_like)`，经 msgpack IPC 传输 |
| 采样类型 | `SamplingType`（IntEnum）：GREEDY=0 / RANDOM=1 / RANDOM_SEED=2，由 `temperature<1e-5` 推断（`sampling_params.py:80-83,738`） | 无类型枚举，贪心判定为 `top_k<=1` |
| `temperature` | 默认 1.0，范围 [0,2]；`0<temp<0.01` 钳制到 0.01（`_MAX_TEMP=1e-2`）；`<1e-5`（`_SAMPLING_EPS`）视为贪心 | 默认 1.0；`0<=temp<1e-6` 时置 `temperature=1.0, top_k=1`（`_SAMPLING_EPS=1e-6`，`sampling_params.py:40,91`） |
| `top_p` | 默认 1.0，范围 (0,1] | 同 (0,1] |
| `top_k` | 默认 0；0/-1 表示禁用，启用须 >=1 | 默认 `TOP_K_ALL=1<<30`（`sampling_params.py:40`），-1 同义 |
| `min_p` | 默认 0.0，范围 [0,1] | 同 [0,1] |
| `seed` | `seed`，-1 视为 None | `sampling_seed`（仅确定性推理启用时生效） |
| `logit_bias` | token_id→bias，钳制到 [-100,100]，须为词表内 id | 同语义，键须在词表内 |
| 长度控制 | `max_tokens=16`、`min_tokens=0`（<=max） | `max_new_tokens=128`、`min_new_tokens=0`（<=max） |
| 停止条件 | `stop`、`stop_token_ids`、`include_stop_str_in_output`、`ignore_eos` | `stop`、`stop_token_ids`、**`stop_regex`**（正则停止，vLLM 无）、`no_stop_trim`、`ignore_eos`；内部归一化为 `stop_strs`/`stop_regex_strs` |
| logprobs | `logprobs`、`prompt_logprobs`（-1 全词表）、`logprob_token_ids`（<=128，`MAX_LOGPROB_TOKEN_IDS`）、`flat_logprobs` | `top_logprobs_nums`/`token_ids_logprobs`（由 `ForwardBatch` 携带） |
| 结构化输出 | `structured_outputs`：json/regex/choice/grammar/json_object/structural_tag 六选一，多选报错 | `json_schema`/`regex`/`ebnf`/`structural_tag` 四者互斥（`verify` 断言至多一个非 None） |
| 词表约束 | `allowed_token_ids`（白名单）、`bad_words`（禁止词，上限 `VLLM_MAX_NUM_BAD_WORDS`） | 无白名单/坏词字段，仅 `logit_bias` |
| 扩展通道 | `extra_args`（引擎内不使用）、`repetition_detection`（N-gram 提前终止） | `custom_params`（须为 JSON 安全值，`CustomParamValue`，供自定义 logit processor 使用） |
| 返回数 | `n`，上限 `VLLM_MAX_N_SEQUENCES`（默认 16384）；贪心时 n 必须为 1 | `n=1` |
| 归一化时机 | `update_from_generation_config` + 引擎侧 `verify(model_config, ...)` 深度校验 | `__post_init__`（None 落默认）+ `verify(vocab_size)` + 调度侧 `normalize(tokenizer)`（sre_parse 算 regex 上界、清空 API 别名） |

**关键差异**：
- **贪心判定口径**：vLLM 以 `temperature<1e-5` 推断 `SamplingType.GREEDY`，并对零温强制 n=1；SGLang 以 `top_k<=1` 聚合为 `is_all_greedy` 短路，零温 `0<=temp<1e-6` 时强制置 `temp=1.0, top_k=1`。
- **top_k 禁用语义**：vLLM `top_k=0/-1` 表示不启用（0 为默认）；SGLang `TOP_K_ALL=2**30` 表示全开（默认）。二者数值含义相反，跨引擎迁移需显式转换。
- **停止能力**：SGLang 独有 `stop_regex`（正则停止，`normalize()` 用 `sre_parse` 计算严格上界 `stop_regex_max_len`，通配计为 `MAX_LEN=2**30`）；vLLM 无正则停止。
- **结构化输出**：vLLM 六选一且含 `json_object`/`choice`；SGLang 四选一（json_schema/regex/ebnf/structural_tag），无 choice/json_object。
- **tokenizer 依赖**：SGLang `normalize()` 要求 `skip_tokenizer_init=True` 时禁用字符串停止与 `min_new_tokens`（依赖 tokenizer.decode/eos_token_id）；vLLM `stop` 要求 `detokenize=True`。

### 二、批量张量化对比：SamplingMetadata vs SamplingBatchInfo

| 维度 | vLLM v1 `SamplingMetadata` | SGLang `SamplingBatchInfo` |
|---|---|---|
| 定义位置 | `vllm/v1/sample/metadata.py:15`，dataclass，由 `SampleArgs.from_sampler_state` 组装 | `srt/sampling/sampling_batch_info.py:29`，dataclass，由 `from_schedule_batch(batch, vocab_size)`（`sampling_batch_info.py:87`）逐请求构建 |
| **张量粒度** | 每 **token** 一行（投机解码每位置一 token） | 每 **请求**一行：`temperatures[bs,1]`、`top_ps[bs]`、`top_ks[bs]`(int32)、`min_ps[bs]` |
| 聚合标志 | `all_greedy` / `all_random` | `is_all_greedy` / `is_any_greedy`（`top_k<=1` 推导）+ `need_top_p_sampling` / `need_top_k_sampling` / `need_min_p_sampling`（`sampling_batch_info.py:42-48,204-208`） |
| 随机源 | `generators: dict[int, torch.Generator]` 逐请求 Generator | `sampling_seed` int64 张量（仅 `deterministic.enable_deterministic_inference` 时生成，None 统一填 42） |
| 惩罚载体 | `frequency_penalties`/`presence_penalties`/`repetition_penalties` 每 token 标量 + `prompt_token_ids`/`output_token_ids`（采样器内计数） | `penalizer_orchestrator`（四类 Penalizer 的 `[bs,vocab]` 累积张量）+ `acc_additive_penalties`/`acc_scaling_penalties`（overlap 预累积） |
| logprob 需求 | `max_num_logprobs`（None/0/-1 三态）+ `logprob_token_ids`（精确 token logprob） | `top_logprobs_nums`/`token_ids_logprobs`（`ForwardBatch` 携带） |
| logit 附加 | `allowed_token_ids_mask`、`bad_words_token_ids`、`logitsprocs`（处理器链）、`spec_token_ids`、`thinking_budget_state_holder` | `grammars`/`grammar_mask`（文法约束掩码）、`logit_bias[bs,vocab]` 稀疏张量、`custom_logit_processor` + 按请求 bool 掩码 |
| 构建传输 | 由 `v1/worker/gpu_input_batch.py:943` 从每请求 SamplingParams 构造 | host 侧组张量 + `pin_memory` + `non_blocking=True` 异步拷贝到 `batch.device` |
| 批动态维护 | `BatchUpdateBuilder`→`BatchUpdate`（removed/added/moved）逐请求同步状态 | `filter_batch`（`sampling_batch_info.py:302`，高级索引重筛）/ `merge_batch`（388，`merge_bias_tensor` 补零对齐后 cat） |
| forward 隔离 | 每步构造新 metadata | `copy_for_forward()`（453）：先 `update_penalties()`（266）累积惩罚，再 `dataclasses.replace(self, penalizer_orchestrator=None)` 解绑编排器，防 overlap 重复累积 |
| 消耗方 | `v1/sample/sampler.py` `Sampler.forward(logits, sampling_metadata)` | `srt/layers/sampler.py:98` `Sampler.forward(logits_output, sampling_info)`，借用到 `ForwardBatch.sampling_info`（`forward_batch_info.py:472,805`） |

**关键差异**：
- **行粒度**：vLLM 在 token 空间采样（投机解码一位置一 token），SGLang decode 每请求只采 1 个 token 故按请求行——这决定惩罚计数、logprobs 收集的索引方案不同。
- **惩罚存储形态**：vLLM 存每 token 惩罚标量 + token 序列，采样时计数；SGLang 直接累积 `[bs,vocab]` 完整张量（frequency/presence/repetition/min_new_tokens 四类 Penalizer）。
- **确定性**：vLLM 用标准 `torch.Generator`（框架无关）；SGLang 用 `sampling_seed` 张量 + 自定义 Gumbel，且 flashinfer 后端不支持 seed。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
