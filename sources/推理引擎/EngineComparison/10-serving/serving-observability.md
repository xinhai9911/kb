## 10-serving（二）：部署形态与监控可观测对比

离线/在线 API、协议映射与工具参数对比见 [serving-comparison_part1.md](serving-comparison_part1.md)。本文聚焦部署生态（Ray/gRPC/sidecar/弹性/外部集成）与可观测性（metrics/tracing）。

### 1. 部署形态对比

| 维度 | vLLM | SGLang |
|---|---|---|
| CLI 入口 | `vllm serve`（`cli/serve.py` → `api_server.run_server`）；`vllm chat`/`complete`/`run-batch`/`bench`/`collect-env`；`python -m vllm.entrypoints.grpc_server` | `sglang serve` / `python -m sglang.launch_server` → `run_server` 按标志分派；`python -m sglang.check_env` |
| 引擎/API 分离 | `--headless` 只起 core engines 不起 HTTP；`build_async_engine_client` 支持 in-process 或 multiprocess RPC（ZMQ，`--api-server-count>1` 每 API server 一客户端） | 默认 HTTP server/Engine/TokenizerManager 同主进程；`HttpServerEngineAdapter` 把 EngineBase 方法转 HTTP POST（张量经 `MultiprocessingSerializer`），`launch_server_process` 轮询 `/health_generate` |
| Ray | 多节点 TP/PP 依赖 Ray（`vllm serve` 启动时配置）；多进程 DP 另有 `external_launcher` 路径 | `--use-ray`：HTTP 服务但 scheduler 用 Ray actor（`srt/ray/http_server.py`）；弹性 EP 运行时扩缩不支持 `--use-ray`（server_args.py:7194） |
| gRPC | `--grpc` 独立 gRPC server（`grpc_server.py`，smg-grpc-servicer）：`VllmEngineServicer` 绑 `AsyncLLM` + K8s health 探针 + gRPC reflection；传输限长 -1 | `--smg-grpc-mode`（或旧 `--grpc-mode`）独立 SMG gRPC + aiohttp sidecar（`--smg-http-sidecar-port`=port+1，暴露 `/metrics` 与 profiling）；`--grpc-port`（`SGLANG_GRPC_PORT`）Rust gRPC 与 HTTP 同进程并存（PyO3 `RuntimeHandle`，`_BACKPRESSURE_TIMEOUT_S=300`），仅单 tokenizer 模式 |
| sidecar | 无内建 sidecar（端点插件经 `vllm.plugins.load_endpoint_plugins`） | `--sidecar <module>` 子进程 spawn 任意服务，设 `SGLANG_GRPC_ENDPOINT` 环境变量指向本实例；`SubprocessWatchdog` 监控存活 |
| 前端/前端优化 | Rust 前端：`VLLM_USE_RUST_FRONTEND=1` + `VLLM_RUST_FRONTEND_PATH`（`RustFrontendProcessManager`）；Rust bench（`VLLM_USE_RUST_BENCH=1`） | `--enable-http2` 用 Granian server；`--enable-ssl-refresh` 证书热刷新（`SSLCertRefresher`，watchfiles） |
| 弹性 | `--enable-elastic-ep` 弹性专家并行：`/scale_elastic_ep`、`/is_scaling_elastic_ep`（api_server_count 压到 1） | Elastic EP 运行时 scale-up（`server_args` 约束：不支持 `--use-ray`/`--grpc-port`） |
| 容错/生命周期 | watchdog 每 5s 检查引擎死亡，默认关停（`VLLM_KEEP_ALIVE_ON_ENGINE_DEATH` 可关）；`shutdown_timeout` 0=abort/>0=drain；`/fault_tolerance/apply`（`--enable-fault-tolerance`） | `gracefully_exit`/`ServerStatus` 状态机；`/health` 超时置 `UnHealthy` 返 503（`HEALTH_CHECK_TIMEOUT` 默认 20s）；`--warmups` 自定义预热 |
| 外部生态 | 离线/在线一体（`LLM` 与 server 同引擎面）；`vllm run-batch` 本地/HTTP JSONL 批跑；MCP 外部工具；DP supervisor `/health` `/ready` `/readyz` | `sglang.lang` 前端 DSL（`lang/api.py` + interpreter/tracer）提供 Python 链式编程；`HttpServerEngineAdapter` 供 VerlEngine 集成；`--encoder-only` 部署 disaggregation 纯 encoder |

### 2. 监控 / 可观测对比

| 维度 | vLLM | SGLang |
|---|---|---|
| 指标端点 | `/metrics`：`prometheus-fastapi-instrumentator` + `vllm.v1.metrics.prometheus` 注册表（`serve/instrumentator/metrics.py`）；排除 `/metrics` `/health` `/load` `/ping` `/version` `/server_info` 路由本身 | `/metrics`：`Mount("/metrics", make_asgi_app(registry))`（`utils/common.py:2538`），需 `--enable-metrics`；SMG gRPC 模式经 sidecar multiprocess 聚合 |
| 指标前缀/代表项 | `vllm:*`：`num_requests_running`/`num_requests_waiting(_by_reason)`、`kv_cache_usage_perc`、`prefix_cache_queries`/`hits`、`engine_sleep_state`、`time_to_first_token_seconds`（`v1/metrics/loggers.py`） | `sglang:*`：`num_requests_total`、TTFT/e2e latency buckets、speculative acceptance 长度与速率（`observability/metrics_collector.py:417`） |
| 负载视图 | `/load`（统计 responses/messages/chat/completions/audio/embeddings/pooling 等 GPU 占用请求数） | `/v1/loads`（各 DP rank 调度器负载，`include=core,memory,spec,lora,disagg,queues,all`，支持 `format=prometheus`） |
| 逐请求指标 | `--enable-per-request-metrics`（要求引擎 stats logging，`--disable-log-stats` 时报错）；`get_metrics()` 离线聚合快照 | `req_time_stats.py`/`APIServerReqTimeStats`（created/tokenize/dispatch/response 时间戳）；`--export-metrics-to-file` 逐请求导出 |
| Tracing | serving 层 `_get_trace_headers`（generate/base/serving.py:191）经 `engine_client.is_tracing_enabled()` 决定是否抽取 `traceparent`/`tracestate` 转发引擎 | `--enable-trace` 开 OTLP（`observability/trace.py`）：`trace_modules`（request/mooncake，默认 request）、`otlp_traces_endpoint`（默认 localhost:4317）、`SGLANG_TRACE_LEVEL`（默认 3）、`/set_trace_level`；`trace_async.py` 异步 spans；`mooncake_trace.py` 传输 trace |
| Profiling | `/start_profile` `/stop_profile`（需 `profiler_config`） | `/start_profile` `/stop_profile`、`/freeze_gc`、`/set_trace_level`、`forward_pass_metrics` |

要点：vLLM 指标以引擎运行态（KV cache/前缀缓存/队列）为核心，tracing 仅做 header 透传；SGLang 指标含更多请求级与投机解码细节，tracing 是独立 OTLP 子系统且可运行时调级别/模块。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
