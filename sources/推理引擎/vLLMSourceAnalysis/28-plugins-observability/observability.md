## 可观测性：OTel 追踪与日志设施

vLLM 的可观测性分两层：**OpenTelemetry 分布式追踪**（`vllm/tracing/`）与**日志格式化/过滤工具**（`vllm/logging_utils/`）。前者导出 trace 到 OTLP Collector，后者增强 Python logging 输出。

### 追踪后端注册表与统一入口

`tracing/__init__.py` 定义后端注册表 `_REGISTERED_TRACING_BACKENDS`，目前唯一后端 `"otel"` 绑定了 5 个函数；对外仅暴露统一 API，OTel 不可用时静默降级：

| 统一入口 | 行为 |
|---|---|
| `init_tracer(module, otlp_endpoint, extra_attributes)` | 后端可用才初始化，否则返回 `None`；调用点如 `v1/engine/llm_engine.py:68`、`v1/engine/async_llm.py:119` |
| `maybe_init_worker_tracer(module, process_kind, process_name)` | worker/EngineCore 进程初始化，`v1/executor/multiproc_executor.py`、`v1/engine/core.py` 调用 |
| `instrument(obj, span_name, attributes, record_exception)` | 装饰器：同步/异步函数包裹为 span；不可用时原样返回 `obj`，零开销 |
| `instrument_manual(span_name, start_time, end_time, attributes, context, kind)` | 用显式纳秒时间戳手工建 span（如编译阶段计时） |
| `is_tracing_available()` | 任意后端可用即 True，`config/observability.py:132` 用它校验 `--otlp-traces-endpoint` |

### OTel 导出配置（tracing/otel.py）

`init_otel_tracer`（`otel.py:60`）是主进程初始化核心：
1. 把 endpoint 写回环境变量 `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`，**子进程据此继承**。
2. 构造 `Resource`：固定属性 `vllm.instrumenting_module_name`、`vllm.process_id`（`os.getpid()`），外加 `extra_attributes`。
3. `TracerProvider(resource)` → `get_span_exporter(endpoint)` → 挂 `BatchSpanProcessor` → `set_tracer_provider` → `atexit.register(provider.shutdown)` → 返回 `get_tracer(module)`。

导出协议由 `OTEL_EXPORTER_OTLP_TRACES_PROTOCOL` 决定（默认 `grpc`），`get_span_exporter`（`otel.py:94`）：

```python
if protocol == "grpc":
    exporter = OTLPGrpcExporter(endpoint=endpoint, insecure=True)
elif protocol == "http/protobuf":
    exporter = OTLPHttpExporter(endpoint=endpoint)
else:
    raise ValueError(f"Unsupported OTLP protocol '{protocol}' is configured")
```

`init_otel_worker_tracer`（`otel.py:105`）从环境变量读 endpoint，为空则返回 `None`；否则补充 `vllm.process_kind`、`vllm.process_name` 属性后复用 `init_otel_tracer`。OTel 未安装时 `_IS_OTEL_AVAILABLE=False`，保留 `otel_import_error_traceback` 供诊断。

### 上下文传播

| 函数 | 行为 |
|---|---|
| `extract_trace_context(headers)` | 用 `TraceContextTextMapPropagator().extract` 从 HTTP headers 提取父上下文 |
| `_get_smart_context()` | 当前进程已有有效 span → 返回 `None`（沿用活动上下文）；否则从环境变量 `traceparent`/`tracestate`（大小写不敏感）提取，用于主进程→子进程 |
| `propagate_trace_to_env()` | contextmanager：span 期间 `inject()` 把 `traceparent`/`tracestate` 写进 `os.environ`，保证随后 spawn 的 worker 继承，退出后恢复原值 |

`instrument_otel`（`otel.py:134`）预计算静态代码属性（`code.function`/`code.namespace`/`code.filepath`/`code.lineno`，来自 `LoadingSpanAttributes`），默认 span 名取 `func.__qualname__`，按 `inspect.iscoroutinefunction` 选择 async/sync wrapper，同时包裹 `propagate_trace_to_env()`。

