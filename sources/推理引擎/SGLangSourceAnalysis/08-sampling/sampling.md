## SamplingParams 参数模型与 SamplingBatchInfo 批量张量化

SGLang 采样体系由三层构成：`SamplingParams`（`srt/sampling/sampling_params.py`）定义单请求参数模型；`SamplingBatchInfo`（`srt/sampling/sampling_batch_info.py`）把批量请求的参数组织为 GPU 张量；`Sampler`（`srt/layers/sampler.py`）消费这些张量做采样。本文聚焦前两层，采样后端见 [sampling-backend_part1.md](sampling-backend_part1.md)。

### SamplingParams：msgspec 结构体参数模型

`SamplingParams` 继承 `msgspec.Struct`（`kw_only=True, array_like=True`），随请求经 msgpack IPC 传输（`sampling_params.py:45`）。它同时承载「API 入参」与「规范化后的内部字段」两类字段：

| 分类 | 字段（默认值） | 说明 |
|---|---|---|
| 解码约束 | `max_new_tokens=128`、`min_new_tokens=0`、`n=1`、`ignore_eos=False` | 长度/并行采样控制 |
| 停止条件 | `stop`（别名）、`stop_token_ids`、`stop_regex`（别名）、`no_stop_trim=False`、`skip_special_tokens=True`、`spaces_between_special_tokens=True` | `stop`/`stop_regex` 在 `normalize()` 中被拷贝到内部字段后清空 |
| 采样分布 | `temperature=1.0`、`top_p=1.0`、`top_k=TOP_K_ALL`、`min_p=0.0` | `TOP_K_ALL = 1 << 30`（`sampling_params.py:40`），`-1` 同义 |
| 惩罚 | `frequency_penalty=0.0`、`presence_penalty=0.0`、`repetition_penalty=1.0` | 见 penaltylib 实现 |
| 结构约束 | `json_schema`、`regex`、`ebnf`、`structural_tag` | 四者互斥（`verify` 断言至多一个非 None） |
| 其他 | `logit_bias`、`sampling_seed`、`custom_params`、`stream_interval` | `custom_params` 必须为 JSON 安全标量/列表/字典（`CustomParamValue`，`sampling_params.py:32`），供自定义 logit processor 使用 |
| 内部字段 | `stop_strs`、`stop_regex_strs`、`stop_str_max_len`、`stop_regex_max_len`、`is_normalized` | 由 `normalize()` 填充，非 API 面 |

**三个生命周期方法**：

- `__post_init__`（`sampling_params.py:91`）：非可选参数把 `None` 视作默认值，保证 `/generate` 传 `null` 不崩；特殊处理：`0 <= temperature < 1e-6` 时置 `temperature=1.0`、`top_k=1`（贪心）；`top_k == -1` 还原为 `TOP_K_ALL`。已 `is_normalized` 则直接返回，避免反序列化后重置 tokenizer 派生字段。
- `verify(vocab_size)`（`sampling_params.py:151`）：校验温度非负有限、`top_p ∈ (0,1]`、`min_p ∈ [0,1]`、`top_k ≥ 1`、三个 penalty 范围（repetition 为 `(0,2]`，`1.0` 表示不惩罚）、`min_new_tokens ≤ max_new_tokens`、`logit_bias` 键在词表内。
- `normalize(tokenizer)`（`sampling_params.py:212`）：把 stop 字符串经 tokenizer 编码得到 `stop_str_max_len`（供流式停止匹配的缓冲长度）；stop_regex 用 `sre_parse` 递归计算严格上界 `stop_regex_max_len`（`get_max_seq_length`，`sampling_params.py:261`，通配重复计为 `MAX_LEN=2**30`）；`raise_if_tokenizer_required`（`sampling_params.py:305`）保证 `skip_tokenizer_init=True` 时字符串停止条件与 `min_new_tokens` 不可用（它们依赖 tokenizer.decode / eos_token_id）。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
