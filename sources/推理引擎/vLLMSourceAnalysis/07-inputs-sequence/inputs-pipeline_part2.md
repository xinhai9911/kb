## 输入管线（二）：解析、预处理与 enc-dec 装配

本文承接 [inputs-pipeline_part1.md](inputs-pipeline_part1.md)，基于 `vllm/renderers/inputs/preprocess.py` 与 `vllm/inputs/preprocess.py`、`vllm/inputs/engine.py`，说明 prompt 从原始形态到 `EngineInput` 的实际处理链路。

### 整体链路

```
PromptType（用户传入）
  → parse_dec_only_prompt / parse_enc_dec_prompt   # 归一为 dict + 类型拒绝
  → InputPreprocessor.preprocess
      → _prompt_to_llm_inputs                      # 按 key 分派
          → _process_embeds / _process_tokens / _process_text
              → renderer._tokenize_singleton_prompt / renderer._process_multimodal
  → EngineInput（TokensInput / EmbedsInput / MultiModalInput / EncoderDecoderInput）
```

### Prompt 解析与校验（vllm/renderers/inputs/preprocess.py）

`parse_dec_only_prompt` / `parse_enc_dec_prompt` 把任意 `PromptType` 归一成 dict，并在此层集中做类型拒绝：

| 输入形态 | 归一结果 | 拒绝条件（抛 `TypeError`） |
|---|---|---|
| `str` | `TextPrompt(prompt=...)` | — |
| `list` | `TokensPrompt(prompt_token_ids=...)` | 非全 `int` → "Token prompt should be a list of integers" |
| `dict` | 原样返回 | 无 `prompt`/`prompt_token_ids`/`prompt_embeds` → "must contain text, tokens, or embeddings" |
| 其他 | — | "Prompt should be a string, list of tokens, or dictionary" |

分支专属限制：

| 函数 | 额外拒绝 |
|---|---|
| `parse_dec_only_prompt` | dict 含 `encoder_prompt` → "Cannot pass encoder-decoder prompt to decoder-only models" |
| `_parse_enc_prompt` | 含 `prompt_embeds` → "Cannot pass embeddings prompt to encoder-decoder models" |
| `_parse_dec_prompt` | 同上 embeds 限制；且含 `multi_modal_data`/`mm_processor_kwargs`/`multi_modal_uuids` → "Cannot pass multi-modal inputs to decoder prompt" |

`_validate_prompt_dict` 只在「有 `prompt` 且既无 `prompt_token_ids` 也无 `prompt_embeds`」时生效，此时校验 `prompt` 必须是 `str`，否则 "Prompt text should be a string"。

`parse_enc_dec_prompt` 先看 dict 是否含 `encoder_prompt`：含则拆出 encoder/decoder 两侧分别解析；否则整个 prompt 视作 encoder prompt、decoder 侧为 `None`。

标准化后的 dict 类型别名：

```python
DecoderOnlyDictPrompt = TextPrompt | TokensPrompt | EmbedsPrompt
EncoderDictPrompt     = TextPrompt | TokensPrompt
DecoderDictPrompt     = TextPrompt | TokensPrompt
SingletonDictPrompt   = DecoderOnlyDictPrompt | EncoderDictPrompt | DecoderDictPrompt
DictPrompt            = DecoderOnlyDictPrompt | EncoderDecoderDictPrompt
```

同文件的辅助工具：

| 函数 | 行为 |
|---|---|
| `prompt_to_seq(prompt_or_prompts)` | 把单 prompt 与 prompt 列表统一成序列；`dict`/`str`/`bytes` 或「非空且全 `int` 的 list」视为单个 |
| `conversation_to_seq(...)` | 对 chat 消息列表做同样归一（非空且全 `dict` 视为单个会话） |
| `parse_model_prompt(model_config, prompt)` | 按 `model_config.is_encoder_decoder` 分派到两个 parse 函数 |
| `extract_target_prompt(model_config, prompt)` | enc-dec 时取 `encoder_prompt`，否则取整体 |
| `extract_prompt_components(...)` | 返回 `PromptComponents(text, token_ids, embeds)` NamedTuple |
| `extract_prompt_len(...)` | 经 `length_from_prompt_token_ids_or_embeds` 求 prompt 长度（兼容纯 embeds） |

### InputPreprocessor（vllm/inputs/preprocess.py）

构造 `InputPreprocessor(vllm_config, renderer=None, mm_registry=MULTIMODAL_REGISTRY)`；`renderer` 缺省由 `renderer_from_config(vllm_config)` 生成。该类本身**不持有 tokenizer**，tokenize 与多模态处理全部委托给 renderer。

