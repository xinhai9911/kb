## 工具约束 ↔ Grammar 约束的衔接链路

本文打通 function_call 与 constrained 两个目录：`FunctionCallParser.get_structure_constraint` 如何把 tool_choice/strict 决策为 `structural_tag` 或 `json_schema`，两种 structural tag 格式如何编译进后端，以及 JSON schema 数组约束与 `parallel_tool_calls` 的关系。

### 约束决策树（function_call_parser.py:243）

`get_structure_constraint(tool_choice, parallel_tool_calls, thinking_mode)` 的判定顺序：

| 分支 | 条件 | 产出 |
|---|---|---|
| 模型原生 auto tag | `tool_choice=="auto"` 且非 strict | `detector.get_auto_tool_call_structural_tag(...)`（仅个别格式支持，如 KimiK3Detector） |
| 模型原生 structural tag | `required`/具名，或 auto+strict | `detector.get_structural_tag(tools, tool_choice, thinking_mode, parallel_tool_calls)` → xgrammar `get_model_structural_tag(model=tag_name, tools, tool_choice, reasoning)` |
| legacy structural tag 兜底 | detector 声明 `supports_structural_tag()` | `get_legacy_structural_tag(at_least_one=is_required)` |
| JSON schema 兜底 | required/具名 且 `not detector.parses_required_natively()` | `("json_schema", get_json_schema_constraint(tools, tool_choice, parallel_tool_calls))` |

strict 语义：`SGLANG_TOOL_STRICT_LEVEL`（`environ.py:207`，`ToolStrictLevel`：`OFF=0/FUNCTION=1/PARAMETER=2`）。auto 时 `should_constrain_auto` = 任一 tool `strict=True` 或 strict level ≥ `FUNCTION`；PARAMETER 级别会把全部工具的 `strict` 强制置 True 再构建 tag。strict 时 schema 才写入 grammar；非 strict 的 legacy tag 结构 `schema={}`（`function_call_parser.py:220-223`，`parameters if is_strict else {}`）。

`thinking_mode` 参数（`serving_chat.py:1086 xgrammar_reasoning = thinking_mode and reasoning_parser is None`）控制原生 tag 是否包含 `<think>` 前缀——配置了 `--reasoning-parser` 时交给 `ReasonerGrammarBackend` 处理，避免双重约束。

### structural_tag 两种格式

| 格式 | 判别 | 结构 | 编译 |
|---|---|---|---|
| legacy（`LegacyStructuralTagResponseFormat`） | `utils.is_legacy_structural_tag`：有 `structures` 字段 | `{type:"structural_tag", structures:[{begin,schema,end}], triggers:[...], at_least_one}` | xgrammar：`StructuralTag.from_legacy_structural_tag` → `compile_structural_tag`；llguidance：`StructTag.to_grammar`（每个 structure 配一个 `begin` 前缀匹配的 trigger） |
| new（xgrammar 原生 `StructuralTag`） | 有 `format` 字段 | `{format:{sequence/or/triggered_tags/tags_with_separator/tag/json_schema/qwen_xml_parameter...}}` | 直接 `GrammarCompiler.compile_structural_tag(key_string)` |

两端点在 `xgrammar_backend.py:368 dispatch_structural_tag` 汇合；编译前有 `_sanitize_structural_format`/`_sanitize_structural_tag_structures` 把缺失的 `json_schema` 字段补成空 dict。请求侧 `ChatCompletionRequest.to_sampling_params`（`protocol.py:1136-1139`）把 `response_format.type=="structural_tag"` 也串到 `sampling_params["structural_tag"]`（`model_dump(by_alias=True)` 保证 `schema` 别名正确）。

### 模型原生 structural tag 名称（get_structural_tag_name）

| Detector | 名称（xgrammar builtin key） |
|---|---|
| `deepseekv32_detector.py:387` | `"deepseek_v3_2"` |
| `deepseekv4_detector.py:66` | 自实现 |
| `qwen3_coder_detector.py:480` | `"qwen_3_coder"` |
| `gpt_oss_detector.py:243` | 自实现 |
| `glm47_moe_detector.py:839` | 自实现 |
| `kimik2_detector.py:472` | 自实现 |

基类 `get_structural_tag`（`base_format_detector.py:388`）走 `xgrammar.get_model_structural_tag(model, tools, tool_choice, reasoning)`（tools/tool_choice 先 `model_dump()` 成 dict）；Kimi K3 等则用 `kimik3_structural_tag.py` 自行组装 tag（支持 `parallel_tool_calls` 控制，因为 xgrammar builtin 不暴露该开关）。

### JSON schema 数组约束（utils.py:413）

`get_json_schema_constraint(tools, tool_choice, parallel_tool_calls)` 产出供 grammar 编译的 schema：

| tool_choice | schema |
|---|---|
| 具名函数 | `{type:"array", minItems:1, items:{properties:{name:{type:"string",enum:[fn_name]}, parameters}, required:["name","parameters"]}}` |
| `"required"` | `{type:"array", minItems:1, items:{type:"object", anyOf:[每个工具的 {name,parameters} schema]}}`，附加跨工具合并的 `$defs`（`_get_tool_schema_defs`，冲突抛 `ValueError`） |
| `parallel_tool_calls=False` | 两种 schema 均加 `maxItems:1` |

辅助工具：`normalize_json_schema_types`（`utils.py:113`）原地把 DB/ORM 型 type（`varchar/int/enum/dict[str,int]` 等）改写为标准 JSON Schema 类型再进 prompt 与 grammar；`_partial_json_loads`（188）包装 `partial_json_parser`，把 `AssertionError` 转 `JSONDecodeError` 让流式解析按「未完成」处理；`safe_literal_eval`/`safe_ast_parse`（带 `_safe_ast_lock` 抑制全局 warning 竞态）供 Pythonic 解析用。

### 约束与输出约束互斥

`to_sampling_params`（`protocol.py:1141-1170`）：
- `tool_call_constraint` 与 regex/ebnf/structural_tag/json_schema 并存：required/具名抛 `ValueError`（无法同时满足）；auto 仅 `logger.warning("Constrained decoding is not compatible with tool calls.")` 并忽略工具约束。
- 工具约束最终落为 `sampling_params["structural_tag"]`（`constraint_value.model_dump(by_alias=True)` 序列化）或 `sampling_params["json_schema"]`（字符串），进入 `SamplingParams.normalize()` 的互斥校验（`sampling_params.py:202-209`），随后由 `GrammarManager.process_req_with_grammar` 构造 `("structural_tag", ...)`/`("json", ...)` key 走 grammar 后端（见 constrained-decoding.md）。

### 全链路示意

```
/chat/completions(tools, tool_choice, parallel_tool_calls)
  → _effective_tools
  → FunctionCallParser.get_structure_constraint
       ├─ ("structural_tag", Legacy/原生 StructuralTag) ─┐
       └─ ("json_schema", JSON array schema) ───────────┼─→ SamplingParams.structural_tag/json_schema
                                                        ↓
  GrammarManager.process_req_with_grammar(key) ─→ BaseGrammarBackend(dispatch_*)
       → GrammarCompiler 编译 → req.grammar(Future→Object, 每请求 copy)
  scheduler 采样前: sampling_batch_info.update_regex_vocab_mask → fill_vocab_mask_batched → GrammarMask
       → sampler: grammar_mask.apply(logits) 置 -inf
  batch_result_processor: req.grammar.accept_token(next_token_id) 推进 FSM
  输出侧: FunctionCallParser.parse_stream_chunk / JsonArrayParser → ToolCallItem → SSE tool_calls delta
```

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
