## 输出结构与 Logprobs / Logits 处理

本文基于 `vllm/outputs.py`、`vllm/logprobs.py`、`vllm/pooling_params.py`、`vllm/logits_process.py`，说明引擎对外输出类型、logprob 容器、池化参数与 logits 偏置处理。

### 输出类型族（vllm/outputs.py）

生成与池化两条输出链：

| 类 | 用途 | 关键字段 |
|---|---|---|
| `RequestOutput` | 生成请求的整体输出（对外） | `request_id`、`prompt`、`prompt_token_ids`、`prompt_logprobs`、`outputs`、`finished`、`metrics`、`lora_request`、`encoder_prompt(_token_ids)`、`num_cached_tokens`、`num_cache_creation_tokens`、`kv/ec_transfer_params` |
| `CompletionOutput` | 单条生成序列 | `index`、`text`、`token_ids`、`cumulative_logprob`、`logprobs`、`routed_experts`、`finish_reason`、`stop_reason`、`lora_request`、`sampling_mask` |
| `PoolingOutput` | 池化输出的基础载荷 | `data: torch.Tensor` |
| `EmbeddingOutput` | 嵌入结果 | `embedding: list[float]`（`from_base` 要求 1-D） |
| `ClassificationOutput` | 分类概率 | `probs: list[float]`（`from_base` 要求 1-D） |
| `ScoringOutput` | 相似度分数 | `score: float`（`from_base` 对 `data` 先 `squeeze`） |
| `PoolingRequestOutput[_O]` | 池化请求整体输出（泛型） | `request_id`、`outputs`、`prompt_token_ids`、`num_cached_tokens`、`finished` |

- `SamplingMask`（dataclass）：逐生成 token 经 top-k/top-p/min-p 过滤后存活的词表 ID 集合（`token_ids: list[list[int]]`），仅请求时填充。
- `EmbeddingRequestOutput`/`ClassificationRequestOutput`/`ScoringRequestOutput` 均通过 `from_base(PoolingRequestOutput)` 转换。
- `STREAM_FINISHED`：流式输入用终结哨兵（`finished=True`、空 outputs 的空 `RequestOutput`）。

`RequestOutput` 要点：

- 构造接受 `**kwargs` 并 `logger.warning_once` 忽略——前向兼容旧代码调用新版本接口。
- `add(next_output, aggregate)` 合并后续输出：`aggregate=True` 时同 `index` 的 `CompletionOutput` 拼接 `text`、`token_ids`（必要时转 `list`）、`logprobs`，并用新输出覆盖 `cumulative_logprob`/`finish_reason`/`stop_reason`；`aggregate=False` 整体替换；新 index 直接追加。
- 编码器侧字段（`encoder_prompt`/`encoder_prompt_token_ids`）decoder-only 时为 `None`。

### Logprobs（vllm/logprobs.py）

| 类型 | 定义 |
|---|---|
| `Logprob` | dataclass：`logprob: float`、`rank: int \| None`、`decoded_token: str \| None`；不用 msgspec（OpenAI server 输出需可序列化） |
| `LogprobsOnePosition` | `dict[int, Logprob]`，单位置 token_id→logprob |
| `PromptLogprobs` | `FlatLogprobs \| list[LogprobsOnePosition \| None]`（首 token 为 `None`） |
| `SampleLogprobs` | `FlatLogprobs \| list[LogprobsOnePosition]` |

`FlatLogprobs`（`MutableSequence[LogprobsOnePosition | None]`）：把整条请求的 logprob 展平为基本类型列表（`start_indices`/`end_indices`、`token_ids`、`logprobs`、`ranks`、`decoded_tokens`），无论序列长度与 `top_logprobs` 设置，只引入常数个对象，显著降低 GC 开销。

