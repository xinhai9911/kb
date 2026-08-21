## HTTP 服务与端点清单（SGLang Runtime）_part1：启动与端点总览

源码：`sglang/srt/entrypoints/http_server.py`（约 105KB，SRT 的 HTTP 入口）+ `sglang/srt/entrypoints/v1_loads.py`（/v1/loads）+ `sglang/srt/entrypoints/openai/protocol.py`（请求模型）+ `sglang/launch_server.py`（CLI 入口）。端点细节见 [_part2](http-server_part2.md)。

### 定位与启动流程

`launch_server`（`http_server.py:2766`）是 SRT 服务端入口：先 `Engine._launch_subprocesses` 拉起 Scheduler/Detokenizer 子进程（进程拓扑见 [00-overview](../00-overview/architecture_part1.md)），再 `_setup_and_run_http_server`（:2513）注册全局状态、挂中间件并启动 uvicorn。HTTP server、Engine、TokenizerManager 三者同在主进程。

```python
# http_server.py:456  FastAPI 应用
app = FastAPI(lifespan=lifespan, openapi_url=None if get_bool_env_var("DISABLE_OPENAPI_DOC") else "/openapi.json")
app.router.route_class = ORJSONRoute      # orjson 解析/序列化大 JSON body
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, ...)
```

- `ORJSONRequest`/`ORJSONRoute`（:434-453）：把 FastAPI 的 stdlib json 换成 orjson，`>64` 位整数与裸 NaN/Infinity 直接 400。
- `lifespan`（:270）：`--enable-metrics` 时挂 Prometheus 中间件、`--enable-trace` 时初始化 OTLP；在 `app.state` 上构造全部 `openai_serving_*` / `ollama_serving` / `anthropic_serving` 实例；可选启动 native gRPC server 与 sidecar；后台线程 `_wait_and_warmup` 预热。
- 全局状态 `_GlobalState`（:197）保存 `tokenizer_manager`、`template_manager`、`scheduler_info`，经 `get_global_state()` 供各 handler 读取。
- 多 tokenizer 模式（`--tokenizer-worker-num>1`）：`init_multi_tokenizer`（:216）从共享内存读 `port_args`/`server_args`，每 worker 独立进程起 HTTP server（uvicorn `workers=N`）；此时不支持 `--api-key`。
- 服务器选择：默认 uvicorn（uvloop）；`--enable-http2` 换 Granian；`--enable-ssl-refresh` 走 `SSLCertRefresher`。

### 端点总览（方法 / 路径 / 用途 / 模块）

按协议族分组。行内标注 handler 与源码位置。

| 族 | 方法 | 路径 | 用途 |
|---|---|---|---|
| 核心生成 | POST/PUT | `/generate` | v0 风格生成（`GenerateReqInput`，流式/非流式），`generate_request` :889 |
| 核心生成 | POST/PUT | `/encode` `/classify` | embedding / 奖励模型（`EmbeddingReqInput`），:942/:954 |
| 健康/信息 | GET | `/health` `/health_generate` | 健康检查（下钻送一个 token），:654 |
| 健康/信息 | GET | `/ping` | SageMaker 静态健康（恒 200），:2023 |
| 健康/信息 | GET | `/model_info`（`/get_model_info` 旧名） | 模型路径/服务名/is_generation/parser 等，:738 |
| 健康/信息 | GET | `/server_info`（`/get_server_info` 旧名） | `ServerArgs` + scheduler 状态 + 版本，:796 |
| 健康/信息 | GET | `/weight_version` | 已废弃，恒 404（提示用 /model_info），:776 |
| 健康/信息 | GET | `/get_load` | 废弃 shim，投影到旧字段（dp_rank/num_reqs/…），:829 |
| 指标/负载 | GET | `/metrics` | Prometheus 指标（`Mount` 于 `utils/common.py:2538`，需 `--enable-metrics`） |
| 指标/负载 | GET | `/v1/loads` | 各 DP rank 调度器负载（json/prometheus），`v1_loads.py:93` |
| 工具/管理 | GET/POST | `/flush_cache` `/abort_request` `/set_internal_state` | 缓存清理 / 请求中止 / 运行时改 `server_args`（:966/:1607/:858，后者 ADMIN_OPTIONAL） |
| 工具/管理 | POST | `/open_session` `/close_session` | 会话式持续提示，:1573/:1587 |
| 工具/管理 | POST | `/start_profile` `/stop_profile` `/set_trace_level` `/freeze_gc` | 剖析 / trace 级别 / GC 冻结，:1157-1200 |
| 工具/管理 | GET/POST | `/start_expert_distribution_record` 等 3 个 | MoE 专家分布记录，:1202-1233 |
| 工具/管理 | POST | `/parse_function_call` `/separate_reasoning` | 函数调用解析 / 推理文本分离（reasoning parser），:1620/:1648 |
| 工具/管理 | POST | `/pause_generation` `/continue_generation` | 暂停/恢复生成（权重更新期），:1685/:1698 |
| 工具/管理 | GET/POST | `/release_memory_occupation` `/resume_memory_occupation` | 释放/恢复显存，:1482/:1494 |
| 工具/管理 | GET/POST | `/slow_down` `/weights_checker` `/configure_logging` | 慢化请求 / 权重一致性校验 / 日志级别，:1506-1599 |
| 工具/管理 | POST | `/load_lora_adapter` `/load_lora_adapter_from_tensors` `/unload_lora_adapter` | 运行时 LoRA 热加载/卸载，:1539-1571 |

### 健康检查与指标

- `/health` 与 `/health_generate`（:654）共享 handler：`gracefully_exit` 或 `ServerStatus.Starting` 时直接 503；`/health` 在 `SGLANG_ENABLE_HEALTH_ENDPOINT_GENERATION` 未设时只回 200，否则与 `/health_generate` 一样构造 `GenerateReqInput(input_ids=[0], sampling_params={"max_new_tokens":1,"temperature":0.0})` 下钻一个 token，收到任何回包即判健康（`HEALTH_CHECK_TIMEOUT` 默认 20s），超时置 `ServerStatus.UnHealthy` 返 503。
- `/metrics` 由 `add_prometheus_middleware`（`utils/common.py:2538`）以 `Mount("/metrics", make_asgi_app(registry))` 挂载，`--enable-metrics` 时启用。
- `/v1/loads`（`v1_loads.py:93`）查询参数 `dp_rank`（按 DP rank 过滤）、`include`（`core,memory,spec,lora,disagg,queues,all`）、`format=prometheus`；返回 `timestamp/version/accelerator/num_accelerators/loads[]`，负载来自 `TokenizerManager.get_loads`。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
