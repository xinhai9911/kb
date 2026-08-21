## 10-serving（一）：离线/在线 API 与协议族对比 _part1

本文对比 vLLM 与 SGLang 的离/在线 API 与协议族覆盖。请求模型映射与工具参数见 [serving-comparison_part2.md](serving-comparison_part2.md)，部署形态与监控见 [serving-observability.md](serving-observability.md)。

### 1. 离线 API：vLLM `LLM` vs SGLang `Engine`

| 维度 | vLLM `LLM` | SGLang `Engine` |
|---|---|---|
| 源码 | `vllm/entrypoints/llm.py` + `offline_utils.py`（`OfflineInferenceMixin`） | `sglang/srt/entrypoints/engine.py:207`（`Engine`）+ `EngineBase.py:7`（抽象基类）+ `engine_score_mixin.py` |
| 构造 | `LLM(model, **kwargs)`，kwargs 直通 `EngineArgs`；强制注入 `disable_log_stats=True` | `Engine(model_path=..., **kwargs)`，kwargs 直通 `ServerArgs`；默认 `log_level="error"`，支持直接传 `server_args=` |
| 进程拓扑 | 内部构造 `LLMEngine`（V1），EngineCore 默认独立进程 | `_launch_subprocesses`（:1060）拉起 Scheduler（每 TP rank 一进程）+ DetokenizerManager 子进程，主进程持 `TokenizerManager` |
| 文本生成 | `generate(prompts, sampling_params)` → `list[RequestOutput]`；`chat()`/`enqueue()`/`wait_for_completion()` | `generate(prompt, sampling_params, stream=False)` → `Dict`/`Iterator[Dict]`；`async_generate()` 异步版 |
| 流式 | 同步引擎不流式；流式走 `AsyncLLM` / `vllm serve` | 同步 `generate(stream=True)` 用 `self.loop.run_until_complete` 包装 async generator（engine.py:360） |
| 输出模型 | 强类型 `RequestOutput`（requests 抽象） | 裸 dict（`text`/`meta_info`/`output_ids`） |
| 嵌入/打分 | `encode(prompts, pooling_params, pooling_task=...)`（必须显式指定任务）；`embed`/`classify`/`score` 便捷封装 | `encode/async_encode` → `Dict`（`EmbeddingReqInput`）；`score`（`EngineScoreMixin`，CausalLM 概率或分类头 logits） |
| 权重热更新 | `start_weight_update`/`update_weights`/`finish_weight_update`/`update_weight_version`（RL 链） | `update_weights_from_tensor/distributed/disk/ipc` + `init_weights_update_group` + `get_weights_by_name` 全家桶 |
| LoRA | 运行时 LoRA 更新在在线层（`/v1/load_lora_adapter`） | `load_lora_adapter`/`unload_lora_adapter`/`async_load_lora_adapter` 内置 |
| 会话 | 无内置 session 概念 | `open_session`/`close_session` + `session_id`（持续提示） |
| 管理方法 | `reset_prefix_cache`/`sleep(0/1/2)`/`wake_up`/`collective_rpc`/`apply_model`/`get_metrics()`/`get_world_size` | `flush_cache`/`freeze_gc`/`release_memory_occupation`/`resume_memory_occupation`/`collective_rpc`/`get_server_info`/`get_model_info` |
| 抽象基类 | 无独立基类（`LLMEngine` 为引擎接口） | `EngineBase` 抽象：`generate`/`flush_cache`/`update_weights_from_tensor`/`load_lora_adapter`/`release_memory_occupation`/`resume_memory_occupation`/`shutdown` |
| 特殊形态 | — | `HttpServerEngineAdapter`（`http_server_engine.py:49`）：`EngineBase` 的 HTTP 形态，子进程起 `launch_server`，供 VerlEngine 等外部调用方使用 |

共同点：离线接口 = 直接驱动引擎进程、不经 HTTP；差异集中在输出形态（裸 dict vs `RequestOutput`）与流式实现。

### 2. 在线服务端点面（协议族覆盖）

| 协议/端点 | vLLM `vllm serve` | SGLang `sglang serve` |
|---|---|---|
| 核心原生端点 | 无（原生仅 pooling 类） | `/generate`（v0 风格，POST/PUT）、`/encode`、`/classify` |
| OpenAI | `/v1/chat/completions`(+batch)、`/v1/completions`、`/v1/responses`(GET/`{id}`/cancel)、`/v1/embeddings`、`/v1/classify`、`/pooling`、`/score`、`/rerank`、`/v1/models`、`/tokenize`、`/detokenize`、`/tokenizer_info` | 同左（completions/chat/embeddings/classify/score/rerank/tokenize/detokenize/responses/models）+ `/v1/audio/transcriptions`、WS `/v1/realtime` |
| 扩展协议 | Anthropic `/v1/messages`(+count_tokens)、Cohere `/cohere/v2/chat`（需 `VLLM_ENABLE_COHERE_API=1`）、SageMaker `/ping` `/invocations` | Anthropic `/v1/messages`、SageMaker `/ping` `/invocations`、**Ollama** `/api/chat|generate|tags|show`、**Vertex** `/vertex_generate`（`AIP_PREDICT_ROUTE` 可改） |
| 健康/负载 | `/health`（引擎死 503）、`/load`（GPU 占用请求数）、`/version` | `/health`（仅存活）、`/health_generate`（下钻真实 token）、`/v1/loads`（core/memory/spec/lora/disagg 分节）、`/model_info`、`/server_info` |
| 管理端点 | dev 模式（`VLLM_SERVER_DEV_MODE`）下 `/sleep` `/wake_up` `/is_sleeping` `/collective_rpc`；`/start_profile` `/stop_profile` | 大量常开管理端点：`/flush_cache` `/abort_request` `/set_internal_state` `/open_session` `/close_session` `/pause_generation` `/continue_generation` `/load_lora_adapter` `/update_weights_from_*` `/hicache/*` `/dumper/{method}` `/parse_function_call` `/separate_reasoning` |
| 负载均衡/DP | `--data-parallel-*` 三模式（multi-port-external-lb / external-lb / hybrid-lb），`DPSupervisor` 探活，SO_REUSEPORT 多端口复用 | `--tokenizer-worker-num>1` 多 tokenizer worker 独立 HTTP 进程，`MultiTokenizerRouter` 中转 |
| 鉴权 | 无内建 API key 鉴权 | `--api-key`（全端点）/`--admin-api-key`（管理端点），`utils/auth.py` 中间件 |
| HTTP 框架 | FastAPI + uvicorn | FastAPI + uvicorn/uvloop，`--enable-http2` 换 Granian；`ORJSONRoute` 用 orjson 解析大 body |
| 指标 | `/metrics`（prometheus-fastapi-instrumentator + v1 registry） | `/metrics`（Mount，需 `--enable-metrics`，multiprocess 聚合） |

两者在 `/v1/chat/completions`、`/v1/completions`、`/v1/embeddings`、`/v1/models`、`/health`、`/metrics` 上协议对齐；SGLang 端点面更「自研化」，vLLM 生产面以 OpenAI 协议为主、管理面收敛到 dev 模式。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
