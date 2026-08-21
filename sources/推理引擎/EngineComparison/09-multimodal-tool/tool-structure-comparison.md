## 工具调用与约束解码对比：vLLM `tool_parsers`/`structured_output` vs SGLang `function_call`/`constrained`

对比工具调用解析、约束解码（grammar）与 reasoning 机制。事实基准：vLLM `vllm/tool_parsers/`+`vllm/parser/`+`vllm/v1/structured_output/`+`vllm/reasoning/` 与 SGLang `sglang/srt/function_call/`+`srt/constrained/`。

### 一、总览

| 维度 | vLLM | SGLang SRT |
|---|---|---|
| 工具解析包 | `vllm/tool_parsers/`（`abstract_tool_parser.py` 定义 `ToolParser`+`ToolParserManager`） | `sglang/srt/function_call/`（`BaseFormatDetector`+`FunctionCallParser`） |
| 约束解码包 | `vllm/v1/structured_output/`（`StructuredOutputManager` 单例，单后端全局）+ `config/structured_outputs.py` | `sglang/srt/constrained/`（`GrammarManager` per-scheduler + `BaseGrammarBackend`） |
| 推理解析包 | `vllm/reasoning/` + `vllm/parser/engine/`（`ParserEngine` 声明式状态机） | 推理集成在 detector + `ReasonerGrammarBackend` 包装 |
| 前端组合 | `ParserManager.get_parser`：DelegatingParser（Reasoning+Tool 委托）/ HarmonyParser / ParserEngine 折叠 | `serving_chat.py` 直接调 `FunctionCallParser`，无统一 Parser 组合层 |

### 二、工具解析器注册与选择

| 维度 | vLLM `ToolParserManager` | SGLang `ToolCallParserEnum` |
|---|---|---|
| 注册数 | **48 个名称**（`__init__.py` `_TOOL_PARSERS_TO_REGISTER`，惰性注册） | **33 个 parser 名**（`function_call_parser.py:64-99` 纯类字典）+ `JsonArrayParser` 通用兜底 |
| 注册机制 | `register_lazy_module`/装饰器/`import_tool_parser` 插件（`--tool-parser-plugin`） | 无注册表层，`inspect.signature` 条件注入 tokenizer |
| 选择方式 | **显式指定** `--enable-auto-tool-choice`+`--tool-call-parser`，无自动探测，未配解析器直接抛 TypeError | `--tool-call-parser` 支持 `auto`，自动探测在 `parser/template_detection.py` |
| structural tag | 类属性 `structural_tag_model` 声明 xgrammar builtin key（hermes/llama/deepseek_r1/qwen_3_coder/glm_4_7/kimi…） | `detector.get_structural_tag_name()` → `xgrammar.get_model_structural_tag`，个别自实现（deepseekv4/gpt_oss/glm47/kimik2） |

> 关键差异 ①：vLLM 工具解析**必须手动指定**、由 `ParserManager` 组合成统一 `Parser`；SGLang 支持 **auto 自动探测**模型格式，约束决策（structural tag vs json_schema）集中在 `get_structure_constraint` 一棵决策树。

### 三、接口契约对比

| 契约 | vLLM `ToolParser` | SGLang `BaseFormatDetector` |
|---|---|---|
| 能力声明 | `supports_required_and_named`/`structural_tag_model`/`engine_based_streaming` 类属性 | `parses_required_natively()`/`supports_structural_tag()` + `ToolStrictLevel` |
| 非流式 | `extract_tool_calls(model_output, request)` → `ExtractedToolCallInformation` | `detect_and_parse(full_text)` → `(calls, content)` |
| 流式 | `extract_tool_calls_streaming(previous/current/delta text+token_ids, request)` → `DeltaMessage\|None` | `parse_streaming_increment(new_text, tools)` 内部自行缓冲（`_buffer`） |
| 流式状态 | `prev_tool_call_arr`/`current_tool_id`/`current_tool_name_sent`/`streamed_args_for_tool` | **同名同义四字段**（高度同构） |
| 完成收尾 | `get_remaining_unstreamed_args()` 补发尾巴 | `finish()` 冲刷滞留文本 |
| 错误处理 | 解析异常吞掉，原文回吐 / 返回 None | `partial_json_parser` 失败按「未完成」处理；非法工具名受 `SGLANG_FORWARD_UNKNOWN_TOOLS` 控制 |

### 四、工具约束决策（structural tag / tool_choice）

