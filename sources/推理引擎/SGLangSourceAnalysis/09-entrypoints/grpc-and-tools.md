## gRPC、SSL 与工具端点（及 vLLM 对照）

源码：`sglang/launch_server.py`、`sglang/srt/entrypoints/grpc_server.py`、`grpc_bridge.py`、`ssl_utils.py`、`sidecar.py`、`http_server_engine.py`、`warmup.py`、`tool.py`、`context.py`、`check_env.py`（`sglang/check_env.py`）。

### launch_server.py：服务模式分派

`python -m sglang.launch_server`（或推荐的 `sglang serve`）→ `prepare_server_args`（CLI 解析，`srt/server_args.py`）→ `run_server(server_args)` 按标志分派：

| 条件 | 分派目标 | 说明 |
|---|---|---|
| `--encoder-only` | `disaggregation/encode_server.py` / `encode_grpc_server.py` | 预填充分离部署的纯 encoder 服务 |
| `--smg-grpc-mode`（或旧 `--grpc-mode`） | `entrypoints/grpc_server.py::serve_grpc` | 独立 gRPC 服务（基于 `smg-grpc-servicer` 包），不启动 FastAPI |
| `--use-ray` | `srt/ray/http_server.py` | Ray 后端：HTTP 服务但 scheduler 用 Ray actor |
| 默认 | `srt/entrypoints/http_server.py::launch_server` | 标准 SRT（FastAPI + 多进程引擎） |

另有 native gRPC 通道：`--grpc-port`（`SGLANG_GRPC_PORT`）让 Rust gRPC server 与默认 HTTP server 同进程并存（仅单 tokenizer 模式，`__post_init__` 拒绝 `--tokenizer-worker-num>1`）。

### grpc_server.py：SMG gRPC 模式 + HTTP sidecar

`serve_grpc`（:156）启动基于 `smg-grpc-servicer` 的 gRPC server，并额外用 aiohttp 起一个轻量 sidecar（默认 `--smg-http-sidecar-port` = `--port + 1`）暴露：

| 端点 | 说明 |
|---|---|
| `GET /metrics` | Prometheus（`multiprocess.MultiProcessCollector` 聚合各进程指标，需 `--enable-metrics`） |
| `POST /start_profile` `/stop_profile` | profiling 控制（构建 `ProfileReq` 经 `request_manager.send_communicator_req` 发给 scheduler） |

sidecar 依赖 `smg-grpc-servicer >= 0.5.3` 的 `on_request_manager_ready` 回调；旧版本无此 hook 时按 `--enable-metrics` 决定报错还是禁用 sidecar。

### grpc_bridge.py：native gRPC 的 Python 桥

`RuntimeHandle`（:56）是 Rust gRPC server（PyO3）回调 Python 的薄桥：Rust 侧经 `chunk_callback`（Rust→PyO3 对象）逐块取回 TokenizerManager 输出，带 `_BACKPRESSURE_TIMEOUT_S = 300.0` 背压控制；`_GrpcRequest`（:38）是 FastAPI `Request` 的 shim，让 `OpenAIServing*` 在 gRPC 路径下复用同一套协议转换逻辑。`abort`、`submit_*`、info 方法均为同步，由 `_start_native_grpc_server_for_runtime`（`http_server.py:2728`）装配。

### SSL 与 sidecar

- `ssl_utils.py`：`SSLCertRefresher` 用 `watchfiles.awatch` 监控证书/私钥/CA 文件变更，就地更新 `ssl.SSLContext`（热刷新）；由 `--enable-ssl-refresh` 开启（多 tokenizer worker 下不支持）。
- `sidecar.py`：`--sidecar <module>` 在子进程启动任意外部服务（spawn），设 `SGLANG_GRPC_ENDPOINT` 环境变量指向本实例 gRPC 端点；`SubprocessWatchdog` 监控存活。
- `http_server_engine.py`：`HttpServerEngineAdapter` 把 EngineBase 方法转成 HTTP POST（`update_weights_from_tensor` 用 `MultiprocessingSerializer` 序列化张量）；`launch_server_process` 轮询 `/health_generate` 直到就绪。
- `warmup.py` / `tool.py` / `context.py`：服务预热（`execute_warmups`，`http_server.py:381` 支持 `--warmups` 自定义）；`Tool`/`ConversationContext`/`HarmonyContext` 是 tool-calling（browser/python/MCP）与会话上下文的基础设施，服务 `/v1/responses` 等工具端点。
- `check_env.py`（`sglang/check_env.py`）：`python -m sglang.check_env` 打印 Python/PyTorch/CUDA 及 30+ 包版本、GPU 拓扑、驱动信息（按 CUDA/HIP/NPU/MUSA/MPS 分平台）。

### 与 vLLM OpenAI server（vLLM KB 09-entrypoints）对照

| 维度 | SGLang SRT | vLLM `vllm serve` |
|---|---|---|
| HTTP 框架 | FastAPI + uvicorn/uvloop（可选 Granian HTTP/2） | FastAPI + uvicorn |
| 入口 | `sglang serve` / `launch_server.py` | `vllm serve` / `cli/serve.py` |
| 核心端点 | `/generate`、`/encode`、`/classify`（原生）；`/v1/*`（OpenAI 兼容） | 纯 `/v1/*`；原生端点仅 pooling 类 |
| OpenAI 兼容 | completions/chat/embeddings/classify/tokenize/detokenize/score/rerank/responses/models/audio/realtime | completions/chat/embeddings/classify/pooling/score/rerank/responses/models/tokenize/audio/realtime 等 |
| 其他协议 | Ollama 4 端点、Anthropic Messages、SageMaker、Vertex | Anthropic、Cohere、SageMaker |
| 健康检查 | `/health` 默认只探存活；`/health_generate` 送真实 token（`SGLANG_ENABLE_HEALTH_ENDPOINT_GENERATION` 控制 `/health` 是否生成） | `/health`（引擎死亡 503）+ `/load` |
| 负载指标 | `/get_load`（废弃）、`/v1/loads`（核心/内存/spec/lora/disagg 分节） | `/load`（GPU 占用请求数） |
| 指标 | `/metrics`（Prometheus multiprocess） | `/metrics` |
| 管理端点 | `/start_profile` 等原生管理端点 + `/set_internal_state`/`/dumper` | dev 模式（`VLLM_SERVER_DEV_MODE`）下的 `/sleep`/`/wake_up`/`/collective_rpc` 等 |
| gRPC | SMG gRPC（独立）/ native Rust gRPC（并存，`--grpc-port`） | `--grpc` 独立 gRPC server |
| 鉴权 | `--api-key` / `--admin-api-key`（`utils/auth.py` 中间件） | vLLM 服务端无内建 API key 鉴权 |

SGLang 的端点面更「自研化」：原生 `/generate` 与大量权重更新/LoRA/会话管理端点直接暴露 HTTP；vLLM 则把管理面收敛到 dev 模式端点，生产面以 OpenAI 协议为主。两者在 `/v1/chat/completions`、`/v1/completions`、`/v1/embeddings`、`/v1/models`、`/health`、`/metrics` 上保持协议对齐。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
