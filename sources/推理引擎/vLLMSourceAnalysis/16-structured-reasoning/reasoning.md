## ReasoningParser 推理内容解析体系

本文基于 vLLM `vllm/reasoning/`、`vllm/parser/` 源码，说明推理模型（CoT）输出的思考/答案分离机制、解析器注册与按模型选择方式，以及与结构化输出的衔接。

### 抽象契约：ReasoningParser

基类定义于 `vllm/reasoning/abs_reasoning_parsers.py`，构造器接收 `tokenizer` 与可选 `model_config`（用 `get` 而非 `pop` 取，便于复合解析器向嵌套解析器透传 kwargs）。

| 成员 | 类型 | 说明 |
|---|---|---|
| `engine_based_streaming` | 类属性 `bool=False` | 引擎驱动（声明式 parser engine）还是文本驱动；决定流式路径与 `finish_streaming()` 缓冲冲刷 |
| `vocab` | `cached_property` | `model_tokenizer.get_vocab()` 缓存 |
| `reasoning_start_str/end_str` | 属性，默认 `None` | 思考块定界串（如 `<think>`/`</think>`、`<seed:think>`） |
| `is_reasoning_end(input_ids)` | 抽象 | 按 token id 判定思考内容是否已结束；被 xgrammar 等结构化引擎调用 |
| `is_reasoning_end_streaming(input_ids, delta_ids)` | 非抽象 | 解码步增量判断；默认委托 `is_reasoning_end` |
| `extract_content_ids(input_ids)` | 抽象 | 从全量输出 id 中剥离思考段，返回答案 token id |
| `extract_reasoning(model_output, request)` | 抽象 | 非流式：整串拆分为 `(reasoning, content)` |
| `extract_reasoning_streaming(...)` | 抽象 | 流式：返回 `DeltaMessage(reasoning=..., content=...)` 或 `None` |
| `count_reasoning_tokens(token_ids)` | 默认返回 0 | 统计思考 token 数（用于 usage 指标），需显式 opt-in |
| `adjust_request(request)` | 默认原样返回 | 请求参数修正钩子 |
| `adjust_initial_state_from_prompt(prompt_token_ids)` | no-op | 流式开始时按 prompt 修正初始解析状态 |
| `has_engine_confirmed_reasoning_end()` | 默认 `False` | 仅引擎型解析器使用，返回 detokenizer 已确认的思考结束状态 |
| `prepare_structured_tag(original_tag, tool_server)` | 默认原样返回 | 结构化标签准备 |

### 注册机制：ReasoningParserManager

同文件中的中心注册表，双表结构：

- `reasoning_parsers: dict[str, type]`：即时注册缓存（首次懒加载后落此表）。
- `lazy_parsers: dict[str, tuple[module_path, class_name]]`：懒注册映射。

| 方法 | 行为 |
|---|---|
| `get_reasoning_parser(name)` | 命中即返回；懒表则 `_load_lazy_parser` 导入并缓存；都未命中抛 `KeyError` 并列出全部可用名 |
| `_load_lazy_parser(name)` | `importlib.import_module` → `getattr` → 校验 `issubclass(ReasoningParser)`，失败打日志并 re-raise |
| `register_module(name, force, module)` | 双用法：显式调用立即注册；或作装饰器（`module=None`）写入 `lazy_parsers`；`force=False` 时重名抛 `KeyError` |
| `register_lazy_module(name, module_path, class_name)` | 注册懒模块映射 |
| `import_reasoning_parser(plugin_path)` | 按文件路径动态导入用户插件（`--reasoning-parser-plugin`），失败仅记日志不中断 |

### 按模型选择

`vllm/reasoning/__init__.py` 维护 `_REASONING_PARSERS_TO_REGISTER`（约 30 个条目：`deepseek_r1`→`DeepSeekR1ReasoningParser`、`deepseek_v4`→`DeepSeekV4ParserReasoningAdapter`、`qwen3`/`mimo`→`Qwen3ParserReasoningAdapter`、`kimi_k2`/`kimi_k3`、`minimax_m2`、`step3`/`step3p5`、`gemma4`、`glm47`、`granite` 等），`register_lazy_reasoning_parsers()` 逐条 `register_lazy_module`，模块导入即执行。多数 parser 为引擎适配器薄壳（如 `deepseek_v4_engine_reasoning_parser.py` 仅 re-export `vllm.parser.engine.registered_adapters.DeepSeekV4ParserReasoningAdapter`）。

选择链路：

