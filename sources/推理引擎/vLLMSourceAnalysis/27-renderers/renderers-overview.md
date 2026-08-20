## Renderers 渲染器体系总览

本文基于 `vllm/renderers/` 源码,说明「渲染器」(Renderer)如何把用户输入(聊天消息/补全提示/嵌入向量)逐步渲染、分词、多模态处理为引擎输入 `EngineInput`。

### 模块定位与文件清单

渲染器是 vLLM 前端的「提示词处理中枢」:取代旧版 `InputPreprocessor`,统一处理 tokenize、chat template、多模态预处理,并把输出交给 `EngineCoreRequest` 前的 `InputProcessor`(见 [07-inputs-sequence](../07-inputs-sequence/inputs-pipeline_part1.md))。

| 文件 | 职责 |
|---|---|
| `base.py` | `BaseRenderer`(ABC):渲染→分词→多模态→EngineInput 四步契约 |
| `registry.py` | `RendererRegistry` + 全局 `RENDERER_REGISTRY` + `renderer_from_config` |
| `hf.py` | `HfRenderer`:默认渲染器,Jinja chat template + offsets + prompt_embeds 展开 |
| `cohere.py` | `CohereRenderer`:用 `cohere_melody`(Rust)渲染 cmd3/cmd4 |
| `deepseek_v32.py` / `deepseek_v4.py` | 委托 `DeepseekV32/4Tokenizer.apply_chat_template` |
| `kimi_k3.py` | `KimiK3Renderer`:K3 无 Jinja,走 `encoding_k3`,强制 `tokenize=True` |
| `mistral.py` | `MistralRenderer`:mistral-common 模板,异常统一转 `ValueError` |
| `inkling.py` + `inkling_encoding.py` | `InklingRenderer`:无模板无文本形式,消息直接渲染成 token ids |
| `terratorch.py` | `TerratorchRenderer`:dummy 单 token `[1]` + 多模态透传 |
| `embed_utils.py` | `safe_load_prompt_embeds`:base64 解码 `torch.load`(weights_only)+ 校验 |
| `params.py` | `ChatParams` / `TokenizeParams`(frozen dataclass) |
| `online_renderer.py` / `online_derenderer.py` | 在线服务端封装:请求级模板/工具校验,以及输出反渲染 |
| `inputs/` | `preprocess.py`(DictPrompt 规范化)、`tokenize.py`(TokPrompt 类型) |

### BaseRenderer 四步契约

`BaseRenderer(ABC, Generic[TokenizerLike])`(`base.py:72`)是唯一抽象基类。子类只须实现一个方法 `render_messages`(返回 `(ConversationMessage[], DictPrompt)`),其余流水线全部在基类:

```python
# 1) render    : 原始输入 -> DictPrompt(Text/Tokens/EmbedsPrompt)
dict_prompts = render_prompts(prompts)          # bytes -> EmbedsPrompt(base64)
# 2) tokenize  : DictPrompt -> TokPrompt(含 enc/dec 分支)
tok_prompts  = tokenize_prompts(dict_prompts, tok_params)
# 3) extras    : 附加引擎字段(mm_processor_kwargs / cache_salt)
_apply_prompt_extras(tok_prompts, prompt_extras)
# 4) engine    : TokPrompt -> EngineInput(多模态在此展开)
[process_for_engine(p, arrival_time) for p in tok_prompts]
```

顶层入口两套、各有 async 变体:`render_cmpl`(补全,输入 `DictPrompt | bytes` 序列)与 `render_chat`(聊天,输入 `list[ChatCompletionMessageParam]`,返回 `(conversations, engine_prompts)`)。

**支持输入形式**(`render_cmpl`):

| 形式 | 归一化 | 说明 |
|---|---|---|
| `str` | `TextPrompt(prompt=...)` | 直接文本 |
| `list[int]` | `TokensPrompt(prompt_token_ids=...)` | 预分词输入 |
| `dict` | 校验后透传 | 含 `prompt`/`prompt_token_ids`/`prompt_embeds`/`multi_modal_data` |
| `bytes` | `safe_load_prompt_embeds` → `EmbedsPrompt` | base64 编码的 torch.Tensor,需 `--enable-prompt-embeds` |
| `EncoderDecoderPrompt` | `EncoderDecoderDictPrompt` | 仅 encoder-decoder 模型 |

**构造期初始化**(`base.py:73-153`):

