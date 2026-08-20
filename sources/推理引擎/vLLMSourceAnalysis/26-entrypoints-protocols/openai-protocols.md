## OpenAI 兼容协议模型层总览

本文聚焦 `vllm/entrypoints/` 的**协议与请求模型层**。注意当前版本 openai 目录已按端点重组（非旧版单一 `protocols.py`/`serving_*.py`），全部请求模型为 pydantic `BaseModel`（继承共享基类 `OpenAIBaseModel`，`extra="allow"` 容忍未知字段），每个请求模型都内嵌 `to_sampling_params()`/`build_tok_params()` 等转换方法。

### 目录结构与共享基类

| 模块 | 内容 |
|---|---|
| `openai/engine/protocol.py` | 共享基类与通用类型：`OpenAIBaseModel`、`UsageInfo`、`ErrorResponse`、`StopParam`、`StreamOptions`、`FunctionCall`/`ToolCall`、`DeltaMessage`、`response_format` 相关类型 |
| `openai/chat_completion/protocol.py` | `ChatCompletionRequest`/`ChatCompletionResponse`/流式 chunk、`BatchChatCompletionRequest` |
| `openai/completion/protocol.py` | `CompletionRequest`/`CompletionResponse` 及其流式变体 |
| `openai/responses/protocol.py` | `ResponsesRequest`/`ResponsesResponse` 与 `StreamingResponsesResponse` 事件联合 |
| `pooling/base/protocol.py` | 池化请求 mixin（`ChatRequestMixin`/`CompletionRequestMixin`/`EmbedRequestMixin` 等），被 embed/classify 复用 |
| `pooling/embed/protocol.py` | `EmbeddingRequest` 联合类型 + OpenAI/Cohere 两种响应模型 |
| `pooling/classify/protocol.py` | `/v1/classify` 分类请求 |

### OpenAIBaseModel 与通用字段

`OpenAIBaseModel`（`openai/engine/protocol.py:36`）两个关键点：

- `model_config = ConfigDict(extra="allow")`：**OpenAI API 允许额外字段**，pydantic 不会拒绝；未识别字段通过 wrap validator 记录 `logger.debug`（"present in the request but ignored"），不报错。
- `field_names` 类变量缓存字段名+别名，避免逐请求反射。

共享类型：

| 类型 | 定义 | 说明 |
|---|---|---|
| `StopParam` | `str \| list[str] \| None` | list 上限由环境变量 `VLLM_MAX_STOP_STRINGS` 约束（`Annotated[list[str], Field(max_length=...)]`） |
| `UsageInfo` | prompt/completion/total_tokens | 含 `prompt_tokens_details`（cached_tokens、created_cache_tokens、multimodal_tokens）与 `completion_tokens_details`（reasoning_tokens） |
| `ErrorInfo`/`ErrorResponse` | message/type/param/code | `code` 为 `int`（HTTP 状态码值），`ErrorResponse` 供非流式与流式统一返回 |
| `GenerationError` | 继承 `VLLMServerError` | `finish_reason == "error"` 时抛出，`status_code=500` |
| `FunctionCall`/`ToolCall` | name/arguments | `FunctionCall.id` 标 `exclude=True`，序列化时不输出（保持 OpenAI 兼容） |
| `ResponseFormat` | `Literal["text","json_object","json_schema"]` | 另有 `StructuralTagResponseFormat`/`LegacyStructuralTagResponseFormat`（structural_tag 类型） |

### ChatCompletionRequest 字段分组

按注释分段（`chat-completion-sampling-params`/`chat-completion-extra-params`），字段要点：

| 分组 | 代表字段 | 默认值 |
|---|---|---|
| OpenAI 标准 | `messages`、`model`、`temperature`、`top_p`、`n=1`、`max_tokens`(已弃用) vs `max_completion_tokens`、`stream=False`、`stop`、`logit_bias`、`seed`、`frequency/presence_penalty` | `stop=[]`、`n=1` |
| 采样扩展 | `top_k`、`min_p`、`repetition_penalty`、`length_penalty=1.0`、`ignore_eos`、`min_tokens`、`use_beam_search`、`stop_token_ids`、`allowed_token_ids`、`bad_words`、`prompt_logprobs`、`logprob_token_ids` | 见字段 |
| 模板扩展 | `chat_template`、`chat_template_kwargs`、`add_generation_prompt=True`、`continue_final_message`、`add_special_tokens=False`、`documents`、`echo` | |
| 结构化输出 | `response_format`、`structured_outputs`、`reasoning_effort`(含 `xhigh`/`max`)、`thinking_token_budget`、`include_reasoning=True` | |
| 服务扩展 | `request_id`(默认 `random_uuid`)、`priority`、`cache_salt`、`kv/ec_transfer_params`、`vllm_xargs`、`session_id`、`return_token_ids`、`routed_experts_prompt_start` | |

