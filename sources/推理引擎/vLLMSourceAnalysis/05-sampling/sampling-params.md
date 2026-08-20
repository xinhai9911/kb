## SamplingParams 采样参数

`SamplingParams`（vllm/sampling_params.py，pydantic+msgspec Struct）遵循 OpenAI completions 参数语义并扩展 beam search。构造后经 `__post_init__` 统一归一化与校验。

### 采样类型

`SamplingType`（IntEnum）：GREEDY=0（`temperature < 1e-5`，零温度贪心）、RANDOM=1（无 seed）、RANDOM_SEED=2（设 seed）。

### 核心采样参数

| 参数名 | 类型 | 必选 | 说明 |
|--------|------|------|------|
| `temperature` | number | 否 | 随机性控制，默认 1.0。0 表示贪心；范围 [0,2]；0<temp<0.01 钳制到 0.01 并告警 |
| `top_p` | number | 否 | 核采样累计概率，默认 1.0，范围 (0,1] |
| `top_k` | integer | 否 | 保留 top-k token，默认 0（0/-1 表示不启用，启用须 >=1） |
| `min_p` | number | 否 | 相对最高概率的最小概率阈值，默认 0.0，范围 [0,1] |
| `seed` | integer | 否 | 随机种子，默认 None；-1 视为 None |
| `logit_bias` | array | 否 | token_id→bias 映射，构造 logits 处理器；bias 钳制到 [-100,100]；须为词表内 id |
| `allowed_token_ids` | array | 否 | 仅保留这些 token 的分数；不可为空 list |

### 惩罚参数

| 参数名 | 类型 | 必选 | 说明 |
|--------|------|------|------|
| `presence_penalty` | number | 否 | 出现惩罚，默认 0.0，范围 [-2,2]；>0 鼓励新 token |
| `frequency_penalty` | number | 否 | 频率惩罚，默认 0.0，范围 [-2,2] |
| `repetition_penalty` | number | 否 | 重复惩罚，默认 1.0；须为有限数且 >0 |

### 停止条件

| 参数名 | 类型 | 必选 | 说明 |
|--------|------|------|------|
| `max_tokens` | integer | 否 | 每序列最大生成 token 数，默认 16；>=1 |
| `min_tokens` | integer | 否 | EOS/stop 生效前最小生成数，默认 0；须 <=max_tokens |
| `stop` | array | 否 | 停止字符串（str 或 list），输出不含停止串；不可含空串；须 detokenize=True |
| `stop_token_ids` | array | 否 | 停止 token id 列表，输出含停止 token（特殊 token 除外） |
| `ignore_eos` | boolean | 否 | 忽略 EOS 继续生成，默认 false |
| `thinking_token_budget` | integer | 否 | 思考 token 上限，默认 None（不限）；-1 表示不限；须为非负整数 |

### logprobs 参数

| 参数名 | 类型 | 必选 | 说明 |
|--------|------|------|------|
| `logprobs` | integer | 否 | 每个输出 token 返回 top-N logprobs，默认 None；-1 返回全词表；True 归一化为 1；结果为最多 logprobs+1 个（含采样 token） |
| `prompt_logprobs` | integer | 否 | 每个 prompt token 的 top-N logprobs，默认 None；-1 返回全词表 |
| `logprob_token_ids` | array | 否 | 指定 token id 的 logprobs（高效评分），长度 <=128；须为词表内 id；与 logprobs 同时设置时须相等 |
| `flat_logprobs` | boolean | 否 | 扁平化 FlatLogprobs 返回，降低 GC 开销，默认 false |

### 输出与流式参数

