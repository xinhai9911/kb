## 工具调用解析（ToolParser）：模型选择、服务层分派与主流解析器对比

承接 part1 的接口契约与注册机制。本文说明「如何按模型选到解析器」「服务层如何按 `tool_choice` 分派」，并给出主流解析器对比表与三类流式实现路线。

### 按模型选择：必须显式指定，无自动探测

vLLM **不会**根据模型名自动推断解析器。选择链依赖三个 CLI 参数（`vllm/entrypoints/openai/cli_args.py`）：

| 参数 | 作用 |
|---|---|
| `--enable-auto-tool-choice` | 总开关；开启后 `tool_choice="auto"` 才进入解析流程 |
| `--tool-call-parser <name>` | 指定注册表中的解析器名称（见 part1 `_TOOL_PARSERS_TO_REGISTER`） |
| `--tool-parser-plugin <path>` | 加载外部自定义解析器文件，注册的新名称可被上面引用 |

校验与装配：

1. `cli_args.py:422`：`--enable-auto-tool-choice` 未配 `--tool-call-parser` 直接抛 `TypeError`。
2. `cli_args.py:208-213`：`tool_call_parser` 的 `metavar` 由 `ToolParserManager.list_registered()` 动态生成，展示全部内置选项。
3. `api_server.py:493/638`：启动时若有 `--tool-parser-plugin`，调 `ToolParserManager.import_tool_parser(path)`（基于 `import_from_path`）加载插件。

解析器工厂在 `vllm/parser/parser_manager.py` 的 `ParserManager`：

```python
@classmethod
def get_tool_parser(cls, tool_parser_name, enable_auto_tools=False, model_name=None):
    parser = None
    if not enable_auto_tools or tool_parser_name is None:
        return parser
    parser = ToolParserManager.get_tool_parser(tool_parser_name)  # KeyError -> TypeError
    ...
```

`model_name` 唯一用途是这条 pythonic 警告，不做自动匹配；未注册名称抛 `TypeError`。`get_parser()` 再把 reasoning + tool 两个解析器类组合成最终 `Parser` 子类：

| 组合方式 | 条件 |
|---|---|
| 直接返回 `ParserEngine` 类 | reasoning 与 tool 解析器是**同一引擎**的两半（`_parser_engine_cls` 相同） |
| `_KimiK3Parser` | 任一名称是 `kimi_k3` |
| `HarmonyParser` | `is_harmony=True`（gpt-oss 模型） |
| `DelegatingParser` 子类 | 默认：持 `reasoning_parser_cls` + `tool_parser_cls` 委托 |

### 服务层分派：supports_required_and_named 是核心开关

`DelegatingParser`（`vllm/parser/abstract_parser.py`）在 non-streaming 与 streaming 两条路径按同一规则分派：`supports_required_and_named=True` 时 `tool_choice="required"` / 具名函数走服务层**通用 JSON 解析**；`False` 或 `tool_choice="auto"` 则全部交给解析器自己的 `extract_tool_calls*`（`abstract_parser.py:421-513`）。

| tool_choice | non-streaming 处理 |
|---|---|
| `none` | 跳过；`_engine_based=True` 时仍跑引擎管线再清空 `tool_calls`（`abstract_parser.py:666-683`） |
| 具名函数 + 支持 | 用请求里的函数名包 `FunctionCall(name, arguments=content)`，不做解析 |
| `required` + 支持 | `TypeAdapter(list[FunctionDefinition]).validate_json(content)` 批量解析 |
| `auto`（或回退） | `extract_tool_calls()` → `ExtractedToolCallInformation(tools_called, tool_calls, content)` |

流式路径 `_extract_tool_calls_streaming`（`abstract_parser.py:648-723`）分派到 `vllm/tool_parsers/streaming.py` 的两个**通用辅助函数**：

- `extract_named_tool_call_streaming`：首帧下发 `id`+`name`，之后每帧只带 `arguments=delta_text`；Mistral tokenizer 时工具 id 走 `MistralToolCall.generate_random_id()`。
- `extract_required_tool_call_streaming`：基于 `partial_json_parser`（`Allow.ALL`）解析**部分 JSON 数组**，`filter_delta_text` 裁剪未闭合的 `}` 与 `,`，以 `obj[-1]` 定位当前工具。
- 二者均返回 `(DeltaMessage | None, function_name_returned)` 二元组供上层续传状态。

### 代表性解析器对比

