## 工具调用解析（FunctionCallParser）与 OpenAI tools 协议映射

本文基于 `sglang/srt/function_call/`（39 文件）与 `sglang/srt/entrypoints/openai/protocol.py`、`serving_chat.py`，说明 tools schema 定义、/v1/chat/completions 请求如何映射到工具约束与输出解析，以及流式工具调用增量解析。

### 模块结构

| 文件 | 职责 |
|---|---|
| `core_types.py` | `ToolCallItem`（tool_index/name/parameters）、`StreamingParseResult`（normal_text/calls）、`StructureInfo`（begin/end/trigger）、`_GetInfoFunc` |
| `base_format_detector.py` | `BaseFormatDetector` 抽象基类：一次性解析 + 流式增量解析两套接口、流式状态机、structural_tag 钩子 |
| `function_call_parser.py` | `FunctionCallParser` 门面：`ToolCallParserEnum` 注册表（33 个 parser 名 → detector 类）、约束生成 `get_structure_constraint` |
| `utils.py` | JSON schema 规整（`normalize_json_schema_types` 处理 DB/ORM 非标准 type）、partial JSON 解析、`get_json_schema_constraint` |
| `json_array_parser.py` | `JsonArrayParser`：`tool_choice=required/具名` 且无 structural_tag 时的通用 JSON 数组解析（bot_token=`[`） |
| `*_detector.py`（约 35 个） | 各模型工具调用格式的具体探测/解析实现（hermes、deepseekv3/v31/v32/v4、glm4/47、kimi_k2/k3、qwen25/qwen3_coder、minimax_m2/m3 等） |

### OpenAI tools 协议类型（protocol.py）

| 类型 | 行号 | 说明 |
|---|---|---|
| `Tool` | 759 | `type="function"` + `function: Function` + `defer_loading`（向下传播到 function） |
| `ToolChoice` | 784 | 具名函数选择：`function.name` + `type="function"`；请求侧还接受字符串 `"auto"/"none"/"required"` |
| `ToolCallConstraint` | 253 | 类型别名：`("structural_tag", StructuralTagResponseFormat)` 或 `("json_schema", Any)`，是「约束→sampling_params」的唯一交接类型 |
| `StructuresResponseFormat` | 235 | 单工具结构：`begin`/`schema`(别名 `schema_`)/`end` |
| `LegacyStructuralTagResponseFormat` | 242 | `type="structural_tag"` + `structures`/`triggers`/`at_least_one`（向后兼容格式） |
| `StructuralTagResponseFormat` | 249 | 别名：legacy 格式 或 xgrammar 原生 `StructuralTag` |

`Function` 含 `parameters`（JSON Schema dict）与 `strict: Optional[StrictBool]`；`strict` 为真时参数 schema 会作为 grammar 约束写入输出格式（见 tool-constraint-bridge.md）。

### /v1/chat/completions 请求映射链路（serving_chat.py）

1. `_effective_tools`（`serving_chat.py:377`）：`request.tools` 并集 system/developer 消息级 `message.tools`。
2. `tool_call_parser` 来自 `--tool-call-parser`（`server_args.py:8764`，可选 `auto` + 33 个 parser 名，自动探测在 `parser/template_detection.py`）。
3. `_tool_call_parsing_active`（`serving_chat.py:817`）：`tool_choice != "none"` 且存在 tools 且配置了 parser → 该请求输出走工具解析器。
4. 构造约束（`serving_chat.py:1104-1135`）：`FunctionCallParser.get_structure_constraint(tool_choice, parallel_tool_calls, thinking_mode)` 产出 `ToolCallConstraint`；若为 `None` 且 required/具名，回退 `get_json_schema_constraint`。
5. `MessageProcessingResult.tool_call_constraint` → `ChatCompletionRequest.to_sampling_params`（`protocol.py:1072`，接收 `tool_call_constraint` 参数）：`structural_tag`/`json_schema` 经 `convert_json_schema_to_str` 写入 `sampling_params`；与 response_format/regex/ebnf 同时存在时：required/具名抛 `ValueError`，auto 仅告警。
6. 请求级 `tools`（过滤后的 dump）只用于 chat template 渲染；实际约束与解析均以 `_effective_tools` 为准。

