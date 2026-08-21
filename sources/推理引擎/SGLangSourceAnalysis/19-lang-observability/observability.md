## 可观测性：Prometheus 指标与 OTel 追踪

本文覆盖 `srt/observability/`（14 文件），说明 SGLang 的两套可观测设施：**Prometheus 指标**（`metrics_collector.py` 多收集器 + `/metrics` 端点 + 请求级导出）与 **OTel 分布式追踪**（`trace.py` 同步 / `trace_async.py` 异步 ZMQ 导出）。vLLM 对照见文末。

### 模块文件地图（srt/observability/）

| 文件 | 职责 |
|---|---|
| `metrics_collector.py`（2430 行） | 所有指标收集器与数据结构（见下） |
| `trace.py` | OTel 追踪：`process_tracing_init`、`TraceReqContext`、`SpanAttributes` |
| `trace_async.py` | `SGLANG_TRACE_ASYNC=1` 时把 span 创建卸载到独立 exporter 进程（ZMQ PUSH/PULL） |
| `req_time_stats.py` | 请求管线分阶段计时 `RequestStage` + trace/metrics 联动 |
| `forward_pass_metrics.py` | 调度器每迭代指标经 ZMQ PUB 发布（msgspec 零拷贝） |
| `request_metrics_exporter.py` | 请求级指标落盘导出（`--export-metrics-to-file`） |
| `func_timer.py` | `@time_func_latency` 装饰器（sync/async 函数耗时） |
| `cpu_monitor.py` / `startup_time.py` / `startup_func_log_and_timer.py` | CPU 负载、启动时间与启动函数计时 |
| `mooncake_trace.py` | Mooncake KV 传输链路追踪辅助 |
| `ray_wrappers.py` | Ray 场景下的指标收集器包装 |
| `utils.py` / `label_transform.py` | bucket 生成（`two_sides_exponential_buckets`/`exponential_buckets`）、priority 基数控制（`transform_priority` 归并为 LOW/HIGH/UNKNOWN） |

### MetricsCollector 家族（metrics_collector.py）

所有收集器经 `_StatLoggerDIMixin`（:214）支持依赖注入——`_counter_cls/_gauge_cls/_histogram_cls/_summary_cls` 置空用 `prometheus_client`，非空（如 `ray_wrappers`）则换实现。指标统一命名 `sglang:*`，`labelnames` 来自服务器标签，`multiprocess_mode="mostrecent"`（多进程共享，主进程聚合）。

| 收集器 | 职责与代表性指标 |
|---|---|
| `SchedulerMetricsCollector`（:237） | 调度侧：`sglang:num_running_reqs`/`num_queue_reqs`/`gen_throughput`/`cache_hit_rate`/`token_usage`/`full_token_usage`/`spec_accept_length`/`weight_load_duration_seconds`/`num_retracted_requests_total`/`num_grammar_queue_reqs` 等；`log_stats` 统一上报 |
| `TokenizerMetricsCollector`（:1480） | 请求侧：`observe_one_finished_request`/`observe_time_to_first_token`（含 straggler 检测）/`observe_inter_token_latency`/`emit_startup_time` |
| `StorageMetricsCollector`（:1849） | HiCache 存储：prefetch/backup/dropped tokens 计数 |
| `RadixCacheMetricsCollector`（:1989） | 前缀树：eviction/load_back/backup 的 token 数、字节数与耗时 |
| `ExpertDispatchCollector`（:1974） | MoE 专家分发（EP 规模参数） |
| `EncoderMetricsCollector`（:2187） | 多模态 encoder：cache eviction、queue/preprocess/model_forward/transfer 分阶段直方图 |

辅助结构：`QueueCount`（:44）、`SchedulerStats`（:64，`from_reqs` 统计队列/运行中请求）、`DPCooperationInfo`（:171，DP 协作标签）、`resolve_collector_class`（:200，按 `server_args.stat_loggers[role]` 换子类）、`get_histogram_conf_from_env`（:2419）。

### /metrics 端点与 HTTP 中间件

`srt/utils/common.py`：`set_prometheus_multiproc_dir`（:2520）必须在导入 `prometheus_client` 前设置 `PROMETHEUS_MULTIPROC_DIR`（默认临时目录）；`add_prometheus_middleware`（:2538）挂 `MultiProcessCollector` + `make_asgi_app` 到 `/metrics`（`--enable-metrics` 时由 `http_server.py:285,2540` 调用）；`add_prometheus_track_response_middleware`（:2571）新增 `sglang:http_requests_total`/`http_responses_total`/`http_requests_active`/`routing_keys_active`（`x-smg-routing-key` 路由键去重计数）。

`func_timer.enable_func_timer`（`--enable-metrics` 时开启）注册 `sglang:func_latency_seconds` Histogram，bucket `0.05*1.5^i`（约 50ms~50s），`@time_func_latency` 装饰器同时支持同步与异步函数。