- 线程池:`_executor = ThreadPoolExecutor(max_workers=model_config.renderer_num_workers)`(默认 1)跑分词;`_mm_executor`(单 worker,保证 P0/P1 顺序,见 #38418)专跑多模态,避免排队阻塞。
- 多模态:`if mm_registry.supports_multimodal_inputs(...)` 时经 `mm_registry.create_processor` 创建 `mm_processor`(发送端缓存);另建 `_readonly_mm_processor`(processor_only 缓存)供 `/tokenize` 端点用,隔离缓存污染;`maybe_init_mm_gpu_ipc_pool` 按 `mm_ipc_gpu_memory_gb` 初始化 GPU IPC 池。
- `MultiModalTimingRegistry` 记录每请求多模态耗时。

**分词与校验**(`params.py`):

- `TokenizeParams` 控制 `max_total_tokens`/`max_output_tokens`/`pad_prompt_tokens`/`truncate_prompt_tokens`(负值映射 `max_input_tokens`)/`truncation_side`/`return_token_offsets`/`needs_detokenization`。
- `apply_pre_tokenization` 做字符级长度检查与小写化;`apply_post_tokenization` 做 token padding/truncation/长度检查,超限抛 `VLLMValidationError`。
- 默认参数:`default_cmpl_tok_params` 的 `add_special_tokens=True`、`default_chat_tok_params` 为 `False`;有 `mm_processor` 时直接取 `processor.info.default_tok_params`。

**字符偏移(offset)**:`_can_produce_offsets()` 默认 `False`,仅 `HfRenderer` 在 `tokenizer.is_fast` 时返回 `True`。`return_token_offsets` 且无多模态时才请求 `offset_mapping`,结果挂到 `TokensInput.prompt_token_offsets`。

**多模态 UUID**:`_process_mm_uuids` 在 `mm_processor_cache_gb==0` 且关闭 prefix caching 时忽略用户 UUID,统一改写为 `<mm_req_id>-<modality>-<index>`;随后校验 data/uuids 槽位一一对应。

**encoder-decoder 分支**:`_process_enc_dec` 用 `build_enc_dec_input` 组装,`decoder_start_token_id` 取 `hf_config.decoder_start_token_id`,缺失回退 `<BOS>`;`EncDecMultiModalProcessor.skip_decoder_start_token` 时跳过。

### 注册与按模型选择

渲染器与分词器共用同一套 mode 字符串(`registry.py`):

```python
_VLLM_RENDERERS = {
    "cohere": ("cohere", "CohereRenderer"),
    "deepseek_v32": ("deepseek_v32", "DeepseekV32Renderer"),
    "deepseek_v4": ("deepseek_v4", "DeepseekV4Renderer"),
    "hf": ("hf", "HfRenderer"),
    "kimi_audio": ("hf", "HfRenderer"),   # 分词用 KimiAudioTokenizer,渲染走通用 Hf
    "kimi_k3": ("kimi_k3", "KimiK3Renderer"),
    "mistral": ("mistral", "MistralRenderer"),
    "terratorch": ("terratorch", "TerratorchRenderer"),
    "inkling": ("inkling", "InklingRenderer"),
}
```

- `RendererRegistry.register(mode, module, cls)` 重复注册只告警覆盖;`load_renderer_cls` 经 `resolve_obj_by_qualname` 懒加载类。
- 选择入口 `renderer_from_config(config)`(`registry.py:82`):先 `cached_tokenizer_from_config` 取缓存 tokenizer,再 `tokenizer_args_from_config(model_config)[0]` 拿到解析后的 `tokenizer_mode`(即 renderer mode),最后 `RENDERER_REGISTRY.load_renderer`。
- `tokenizer_mode` 默认 `"auto"`,由 `ModelConfig` 按架构自动推断(`config/model.py:675`):`Terratorch`→`terratorch`、`MoonshotKimiaForCausalLM`→`kimi_audio`、`KimiK3ForConditionalGeneration`→`kimi_k3`、`DeepseekV32ForCausalLM`→`deepseek_v32`、`DeepseekV4ForCausalLM`→`deepseek_v4`、`Inkling*`→`inkling`;Mistral 仓库则按 `tekken.json`/`tokenizer.model.v*` 判定(`tokenizers/registry.py:149`)。
- 实例化点:`v1/engine/llm_engine.py:91`、`v1/engine/async_llm.py:135`、`v1/engine/input_processor.py:58`、`inputs/preprocess.py:58`、`entrypoints/openai/api_server.py:382`(在线服务)。

### 代表渲染器对比

| 渲染器 | 模板后端 | content_format | 关键差异 |
|---|---|---|---|
| `HfRenderer` | `tokenizer.apply_chat_template`(Jinja) | 按模板 AST 自动解析(`resolve_chat_template_content_format`) | 通用;支持 offsets、`prompt_embeds` 占位符展开、Kimi-K2.5 `use_unified_vision_chunk` 视频块 |
| `CohereRenderer` | `cohere_melody.render_cmd3/cmd4`(Rust) | `"openai"` | `chat_template_kwargs` 双词表(Cohere v2 字段 + melody 配置槽);拒绝 `template_jinja` 直传;工具/引用/思维块归一化 |
| `DeepseekV32/V4Renderer` | `DeepseekV32/4Tokenizer.apply_chat_template` | `"string"` | 直接透传 `get_apply_chat_template_kwargs()` |
| `MistralRenderer` | mistral-common `apply_chat_template` | `"string"` | `AssertionError`/`MistralCommonException` → `ValueError` |
| `KimiK3Renderer` | K3 `encoding_k3`,`tokenize=True` 强制 | `"string"` | 急切分词(结构符是特殊 token);工具消息按 tool_call 顺序重排;图像默认 `image_mode=None` 保留 alpha |
| `InklingRenderer` | 无(直接 `render_inkling_messages` → token ids) | `"string"` | 无 Jinja/无文本形式;`reasoning_effort` 名称→数值映射 |
| `TerratorchRenderer` | 无 | `"string"` | dummy token `[1]`,纯多模态透传 |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