| 分支 | vLLM | SGLang `get_structure_constraint`（function_call_parser.py:243） |
|---|---|---|
| 约束入口 | `ToolParser.adjust_request` 从 tools 构造 `StructuredOutputsParams`（JSON schema+strict） | `("structural_tag", StructuralTagResponseFormat)` 或 `("json_schema", Any)` 唯一交接类型 `ToolCallConstraint` |
| 原生 tag | `structural_tag_model` → xgrammar builtin | 原生 tag（`get_structural_tag`）→ xgrammar；legacy 格式兜底（`get_legacy_structural_tag`） |
| JSON schema 兜底 | `supports_required_and_named=True` 时服务层通用 JSON 解析（`streaming.py`） | `parses_required_natively()` 为假时 `get_json_schema_constraint`（数组 schema，`maxItems` 控并行） |
| strict 语义 | `VLLM_ENFORCE_STRICT_TOOL_CALLING` 强制 structural tag、关闭通用 JSON | `SGLANG_TOOL_STRICT_LEVEL`：OFF=0/FUNCTION=1/PARAMETER=2，PARAMETER 级强制全工具 strict 入 grammar |
| 互斥 | `StructuredOutputsParams` 六类约束（json/regex/choice/grammar/json_object/structural_tag）互斥 | `json_schema/regex/ebnf/structural_tag` 四类互斥（`sampling_params.py:71`）；工具约束与 response_format 并存时 required/具名抛错、auto 告警 |

### 五、约束解码后端对比

| 维度 | vLLM `v1/structured_output/` | SGLang `srt/constrained/` |
|---|---|---|
| 后端 | xgrammar / **guidance** / outlines / lm-format-enforcer（`backend_*`，懒导入） | xgrammar / outlines / **llguidance**（`--grammar-backend`，可 `register_grammar_backend` 自定义）；xgrammar 初始化失败回退 none |
| 请求 FSM | `StructuredOutputGrammar`（accept_tokens/validate_tokens/rollback/fill_bitmask） | `BaseGrammarObject`（accept_token/fill_vocab_mask/try_jump_forward/copy） |
| 缓存 | `StructuredOutputRequest._grammar` Future + `structured_output_key`（json→json_object→regex→choice→grammar→structural_tag 优先级） | `BaseGrammarBackend.cache` + `get_cached_or_future_value`，命中 `value.copy()` 独立 FSM |
| 编译调度 | `StructuredOutputManager.grammar_init` 异步 `ThreadPoolExecutor`；外部启动器改同步防死锁 | `GrammarManager` 异步编译队列 + PP0 轮询 `all_gather_object` 跨 DP/TP 同步 + `_pp_sync_ready_failed` 逐级 PP 转发 |
| 失败处理 | Future 携带异常，`grammar_compile_error_reqs` 仅该请求失败 | `InvalidGrammarObject` 统一表达，`set_finish_with_abort` |
| structural tag | `compile_structural_tag`（`XgrammarBackend`） | legacy（`StructuralTag.from_legacy_structural_tag`）与 xgrammar 原生 new 两格式；llguidance `StructTag.to_grammar` |
| jump-forward | —（validate_tokens 只服务投机过滤） | xgrammar `find_jump_forward_string` / outlines 压缩 FSM 表（未启用）/ llguidance `compute_ff_tokens` |
| ReDoS 防护 | `compile_regex_with_timeout`（`VLLM_REGEX_COMPILATION_TIMEOUT_S`） | NUL 预检（`\x00` 会段错误，mlc-ai/xgrammar#850） |

### 六、采样衔接与 bitmask

| 环节 | vLLM | SGLang |
|---|---|---|
| 等待编译 | `WAITING_FOR_STRUCTURED_OUTPUT_GRAMMAR` 状态 | grammar Future 未就绪时请求不入队（`scheduler.py:2706`） |
| mask 生成 | `grammar_bitmask(requests, ids, spec_tokens)` 产出 np.int32 bitmask，投机窗口模拟思考越过点 | `update_regex_vocab_mask`（`sampling_batch_info.py:239`）→ `fill_vocab_mask_batched` → `GrammarMask` |
| 应用 | GPU `xgr.apply_token_bitmask_inplace`；`StructuredOutputsWorker` Triton kernel（CPU/自适应验证） | `sgl_kernel.apply_token_bitmask_inplace_cuda` / Triton `bitmask_ops` / npu-cpu 分支 |
| 推进 | `should_advance`+`trim_reasoning_for_advance`+`grammar.accept_tokens` | `_apply_prefill_grammar`（`batch_result_processor.py:574`）`accept_token`，非法抛 `ValueError`→`FINISH_ABORT` |
| 投机 | `validate_tokens` 过滤草稿后回填 | `spec_utils.traverse_tree` 逐草稿节点 accept/fill/rollback；llguidance 原生草稿链 kernel |

Reasoning 对比与流式解析路线见 [_part2](tool-structure-comparison_part2.md)。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
