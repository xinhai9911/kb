## 输入管线（一）：Prompt 与 Input 的两层 Schema

本文基于 `vllm/inputs/`（`llm.py`、`engine.py`、`__init__.py`），说明用户侧 prompt 类型与引擎侧 input 类型的定义。预处理流程见 [inputs-pipeline_part2.md](inputs-pipeline_part2.md)。

> 注意：当前版本 `vllm/inputs/` 目录下**不存在** `registry.py`/`parse.py`/`prepare.py`，只有 `__init__.py`、`engine.py`、`llm.py`、`preprocess.py`。输入注册表已迁至 `vllm/multimodal/`（`MULTIMODAL_REGISTRY`）与 `vllm/renderers/registry.py`；prompt 解析函数位于 `vllm/renderers/inputs/preprocess.py`。

### 三层类型分工

vLLM 把输入分为三层，均为 `TypedDict`/`TypeAlias`（无运行时类，靠 `type` 字段做 tagged union）：

| 层 | 文件 | 顶层别名 | 作用 |
|---|---|---|---|
| 用户侧 prompt | `vllm/inputs/llm.py` | `PromptType` | `LLM` API 接受的原始格式，允许 `str`/`list[int]`/dict |
| 标准化 dict prompt | `vllm/renderers/inputs/preprocess.py` | `DictPrompt` | 已归一为 dict、但尚未 tokenize |
| 引擎侧 input | `vllm/inputs/engine.py` | `EngineInput` | 已 tokenize/已跑多模态处理器，含 `type` 判别字段 |

`vllm/inputs/__init__.py` 只做再导出：`llm.py` 侧导出 `PromptType`/`TextPrompt`/`TokensPrompt`/`EmbedsPrompt`/`ExplicitEncoderDecoderPrompt`/`DataPrompt`/`ModalityData`/`MultiModalDataDict`/`MultiModalDataBuiltins`/`MultiModalUUIDDict`；`engine.py` 侧导出各 `*Input` 类型与 `tokens_input`/`embeds_input`/`mm_input`/`mm_enc_dec_input`/`build_enc_dec_input`/`split_enc_dec_input`。

### 用户侧 Prompt 类型（vllm/inputs/llm.py）

所有 singleton prompt 共享 `_PromptOptions` 的可选字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `multi_modal_data` | `MultiModalDataDict \| None` | 按模态给出数据项；数量受 `--limit-mm-per-prompt` 限制 |
| `mm_processor_kwargs` | `dict[str, Any] \| None` | 转发给多模态 mapper/processor；多模态各自注册时会分别尝试传入 |
| `multi_modal_uuids` | `MultiModalUUIDDict` | 用户指定的每项 UUID；`None` 项由 `MultiModalHasher` 计算，非 `None` 项覆盖默认哈希且必须逐项唯一 |
| `cache_salt` | `str` | prefix caching 的盐值 |

具体 prompt 类：

| 类 | 必选字段 | 独有可选字段 |
|---|---|---|
| `TextPrompt` | `prompt: str` | — |
| `TokensPrompt` | `prompt_token_ids: list[int]` | `prompt`、`token_type_ids`（cross-encoder 用）、`prompt_token_offsets` |
| `EmbedsPrompt` | `prompt_embeds: torch.Tensor` | `prompt`、`prompt_token_ids`、`prompt_is_token_ids` |
| `ExplicitEncoderDecoderPrompt` | `encoder_prompt`、`decoder_prompt`（可为 `None`） | — |
| `DataPrompt` | `data: Any`、`data_format: str` | 由 IO processor 插件转换成 `PromptType` |

- `prompt_token_offsets` 是逐 token 的 char 级 `(start, end)`，仅在**同时**满足「请求了 offsets」+「使用 Fast(Rust) tokenizer」+「无多模态数据」时才存在，长度等于 `prompt_token_ids`。
- `EmbedsPrompt` 的混合模式（chat completion 内嵌 `prompt_embeds` content part）：`prompt_is_token_ids` 为逐位置掩码，`True` 用真实 token id，`False` 用 `prompt_embeds` 对应行；`prompt_is_token_ids` 为 `False` 的位置在 `prompt_token_ids` 中放占位 token，前向时被 `prompt_embeds` 条目替换。两者同时设置时长度必须一致。

多模态数据别名：

```python
ModalityData = _T | list[_T | None] | None   # 仅在提供 UUID 时才能为 None
MultiModalDataDict = Mapping[str, ModalityData[Any]]
MultiModalUUIDDict = Mapping[str, Sequence[str | None] | str]
```

