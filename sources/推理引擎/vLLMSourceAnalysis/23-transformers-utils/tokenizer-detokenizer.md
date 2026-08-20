## tokenizers/ 分词器与 detokenizer 反分词

本版本（Transformers v5，vLLM ≥0.24）将分词器从 `transformers_utils/` 迁出至 `vllm/tokenizers/`（`hf.py`、`registry.py`、`protocol.py`、`detokenizer_utils.py` 等），反分词器位于 `vllm/v1/engine/detokenizer.py`；`transformers_utils/` 仅保留 `processor.py` 与 `processors/` 输入处理器。

### 使用链路：entrypoint → Renderer → Tokenizer

| 环节 | 位置 | 行为 |
|---|---|---|
| 在线/离线入口 | `entrypoints/llm.py:387` `LLM.get_tokenizer()` → `v1/engine/llm_engine.py:388` | 委托给 Renderer |
| Renderer 装载 | `renderers/registry.py:82` `renderer_from_config(config)` | 调 `cached_tokenizer_from_config(model_config)` 后按 tokenizer 模式选渲染器 |
| 词表/编码服务 | `LLMEngine.tokenizer` / `AsyncLLM.get_tokenizer` | 供 chat 模板、`apply_chat_template`、结构化输出、多模态等消费 |
| 反解码 | `v1/engine/output_processor.py` | 每请求 `IncrementalDetokenizer`（见下） |

各模型内部也可直接 `cached_tokenizer_from_config(model_config)`（`model_executor/models/` 中 ASR/OCR/VL 等，以及 `multimodal/registry.py`、`v1/structured_output/__init__.py`、`config/reasoning.py`）。

### TokenizerLike 协议（protocol.py）

定义 vLLM 所需的 tokenizer 最小接口（协议类，鸭子类型）：`from_pretrained`、`num_special_tokens_to_add`、`all_special_tokens/ids`、`bos/eos/pad_token_id`、`is_fast`、`vocab_size`、`max_token_id`、`max_chars_per_token`、`truncation_side`、`__call__`、`get_vocab/get_added_vocab`、`encode`、`apply_chat_template`、`convert_tokens_to_ids/string`、`decode`、`convert_ids_to_tokens`。`__hash__ = hash(id(self))`、`__len__ = vocab_size`。

### tokenizer 模式注册（registry.py）

`_VLLM_TOKENIZERS`：tokenizer 模式 →（模块, 类名）：

| 模式 | 实现 | 说明 |
|---|---|---|
| `hf` | `hf.CachedHfTokenizer` | 默认，AutoTokenizer + 属性缓存 |
| `cohere` / `inkling` / `kimi_k3` | `hf.CachedHfTokenizer` | 仅渲染器换模板（cohere 用 melody，inkling 无 Jinja 模板） |
| `mistral` | `mistral.MistralTokenizer` | 官方 Mistral tokenizer（`tekken.json`/`tokenizer.model.v*`） |
| `deepseek_v32` / `deepseek_v4` | `deepseek_v32.DeepseekV32Tokenizer` 等 | 自研 DeepSeek 分词器 |
| `kimi_audio` | `kimi_audio.KimiAudioTokenizer` | 音频专用 |

- `_TokenizerRegistry.register(模式, 模块, 类名)` / `load_tokenizer_cls`（`resolve_obj_by_qualname`）；`TokenizerRegistry` 为全局单例。
- `_MODEL_TYPES_WITH_INCORRECT_TOKENIZER_CLASS = {"internlm2","step3_vl","step3p7","unlimited-ocr"}`：hub 上 tokenizer_class 有误的模型，绕过 AutoTokenizer 直接用 `TokenizersBackend`。

### get_tokenizer 解析流程（registry.py:186）

1. `VLLM_USE_FASTOKENS=1` 时先 `apply_fastokens_patch()`（进程级、幂等，替换 HF fast tokenizer 的 Rust BPE 后端）。
2. `cached_resolve_tokenizer_args`（`lru_cache`）解析：`runner_type` 决定 `truncation_side`（generate/draft→`"left"`，pooling→`"right"`）；`tokenizer_mode="slow"` 强制 `use_fast=False` 且不可与 fast 冲突；`auto` 且仓库为 Mistral 格式（`is_mistral_model_repo` + 含 tekken 文件）→ `mistral`，否则回退 `hf`；ModelScope 模式下先 `snapshot_download` 分词器文件（`ignore_file_pattern` 跳过权重）。
3. `TokenizerRegistry.load_tokenizer_cls(mode)` 选类；HF 类时 `config_format="hf"` 强制走 `get_config()`（Mistral 双格式仓库避免选错 tokenizer 类），并把已加载的 config 传回 `kwargs["config"]` 复用（防并发刷新竞态）。
4. `from_pretrained(...)`；hub 错误提示 `--trust-remote-code` 与升级 transformers。
5. `cached_get_tokenizer = lru_cache(get_tokenizer)` 进程级缓存；`cached_tokenizer_from_config(model_config)` 在 `skip_tokenizer_init` 时返回 `None`，并先 `_maybe_register_hf_config` 确保 AutoConfig 已注册。

