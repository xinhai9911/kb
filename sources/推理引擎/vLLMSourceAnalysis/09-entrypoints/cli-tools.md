## CLI 工具与服务入口

源码：`vllm/entrypoints/cli/main.py`（子命令调度）、`cli/serve.py`、`cli/openai.py`、`cli/launch.py`、`cli/run_batch.py`、`cli/collect_env.py`、`cli/benchmark/`；`openai/cli_args.py`（serve 参数）；`grpc_server.py`；`generate/`、`anthropic/`、`cohere/`、`mcp/`、`scale_out/`。

### vllm 子命令一览（cli/main.py）

子命令均为懒加载模块，`--omni` 委托给 vllm-omni；`bench` 在平台未定时强制切 CPU 平台。

| 子命令 | 来源模块 | 用途 |
|--------|----------|------|
| `serve` | cli/serve.py | 启动 OpenAI 兼容 HTTP 服务（默认模型 Qwen/Qwen3-0.6B） |
| `launch render` | cli/launch.py | CPU-only 渲染服务（仅预处理/后处理，无 GPU 推理） |
| `bench <type>` | cli/benchmark/ | 基准测试家族 |
| `chat` | cli/openai.py | 交互式对话（`vllm chat`，默认 `http://localhost:8000/v1`） |
| `complete` | cli/openai.py | 交互式补全（`vllm complete`） |
| `run-batch` | cli/run_batch.py | 批量跑 prompts，读写 JSONL 文件 |
| `collect-env` | cli/collect_env.py | 收集环境信息 |

帮助风格：`vllm serve --help=<ConfigGroup|all|flag>`。

### vllm serve

- `--grpc` 时转 `grpc_server.serve_grpc`。
- Headless：`--headless` 只启动 core engines，不启动 API server（API 由外部进程接入）。
- 数据并行负载均衡两两互斥，三种模式：
  - `--data-parallel-multi-port-external-lb`：每个 DP rank 一个端口，`DPSupervisor` 在 supervisor 端口上探活；
  - `--data-parallel-external-lb` / `--data-parallel-rank`：外部 LB；
  - `--data-parallel-hybrid-lb` / `--data-parallel-start-rank`：混合内部/外部 LB。
- `api_server_count` 自动推导：外部 LB/multi-port/Rust 前端为 1；hybrid 为 `data_parallel_size_local`；否则为 `data_parallel_size`。多 API server 复用端口（SO_REUSEPORT）。
- Rust 前端：设 `VLLM_USE_RUST_FRONTEND=1` + `VLLM_RUST_FRONTEND_PATH` 时由 `RustFrontendProcessManager` 启动。
- `--enable-elastic-ep` 时 api_server_count 被压到 1。

### vllm bench（cli/benchmark/）

| 子命令 | 用途 |
|--------|------|
| `throughput` | 离线推理吞吐 |
| `latency` | 单批请求延迟 |
| `serve` | 在线服务吞吐（可委托 Rust 二进制，`VLLM_USE_RUST_BENCH=1`） |
| `startup` | 模型启动时间 |
| `sweep` | 参数扫描 |
| `mm-processor` | 多模态处理器延迟 |

子命令 lazily 导入（避免每次 `--help` 拖依赖）；`vllm bench serve` + `VLLM_USE_RUST_BENCH=1` 时 `os.execv` 委托 Rust CLI。

### vllm generate（说明）

任务描述中的 `generate/` 目录在本源码版本中不是独立 CLI 工具，而是代码包：提供 `BeamSearchOfflineMixin`（`LLM` 束搜索离线能力）、`generative_scoring`（端点 `/generative_scoring`）、`base/serving.py`（`GenerateBaseServing`，chat/completion/responses 共用的生成基类）。

### gRPC 服务（grpc_server.py）

由 `vllm serve --grpc` 或 `python -m vllm.entrypoints.grpc_server --model <model> --port 50051` 启动，依赖 `smg-grpc-servicer`（`pip install vllm[grpc]`）。服务：

- `VllmEngineServicer`（smg 生成的 gRPC 引擎协议）绑定 `AsyncLLM`；
- 附加 `grpc.health.v1.Health` 健康探针（K8s）与 gRPC reflection（grpcurl）；
- 传输限长均设 `-1`（无限），keepalive 参数放宽。

### 兼容与扩展端点清单

- Anthropic：`POST /v1/messages`、`POST /v1/messages/count_tokens`（`anthropic/api_router.py`，错误体转 Anthropic shape）。
- Cohere：`POST /cohere/v2/chat`，需 `VLLM_ENABLE_COHERE_API=1` 与 `pip install cohere`；未启用时 attach_router 成为 no-op，另有中间件把错误统一为 `{message, id}`。
- MCP：`mcp/` 无 HTTP 路由——`MCPToolServer` 通过 `--tool-server <url>` 接入外部 MCP SSE 服务，把工具描述转 harmony 格式注入对话（`HarmonyBrowserTool`/`HarmonyPythonTool` 为内置示例工具）；`--tool-server demo` 用 `DemoToolServer`。
- scale_out：`/inference/v1/generate`+`/abort_requests`（token in/token out）、render/derender 四端点。
- generate/beam_search：离线 `LLM` 的束搜索能力扩展。
- SageMaker：`/ping`、`/invocations`（`sagemaker_standards` 注册的容器标准）。
- Dev 路由（`VLLM_SERVER_DEV_MODE`）与 `/sleep`、`/wake_up`、`/is_sleeping`、`/collective_rpc`、缓存/RLHF/server_info：生产环境勿启用。

### collect-env 与其他

`vllm collect-env` 收集环境用于 issue 报告。`vllm run-batch -i INPUT.jsonl -o OUTPUT.jsonl --model <model>`：本地或 HTTP 文件输入输出，`--enable-metrics` 时 `start_http_server` 起 Prometheus；默认使用 OpenAI 兼容 API 处理本地文件（支持 chat/completions/embeddings/audio 等请求类型）。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)