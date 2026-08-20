## 工具调用解析（ToolParser）：请求改写与注册表

本文承接 [tool-parsers-overview_part1.md](tool-parsers-overview_part1.md)，说明 `adjust_request` 请求侧改写、`get_structural_tag` 双开关，以及 `ToolParserManager` 注册表机制。

### adjust_request：请求侧改写

基类 `adjust_request()` 做两件事（`abstract_tool_parser.py:119-166`）：

1. 若 `request.structured_outputs.structural_tag` 已被设置（统一 parser 已处理 model-specific tag），直接原样返回。
2. 否则由 `get_json_schema_from_tools(tool_choice, tools)` 推导 schema；非 `None` 时：
   - `ChatCompletionRequest` → 写 `request.structured_outputs = StructuredOutputsParams(json=...)` 并**清空** `response_format`；
   - `ResponsesRequest` → 一次性构造 `ResponseTextConfig(format=ResponseFormatTextJSONSchemaConfig(type="json_schema", name="tool_calling_response", schema=..., strict=True))`（注释说明必须单次构造，否则 Pydantic v2 的 `__fields_set__` 不记录 `format`，会在 `model_dump` 中丢失）。

子类常见覆写模式：把 `request.skip_special_tokens = False`。原因在 `hermes_tool_parser.py:64-67` 写得最清楚——`<tool_call>` 一类标记在部分模型里被标为 special token，若在进入解析器前被跳过，工具调用就解析不出来。采用此模式的有 hermes、granite4、internlm2、kimi_k2、gigachat3、step3、cohere 等。

另一类覆写是**完全绕过**基类逻辑：

- `MistralToolParser.adjust_request` 直接委派 `self._parser_engine.adjust_request(request)`，注释说明 Mistral 通过 grammar `mode`（auto/none/required/named）表达 `tool_choice`，再叠加 tool-derived json_schema 会被 mistral-common 并成 union，导致模型可以用裸 JSON 顶替真正的 `[TOOL_CALLS]`。
- `Gemma4EngineToolParser.adjust_request` 在 required/named 时只设 `skip_special_tokens=False` 就返回，避免强制 JSON 与原生 `<|tool_call>call:...` 语法冲突（注释指出会「leak as content and crashes EngineCore under speculative decoding」）。
- `RustToolParser.adjust_request` 有意不调 `super()`，仅在 `preserve_special_tokens()` 为真时设 `skip_special_tokens=False`——Rust 侧被视为不透明的语法权威。

### get_structural_tag

```python
def get_structural_tag(self, request, *, reasoning: bool = False):
    if self.structural_tag_model is None:
        return None
    if not envs.VLLM_ENFORCE_STRICT_TOOL_CALLING:
        return None
    from vllm.tool_parsers.structural_tag_registry import get_model_structural_tag
    return get_model_structural_tag(model=self.structural_tag_model, tools=request.tools,
                                    tool_choice=request.tool_choice, reasoning=reasoning)
```

即：**双开关**——既要解析器声明了 `structural_tag_model`，又要 `VLLM_ENFORCE_STRICT_TOOL_CALLING` 打开，才会生成 structural tag。`get_model_structural_tag` 内部再判：无 tools 或 `tool_choice == "none"` 返回 `None`；`tool_choice == "auto"` 且没有任何 tool 标了 `strict=True` 也返回 `None`（即宽松模式不加约束）。

模型 key 分两个来源：`XGRAMMAR_BUILTIN_STRUCTURAL_TAG_MODELS = {llama, kimi, deepseek_r1, deepseek_v3_1, qwen_3_5, qwen_3_coder, qwen_3, deepseek_v3_2, glm_4_7, deepseek_v4}`（转发给 `xgrammar.get_model_structural_tag`）与 `VLLM_BUILTIN_STRUCTURAL_TAG_MODELS = {hermes, kimi_k3}`（走 `_VLLM_STRUCTURAL_TAG_REGISTRY` 中经 `@register_vllm_structural_tag` 注册的构造函数）。key 不在两者之内会抛 `ValueError: Unknown format type`。

### ToolParserManager 注册表

`ToolParserManager` 是纯类方法注册表，持两张表：

| 表 | 类型 | 内容 |
|---|---|---|
| `tool_parsers` | `dict[str, type[ToolParser]]` | 已就绪（eager 注册或惰性加载后缓存）的类 |
| `lazy_parsers` | `dict[str, tuple[str, str]]` | name → (module_path, class_name)，尚未 import |

| 方法 | 行为 |
|---|---|
| `get_tool_parser(name)` | 先查 `tool_parsers`；命中 `lazy_parsers` 则走 `_load_lazy_parser`；都没有抛 `KeyError(f"Tool parser '{name}' not found.")` |
| `_load_lazy_parser(name)` | `importlib.import_module` → `getattr` 取类 → 校验 `issubclass(..., ToolParser)`（否则 `TypeError`）→ **回写 `tool_parsers[name]` 缓存** |
| `register_lazy_module(name, module_path, class_name)` | 只写映射，不 import |
| `register_module(name=None, force=True, module=None)` | 传 `module` 即刻注册；不传则作装饰器使用，且**装饰器路径只写 `lazy_parsers`**（"Lazy mapping only: do not import now"） |
| `_register_module(module, module_name, force)` | 校验子类关系；`module_name` 可为 `str`/`list[str]`/`None`（`None` 取 `module.__name__`）；`force=False` 且重名时抛 `KeyError` |
| `list_registered()` | 返回两表 key 的并集（排序） |
| `import_tool_parser(plugin_path)` | 用 `import_from_path` 从任意文件路径加载用户自定义解析器；失败仅 `logger.exception` 不抛 |

**惰性注册是本模块的关键设计**：约 40 个实现文件中不少要 import `transformers`、`partial_json_parser`、xgrammar、甚至 Rust 扩展，全部 eager import 会显著拖慢启动。`__init__.py` 只写 48 条 `(name → module_path, class_name)` 映射，真正 import 发生在 `get_tool_parser(name)` 首次命中时。

同一个类可注册多个别名，例如 `llama3_json` 与 `llama4_json` 同指 `Llama3JsonToolParser`；`glm45`/`glm47` 同指 `Glm47MoeModelToolParser`；`mimo`/`qwen3_coder`/`qwen3_xml` 同指 `Qwen3EngineToolParser`；`cohere_command3`/`cohere_command4` 同文件不同类。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