- `append` / `append_fast`：前者从 `LogprobsOnePosition` dict 展开；后者直接收四组列表（省去中间 dict）。
- `__getitem__`：int 返回 `LogprobsOnePosition`；slice 返回新的 `FlatLogprobs`（索引重定位为 0 基）；`__setitem__`/`__delitem__`/`insert` 均抛 `TypeError`（只读容器）。
- 工厂函数：`create_prompt_logprobs(flat)` 先 `append(None)`（首 token 无 logprob）；`create_sample_logprobs(flat)` 返回空容器。
- `append_logprobs_for_next_position(request_logprobs, token_ids, logprobs, decoded_tokens, rank, num_logprobs)`：`num_logprobs == -1` 表示取全部；`ranks = chain((rank,), range(1, num_logprobs+1))`——采样 token 的 rank 在前，再跟 top-k 名次；重复插入同一 dict 键等价于一次写入，无需特判采样 token 是否在 topk 内。

### PoolingParams（vllm/pooling_params.py）

`PoolingParams` 为 `msgspec.Struct`（`omit_defaults=True`、`array_like=True`）。公开字段：

| 字段 | 说明 |
|---|---|
| `use_activation: bool \| None` | 是否对 pooler 输出施加激活；`None` 用 pooler 默认（多数为 `True`） |
| `dimensions: int \| None` | Matryoshka 维度压缩（仅 embed/token_embed） |
| `step_tag_id` / `returned_token_ids` | 逐 step 池化（`tok_pooling_type == "STEP"`）专用 |
| `task` / `requires_token_ids` | 内部使用：池化任务（`embed`/`classify`/`token_embed`/`token_classify` 等）与 token 依赖 |
| `skip_reading_prefix_cache` | 请求级覆盖 |
| `late_interaction_params` | `LateInteractionParams`（`mode`/`query_key`/`query_uses`），worker 侧 late-interaction 打分元数据 |
| `extra_kwargs` / `output_kind` | 扩展参数；`output_kind` 必须为 `FINAL_ONLY`（`__post_init__` 校验） |

`verify(model_config)` 流程：`task == "plugin"` → 置 `skip_reading_prefix_cache=True` 并跳过校验（插件自验）；`task` 不在 `valid_parameters`（`embed:[dimensions,use_activation]`、`classify:[use_activation]`、`token_embed:[dimensions,use_activation]`、`token_classify:[use_activation]`）→ 跳过；否则依次：

1. `_merge_default_parameters`：从 `model_config.pooler_config` 回填未设字段；`token_embed`/`token_classify` 强制 `skip_reading_prefix_cache=True`（防前缀缓存使池化输出短于 `n_prompt_tokens`）；`tok_pooling_type != "STEP"` 时若设了 `step_tag_id`/`returned_token_ids` 抛 `VLLMValidationError`。
2. `_set_default_parameters`：embed 类默认 `use_activation=True`；`dimensions` 需在 `[1, embedding_size]` 且模型必须 `is_matryoshka`，并须命中 `matryoshka_dimensions` 集合，否则 `VLLMValidationError`。
3. `_verify_valid_parameters`：拒绝任务不支持的参数。

`__post_init__` 额外调用 `check_removed_pooling_task`（`vllm/tasks`）拒绝已移除任务。

### Logits 处理（vllm/logits_process.py）

```python
LogitsProcessor: TypeAlias = (
    Callable[[list[int], torch.Tensor], torch.Tensor]          # (past_tokens, logits) -> logits
    | Callable[[list[int], list[int], torch.Tensor], torch.Tensor]  # (+ prompt_tokens)
)
```

`get_bad_words_logits_processors(bad_words, tokenizer)`：对每个坏词按 `add_prefix_space ∈ {False, True}` 编码两次（抑制句首/句中两种形态），去重首 token 后构造一个 `NoBadWordsLogitsProcessor`。

`NoBadWordsLogitsProcessor`：

- 常量 `_SMALLEST_LOGIT = -inf`、`_NEUTRAL_LOGIT = 0.0`；`word_bias` 惰性初始化（首次调用时按词表长度建零张量）。
- `_init_word_bias`：单 token 坏词直接置 `-inf`；`_check_token_ids_bounds` 校验所有 token id 满足 `0 <= id < vocab_size`，否则 `ValueError`。
- `__call__(past_tokens_ids, logits)`：对多 token 坏词，若其长度大于已生成历史 +1 则跳过；否则匹配历史尾部前缀，命中则把末 token 的 logit 置 `-inf`（`last_token_bias`），最终 `logits + word_bias + last_token_bias` 返回。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
