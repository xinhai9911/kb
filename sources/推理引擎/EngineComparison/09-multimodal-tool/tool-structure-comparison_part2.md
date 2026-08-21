## 工具调用与约束解码对比（续）：Reasoning 与流式解析路线

承接 [tool-structure-comparison.md](tool-structure-comparison.md) 的一至六节（注册/契约/约束决策/后端/采样衔接）。

### 七、Reasoning 对比

| 维度 | vLLM | SGLang |
|---|---|---|
| 解析器 | `ReasoningParser`（`vllm/reasoning/abs_reasoning_parsers.py`）+ `ReasoningParserManager`，`_REASONING_PARSERS_TO_REGISTER` 约 30 注册名（deepseek_r1/v3/v4、qwen3、kimi_k2/k3、minimax_m2、step3/step3p5、glm45/47 等） | 无独立 ReasoningParser 抽象：`reasoning_parser.detector.think_end_token` 编码 `think_end_ids`（`reasoner_grammar_backend.py`） |
| 实现路线 | 文本驱动（`BaseThinkingReasoningParser`：start/end token 双向扫描、`count_reasoning_tokens` 深度计数）与引擎驱动（`vllm/parser/engine/` `ParserEngineConfig` terminals + `SemanticEvent` 事件流）两套 | detector 内置探测（`think_end_token`）+ `TokenSequenceMatcher` 匹配，不设独立解析器层 |
| 与约束解码衔接 | `StructuredOutputManager.should_fill_bitmask` 用 `reasoner.is_reasoning_end(prompt)` 惰性初始化 `reasoning_ended`；`enable_in_reasoning` 强制思考段也受语法约束 | `ReasonerGrammarBackend` 包装内层 grammar：thinking 阶段不施约束，可选 token filter（`--enable-strict-thinking` 排除 `think_excluded_token_ids` 或到 `max_think_tokens` 强制输出 think_end）；`custom_params.thinking_budget` 可改写 `max_think_tokens` |
| 思考 token 保护 | `should_advance` 用 delta 窗口判 `is_reasoning_end_streaming`，`trim_reasoning_for_advance` 丢弃步内思考 token 防 grammar 拒绝（issue #44006）；投机窗口用 `simulated_buf` 模拟越过点后填 bitmask | `fill_vocab_mask` 在 thinking 阶段直接放行全部 token，generation 阶段才转发内层 grammar |
| 思考统计 | `count_reasoning_tokens` 显式 opt-in（usage 指标） | — |

### 八、流式工具解析路线对照

vLLM 侧归纳为三条技术路线（`vllm/tool_parsers/`），SGLang 侧对应关系：

| 路线 | vLLM 代表 | SGLang 对应 |
|---|---|---|
| partial JSON 前缀 diff | llama3_json/granite/hermes/pythonic：`partial_json_loads`（`Allow` 位掩码控制可推断内容）+ `find_common_prefix` 只下发新增片段；函数名未定前关 `Allow.STR` | `BaseFormatDetector.parse_streaming_increment` 基类实现（`base_format_detector.py:125-344`）：`partial_json_parser.loads`+`_find_common_prefix` 增量 diff；通用 `JsonArrayParser` 兜底 required/具名 |
| 标记/正则状态机 | deepseek_v3/v31/jamba/internlm：token id 序列数 `<｜tool▁call▁begin｜>` 等标记定位工具，正则按段抠 type/name/args | 各 `*_detector.py` 覆写（hermes、deepseekv3/v31/v32/v4、glm4/47、kimi_k2/k3、qwen25/qwen3_coder、minimax_m2/m3 约 35 个 detector） |
| 引擎驱动 | `engine_based_streaming=True` 适配器（mistral/qwen3/deepseek_v32/v4/glm47/kimi_k2/minimax_m2/gemma4/ling3/inkling/seed_oss）：解析前移到 `ParserEngine`，`ParserEngineToolAdapter` 透传 | 无对等物：约束交给 grammar 后端，解析仍为文本驱动 |
| 完成收尾 | `get_remaining_unstreamed_args()` 前缀比对补发未下发参数尾巴 | `parse_stream_end`→`detector.finish()` 冲刷为等 marker 滞留的文本 |

### 九、关键结论

| 结论 | 说明 |
|---|---|
| 注册哲学 | vLLM 双注册表（`ToolParserManager` 48 / `ReasoningParserManager` ~30）+ 显式 CLI 选择 + 统一 `ParserManager` 组合层；SGLang 单 `ToolCallParserEnum` 33 名 + auto 探测 |
| 约束架构 | vLLM `StructuredOutputManager` 单后端全局假设（首个请求定后端）；SGLang `BaseGrammarBackend` 缓存 + `GrammarManager` 异步编译 + PP/DP/TP 同步，每请求 `copy()` 独立 FSM |
| 后端生态 | vLLM 独有 guidance/lm-format-enforcer；SGLang 独有 llguidance + jump-forward + structural tag 双格式 |
| reasoning 地位 | vLLM 是一等公民（独立包+两套实现+引擎事件流）；SGLang 是 grammar 包装器（`ReasonerGrammarBackend`）+ detector 属性 |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
