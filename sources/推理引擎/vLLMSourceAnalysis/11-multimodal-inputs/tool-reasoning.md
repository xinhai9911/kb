## 工具调用与推理扩展

源码包：`vllm/parser/`、`vllm/tool_parsers/`、`vllm/reasoning/`。

### 模块布局

| 包 | 职责 |
|---|---|
| `parser/` | 统一 `Parser` 抽象、`ParserManager`、`ParserEngine`、模型专属解析 |
| `tool_parsers/` | `ToolParser` 基类与注册表、各模型工具解析器（约 50 个） |
| `reasoning/` | `ReasoningParser` 基类与注册表、各模型推理解析器（约 35 个） |

### Parser 统一抽象（parser/abstract_parser.py）

`Parser` 把「推理提取（` thinking` 标签内的思维链）」与「工具调用提取（XML/JSON）」统一成单一接口：

| 方法组 | 方法 |
|---|---|
| 推理 | `is_reasoning_end` / `extract_reasoning` / `extract_reasoning_streaming` / `extract_content_ids` / `count_reasoning_tokens` |
| 工具 | `adjust_request` / `extract_tool_calls` / `extract_tool_calls_streaming` |
| 编排 | `parse`（完整输出）与 `parse_delta`（流式 delta，经内部 `StreamState` 先推理后工具、再提交） |

`DelegatingParser`：组合独立 `ReasoningParser` + `ToolParser` 实例的推荐基类。`StreamState` 记录每条流的状态（reasoning 是否结束、已流式参数、历史工具调用数等）。

### ParserManager（parser/parser_manager.py）

| 方法 | 说明 |
|---|---|
| `get_tool_parser` | 按名从 `ToolParserManager` 取解析器；`enable_auto_tools` 未开或未命名时返回 None |
| `get_reasoning_parser` | 按名从 `ReasoningParserManager` 取 |
| `get_parser` | 组合：同一引擎的后端合并为单个 `ParserEngine`；Harmony 模型返回 `HarmonyParser`；kimi_k3 特判；其余动态生成 `DelegatingParser` 子类 |

### ToolParser（tool_parsers/abstract_tool_parser.py）

基类属性：`supports_required_and_named`（标准 JSON 解析是否可用，GLM 等 XML 输出置 False）、`structural_tag_model`（xgrammar 结构标签模型键）、`engine_based_streaming`。`adjust_request` 从工具 schema 构造 `StructuredOutputsParams`（含 JSON schema、strict=True）以约束生成。

`ToolParserManager` 注册表支持立即注册、懒加载（`register_lazy_module`）与装饰器注册；`import_tool_parser` 从任意路径导入插件解析器。已注册名（节选）：openai(gptoss)、hermes、pythonic、llama3_json、llama4_pythonic、mistral、internlm、jamba、granite(-4/-20b-fc)、deepseek_v3/v31/v32/v4、kimi_k2/k3、qwen3_coder/qwen3_xml/mimo、step3/step3p5、minimax_m2/m3、glm45/glm47、hunyuan_a13b、hy_v3、xlam、phi4_mini_json、minicpm5、apertus 等。

流式工具调用的两个关键状态：`prev_tool_call_arr`（已解析调用）、`streamed_args_for_tool`（已发送参数）；`get_remaining_unstreamed_args` 补发未发送的参数。

### ReasoningParser（reasoning/abs_reasoning_parsers.py）

基类属性：`reasoning_start_str` / `reasoning_end_str`（如 `<seed:think>`…`</seed:think>`）；`engine_based_streaming`。抽象方法同 Parser 的推理组。`adjust_initial_state_from_prompt` 允许在流开始处依据 prompt 修正初始状态（如 chat 模板自带开放 reasoning 通道）。`reasoning_parser_cls` 注册名（节选）：deepseek_r1/v3/v4、qwen3、kimi_k2/k3、step3/step3p5、minimax_m2(/m3)、mistral、cohere_command3/4、granite、hunyuan_a13b、holo2、openai_gptoss、gigachat、glm45/glm47 等。

### ParserEngine（parser/engine/）

单一声明式配置（`ParserEngineConfig`）同时驱动推理+工具解析的流式引擎：`StreamingParserEngine` + `TokenIdScanner` + `incremental_lexer`，产出语义事件（`SemanticEvent`/`EventType`）；`registered_adapters.py` 登记各引擎适配器。模型专属解析器位于 `parser/*.py`（deepseek_v32/v4、gemma4、glm47_moe、kimi_k2/k3、ling3、minimax_m2、mistral、nemotron_v3、qwen3、seed_oss、harmony 等）。

### 工具调用与推理流程（服务层）

1. 请求进入时由 `ParserManager` 选型；`tool_choice="auto"` 或指定 `--reasoning-parser` 时启用。
2. 完整响应：`Parser.parse(model_output, request)` → `(reasoning, content, tool_calls)`。
3. 流式响应：`parse_delta(delta_text, delta_token_ids, request, finished=...)` 返回 `DeltaMessage`；引擎侧解析（`engine_based_streaming=True`）时文本直接推进，不由服务层累积。
4. `extract_tool_calls_streaming` 增量拼装工具名与参数 JSON，`DeltaToolCall` 逐 delta 下发。

结构化约束：xgrammar 等后端经 `is_reasoning_end`/`is_reasoning_end_streaming` 判断推理结束时刻；`VLLM_ENFORCE_STRICT_TOOL_CALLING` 强制使用 `structural_tag` 结构标签并关闭 `supports_required_and_named`。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)