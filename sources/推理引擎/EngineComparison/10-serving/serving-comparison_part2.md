## 10-serving（一）：请求模型映射与工具参数对比 _part2

续 [serving-comparison_part1.md](serving-comparison_part1.md)（离线/在线 API 与协议族）。本部分对比请求模型→SamplingParams 映射与 serving 层工具/结构化参数传递。

### 3. 请求模型 → SamplingParams 映射

| 维度 | vLLM | SGLang |
|---|---|---|
| 协议模型文件 | `entrypoints/openai/`（按端点重组）：`engine/protocol.py`（`OpenAIBaseModel`，`extra="allow"`）、`chat_completion/protocol.py`、`completion/protocol.py`、`responses/protocol.py`、`pooling/*` | 原生：`managers/io_struct.py`（`GenerateReqInput` :160 为 pydantic 兼容 `@dataclass`）；OpenAI 兼容：`entrypoints/openai/protocol.py`（`CompletionRequest` :328、`ChatCompletionRequest` :823、`EmbeddingRequest` :1284、`ResponsesRequest` :1576 等全部 `BaseModel`） |
| 转换方式 | 每个请求模型内嵌 `to_sampling_params()`（强类型 `SamplingParams`）+ `build_tok_params()`；serving 层统一 `SamplingParams.from_optional(...)`，传 `skip_clone=True` | `ChatCompletionRequest.to_sampling_params()`（protocol.py:1072）返回 **dict**；优先级 `user 值 > model_generation_config > OpenAI 默认值` |
| 默认采样 | `default_sampling_params` 来自 `model_config.get_diff_sampling_param()`（generation_config 与默认的差异） | 显式传 `model_generation_config`；`get_param` 逐字段回退 |
| max_tokens | `get_max_tokens()`（serve/utils/api_utils.py:169）对四候选取 min：`model_max_len - input_len`、请求值、`override_max_tokens`、平台上限 | chat：`max_new_tokens = max_completion_tokens or max_tokens`；completion（`CompletionRequest.to_sampling_params`，protocol.py:1762）：`min(max_output_tokens, default_max_tokens) - 2`（预留 BOS/EOS） |
| 结构化输出 | `response_format`/`structured_outputs` → `extract_structured_outputs()` 归一后进 `SamplingParams` | `response_format` json_schema/json_object/structural_tag → 直接写进 sampling_params dict（`json_schema`/`structural_tag` 键） |
| 约束解码 | 经 `extra_args`/结构化输出通道 | `regex`/`ebnf`/`json_schema`/`structural_tag` 均为 dict 字段，原生 `/generate` 直通 |
| 渲染入口 | `online_renderer.render_chat/render_completion`（`vllm/renderers/online_renderer.py`）→ `EngineInput`；`parse_chat_messages`（chat_utils.py:1954）产出 conversation + mm_data | chat 经 `TemplateManager` 渲染；原生 `/generate` 由 `TokenizerManager.generate_request`（tokenizer_manager.py:765）→ `normalize_batch_and_arguments` → `TokenizedGenerateReqInput`（msgspec，进程内 ZMQ msgpack） |
| 校验错误 | `VLLMValidationError`（vllm/exceptions.py:27）→ 全局 handler → HTTP 400 | pydantic/fastapi 校验；`ORJSONRoute` 对 >64 位整数/NaN 直接 400 |

### 4. serving 层工具/结构化参数传递

| 维度 | vLLM | SGLang |
|---|---|---|
| tool_choice 默认 | `"none"`；提供 `tools` 但未传时 validator 自动改写为 `"auto"`（`check_tool_usage`）；`tools` 空数组被拒绝 | `tool_choice` 联合类型 + `ToolChoice`；`tool_call_constraint` 传 `to_sampling_params` |
| 模板注入 | `ChatParams.tool_choice = request.tool_choice if request.tools else None`（无 tools 折叠默认）；`exclude_tools_when_tool_choice_none` 可连 tool 定义一起排除 | 约束解码与 tool-call 冲突校验：`tool_choice=="required"`/named 与 `response_format`/regex/ebnf 共存时抛 `ValueError` |
| 工具解析 | `ParserManager.get_parser(tool_parser_name, reasoning_parser_name, enable_auto_tools, ...)`；`--enable-auto-tool-choice` 强制配 `--tool-call-parser`（`validate_parsed_serve_args`） | `init_tokenizer_manager` 按 chat template 自动推断 `reasoning_parser`/`tool_call_parser`；HTTP 暴露 `/parse_function_call`、`/separate_reasoning` |
| MCP/外部工具 | `--tool-server <url>` 接入外部 MCP SSE 服务，`MCPToolServer` 转 harmony 格式注入；Responses 内置 browser/code_interpreter/container（`extract_tool_types`） | `tool.py`：`Tool`/`ConversationContext`/`HarmonyContext` 基础设施，服务 `/v1/responses` 等工具端点 |
| 工具调用 ID | `get_tool_call_id_type`：Kimi 系 `functions.{func}:{idx}`，其余 `chatcmpl-tool-{uuid}` | — |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
