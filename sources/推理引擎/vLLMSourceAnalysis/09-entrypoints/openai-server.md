## OpenAI 兼容服务（vLLM API Server）

源码：`vllm/entrypoints/openai/api_server.py`、`launchers/api_server/routers.py`、`serve/`（instrumentator、lora、profile、tokenize、sagemaker、fault_tolerance、elastic_ep 等）、`openai/{chat_completion,completion,responses,models,engine}`、`generate/api_router.py`、`pooling/`、`scale_out/`、`anthropic/`、`cohere/`。

### 启动与架构

`vllm serve <model> [options]`（`cli/serve.py` -> `api_server.run_server`）。`run_server` 中：`setup_server` 预绑定 socket -> `build_async_engine_client` 构建 `AsyncLLM` 引擎客户端（支持 in-process 或 multiprocess RPC）-> `build_and_serve` 构建 FastAPI 应用并交给 `serve_http` 启动 uvicorn。

- `build_app` 注册路由（`register_api_routers`）+ 端点插件 + 异常处理器 + 中间件。
- `init_app_state` 构造各 serving 实例（`OpenAIServingChat/Completion/Responses/Models`、Anthropic/Cohere、pooling、tokenize、render/derender、generate 状态）。
- 支持 `--grpc` 走 `grpc_server.py`；`--data-parallel-*` 多 API server；`--headless` 只起引擎不起 HTTP。
- 退出时按 `shutdown_timeout`：`abort`（timeout=0）或 `drain`（大于 0）。

### 端点一览（方法 / 路径 / 用途 / 模块）

| 方法 | 路径 | 用途 | 模块 |
|------|------|------|------|
| GET | `/health` | 健康检查（引擎死亡返回 503） | instrumentator/health |
| GET | `/load` | 服务器负载（请求 GPU 占用计数） | instrumentator/basic |
| GET | `/version` | 版本信息 | instrumentator/basic |
| GET | `/metrics` | Prometheus 指标 | instrumentator/metrics |
| POST | `/start_profile` `/stop_profile` | 性能剖析（需 `profiler_config`） | serve/profile |
| POST | `/tokenize` `/detokenize` | 分词/反分词 | serve/tokenize |
| GET | `/tokenizer_info` | 分词器信息（`--enable-tokenizer-info-endpoint`） | serve/tokenize |
| GET | `/v1/models` | 模型列表 | openai/models |
| POST | `/v1/chat/completions` | 对话补全（支持流式） | openai/chat_completion |
| POST | `/v1/chat/completions/batch` | 批量对话补全（输入 batch 文件） | openai/chat_completion |
| POST | `/v1/completions` | 文本补全 | openai/completion |
| POST | `/v1/responses` | Responses API（OpenAI 新式响应） | openai/responses |
| GET | `/v1/responses/{id}` | 检索/续读已生成响应 | openai/responses |
| POST | `/v1/responses/{id}/cancel` | 取消响应 | openai/responses |
| POST | `/v1/messages` `/v1/messages/count_tokens` | Anthropic Messages 兼容 | anthropic |
| POST | `/cohere/v2/chat` | Cohere v2 对话（需 `VLLM_ENABLE_COHERE_API=1` + `cohere` SDK） | cohere |
| POST | `/generative_scoring` | 生成式打分 | generate/generative_scoring |
| POST | `/classify` | 分类 logits | pooling/classify |
| POST | `/pooling` | 通用 pooling 请求 | pooling/pooling |
| POST | `/v1/embeddings` `/v2/embed` | 嵌入向量 | pooling/embed |
| POST | `/score` `/v1/score` `/rerank` `/v1/rerank` `/v2/rerank` | 打分/重排 | pooling/scoring |
| POST | `/inference/v1/generate` `/abort_requests` | Token in/Token out（缩减多模态、disagg 用途） | scale_out/token_in_token_out |
| POST | `/v1/chat/completions/render` `/v1/completions/render` | 仅渲染（Rendered Input） | scale_out/render |
| POST | `/v1/chat/completions/derender` `/v1/completions/derender` | 反渲染 | scale_out/derender |
| POST | `/scale_elastic_ep` `/is_scaling_elastic_ep` | 弹性专家并行伸缩（需 `--enable-elastic-ep`） | serve/elastic_ep |
| GET/POST | `/ping` | SageMaker Ping | serve/sagemaker |
| POST | `/invocations` | SageMaker 调用（按请求类型分发） | serve/sagemaker |
| POST | `/v1/load_lora_adapter` `/v1/unload_lora_adapter` | LoRA 动态加载/卸载（需 `VLLM_ALLOW_RUNTIME_LORA_UPDATING`） | serve/lora |
| POST | `/fault_tolerance/apply` GET `/fault_tolerance/status` | 故障注入（需 `--enable-fault-tolerance`） | serve/fault_tolerance |
| GET/POST | `/docs`、`/static` | 离线文档（`--enable-offline-docs`） | instrumentator/offline_docs |