| 注册名 | 类 | 适用模型 | 工具输出格式 | 流式机制 |
|---|---|---|---|---|
| `hermes` | `Hermes2ProToolParser` | Hermes 2 Pro | `<tool_call>{"name","arguments"}</tool_call>`，可带 `<scratch_pad>` | 每轮重解析全文 `<tool_call>` 区域，与 `streamed_args_for_tool` 前缀 diff |
| `llama3_json` / `llama4_json` | `Llama3JsonToolParser` | Llama 3.x / 4.x | `<|python_tag|>[{...}, ...]` JSON 数组 | `partial_json_loads` + `Allow` 位掩码，`find_common_prefix` 处理 JSON 自动补全 |
| `pythonic` | `PythonicToolParser` | Llama 3.2/4、ToolACE 等 | `[f(a=1), g(b=2)]` Python 调用列表 | AST：`make_valid_python` → `handle_single_tool`，`extract_intermediate_diff` 流式 diff |
| `mistral` | `MistralToolParser`（引擎适配器） | Mistral 系列 | `[TOOL_CALLS]name[ARGS]{json}`，`tool_choice` 用 grammar `mode` 表达 | 引擎驱动（`engine_based_streaming=True`） |
| `granite` | `GraniteToolParser` | Granite 3.0（`<|tool_call|>`）/ 3.1（`<tool_call>`） | 前缀标记 + JSON 数组 | partial JSON 路线，特判「先参数后名字」的推进顺序 |
| `granite4` | `Granite4ToolParser` | Granite 4 | JSON 数组（自定义 `_FunctionCallCtor`） | partial JSON 路线 |
| `phi4_mini_json` | `Phi4MiniJsonToolParser` | Phi-4-mini | `functools[{...}]` 包裹 | **无流式**：`extract_tool_calls_streaming` 恒返回 `None`，等完整输出一次性解析 |
| `deepseek_v3` / `deepseek_v31` | `DeepSeekV3/V31ToolParser` | DeepSeek-V3 / R1 / V3.1 | `<｜tool▁calls▁begin｜>` + `<｜tool▁call▁begin｜>type<｜tool▁sep｜>name\n```json\nargs\n```<｜tool▁call▁end｜>` | `token_ids` 中计数 start/end 标记定位工具，正则逐段流式 |
| `qwen3_coder` / `qwen3_xml` / `mimo` | `Qwen3EngineToolParser`（引擎适配器） | Qwen3 / Qwen3-Coder | XML（引擎驱动） | 引擎驱动 |
| `internlm` | `Internlm2ToolParser` | InternLM2 | `<|action_start|><|plugin|>...` | `position` 游标切分文本与工具段 |
| `gptoss`（`openai`） | `GptOssToolParser` | gpt-oss（Harmony 格式） | stub，实际交给 `HarmonyParser` | 不实现，抛 `NotImplementedError` |

共性细节：多数解析器同时容忍 `"arguments"` / `"parameters"` 两种键（如 llama、granite、internlm、phi4mini），最终统一 `json.dumps` 成字符串参数。

### 流式实现的三条技术路线

1. **partial JSON 前缀 diff**（llama3_json、granite、granite4、hermes、pythonic）：每轮对 `current_text` 做部分 JSON 解析（`Allow` 位掩码控制可推断内容），与上一轮结果比对只下发新增片段；函数名要求一次性完整下发，故名字未确定前关掉 `Allow.STR` 位。
2. **标记/正则状态机**（deepseek_v3/v31、jamba、functiongemma、ernie45、hy_v3、internlm）：在 token id 序列里数 `<｜tool▁call▁begin｜>` 等标记数量判断「开新工具/更新/收尾」，再用正则从文本段中抠出 type/name/args 按段下发。
3. **引擎驱动**（`engine_based_streaming=True` 的适配器：mistral、qwen3、deepseek_v32/v4、glm47、kimi_k2、minimax_m2、gemma4、ling3、inkling、seed_oss）：解析逻辑前移到 `ParserEngine`（`vllm/parser/engine/`），`ParserEngineToolAdapter` 只透传：`extract_tool_calls` 走 `extract_tool_calls_from_content`，流式走 `initialize_streaming(ParserState.CONTENT)` + `extract_tool_calls_streaming`，`finish_streaming()` 收尾。`DelegatingParser` 的 `_engine_based` 由双方 `engine_based_streaming` 共同决定（`abstract_parser.py:130-133`）。

### ParserEngine 适配器

`vllm/parser/engine/registered_adapters.py` 用 `make_adapters(ParserEngineCls)` 批量生成「推理适配器 + 工具适配器」对（如 `MistralParserToolAdapter`、`Qwen3ParserToolAdapter`、`DeepSeekV32ParserToolAdapter`），写回 `parser_engine_cls.reasoning_parser_cls/tool_parser_cls`，供两边的 Manager 惰性加载。

由此，新架构的 `ParserEngine` 通过薄适配器复用既有服务层，无需改动 serving 代码——这是 vLLM 在 tool parser 上的演进主线：从「服务层解析纯文本」走向「引擎增量状态机」。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
