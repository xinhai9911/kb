## 工具调用解析（ToolParser）接口契约与注册机制

本文基于 `vllm/tool_parsers/` 源码，说明 `ToolParser` 抽象契约、`ToolParserManager` 注册表、按名称/模型选择流程，以及 `tool_choice` 在解析层的分派规则。

### 模块结构

目录下没有独立的 `registry.py` / `base.py`：接口与注册表**同在** `abstract_tool_parser.py` 中，`__init__.py` 只做惰性注册表的批量填充。

| 文件 | 职责 |
|---|---|
| `abstract_tool_parser.py` | 定义 `ToolParser` 抽象基类 + `ToolParserManager` 注册表；`__all__ = ["Tool"]` 转出 `Tool` 类型别名 |
| `__init__.py` | 维护 `_TOOL_PARSERS_TO_REGISTER`（name → (filename, class_name)）字典，导入时调用 `register_lazy_tool_parsers()` 批量惰性注册（共 48 个名称） |
| `utils.py` | 公共解析工具：`partial_json_loads`、`is_complete_json`、`find_common_prefix/suffix`、`extract_intermediate_diff`、`partial_tag_overlap`、`consume_space`、`make_valid_python`、`handle_single_tool`、`compute_tool_delta`、`get_json_schema_from_tools` 等 |
| `streaming.py` | `tool_choice` 为 named/required 时的**通用**流式辅助：`extract_named_tool_call_streaming`、`extract_required_tool_call_streaming`、`filter_delta_text` |
| `structural_tag_registry.py` | xgrammar structural tag 桥接：`get_model_structural_tag()`、`XGRAMMAR_BUILTIN_STRUCTURAL_TAG_MODELS`、`VLLM_BUILTIN_STRUCTURAL_TAG_MODELS`、`register_vllm_structural_tag` |
| `rust_tool_parser.py` | `RustToolParser`：桥接 `vllm._rust_tool_parser` PyO3 扩展的通用适配器（自身不注册） |
| `*_tool_parser.py`（约 40 个） | 各模型的具体实现 |

`Tool` 类型别名定义在 `utils.py`：`Tool: TypeAlias = ChatCompletionToolsParam | ResponsesTool`。

### ToolParser 类级契约（能力声明）

三个类属性构成解析器对服务层的「能力声明」（`abstract_tool_parser.py:59-63`）：

| 属性 | 默认 | 语义 |
|---|---|---|
| `supports_required_and_named` | `True` | `True` 时 `tool_choice="required"` / 具名函数走服务层**通用 JSON 解析**（依赖引导解码产出规范 JSON）；`False` 时回退到本解析器的 `extract_tool_calls*`，与 `"auto"` 同等处理 |
| `structural_tag_model` | `None` | 声明其工具调用语法对应的 xgrammar builtin structural tag key（如 `"hermes"`、`"llama"`、`"deepseek_r1"`、`"qwen_3_coder"`、`"glm_4_7"`、`"kimi"`、`"harmony"`） |
| `engine_based_streaming` | `False` | 是否由 `ParserEngine` 增量驱动流式（`ParserEngineToolAdapter` 覆写为 `True`） |

`__init_subclass__` 中有一条隐式联动：若子类声明了 `structural_tag_model` 且环境变量 `VLLM_ENFORCE_STRICT_TOOL_CALLING` 打开，则强制把 `supports_required_and_named` 置为 `False`——因为此时约束由 structural tag 而非 JSON schema 施加。

```python
def __init_subclass__(cls, **kwargs: Any) -> None:
    super().__init_subclass__(**kwargs)
    if (cls.structural_tag_model is not None
            and envs.VLLM_ENFORCE_STRICT_TOOL_CALLING):
        cls.supports_required_and_named = False
```

### 实例级契约（构造与流式状态）

`__init__(tokenizer: TokenizerLike, tools: list[Tool] | None = None)`；`tools` 会被过滤为仅保留 `ChatCompletionToolsParam | FunctionTool` 实例存入 `self.tools`。基类初始化四个流式状态字段，是服务层与子类共同依赖的**事实约定**：

| 字段 | 类型 | 含义 |
|---|---|---|
| `prev_tool_call_arr` | `list[dict]` | 上一轮解析出的工具调用对象数组（含 `name`/`arguments`） |
| `current_tool_id` | `int`（初始 `-1`） | 当前正在解析的工具调用下标 |
| `current_tool_name_sent` | `bool` | 当前工具的函数名是否已下发给客户端 |
| `streamed_args_for_tool` | `list[str]` | 每个工具**已下发**的参数文本，用于 diff |

`vocab` 为 `cached_property`，走 `tokenizer.get_vocab()`（注释说明只有 `TokenizersBackend` 保证有 `.vocab`，故统一用 `get_vocab()`）。

`get_remaining_unstreamed_args()` 是收尾钩子：取 `prev_tool_call_arr[-1]["arguments"]` 与 `streamed_args_for_tool[-1]` 做前缀比对，返回「已解析但未下发」的尾巴。服务层在 `DelegatingParser._append_unstreamed_tool_args()`（`vllm/parser/abstract_parser.py:752-765`）把它拼到最后一个 delta 的 `arguments` 上。

### 两个核心方法：non-streaming vs streaming

| | `extract_tool_calls` | `extract_tool_calls_streaming` |
|---|---|---|
| 入参 | `model_output: str`、`request` | `previous_text`、`current_text`、`delta_text`、`previous_token_ids`、`current_token_ids`、`delta_token_ids`、`request` |
| 返回 | `ExtractedToolCallInformation(tools_called, tool_calls, content)` | `DeltaMessage \| None` |
| 状态 | 基类 docstring 注明「Static because it's stateless」——对完整输出一次性解析 | **必须**是实例方法，依赖上述四个流式状态字段做增量 diff |
| 未实现时 | 抛 `NotImplementedError` | 抛 `NotImplementedError` |
| `None` 语义 | — | 本轮无可下发内容（token 还不足以构成合法片段），服务层跳过该 chunk |

约定俗成的错误处理：几乎所有实现都把解析异常吞掉——non-streaming 返回 `tools_called=False, tool_calls=[], content=model_output`（把原文当普通文本回吐），streaming 返回 `None`。例如 `hermes_tool_parser.py:116-120`、`granite_tool_parser.py:96-100`、`pythonic_tool_parser.py:110-115`。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
