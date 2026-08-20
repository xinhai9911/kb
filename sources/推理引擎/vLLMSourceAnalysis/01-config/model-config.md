## ModelConfig 模型配置

`ModelConfig`(`vllm/config/model.py`,约 2470 行)是模型加载与推理建模的关键入口:承载模型/tokenizer 标识、精度、上下文长度、量化、多模态参数与 HF 配置覆盖,并在 `__post_init__` 中加载 HF 配置、解析任务类型(runner/convert)与 dtype。

### 核心字段

| 参数名 | 类型 | 必选 | 说明 |
|--------|------|------|------|
| `model` | `str` | 否 | HF 模型名/路径,默认 `Qwen/Qwen3-0.6B`;缺省 `served_model_name` 时作为 metrics 的 `model_name` |
| `model_weights` | `str` | 否 | 原始权重路径;模型从对象存储拉起时保留原始 URI |
| `runner` | `RunnerOption` | 否 | `"auto"`/`generate`/`pooling`/`draft`,单实例只支持一种 runner |
| `convert` | `ConvertOption` | 否 | `"auto"`/`none`/`embed`/`classify`,经适配器把文本生成模型转为池化任务 |
| `tokenizer` | `str` | 否 | tokenizer 名/路径,未指定则与 `model` 一致 |
| `tokenizer_mode` | `TokenizerMode \| str` | 否 | `auto`/`hf`/`slow`/`mistral`/`deepseek_v32`/`deepseek_v4`/`inkling`/`kimi_k3`/`cohere`/插件 |
| `trust_remote_code` | `boolean` | 否 | 是否信任远端代码(模型/tokenizer) |
| `dtype` | `ModelDType \| torch.dtype` | 否 | `auto`/`half`/`float16`/`bfloat16`/`float`/`float32`;`auto` 依据模型 config 精度决定 |
| `seed` | `integer` | 否 | 随机种子,确保 TP worker 采样一致 |
| `hf_config` | `PretrainedConfig` | 否(init=False) | `__post_init__` 加载的 HF 模型配置 |
| `hf_text_config` | `PretrainedConfig` | 否(init=False) | 文本子模型配置(多模态模型与 `hf_config` 不同) |
| `hf_config_path` | `str \| None` | 否 | 显式指定 HF config 路径 |
| `revision` / `code_revision` / `tokenizer_revision` | `str \| None` | 否 | HF Hub 分支/标签/commit 版本 |
| `max_model_len` | `integer` | 否 | 上下文长度;`None` 自动推导;支持 `1k/1K/25.6k` 可读格式;`-1` 自动取能装入 GPU 的最大长度 |
| `spec_target_max_model_len` | `integer \| None` | 否 | 投机解码草稿模型的最大长度 |
| `quantization` | `QuantizationMethods \| str \| None` | 否 | 权重量化方法;`None` 时回退到 config 文件的 `quantization_config` |
| `quantization_config` | `dict \| QuantizationConfigArgs \| None` | 否 | 逐层 kind(linear/moe)的量化 spec 与 `ignore` 列表;`quantization` 为 online 简写时自动填充 |
| `allow_deprecated_quantization` | `boolean` | 否 | 允许弃用的量化方法 |
| `enforce_eager` | `boolean` | 否 | 恒用 eager 模式,禁用 CUDA graph |
| `enable_return_routed_experts` | `boolean` | 否 | 是否返回路由专家(与 PP/CP 不兼容) |
| `max_logprobs` | `integer` | 否 | logprobs 上限,默认 20(OpenAI API 默认),`-1` 不设限(可能 OOM) |
| `logprobs_mode` | `LogprobsMode` | 否 | `raw_logprobs`/`processed_logprobs`/`raw_logits`/`processed_logits` |
| `disable_sliding_window` | `boolean` | 否 | 关闭滑动窗口,长度封顶为窗口大小 |
| `disable_cascade_attn` | `boolean` | 否 | 默认 `True` 关闭 V1 级联注意力,需显式 opt-in |
| `skip_tokenizer_init` | `boolean` | 否 | 跳过 tokenizer/detokenizer 初始化,输入须为 token ids |
| `enable_prompt_embeds` | `boolean` | 否 | 允许 `prompt_embeds` 文本嵌入输入,错误形状可能崩溃,仅限可信用户 |
| `served_model_name` | `str \| list[str] \| None` | 否 | API/指标使用的模型名,取首个 |
| `config_format` | `str \| ConfigFormat` | 否 | `auto`/`hf`/`mistral` 的 config 加载格式 |
| `hf_token` | `bool \| str \| None` | 否 | HF 远端文件 HTTP bearer token,`True` 用 `hf auth login` 缓存 |
| `hf_overrides` | `HfOverrides` | 否 | dict 或 callable,加载时修改 HF 配置(见下文) |
| `model_class_overrides` | `dict[str, str]` | 否 | 架构名 → `"module:class"` 运行时注册模型类,仅调试用 |
| `generation_config` | `str` | 否 | `auto`(从模型加载)/`vllm`(用 vLLM 默认)/自定义目录 |
| `override_generation_config` | `dict` | 否 | 覆盖生成参数,如 `{"temperature": 0.5}` |
| `enable_sleep_mode` | `boolean` | 否 | 引擎睡眠模式(仅 cuda/hip) |
| `sleep_mode_backend` | `str` | 否 | 睡眠恢复机制,默认 `"cumem"` |
| `enable_cumem_allocator` | `boolean` | 否 | 启用自定义 cumem 分配器(多节点 NVLink),睡眠模式自动启用 |
| `model_impl` | `str \| ModelImpl` | 否 | `auto`/`vllm`/`transformers`/`terratorch`,模型实现选择 |
| `logits_processors` | `list[str \| type[LogitsProcessor]]` | 否 | logits 处理器 FQN 或类对象 |
| `multimodal_config` | `MultiModalConfig \| None` | 否 | 多模态输入配置;由 MM InitVar 参数在 `__post_init__` 汇总生成 |
| `pooler_config` | `PoolerConfig \| None` | 否 | pooling 任务(embed/classify)的池化配置 |