音频/实时等端点（`v1/audio/transcriptions`、`v1/audio/translations`、WS `/v1/realtime`）仅在 supported_tasks 含 transcription/realtime 时注册。Dev 端点（`VLLM_SERVER_DEV_MODE`）含 `/sleep`、`/wake_up`、`/is_sleeping`、`/collective_rpc`、缓存/RLHF/server_info 等，生产禁用。DP 多端口外部 LB 模式下 `DPSupervisor` 在 `--data-parallel-supervisor-port` 暴露 `/health`、`/ready`、`/readyz`。

### engine/serving 中间层职责

`EngineClient` 抽象引擎客户端，实现可选：
- 进程内 `AsyncLLM`（线程/协程直连）；
- 多进程 RPC（`AsyncLLM` via ZMQ，`--api-server-count > 1` 时每个 API server 一个客户端）。

`BaseServing`（`serve/engine/serving.py`）为各端点 handler 基类：校验模型存在性（`_check_model`，不存在返回 404）、LoRA 适配（`_maybe_get_adapters`，含默认模态 LoRA）、请求 id（取 `X-Request-Id` 头或随机 uuid）、输入日志。具体 handler 继承它：`OpenAIServingChat`/`Completion`/`Responses`、`AnthropicServingMessages`、`CohereServingChatV2`、pooling 各 Serving、`ServingTokens`、`ServingRender/Derender`。路由 handler 装饰器 `validate_json_request`（校验请求体）、`with_cancellation`（客户端断开即取消任务）、`load_aware_call`（计入 `/load` 负载并支持负载感知）。

### 流式响应机制

`stream=true` 时 handler 返回 SSE `text/event-stream`：

- Chat：`OpenAIServingChat.chat_completion_stream_generator` 逐 token 产出 `ChatCompletionStreamResponse` delta；`stream_options.include_usage` 或强制 usage 时末尾追加 usage chunk；工具调用按 choice 跟踪 `tools_streamed`，首 token 后展示 tools。
- Responses：`_convert_stream_to_sse_events` 将事件型响应转为 `event: <type>` + JSON data 的 SSE 帧。
- Completion：`completion_stream_generator` 输出 completion chunk。
- 流中间异常会在 generator 内转为 streamed error（`create_streaming_error_response`）或写入日志；`launcher.py` 中 watchdog 每 5s 检查引擎死亡，默认触发服务器退出（`VLLM_KEEP_ALIVE_ON_ENGINE_DEATH` 可关闭）。

`/load` 端点统计下列端点的 GPU 占用请求数：responses、messages、chat/completions、completions、audio、embeddings、pooling、classify、score、rerank 等。

### 说明

- DP"超时/SLA"配置：entrypoints 层源码中未发现独立 SLA 超时项；相关超时仅 `shutdown_timeout`、`dp_supervisor_probe_*` 探针参数（未另行确认）。
- `--enable-server-load-tracking` 与 Endpoint Load Metrics 请求头 `endpoint-load-metrics-format` 控制 `/load` 行为。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)