### FunctionCallParser 与 detector 注册

`ToolCallParserEnum`（`function_call_parser.py:64-99`）是纯类字典，无 vLLM 式注册表层：名称 → 类，`__init__` 按 `inspect.signature` 条件注入 `tokenizer`。实例方法：

| 方法 | 语义 |
|---|---|
| `parse_non_stream`（132） | 一次性：`detector.has_tool_call` + `detect_and_parse(full_text)`，无工具调用时原样回吐 |
| `parse_stream_chunk`（154） | 流式：`detector.parse_streaming_increment(chunk)`，返回 `(normal_text, calls)` |
| `parse_stream_end`（180） | 流结束冲刷：`detector.finish()` 释放为等 marker 而滞留的文本 |
| `get_structure_constraint`（243） | 按 tool_choice/strict 生成约束（详见 tool-constraint-bridge.md） |
| `get_legacy_structural_tag`（191） | 从 tools 构建 `LegacyStructuralTagResponseFormat`（strict 才带 schema） |

### BaseFormatDetector 流式状态契约

`base_format_detector.py` 的四个流式状态字段（与 vLLM `ToolParser` 高度同构）：

| 字段 | 语义 |
|---|---|
| `_buffer` | 跨 chunk 累积的不完整文本 |
| `prev_tool_call_arr` | 已解析完整工具调用（`{"name", "arguments"}`） |
| `current_tool_id` | 当前流式工具下标，初始 `-1` |
| `current_tool_name_sent` | 工具名是否已下发（名字先带空参数发出，参数再增量 diff） |
| `streamed_args_for_tool` | 每个工具已下发的参数原始串，用于计算剩余 diff |

`parse_streaming_increment`（125-344）基类实现：先检测 `bot_token`/`tool_call_separator` 判定是否进入工具区；用 `partial_json_parser.loads`（`Allow.ALL` 或排除 `STR`）增量解析；`_find_common_prefix` 计算新旧参数 JSON 的公共前缀做 diff；工具名非法时重置状态（`SGLANG_FORWARD_UNKNOWN_TOOLS` 控制是否透传未知工具，`environ.py:656`）。不支持该模式的格式（如 Qwen 独立块、Pythonic）由各 detector 覆写。

### 流式 SSE 输出（serving_chat.py）

`_process_tool_call_stream`（2460）：
- `parser_dict` 惰性创建：required/具名时按 `supports_structural_tag() || parses_required_natively()` 选 `FunctionCallParser` 或 `JsonArrayParser`。
- 首个含 `name` 的 `ToolCallItem` 下发完整 delta（`tool_call_id` 经 `_process_tool_call_id` 生成 + `FunctionResponse(name=...)`）；后续 chunk 仅带 `arguments` 增量，`name/id` 置 `None`。
- `flush=True` 末尾调 `parse_stream_end`，把滞留文本并入 content delta。
- 对 normal_text 部分输出 `DeltaMessage(content=...)`。

### 与 vLLM tool_parsers 对照

| 维度 | vLLM `tool_parsers/` | SGLang `function_call/` |
|---|---|---|
| 接口 | `ToolParser` ABC + `ToolParserManager` 惰性注册表（48 名） | `BaseFormatDetector` ABC + `FunctionCallParser.ToolCallParserEnum` 类字典（33 名） |
| 流式入参 | `extract_tool_calls_streaming(previous_text,current_text,delta_text,prev/curr token_ids,...)` | `parse_streaming_increment(new_text, tools)`，内部自行缓冲 |
| 流式状态 | `prev_tool_call_arr/current_tool_id/current_tool_name_sent/streamed_args_for_tool` | 同名同义字段 |
| structural tag | 类属性 `structural_tag_model`（声明 xgrammar builtin key） | `detector.get_structural_tag_name()` → `xgrammar.get_model_structural_tag` |
| tool_choice 解析 | `supports_required_and_named` 控制通用 JSON 解析 | `parses_required_natively()` + strict level 控制是否上 grammar 约束 |
| 完成收尾 | `get_remaining_unstreamed_args()` 拼尾巴 | `finish()` 冲刷滞留文本 |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