| 方法 | 行为 |
|---|---|
| `preprocess(prompt, tokenization_kwargs=None)` | 入口；按 `model_config.is_encoder_decoder` 走 `_process_encoder_decoder_prompt(parse_enc_dec_prompt(...))` 或 `_process_decoder_only_prompt(parse_dec_only_prompt(...))` |
| `_prompt_to_llm_inputs` | 按 key 优先级分派：`prompt_embeds` → `prompt_token_ids` → `prompt`，都没有则 `assert_never` |
| `_process_text` | 有 `multi_modal_data` 则 `_process_multimodal`（直接传文本），否则 `_tokenize_prompt` 后 `tokens_input()`；末尾无条件回填 `prompt`，有则回填 `cache_salt` |
| `_process_tokens` | 先 `_truncate_inputs` 截断，再按有无多模态分派；末尾按需回填 `prompt`/`cache_salt` |
| `_process_embeds` | 直接委托 `renderer._process_embeds(parsed_content)` |
| `_tokenize_prompt` | 用 `renderer.default_cmpl_tok_params.with_kwargs(**tokenization_kwargs)` 得到 tok params，再 `renderer._tokenize_singleton_prompt(TextPrompt(...))` |
| `_truncate_inputs` | 同上机制，但传入 `TokensPrompt(prompt_token_ids=inputs)`，借 tokenize 路径实现截断 |
| `tokenizer` / `get_tokenizer()` | 透传 `renderer.tokenizer` / `renderer.get_tokenizer()` |

两处易忽略的差异：

- `_process_tokens` 调用 `_process_multimodal` 时透传 `mm_uuids=parsed_content.get("multi_modal_uuids")`，而 `_process_text` **不传** uuids（只传 `mm_processor_kwargs or {}`）。
- `_process_tokens` 内部调用 `_truncate_inputs(..., tokenization_kwargs)`，但对 `_process_multimodal` 传的是同一份 `tokenization_kwargs`；`_prompt_to_llm_inputs` 在 tokens 分支调用 `_process_tokens(prompt)` 时未转发 `tokenization_kwargs`。

`_prompt_to_llm_inputs` 以三个 `@overload` 声明返回类型随入参精化（`EncoderDictPrompt → EncoderInput`、`DecoderDictPrompt → DecoderEngineInput`、`DecoderOnlyDictPrompt → DecoderOnlyEngineInput`）。

### encoder-decoder 输入装配（build_enc_dec_input）

```python
def build_enc_dec_input(encoder_input, decoder_input,
                        decoder_start_token_id, skip_decoder_start_token=False)
```

流程与关键行为：

1. `_validate_enc_input`：embeds 输入抛 `VLLMValidationError("Embedding inputs are not supported for encoder-decoder models")`；`type == "multimodal"` 但缺 `encoder_prompt_token_ids` 抛 `RuntimeError`（提示应为 enc-dec 模型注册 enc-dec 多模态处理器）。
2. `decoder_input is None` 时 decoder 直接复用 encoder input；否则经 `_validate_dec_input`（同样拒绝 embeds）。
3. encoder 为 `multimodal`：encoder 侧被替换为纯 `tokens_input(encoder_prompt_token_ids)`，**`mm_kwargs`/`mm_hashes`/`mm_placeholders` 全部搬到 decoder 侧**（`mm_input(...)`）。
4. encoder 为 `token`：encoder 侧变为 `tokens_input(prompt_token_ids=[])`（空列表），decoder 侧原样保留。
5. 除非 `skip_decoder_start_token`，`_prepare_decoder_input_ids_for_generation` 在 decoder token 首位补 `decoder_start_token_id`（首位已是该 id 或列表非空时不重复补），行为对齐 HF `GenerationMixin._prepare_decoder_input_ids_for_generation()`。
6. `cache_salt` 从 encoder input 继承到 decoder input。

`decoder_start_token_id` 由 `renderer.get_dec_start_token_id()` 提供；`skip_decoder_start_token` 由 `_process_encoder_decoder_prompt` 从 `renderer.mm_processor`（当其为 `EncDecMultiModalProcessor` 时）的同名属性读取，否则为 `False`。

反向拆分用 `split_enc_dec_input(inputs)`：`type == "enc_dec"` 返回 `(encoder_prompt, decoder_prompt)`，否则返回 `(None, inputs)`——decoder-only 统一按「无 encoder」处理，下游可用同一份代码路径。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