### Span 属性常量（tracing/utils.py）

`SpanAttributes` 类集中定义 span 属性名，兼容 OTel gen_ai 语义约定：

| 分组 | 属性示例 |
|---|---|
| 用量 | `gen_ai.usage.completion_tokens`、`gen_ai.usage.prompt_tokens`、`gen_ai.usage.num_sequences` |
| 请求 | `gen_ai.request.max_tokens`、`gen_ai.request.top_p`、`gen_ai.request.temperature`、`gen_ai.request.id`、`gen_ai.request.n` |
| 响应 | `gen_ai.response.model` |
| 时延 | `gen_ai.latency.time_in_queue`、`time_to_first_token`、`e2e`、`time_in_scheduler`、`time_in_model_forward`、`time_in_model_execute`、`time_in_model_prefill`、`time_in_model_decode`、`time_in_model_inference` |

另有 `TRACE_HEADERS = ["traceparent", "tracestate"]`；`contains_trace_headers`/`extract_trace_headers` 用于检测并摘取 W3C 追踪头；`log_tracing_disabled_warning`（`@run_once` 保证只告警一次）在收到携带 trace context 但追踪关闭的请求时调用。

### 日志设施（logging_utils）

`__init__.py` 导出 7 个工具，按用途分四组：

| 组件 | 文件 | 职责 |
|---|---|---|
| `NewLineFormatter` / `ColoredFormatter` | `formatter.py` | 日志格式器 |
| `UvicornAccessLogFilter` / `create_uvicorn_log_config` | `access_log_filter.py` | 过滤 uvicorn access log |
| `dump_engine_exception` / `prepare_object_to_dump` | `dump_input.py` | 引擎异常时落盘调度上下文 |
| `lazy` / `logtime` / `tensors_str_no_data` | `lazy.py` / `log_time.py` / `torch_tensor.py` | 装饰器与小工具 |

**formatter.py**：`NewLineFormatter` 在多行消息每行前补日志前缀对齐；`VLLM_LOGGING_LEVEL==DEBUG` 时启用相对路径并做 `shrink_path` 压缩——去掉 `vllm/` 前缀、`v1` 开头保留前两段、其余压缩为 `a/.../b/c` 形式（如 `fp8_utils.py` 示例）。`ColoredFormatter` 把时间戳与 `[fileinfo:lineno]` 染灰、levelname 按级别着色（DEBUG 白/INFO 绿/WARNING 黄/ERROR 红/CRITICAL 品红），`format()` 后恢复原 `record.levelname` 防复用污染。

**access_log_filter.py**：`UvicornAccessLogFilter(logging.Filter)` 只对 logger 名为 `uvicorn.access` 的记录生效，从 `record.args` 元组第 3 项取请求路径、经 `urlparse` 去 query 后与 `excluded_paths` 精确匹配（典型 `/health`、`/metrics`）。`create_uvicorn_log_config` 产出可直接传给 `uvicorn.run(log_config=...)` 的 dict：access 走 `sys.stdout` 挂该 filter，其余走 `sys.stderr`。

**dump_input.py**：`prepare_object_to_dump` 把任意对象转为可日志字符串——dict/list/set/tuple/Enum 递归展开；torch.Tensor 只打印 `Tensor(shape=..., device=..., dtype=...)` 元数据防泄漏；含 `anon_repr` 的对象用之；否则 `TypeName(...)` 或 `json.dumps` 兜底。`dump_engine_exception` 在 EngineCore 异常时以 ERROR 级别输出 vLLM 版本、config、`SchedulerOutput` 与 `SchedulerStats`，整体包在 `contextlib.suppress(Exception)` 中保证日志本身不抛错。

**小工具**：`lazy` 包装零参 callable，仅在被 `str()`/`repr()` 时求值——避免昂贵的参数序列化拖累未达级别的日志；`logtime(logger, msg)` 装饰器在 DEBUG 级别打印 `time.perf_counter()` 耗时；`tensors_str_no_data` 用 `printoptions(threshold=1, edgeitems=0)` 打印张量结构而不打印数据。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
