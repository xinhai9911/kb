## LLM 离线推理 API

源码：`vllm/entrypoints/llm.py`（主类）+ `offline_utils.py`（`OfflineInferenceMixin`）+ `pooling/offline.py`（`PoolingOfflineMixin`）+ `generate/beam_search/offline.py`（`BeamSearchOfflineMixin`）。

`vllm.LLM` 面向离线推理：内部构造 `LLMEngine`（V1），自动批处理并管理 KV cache。在线服务请用 `AsyncLLM` / `vllm serve`。

### 构造与关键参数

构造函数为 `LLM(model, **kwargs)`，其余参数通过 `EngineArgs` 透传（`kwargs` 亦直通 `EngineArgs`）。常用参数：

| 参数名 | 类型 | 必选 | 说明 |
|--------|------|------|------|
| `model` | string | 是 | HuggingFace 模型名或路径 |
| `tokenizer` | string | 否 | 分词器名或路径，默认同 `model` |
| `tokenizer_mode` | string | 否 | `auto`（优先 fast）/ `slow` |
| `skip_tokenizer_init` | boolean | 否 | 为 True 时跳过分词器初始化，输入须用 `prompt_token_ids` |
| `dtype` | string | 否 | `float32`/`float16`/`bfloat16`/`auto`，config 为 float32 时自动降为 float16 |
| `quantization` | string | 否 | `awq`/`gptq`/`fp8` 等；None 时读模型 `quantization_config` |
| `revision` / `tokenizer_revision` | string | 否 | 模型/分词器版本（分支、tag 或 commit） |
| `chat_template` | string | 否 | 对话模板路径或内容 |
| `seed` | integer | 否 | 采样随机种子，默认 0 |
| `gpu_memory_utilization` | number | 否 | GPU 显存占用比例，默认 0.92 |
| `kv_cache_memory_bytes` | integer | 否 | 每 GPU KV cache 字节数，非 None 时忽略 `gpu_memory_utilization` |
| `cpu_offload_gb` | number | 否 | CPU 内存卸载权重 GiB |
| `enforce_eager` | boolean | 否 | 禁用 CUDA graph 全 eager |
| `tensor_parallel_size` | integer | 否 | TP 并行 GPU 数，默认 1 |
| `trust_remote_code` | boolean | 否 | 是否信任远程代码 |
| `allowed_local_media_path` | string | 否 | 允许读取的本地媒体目录（安全风险，仅信任环境开启） |
| `hf_token` | string/boolean | 否 | HF 远程文件 Bearer 令牌 |
| `compilation_config` | integer/object | 否 | 编译优化配置（整数取 mode） |
| `spec_method` / `spec_model` / `spec_tokens` | string/string/integer | 否 | 投机解码顶层别名 |

默认强制：`disable_log_stats=True` 被注入 `kwargs`；`worker_cls` 为 type 时用 cloudpickle 序列化。

数据并行限制：`data_parallel_size > 1` 且非 `external_launcher`/非 TPU 时报错并提示改用多进程 DP 示例（`examples/features/data_parallel/data_parallel_offline.py`）——单进程仍可能挂起。

### 公开方法一览

