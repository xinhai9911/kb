## Renderers 多模态衔接、在线封装与媒体资源

续 [renderers-overview.md](renderers-overview.md)。覆盖 HfRenderer 特化、渲染器与多模态链路的衔接、在线服务封装及 `vllm/assets/` 媒体资源。

### HfRenderer 特化能力

`HfRenderer`(`renderers/hf.py:906`)是默认渲染器,在基类之上扩展:

**1. Chat template 解析**(`resolve_chat_template`,hf.py:266),优先级:

1. 请求/服务端给定模板(`chat_template` 参数,名称先解析为 Jinja 内容);
2. AutoProcessor 的 `chat_template`(`tools is None` 时,经 `cached_get_processor` 尝试);
3. AutoTokenizer 的 `get_chat_template`;
4. 内置回退文件(`get_chat_template_fallback_path`,按 `model_type`)。

`safe_apply_chat_template`(hf.py:710)还会:检测模板是否支持 `developer` 角色(基于 Jinja AST),不支持则转 `system` 并合并;`resolve_chat_template_kwargs` 静态解析模板变量并剔除无效 kwargs;统一强制 `return_dict=False`(兼容 transformers v5);`return_assistant_tokens_mask` 时查找 `{% generation %}` 标签并经 `assistant_masks` 提取。

**2. content_format 自动探测**(`resolve_chat_template_content_format`,hf.py:569):对模板 AST 做 BFS,识别 `messages[].content` 循环是否展开为列表(openai 格式)还是字符串(string 格式),支持 `auto` 模式。

**3. prompt_embeds 占位符展开**:`_ensure_prompt_embeds_placeholder_token` 把 `<prompt_embeds>`(PROMPT_EMBEDS_PLACEHOLDER_TOKEN)注册为特殊 token(WeakKeyDictionary 缓存)。纯 embeds 模式把 prompt 突变为 `EmbedsPrompt`(`prompt_embeds` 全长张量 + `prompt_is_token_ids` 掩码);混合模式(`_process_tokens` 重写)先在调用多模态 processor **之前** 把 1-token 哨兵展开为 N-token 区间(`apply_token_matches`),再向 `mm_kwargs`/`mm_hashes`/`mm_placeholders` 追加 `prompt_embeds` 条目。

**4. 统一视觉块**(Kimi-K2.5 专用):`use_unified_vision_chunk` 时 `rebuild_mm_uuids_from_mm_data` 重写 chunk UUID,`replace_vision_chunk_video_placeholder` 按 `video_idx` 把 `video_placeholder` 替换为运行时视频块提示词。

### 与多模态链路的衔接(07/11)

渲染器是前端持有 `BaseMultiModalProcessor` 的唯一入口,衔接关系:

| 层 | 位置 | 职责 |
|---|---|---|
| `MULTIMODAL_REGISTRY` | `vllm/multimodal/registry.py` | `create_processor`/`processor_cache_from_config`(见 [11-multimodal-inputs](../11-multimodal-inputs/multimodal-registry.md)) |
| `BaseRenderer.__init__` | `renderers/base.py:113-153` | 创建 `mm_processor` + 只读 `_readonly_mm_processor`、GPU IPC 池、缓存统计 |
| `_process_multimodal` | `renderers/base.py:729` | 组装 `MMProcessorInputs(prompt, mm_data_items, mm_uuid_items, hf_processor_mm_kwargs, tokenization_kwargs)` → `mm_processor.apply()` → `MultiModalInput` |
| `InputProcessor` | `v1/engine/input_processor.py:58` | 复用 `renderer.tokenizer`/`renderer._executor`,转 `EngineCoreRequest` |

关键行为:

- 仅当 `mm_registry.supports_multimodal_inputs(model_config)` 才初始化多模态;文本模型调用 `get_mm_processor()` 抛错。
- `mm_processor.apply()` 产出的 `MultiModalInput` 含 `prompt_token_ids` + `mm_kwargs` + `mm_hashes` + `mm_placeholders`(占位符展开详情见 11 目录)。
- 缓存:发送端缓存命中统计经 `MultiModalCacheStats` 周期性 `stat_mm_cache` 上报;`clear_mm_cache_async` 串行化清理避免与并发 `process_inputs` 竞争。
- `warmup()` 用 `processor.dummy_inputs.get_dummy_processor_inputs` 跑一次假输入,避免首请求多模态延迟;`set_default_torch_num_threads(1)` 防 HF processor 挂起。
- `_process_embeds` 要求 `--enable-prompt-embeds`;`prompt_embeds` 必须是 `(seq_len, hidden_size)` 2D、hidden_size 匹配 `get_hidden_size()`、浮点 dtype,且 `cpu()` 化以便 msgpack 跨进程序列化。

### 在线封装:OnlineRenderer / OnlineDerenderer

`OnlineRenderer`(`renderers/online_renderer.py:63`)包装 `BaseRenderer` 供 OpenAI 服务端:

- `render_chat`:请求级 `--trust-request-chat-template` 守卫(`validate_chat_template`);`tool_choice` 校验;Mistral 请求的 tool_calls 重序列化;`ParserManager` 解析器做 `adjust_request`(工具/推理解析)。
- `preprocess_chat` / `preprocess_completion`:构造 `ChatParams`(默认 kwargs/`media_io_kwargs`/`mm_processor_kwargs` 三级合并)、`TokenizeParams`,调用 `renderer.render_chat_async`/`render_cmpl_async`。
- GPT-OSS(`gpt_oss` 架构)走 Harmony 分支(`_make_request_with_harmony`),不经 chat template。
- 解码端 token 复用:解聚合服务把 prefill 的 token ids 放 `kv_transfer_params.prompt_token_ids`,此处弹出后直接 `tokens_input`,跳过模板与分词。

`OnlineDerenderer`(`online_derenderer.py:42`)是反向链路:把引擎输出的 token 流经增量 detokenize(`detokenize_incrementally`)转成 OpenAI chat/completion 响应(含流式、logprobs、tool 调用),与 renderer 同构但职责在输出侧。

### 媒体资源 assets(`vllm/assets/`)

测试/示例用默认媒体,运行期按需下载并 `lru_cache`:

| 文件 | 内容 |
|---|---|
| `base.py` | `get_cache_dir()`(`VLLM_ASSETS_CACHE` 环境变量);`get_vllm_public_assets(filename, s3_prefix)` 从 `https://vllm-public-assets.s3.us-west-2.amazonaws.com` 下载 |
| `image.py` | `ImageAsset`,13 个命名图片(如 `stop_sign`/`cherry_blossom`,前缀 `vision_model_images`);`pil_image`(jpg)、`image_embeds`(`.pt`,llava 1.5 测试用)、`read_bytes` |
| `audio.py` | `AudioAsset`:`winning_call`/`mary_had_lamb`(`.ogg`,前缀 `multimodal_asset`);`audio_and_sample_rate` 经 `load_audio`、`url` |
| `video.py` | `VideoAsset`:`baby_reading` → `sample_demo_1.mp4`(HF 数据集 `raushan-testing-hf/videos-test`);`video_to_ndarrays`(cv2 + `linspace` 均匀抽帧,BGR→RGB)、`video_to_pil_images_list`、`video_get_metadata`(`do_sample_frames` 控制 HF processor 采样)、`get_audio`(Qwen2.5-Omni 示例) |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