| 参数名 | 类型 | 必选 | 说明 |
|--------|------|------|------|
| `n` | integer | 否 | 每个 prompt 返回输出数，默认 1，上限 VLLM_MAX_N_SEQUENCES（默认 16384） |
| `detokenize` | boolean | 否 | 是否反 tokenize 输出，默认 true（stop 字符串要求其为 true） |
| `skip_special_tokens` | boolean | 否 | 跳过特殊 token，默认 true |
| `spaces_between_special_tokens` | boolean | 否 | 特殊 token 间补空格，默认 true |
| `include_stop_str_in_output` | boolean | 否 | 输出文本包含停止字符串，默认 false |
| `output_kind` | enum | 否 | CUMULATIVE=0（累计）/DELTA=1（增量）/FINAL_ONLY=2（仅最终），默认 CUMULATIVE |
| `stream_interval` | integer | 否 | 每个流式 RequestOutput 的批 token 数，默认 None（跟随引擎）；>=1 |
| `routed_experts_prompt_start` | integer | 否 | 返回路由数据时跳过的 prompt token 数，默认 0 |

### 结构化输出与扩展参数

| 参数名 | 类型 | 必选 | 说明 |
|--------|------|------|------|
| `structured_outputs` | object | 否 | StructuredOutputsParams：json/regex/choice/grammar/json_object/structural_tag 六选一，多选报错 |
| `repetition_detection` | object | 否 | RepetitionDetectionParams：N-gram 重复检测提前终止；max_pattern_size>0 时 min_count>=2 |
| `extra_args` | object | 否 | 自定义采样/插件任意附加参数，引擎内不使用 |
| `bad_words` | array | 否 | 禁止生成的单词列表；不可含空串；经 tokenizer 转为 token 序列，数量上限 VLLM_MAX_NUM_BAD_WORDS |
| `skip_reading_prefix_cache` | boolean | 否 | 仅内部：设 prompt_logprobs 时跳过前缀缓存读取 |

### 校验规则摘要

- `n`：int 且 1<=n<=VLLM_MAX_N_SEQUENCES。
- temperature：有限数、[0,2]；<0 报错；`0<temp<0.01` 钳制到 0.01。
- top_p：`(0,1]`；top_k：int，`>=1` 或 0/-1 禁用；min_p：`[0,1]`。
- presence/frequency penalty：`[-2,2]`；repetition_penalty：有限且 >0。
- logprobs/prompt_logprobs：None、-1（全词表）或 >=0；超过 `model_config.max_logprobs` 报错。
- logit_bias、allowed_token_ids、logprob_token_ids 的 id 必须在词表内。
- temperature<1e-5（贪心）时：top_p=1、top_k=0、min_p=0，且 n 必须为 1。
- 结构化输出约束互斥且至少一个；choice 不可为空 list；grammar/json 不可为空串；json_object 仅可为 True。
- 推测解码下禁用 `min_p>1e-5` 与 `logit_bias`；Diffusion 模型禁用 temperature/min_p/seed/min_tokens/logit_bias/bad_words/allowed_token_ids/结构化输出。

### 工厂与配套

- `SamplingParams.from_optional(...)`：None 值落回默认（n=1、temp=1.0、top_p=1.0、种子将 dict 键转 int 等）。
- `verify(model_config, speculative_config, structured_outputs_config, tokenizer)`：引擎侧深度校验。
- 内部字段：`skip_clone`、`output_text_buffer_length`、`_eos_token_id`、`_all_stop_token_ids`、`_bad_words_token_ids`。
- 常量：`_SAMPLING_EPS=1e-5`、`_MAX_TEMP=1e-2`、`MAX_LOGPROB_TOKEN_IDS=128`。

### BeamSearchParams（束搜索）

| 参数名 | 类型 | 必选 | 说明 |
|--------|------|------|------|
| `beam_width` | integer | 是 | 束宽，1<=width<=VLLM_MAX_N_SEQUENCES |
| `max_tokens` | integer | 是 | 最大生成 token 数 |
| `temperature` | number | 否 | 默认 0.0 |
| `length_penalty` | number | 否 | 长度惩罚，默认 1.0 |
| `ignore_eos` | boolean | 否 | 默认 false |
| `include_stop_str_in_output` | boolean | 否 | 默认 false |
| `structured_outputs` | object | 否 | 结构化输出约束 |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)