| 方法 | 用途 |
|------|------|
| `generate(prompts, sampling_params, ...)` | 文本生成，返回 `list[RequestOutput]`，仅 generative 模型 |
| `enqueue(prompts, ...)` | 只入队不等待，返回 request ids |
| `wait_for_completion(output_type=...)` | 处理队列并返回结果 |
| `chat(messages, ...)` | 对话生成（走 chat template 渲染后再 generate） |
| `enqueue_chat(messages, ...)` | 渲染对话并入队，不等待 |
| `encode(prompts, pooling_params, pooling_task=...)` | pooling 隐藏状态，需 `--runner pooling` |
| `embed(prompts)` / `classify(prompts)` / `score(data_1, data_2)` | 嵌入/分类/相似度的便捷封装 |
| `get_tokenizer()` / `get_world_size(include_dp=True)` | 获取分词器 / 世界规模（TP*PP，含 DP 可选） |
| `start_profile` / `stop_profile` | 引擎性能剖析 |
| `reset_prefix_cache(reset_running_requests, reset_connector)` | 重置前缀缓存 |
| `sleep(level, mode)` / `wake_up(tags)` | 引擎休眠/唤醒（level 0/1/2，先 sleep 再 wake） |
| `collective_rpc(method, timeout, ...)` | 对所有 worker 发起 RPC 调用 |
| `apply_model(func)` | 直接在每个 worker 的模型上运行函数 |
| `get_metrics()` | 返回 Prometheus 聚合指标快照（V1 引擎） |
| `init_weight_transfer_engine` / `start_weight_update` / `update_weights` / `finish_weight_update` / `update_weight_version` / `get_weight_version` | RL 训练权重热更新设施 |
| `from_engine_args(engine_args)` | 从 `EngineArgs` 构造实例 |

### generate 参数细节

`sampling_params` 单值作用于所有 prompt；传入 list 时长度须与 prompts 一致（否则 `ValueError`）。`priority` 为整数列表，一一对应，仅优先级调度策略下生效。`use_tqdm` 可为布尔或可调用（如 `functools.partial(tqdm, leave=False)`）。

`chat` 的 `chat_template_content_format` 取 `string`（字符串渲染）或 `openai`（OpenAI schema 的 content 列表）。`add_generation_prompt=True` 与 `continue_final_message=True` 互斥。多模态输入按 OpenAI API 相同方式传入。

### pooling 离线任务

`encode` 必须显式指定 `pooling_task`（`embed`/`classify`/`token_classify`/`token_embed`/`plugin`/评分任务等），否则报错。具体限制：

- embed/token_embed 需要模型经 `--convert embed` 支持；
- classify 需要模型支持 classification；
- `score` 仅 `num_labels==1` 时启用，且依赖 `SCORE_TYPE_MAP` 映射的评分类型；
- `data` 字段仅 `plugin` 任务可用。

内部请求并发受 `max_num_seqs * 2` 限制，请求先在渲染线程池预处理再注入引擎核心（`_run_tiling_engine`）。

### 进度显示与输出顺序

`_run_engine` 用 tqdm 显示 `Processed prompts` 进度条，并实时估算输入/输出 `toks/s`。生成请求统一设 `RequestOutputKind.FINAL_ONLY`（只取最终输出）。结果按 `int(request_id)` 升序排序返回，保证与输入顺序一致。本源码版本中未见 `ReportTracker` 相关实现（任务描述提及项，当前以 tqdm 进度条实现）。

### 离线请求组装流程

离线批量推理路径为：`generate` -> `_run_completion` -> `_add_completion_requests`：

1. `prompt_to_seq` 统一入参，`_params_to_seq` / `_lora_request_to_seq` / `_priority_to_seq` 将单值广播或校验长度。
2. 逐条 `_preprocess_cmpl_one` -> `renderer.render_cmpl`（解析 `parse_model_prompt`，叠加 tokenization/mm_processor 覆盖参数）得到 `EngineInput`。
3. `_add_request`：生成 `request_id`，设 `FINAL_ONLY`，调 `llm_engine.add_request` 入引擎；按模态匹配默认 LoRA（`_resolve_mm_lora`）。
4. `_run_engine`：循环 `llm_engine.step()` 直到 `has_unfinished_requests()` 为假，收集 finished 输出。

chat 路径类似：`_preprocess_chat_one` -> `renderer.render_chat` -> 逐条入队，并额外做特殊 token 保真处理（`_adjust_params_for_parsing`）：Gemma4 等将思维分隔符/工具调用注册为特殊 token 的模型，thinking/tool 开启时把 `skip_special_tokens` 置为 False。add 中途异常会 `abort_request` 已入队项。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)