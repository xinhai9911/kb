## 请求模型 → 引擎参数映射（SamplingParams / PoolingParams）

四类 OpenAI 请求最终都收敛为引擎侧的 `SamplingParams`（生成）或 `PoolingParams`（池化）。每个请求模型自带 `to_sampling_params()`/`to_pooling_params()` 转换方法，serving 层调用前先用 `get_max_tokens()` 计算实际 `max_tokens`。

### 总体调用链

```
ChatCompletionRequest.to_sampling_params(max_tokens, default_sampling_params)
CompletionRequest.to_sampling_params(max_tokens, default_sampling_params)
ResponsesRequest.to_sampling_params(default_max_tokens, default_sampling_params)
Embedding*.to_pooling_params()  → PoolingParams(task="embed", dimensions=..., use_activation=...)
```

serving 层统一用 `SamplingParams.from_optional(...)` 构造，传 `skip_clone=True`（每请求新对象，跳过深拷贝）。`default_sampling_params` 来自 `model_config.get_diff_sampling_param()`（模型 generation_config 与默认的差异项）。

### max_tokens 计算（serve/utils/api_utils.py:169 get_max_tokens）

对四种候选取最小值：`model_max_tokens = max_model_len - input_length`、请求值（未传则用 default 的 `max_tokens`）、`override_max_tokens`（服务端 `--override-generation-config max_new_tokens` 或 generation_config）、平台 `get_max_output_tokens(input_length)`。prompt 超长先抛 `ValueError`。`truncate_prompt_tokens` 可先截断再校验。

| 端点 | 调用参数 |
|---|---|
| chat | `request.max_completion_tokens if 非 None else request.max_tokens` |
| completion | `request.max_tokens`（默认 16） |
| responses | `request.max_output_tokens`，且内部再 `min(max_output_tokens, default)` |

### Chat → SamplingParams（chat_completion/protocol.py:661）

`from_optional` 参数映射要点：

| 请求字段 | 映射 | 说明 |
|---|---|---|
| `n`/`temperature`/`top_p`/`top_k`/`min_p`/`repetition_penalty` | 直通 | 显式 `None` 时回退 `default_sampling_params`，再回退 `_DEFAULT_SAMPLING_PARAMS`（temp=1.0, top_p=1.0, top_k=0, min_p=0.0, rep=1.0） |
| `stop_token_ids` | 与 server 默认去重合并 | 服务端模型特定 stop id（如 gpt-oss 的 `</call>`）用 `dict.fromkeys` 合并 |
| `stream` | `RequestOutputKind.DELTA` / `FINAL_ONLY` | 决定输出组装方式 |
| `logprobs` | 仅当 `logprobs=True and not logprob_token_ids` 时传 `top_logprobs` | 有 `logprob_token_ids` 时 logprobs 留 `None` |
| `prompt_logprobs` | `echo=True` 时回退为 `top_logprobs` | |
| `response_format`/`structured_outputs` | `extract_structured_outputs()` | 经 `structured_outputs_from_response_format` 归一 |
| `kv/ec_transfer_params`、`vllm_xargs` | 塞入 `extra_args` | 自定义扩展透传通道 |
| `thinking_token_budget`、`repetition_detection`、`allowed_token_ids`、`bad_words`、`routed_experts_prompt_start` | 直通 | 均为 vLLM 扩展 |

`use_beam_search=True` 时改走 `to_beam_search_params()` → `BeamSearchParams(beam_width=n, max_tokens, ignore_eos, temperature, length_penalty, include_stop_str_in_output)`，由 `BeamSearchOnlineMixin.beam_search` 处理。

### Completion → SamplingParams（completion/protocol.py:313）

与 Chat 大体一致，差异：`logprobs` 字段本身就是 `int`（top-k 数量），`logprob_token_ids` 存在时置 `None`；`echo and max_tokens==0` 时 `max_tokens` 强制为 1（纯回显不回显+生成）；`prompt_logprobs` 在 `echo` 时回退 `self.logprobs`。

### Responses → SamplingParams（responses/protocol.py:392）

`max_tokens = min(max_output_tokens, default_max_tokens)`；`stop` 字符串被包成 list；`top_logprobs` 仅在 `include` 列表含 `"message.output_text.logprobs"` 时生效（`is_include_output_logprobs`）；缺失的温度/penalty 统一回退默认；无 beam search。

### Embedding → PoolingParams（pooling/embed/protocol.py:41）

```python
def to_pooling_params(self):
    return PoolingParams(task="embed", dimensions=self.dimensions,
                         use_activation=self.use_activation)
```

`task` 枚举见 `vllm/tasks`；`dimensions` 请求截断维度；`use_activation=None` 时用 pooler 默认（多数模型为 `True`）。`reject_removed_pooling_parameters` 拒绝已删除的 `normalize` 参数。serving 层 `_prepare_generators` 先 `pooling_params.verify(self.model_config)` 再经 `engine_client.encode(request_id, prompt, pooling_params, ...)` 提交（pooling/base/serving.py:171）。

### 分词/模板参数（build_tok_params / build_chat_params）

- `build_tok_params(model_config)`：产出 `TokenizeParams(max_total_tokens=max_model_len, max_output_tokens, truncate_prompt_tokens, truncation_side, add_special_tokens, ...)`，用于 renderer 校验长度与截断。Embedding 型还受 pooler_config 影响：`enable_chunked_processing` 时 `max_total_tokens=None`；否则 `max_output_tokens = max_model_len - max_embed_len`。
- `build_chat_params(default_template, content_format)`：产出 `ChatParams(chat_template, chat_template_kwargs=merge_kwargs(请求 kwargs, 系统 extras), media_io_kwargs, tool_choice, response_format)`。系统 extras 含 `add_generation_prompt`/`continue_final_message`/`documents`/`reasoning_effort`；`reasoning_effort` 非空且未显式给 `enable_thinking` 时注入 `enable_thinking = (effort != "none")`；`tool_choice` 在 `tools` 为空时折叠为 `None`，避免模板渲染出模型可见的工具指令。

### parse_chat_messages（chat_utils.py:1954）

```python
def parse_chat_messages(messages, model_config, content_format,
                        media_io_kwargs=None, mm_processor_kwargs=None):
    # → (conversation: list[ConversationMessage],
    #    mm_data: MultiModalDataDict | None, mm_uuids: MultiModalUUIDDict | None)
```

流程：逐条消息 `_parse_chat_message_content` 展开（content 字符串 / content part 列表 / 多模态 media 解析），经 `_postprocess_messages` 把 assistant `tool_calls` 的 `arguments` JSON 字符串解析为 dict（模板期望 dict 而非 str，`type != "function"` 拒绝），最后由 `MultiModalItemTracker.resolve_items()` 汇总多模态数据。`parse_chat_messages_async` 为异步变体（在线路径）。

### 请求 → EngineInput 的渲染入口

serving 层调 `online_renderer.render_chat(request)` / `render_completion(request)`（`vllm/renderers/online_renderer.py`）得到 `list[EngineInput]`（含 `prompt_token_ids`、`mm_placeholders` 等），随后才做 `to_sampling_params` 并提交引擎。Responses 走 `online_renderer.preprocess_chat(request, messages, ...)` 并在 tool 循环中反复 `_render_next_turn`。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