多模态相关字段以 `InitVar` 形式传入 `__post_init__`(不属于存储字段):`language_model_only`、`limit_mm_per_prompt`、`mm_processor_kwargs`、`mm_processor_cache_gb`、`mm_encoder_tp_mode`、`mm_tensor_ipc`、`interleave_mm_strings`、`skip_mm_profiling`、`video_pruning_rate` 等。

### 任务类型解析(runner/convert)

任务类型由 `runner` + `convert` 决定,`auto` 时按架构名后缀匹配 `_SUFFIX_TO_DEFAULTS`:

| 架构后缀 | runner | convert |
|----------|--------|---------|
| `ForCausalLM`/`ForConditionalGeneration`/`ChatModel`/`LMHeadModel` | `generate` | `none` |
| `ForTextEncoding`/`EmbeddingModel`/`ForRewardModeling`/`RewardModel` | `pooling` | `embed` |
| `ForSequenceClassification`/`ForTokenClassification`/`For*Classification`/`ClassificationModel` | `pooling` | `classify` |
| 其余以 `Model` 结尾 | `pooling` | `embed` |

`try_match_architecture_defaults(arch, runner_type, convert_type)` 只接受后缀匹配;`iter_architecture_defaults()` 遍历该表。`convert != "auto"` 时强制 `runner="pooling"`。最终 `runner_type` 供模型注册表选择:"generate" 用文本生成模型,"pooling" 走 embed/classify 池化路径。

### hf_overrides 机制

- `HfOverrides = dict[str, Any] | Callable[[PretrainedConfig], PretrainedConfig]`。
- dict 形式:按 key 覆盖 HF config;值为 dict 且目标属性是嵌套 `PretrainedConfig` 时,经 `_update_nested` 递归合并,否则直接 `setattr`。
- callable 形式:整体传入 `get_config(...)`,由回调就地修改 config。
- 对应加载调用 `get_config(..., hf_overrides=dict, hf_overrides_fn=callable)`。

### 关键方法/派生属性

| 名称 | 说明 |
|------|------|
| `architecture` / `architectures` | 实际使用的模型架构名 / HF 架构列表 |
| `is_multimodal_model` | 是否多模态模型 |
| `is_encoder_decoder` / `is_diffusion` | 编码器解码器 / dLLM 判定 |
| `is_moe` / `is_hybrid` / `is_attention_free` | MoE / 混用层/无注意力判定 |
| `get_sliding_window` / `get_vocab_size` / `get_hidden_size` | 滑动窗口、词表、隐藏维度 |
| `get_num_kv_heads` / `get_total_num_kv_heads` / `get_head_size` | KV head 数/总头数/头维度 |
| `get_num_layers` / `get_layers_start_end_indices` | 层数(结合并行配置)与起止索引 |
| `get_num_experts` / `get_num_experts_per_tok` | expert 数与每 token 路由数 |
| `get_pooling_task` | pooling 任务类型(基于 `pooler_config.task`) |
| `score_type` / `verify_with_parallel_config` | 打分类型 / 与并行配置一致性校验 |
| `compute_hash` | 计算图相关字段的哈希(忽略 tokenizer、seed 等非图字段) |

dtype 解析:模块级 `str_dtype_to_torch_dtype` 把字符串映射为 `torch.dtype`;`_resolve_auto_dtype` 依据平台支持精度降级(如 FP32 模型自动用 FP16/BF16);`_FLOAT16_NOT_SUPPORTED_MODELS`(gemma2/3、glm4)拒绝 float16。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)