1. 服务端：`ChatCompletionServing`/`ResponsesServing` 用 `--reasoning-parser` 参数调 `ParserManager.get_parser(reasoning_parser_name=..., tool_parser_name=...)`（`vllm/parser/parser_manager.py`）。
2. 引擎内核：`StructuredOutputManager.__init__` 读 `StructuredOutputsConfig.reasoning_parser`（`--reasoning-parser`）→ `ReasoningParserManager.get_reasoning_parser` 得 `reasoner_cls`；解析器实例是**请求级**的（依赖每请求 chat-template kwargs），按需懒构建。
3. `ParserManager.get_parser` 合成逻辑：`is_harmony`（gpt_oss）→ `HarmonyParser`；reasoning/tool 同一 `_parser_engine_cls` 时折叠为共享引擎类；`kimi_k3` 走专属子类；否则生成 `DelegatingParser` 子类组合 `reasoning_parser_cls + tool_parser_cls`。

### 思考/答案分离：文本驱动

`vllm/reasoning/basic_parsers.py` 的 `BaseThinkingReasoningParser`（DeepSeekR1 等文本型解析器基类）：

- 子类必须实现 `start_token`/`end_token` 属性；构造时用 `vocab` 查 token id，查不到抛 `RuntimeError`。
- `is_reasoning_end`：从 `input_ids` 末尾向前扫描，先遇 `end_token_id` 返回 `True`、先遇 `start_token_id` 返回 `False`。
- `extract_content_ids`：若 end id 存在于前 `len-1` 个 id 中，返回其后的子序列；否则返回空。
- `extract_reasoning`（非流式）：先 `partition(start_token)` 去掉起始符，再 `partition(end_token)` 拆 `(reasoning, content)`，无 end 符则整段视为 reasoning。
- `extract_reasoning_streaming`：按 `start/end` id 落在 previous 还是 delta 分五种情形产 `DeltaMessage`；单个 start/end 特殊 token 直接吞掉。
- `count_reasoning_tokens`：深度计数器处理嵌套与孤立 end 符，不出现负数。

### 思考/答案分离：引擎驱动

`vllm/parser/engine/` 提供声明式 `ParserEngine`（继承统一 `Parser`）：子类在 `__init__` 用 `ParserEngineConfig` 定义完整输出格式（terminals：`THINK_START`/`THINK_END`/`TOOL_CALL_START` 等、`initial_state`、token_id_terminals、arg_converter），`StreamingParserEngine.feed(delta_text, delta_token_ids)` 消费 token 序列，产出 `SemanticEvent`（`REASONING_CHUNK`/`REASONING_END`/`TEXT_CHUNK`/`TOOL_CALL_START`/`TOOL_NAME`/`ARG_VALUE_CHUNK`/`TOOL_CALL_END`）。

- `_has_reasoning`：按 config 中是否含 THINK 终端或 `initial_state == REASONING` 判定；`_reasoning_ended` 初始为 `not _has_reasoning`。
- `is_reasoning_end`/`extract_content_ids`：基于 `_reasoning_end_token_id`/`_reasoning_start_token_id` 反向扫描，与文本驱动逻辑等价但走 config。
- `parse_delta`/`extract_reasoning_streaming`：`_events_to_delta` 把事件转 `DeltaMessage`；`finish_streaming()` 在流尾冲刷引擎缓冲文本（如 `<tool_call>` 残留的 `<`）。
- 适配器（`registered_adapters.py`：DeepSeekV4、Qwen3、Gemma4、SeedOss 等）定义各自 `ParserEngineConfig`。

### 前端统一 Parser 与结构化输出衔接

`vllm/parser/abstract_parser.py` 的 `Parser`/`DelegatingParser` 把 ReasoningParser 与 ToolParser 统一为单一接口：`parse()` 返回 `(reasoning, content, tool_calls)`；`parse_delta()` 通过 `StreamState` 编排阶段——prompt 检查（若 prompt 内思考未结束则调 `adjust_initial_state_from_prompt`）→ 思考阶段（`_in_reasoning_phase = not reasoning_ended`）→ 工具调用阶段；`include_reasoning=False` 时抑制 reasoning 增量。`finalize_generation` 在流未完成时用 `get_streaming_fallback_content` 补齐。

与结构化输出的衔接（详见 structured-outputs.md）：结构化引擎（xgrammar）在采样前用 `reasoner.is_reasoning_end / is_reasoning_end_streaming` 判断当前是否已越过思考段；`StructuredOutputManager.should_advance / should_fill_bitmask / trim_reasoning_for_advance` 保证思考 token 不喂给 grammar FSM、答案部分才受约束；`enable_in_reasoning` 则强制思考段也受语法约束。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