**请求级导出**：`request_metrics_exporter.py` 的 `RequestMetricsExporter`（ABC）→ `FileRequestMetricsExporter` 把 `GenerateReqInput` 字段（排除非 JSON 序列化字段 `image_data` 等）与 `meta_info` 写为 `sglang-request-metrics-{YYYYMMDD_HH}.log`，跳过健康检查请求；`RequestMetricsExporterManager` 还尝试加载私有 fork 的导出器。

### 追踪：请求级 TraceReqContext（trace.py）

启用开关：`--enable-trace` + `--otlp-traces-endpoint`（`http_server.py:290` 调 `process_tracing_init`），`--trace-modules` 白名单过滤，`SGLANG_TRACE_LEVEL`（默认 3）控制 span 深度。未装 opentelemetry 时 `opentelemetry_imported=False` 静默降级。

| 组件 | 行为 |
|---|---|
| `process_tracing_init(endpoint, server_name, trace_modules)`（:211） | 建 `TracerProvider(resource=Resource(SERVICE_NAME), id_generator=TraceCustomIdGenerator())` + `BatchSpanProcessor`（`SGLANG_OTLP_EXPORTER_SCHEDULE_DELAY_MILLIS`/`MAX_EXPORT_BATCH_SIZE` 可调）；`SGLANG_TRACE_ASYNC` 时自动 `start_trace_exporter` |
| `get_otlp_span_exporter`（:270） | 协议取 `OTEL_EXPORTER_OTLP_TRACES_PROTOCOL`（默认 grpc），支持 `grpc`/`http/protobuf` |
| `trace_set_thread_info`（:287） | 每线程登记 `TraceThreadInfo(host_id, pid, thread_label, tp/dp/pp_rank)`；`host_id` 取 `/etc/machine-id` 或 MAC，防跨节点 PID 冲突 |
| `TraceReqContext`（:313） | 每请求一个：`trace_req_start` 建 root span（attrs `rid`/`module=sglang::{module}`/`bootstrap_room`）与 thread span；`trace_slice_start/end` 建层级 slice span（`level` 大于全局 level 直接跳过，`__check_fast_return`）；`trace_event` 先缓存再按时间窗挂到 span |
| 跨进程传播 | `__getstate__`（:407）只序列化 `root_span_context`（traceparent 注入）+ `last_span_context`，`__setstate__` 重建为 `is_remote=True` 的 `SpanContext`；`copy_for_thread`/`rebuild_thread_context` 供跨线程（如 KV 传输 chunk）复用 |
| `TraceCustomIdGenerator`（:127） | 自定义 span ID 生成器：支持 `preset_next_span_id` 预置（异步模式用），`_preset_local` 线程隔离 |
| `SpanAttributes`（:840） | 复用 OTel `gen_ai.*` 语义约定：`gen_ai.usage.cached_tokens`、`gen_ai.latency.time_to_first_token`、`time_in_model_prefill`/`time_in_model_decode` 等 |

**异步追踪**（`trace_async.py`）：`SGLANG_TRACE_ASYNC=1` 时 root span 留在调用进程（便宜，用于跨进程 traceparent），其余 slice span 在调用侧**预生成 span ID** 并连同操作经 ZMQ PUSH/PULL 发送给 daemon exporter，exporter 用 `preset_next_span_id` 重建与同步模式完全一致的 span 树；线程信息通过 `_on_thread_info_set` 回调一次性推送。`req_time_stats.py` 定义 `RequestStage` 各阶段（`TOKENIZE`/`API_SERVER_DISPATCH`/`DPC_DISPATCH` 等，level 1-3），同时驱动 trace span 与 `observe_per_stage_req_latency` 指标。

### 与 vLLM 可观测性对照

| 维度 | SGLang | vLLM |
|---|---|---|
| 指标体系 | 多 `MetricsCollector` 类 + `/metrics`（MultiProcessCollector），`sglang:*` 前缀 | `/metrics` + `logging_config`，`vllm:*` 前缀（见 vLLM 28-plugins-observability） |
| 请求级导出 | `RequestMetricsExporter` 落盘 | 无等价物（用日志 dump） |
| 追踪初始化 | `process_tracing_init` + `TraceReqContext` 每请求对象 | `init_tracer`/`instrument` 装饰器（`tracing/otel.py`） |
| 跨进程传播 | `TraceReqContext.__getstate__` 显式序列化 + `trace_async` ZMQ 导出进程 | 环境变量 `traceparent` 注入（`propagate_trace_to_env`）+ W3C headers |
| 深度控制 | `SGLANG_TRACE_LEVEL`（1-3 层级）+ `--trace-modules` | 无等价 level；`instrument` 按函数 |
| 调度遥测 | `forward_pass_metrics` ZMQ PUB 实时流（msgspec） | 无 |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