### HF tokenizer 缓存与线程安全（hf.py）

- `get_cached_tokenizer(tokenizer)`：`copy.copy` + 动态子类 `CachedTokenizer`，缓存 `all_special_ids/tokens`、`max_token_id`（与 `vocab_size` 取大）、`max_chars_per_token`、`is_fast`、`get_vocab`、`len`，避免 transformers 反复重算；`__reduce__` 经 `get_cached_tokenizer` 重建。
- `maybe_make_thread_pool(tokenizer, copies=1)`：对 `TokenizersBackend` 把公共接口路由到深拷贝池（`queue.Queue` 借出/归还），保证多线程安全；`TokenizerPool.__reduce__` 经 `maybe_make_thread_pool` 重建（问题 #45433）。仅 `TokenizerLike` 公共接口线程安全，`_tokenizer` 属性与 `add_special_tokens` 等变异方法不安全。
- `CachedHfTokenizer.from_pretrained`：AutoTokenizer 加载后，若 sentence-transformer `do_lower_case=True` 则把 `special_tokens_map` 全小写重加。

### Detokenizer（v1/engine/detokenizer.py）

`IncrementalDetokenizer.from_new_request` 工厂：`tokenizer is None` → 空实现（跳过反解码）；`USE_FAST_DETOKENIZER`（`tokenizers>=0.22.0`）且为 `TokenizersBackend` → `FastIncrementalDetokenizer`；否则 `SlowIncrementalDetokenizer`。| 类 | 机制 |
|---|---|
| `FastIncrementalDetokenizer` | tokenizers 库 `DecodeStream`（`step(tokenizer, next_token_id)`），构造时以 `ids=prompt_token_ids` 原生 prefill；`_protected_step` 捕获 `Invalid prefix encountered`（重置 stream）与 overflow |
| `SlowIncrementalDetokenizer` | 基于 `detokenize_incrementally`，维护 `tokens/prefix_offset/read_offset` 增量反解码；prompt embeds 请求不可反解码（占位空串） |

公共逻辑 `BaseIncrementalDetokenizer.update(new_token_ids, stop_terminated)`：detokenize 新 token → 按 `stop` 列表做 `check_stop_strings` 截断（返回最早完成的 stop string，`include_stop_str_in_output` 决定截断到尾部还是头部）；`get_next_output_text(finished, delta)` 用 `stop_buffer_length = max(len(stop))-1` 留 buffer（未结束时回退若干字符，避免 stop 字符串被流式吐出一半）。输出处理器（`output_processor.py:669`）在每个 step 调用 `detokenizer.update(...)`，命中 stop string 时置 `finish_reason=STOP`。

### 增量反解码算法（tokenizers/detokenizer_utils.py）

- `convert_prompt_ids_to_tokens`：只把 prompt 尾部 `INITIAL_INCREMENTAL_DETOKENIZATION_OFFSET(5)+2` 个 id 转 token，返回 `(tokens, prefix_offset, read_offset)`。
- `detokenize_incrementally`：取新 token 加入 `output_tokens`，用 `prefix_text` 与 `new_text` 之差产出增量文本；`new_text` 长度不增或尾部含 `�`（未完成的 UTF-8 字节）时返回空串；fast tokenizer 走 `convert_tokens_to_string`，slow + added_vocab 走 `_convert_tokens_to_string_with_added_encoders`。
- `convert_ids_list_to_tokens`：逐 id `decode`，用 pre_tokenizer 配置识别 Metaspace `▁` 标记（SentencePiece 系），恢复 `decode()` 剥掉的句首空格。

### 输入处理器（transformers_utils/processor.py）

- `get_processor`：`convert_model_repo_to_path`（ModelScope 缓存根）→ 从 `processor_config.json`/`preprocessor_config.json`/`tokenizer_config.json` 读 `processor_class` → 优先 `processors` 包内注册类（`getattr(processors, cls_name, None)`），否则 `AutoProcessor`；`cached_get_processor = lru_cache(...)`。
- `cached_processor_from_config`：合并 `ModelConfig.get_multimodal_config().merge_mm_processor_kwargs`，按 `ProcessingKwargs` 键过滤动态参数（`get_processor_kwargs_type/keys`）；`HashableDict/List` 使 lru_cache 可哈希。
- 音频/图像/视频处理器：`cached_get_feature_extractor`、`cached_image_processor_from_config`、`cached_video_processor_from_config`（视频类名含 `VIDEO_PROCESSOR_MAPPING_NAMES` 回退）；`call_hf_processor_mm_only` 只跑多模态分支产出 `BatchFeature`。
- `processors/__init__.py`：`_CLASS_TO_MODULE` 懒加载 40+ 处理器（`InternVLProcessor`、`MiniCPMVProcessor`、`Moondream3Processor`、`MiMoOmniProcessor` 等），docstring 声明两类注册理由：HF 未提供 / vLLM 需覆盖。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