`tool_choice` 联合类型为 `"none" | "auto" | "required" | ChatCompletionNamedToolChoiceParam`，默认 `"none"`；`tools` 为空数组会被拒绝。

### 与 OpenAI 规范的差异（校验差异）

| 差异点 | vLLM 行为 |
|---|---|
| 额外字段 | 容忍并忽略（`extra="allow"`），仅 debug 日志 |
| `system` 消息含非文本 content | 仅 `logger.warning_once`，不拒绝（规范只允许 text） |
| `max_tokens` | 保留但标 `deprecated`，优先 `max_completion_tokens` |
| `tool_choice` 默认 | 规范默认 `"none"`；若提供 `tools` 但未传 `tool_choice`，validator 自动改写为 `"auto"`（`check_tool_usage`） |
| `reasoning_content` | 消息内的已弃用字段在 `before` validator 中被重命名映射到 `reasoning` |
| `prompt_logprobs`/`top_logprobs` | 支持 `-1` 表示全部 token；`top_logprobs` 生效必须 `logprobs=True`；`stream=True` 时 prompt_logprobs 不可用 |
| 非数值字段 | `mode="before"` 时先检查 `isinstance(int,float)`，避免 `TypeError`→500，改为干净的 400 |
| `logprob_token_ids` | 需 `logprobs=True`；与 beam search 互斥 |
| `stream_options` | 必须在 `stream=True` 时使用 |
| `continue_final_message` 与 `add_generation_prompt` | 互斥（校验拒绝） |

### CompletionRequest / ResponsesRequest / EmbeddingRequest 特点

**CompletionRequest**（`completion/protocol.py:46`）：`prompt` 支持 `int 列表 | 嵌套列表 | str | list[str]`；`max_tokens` 默认 16（`normalize_null_max_tokens` 把 `null` 归一为默认值）；`echo` 配合 `max_tokens=0` 时 `to_sampling_params` 把 `max_tokens` 压成 1 实现纯回显；`prompt` 与 `prompt_embeds` 至少一个非空；多 prompt 数量受 `VLLM_MAX_COMPLETION_PROMPTS` 限制。

**ResponsesRequest**（`responses/protocol.py:136`）：`input` 为 `str | list[ResponseInputOutputItem]`（复用 `openai` SDK 的 `ResponseInputItemParam`/`ResponseOutputItem` 类型，含 harmony 消息）；`background`（异步任务，要求 `store=True`）；`store` 默认 `True` 但服务未启用时**静默关闭**而非报错；`prompt` 字段直接拒绝（"prompt template is not supported"）；`input_item_parsing` 预解析 `function_call`/`reasoning`/assistant `message`，补全缺失 `id`/`status`/`annotations`；`text.format` 与 `structured_outputs` 互斥。

**EmbeddingRequest**（`pooling/embed/protocol.py:159`）：Union 联合 5 种请求（completion 型/chat 型/chat 批量/input 型/input 批量），由 `BeforeValidator(reject_removed_pooling_parameters)` 前置校验——`normalize` 参数已删除，提示改用 `use_activation`；`task` 字段通过 `check_removed_pooling_task` 拒绝旧任务名。响应 `EmbeddingResponseData.embedding` 为 `list[float] | str`（base64 编码时）。

### 校验机制：VLLMValidationError

所有协议校验抛 `VLLMValidationError(message, *, parameter, value)`（`vllm/exceptions.py:27`），继承 `VLLMClientError`（4xx 族）。`__str__` 附带 `parameter=... value=...`。该类型被 pydantic `ctx["error"]` 捕获后由全局 handler 转 HTTP 400（见 serving-dispatch 文件）。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