`MultiModalDataBuiltins`（`@final`，`total=False`）声明 vLLM 预定义模态：`image`、`video`、`audio`、`vision_chunk`（图像与视频块的统一"视觉原子"模态）。

prompt 别名层级：

```python
DecoderOnlyPrompt = str | TextPrompt | list[int] | TokensPrompt | EmbedsPrompt
EncoderPrompt     = str | TextPrompt | list[int] | TokensPrompt   # 不支持 embeds
DecoderPrompt     = str | TextPrompt | list[int] | TokensPrompt   # 不支持多模态
EncoderDecoderPrompt = EncoderPrompt | ExplicitEncoderDecoderPrompt
SingletonPrompt = DecoderOnlyPrompt | EncoderPrompt | DecoderPrompt
PromptType = DecoderOnlyPrompt | EncoderDecoderPrompt
```

对 enc-dec 模型传单个 prompt，等价于 `ExplicitEncoderDecoderPrompt(encoder_prompt=prompt, decoder_prompt=None)`；`decoder_prompt=None` 表示自动推断。

### 引擎侧 Input 类型（vllm/inputs/engine.py）

共享 `_InputOptions`：`arrival_time`（渲染前收到时刻）、`cache_salt`。

| 类 | `type` | 关键字段 | 构造函数 |
|---|---|---|---|
| `TokensInput` | `"token"` | `prompt_token_ids`、`prompt`、`prompt_token_offsets`、`assistant_tokens_mask` | `tokens_input()` |
| `EmbedsInput` | `"embeds"` | `prompt_embeds`、`prompt_token_ids`、`is_token_ids` | `embeds_input()` |
| `MultiModalInput` | `"multimodal"` | `prompt_token_ids`（含占位符）、`mm_kwargs`、`mm_hashes`、`mm_placeholders`、`assistant_tokens_mask` | `mm_input()` |
| `MultiModalEncDecInput` | `"multimodal"` | 继承上者 + `encoder_prompt_token_ids`、`encoder_prompt` | `mm_enc_dec_input()` |
| `EncoderDecoderInput` | `"enc_dec"` | `encoder_prompt`、`decoder_prompt`、`arrival_time` | `build_enc_dec_input()` |

多模态元数据别名：

```python
MultiModalHashes       = Mapping[str, list[str]]                    # 每模态每项的哈希
MultiModalPlaceholders = Mapping[str, Sequence[PlaceholderRange]]   # 占位符在 token 序列中的范围
```

字段要点：

- `EmbedsInput.prompt_token_ids` 与 `is_token_ids` 只在混合模式下出现，且**必须同时存在、长度相等**；纯 embeds 输入时两者都不存在。注意用户侧叫 `prompt_is_token_ids`，引擎侧改名为 `is_token_ids`。
- `assistant_tokens_mask` 为逐 token 的 0/1 掩码，标记 assistant 生成的 token；仅当渲染请求设 `return_assistant_tokens_mask=True` 且 chat template 支持 `{% generation %}` 时填充。
- `MultiModalInput.prompt_token_ids` 是**已处理**的 token IDs，其中包含多模态占位符 token。
- `mm_kwargs` 类型为 `MultiModalKwargsOptionalItems`，batch 后直接传给模型。

构造函数均采用「必选参数入 TypedDict，可选参数非 `None` 才写入 key」的模式，避免 `NotRequired` 字段被写成 `None`：

```python
def tokens_input(prompt_token_ids, *, prompt=None, cache_salt=None) -> TokensInput:
    inputs = TokensInput(type="token", prompt_token_ids=prompt_token_ids)
    if prompt is not None:
        inputs["prompt"] = prompt
    if cache_salt is not None:
        inputs["cache_salt"] = cache_salt
    return inputs
```

input 别名层级（与用户侧一一对应）：

```python
DecoderOnlyEngineInput = TokensInput | EmbedsInput | MultiModalInput
EncoderInput           = TokensInput | MultiModalEncDecInput
DecoderEngineInput     = TokensInput | MultiModalInput
SingletonInput         = DecoderOnlyEngineInput | MultiModalEncDecInput
EngineInput            = DecoderOnlyEngineInput | EncoderDecoderInput
```

即便是纯文本 enc-dec 模型，当前也统一按多模态模型实现（见 `MultiModalEncDecInput` docstring，示例为 bart-plugin）。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
