## 输入数据模型

源码包：`vllm/inputs/`、`vllm/tokenizers/`、`vllm/transformers_utils/`。

### inputs 包结构

| 文件 | 职责 |
|---|---|
| `llm.py` | LLM API 层 prompt schema（`TextPrompt` 等） |
| `engine.py` | engine 层输入 schema（`TokensInput` 等）、编码器-解码器组装 |
| `preprocess.py` | `InputPreprocessor`：prompt → engine 输入 |
| `__init__.py` | 统合导出 |

### Prompt 层（inputs/llm.py）

| 类型 | 说明 |
|---|---|
| `TextPrompt` | `prompt: str`，文本待 tokenize |
| `TokensPrompt` | `prompt_token_ids`，可带 `prompt`、`token_type_ids`、`prompt_token_offsets` |
| `EmbedsPrompt` | `prompt_embeds` 直接喂模型；混合模式带 `prompt_token_ids` + `prompt_is_token_ids` 位置掩码 |
| `DecoderOnlyPrompt` | `str / TextPrompt / list[int] / TokensPrompt / EmbedsPrompt` |
| `EncoderDecoderPrompt` | 单例 prompt 或 `ExplicitEncoderDecoderPrompt{encoder_prompt, decoder_prompt}` |
| `DataPrompt` | 由 IO processor 插件转换为 `PromptType` 的通用输入 |

公共选项（`_PromptOptions`）：`multi_modal_data`、`multi_modal_uuids`（用户 UUID，None 时由 hasher 计算）、`mm_processor_kwargs`、`cache_salt`。

| 类型 | 说明 |
|---|---|
| `MultiModalDataDict` | `Mapping[str, ModalityData]`，内建模态 image/video/audio/vision_chunk |
| `MultiModalUUIDDict` | 每条目用户指定 `str/str|None 列表`，用于所有缓存 |
| `vision_chunk` | 统一图像/视频分块模态（`VisionChunk`） |

### Engine 层（inputs/engine.py）

| 类型 | 说明 |
|---|---|
| `TokensInput` | `type="token"` + `prompt_token_ids` |
| `EmbedsInput` | `type="embeds"` + `prompt_embeds`，混合模式另带 `prompt_token_ids`/`is_token_ids` |
| `MultiModalInput` | `type="multimodal"`：`prompt_token_ids` + `mm_kwargs` + `mm_hashes` + `mm_placeholders` |
| `MultiModalEncDecInput` | 编码器-解码器多模态输入（额外 `encoder_prompt_token_ids`） |
| `EncoderDecoderInput` | `{type:"enc_dec", encoder_prompt, decoder_prompt}` |

均有可选 `prompt`（对应文本）、`cache_salt`、`assistant_tokens_mask`（chat 模板 `{% generation %}`）。

### text-to-token 管线

`InputPreprocessor.preprocess(prompt)` 流程：

1. encode-decoder 模型走 `_process_encoder_decoder_prompt`，经 `build_enc_dec_input` 拆分 encoder/decoder，必要时补 `decoder_start_token_id`（`skip_decoder_start_token` 可由 `EncDecMultiModalProcessor` 覆盖）。
2. 否则 `_process_decoder_only_prompt`：
   - 含 `prompt_embeds` → `_process_embeds`
   - 含 `prompt_token_ids` → `_process_tokens`（先 `_truncate_inputs` 截断；带 `multi_modal_data` 时走 `_process_multimodal`）
   - 含 `prompt` → `_process_text`（`_tokenize_prompt` tokenize；带多模态时走 processor）

Tokenize/多模态处理实际由 `renderer`（`BaseRenderer`，`vllm/renderers`）完成，tokenization kwargs 叠加在渲染器默认参数上。

### Tokenizer 封装（vllm/tokenizers/）

| 文件 | 说明 |
|---|---|
| `protocol.py` | `TokenizerLike` 协议：encode/decode/apply_chat_template/convert_tokens_to_ids 等 |
| `registry.py` | `TokenizerRegistry` 按 mode 映射类；`get_tokenizer`/`cached_tokenizer_from_config` |
| `hf.py` | `CachedHfTokenizer` 缓存属性；`maybe_make_thread_pool` 用深拷贝池做线程安全 |
| `detokenizer_utils.py` | 流式 detokenize |

注册的 tokenizer mode（`_VLLM_TOKENIZERS`）：`hf`（默认 CachedHfTokenizer）、`mistral`、`deepseek_v32`、`deepseek_v4`、`kimi_audio`、`inkling`、`cohere` 等。

关键行为：

- `truncation_side`：generate/draft 默认 `left`，pooling 默认 `right`。
- `--tokenizer-mode slow` 强制 `use_fast=False`；Mistral 仓库自动切 `mistral` 模式。
- hub 上 tokenizer_class 错误的模型（internlm2、step3_vl 等）绕过 AutoTokenizer 直取 `TokenizersBackend`。
- ModelScope 可用（`VLLM_USE_MODELSCOPE`）且需 `modelscope>=1.18.1`。
- 使用慢 tokenizer 时告警提示性能下降。

### transformers_utils 集成

| 模块 | 说明 |
|---|---|
| `config.py` | HF config 注册表（`_CONFIG_REGISTRY`：afmoe/deepseek_v4/... 数百定制 config），要求 transformers>=5.0 |
| `configs/` | 各模型定制 `PretrainedConfig` 子类 |
| `processor.py` | `get_processor`/`cached_processor_from_config` 懒加载 HF processor，过滤动态 kwargs 后缓存；`call_hf_processor_mm_only` 只处理媒体 |
| `processors/` | 模型定制 `ProcessorMixin` 子类（glm4v、internvl、qwen3_asr、kimi_audio 等约 40 个） |
| `repo_utils.py`/`s3_utils.py` | HF/S3 远端文件存取、路径转换 |

注意：`processor_config.json`/`preprocessor_config.json` 用于定位 processor_class；视频处理器支持 `video_preprocessor_config.json` 与 transformers model_type 映射回退。

### 增量输入（embedding 切片）

解码器逐步生成时，占位符 token 逐段加入 prompt。`PlaceholderRange` 提供增量索引能力：

- `embeds_cumsum`：`is_embed` 掩码的累计和（list[int]，避免 torch 开销）。
- `get_embeds_indices_in_range(start, end)`：`[start,end)` 区间对应的 encoder 输出 embedding 序号。
- `get_num_embeds()`：本占位符区域实际 embedding 数。
- `extract_embeds_range()`：导出 `is_embed` 为 True 的连续区间列表。

据此新生成的占位符 token 只需从预计算 encoder 输出按区间取对应行，无需重复编码媒体。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)