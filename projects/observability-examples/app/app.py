"""
app.py — 最小可观测性埋点示例（Python + OpenTelemetry）

对应 [[entities/可观测性接入实战]]、[[concepts/可观测性工程]]。
演示：
  - 自动 HTTP 埋点（OTel instrumentor）
  - 手动 span（关键路径 place_order）
  - RED 指标（请求计数 + 直方图延迟，经 Prometheus exporter）
  - 结构化日志带 trace_id（与 trace 关联）

启动：见 docker-compose.yml（镜像内已装依赖）。本地跑见 README。
"""
import logging
import random
import time
from flask import Flask, request
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.trace import get_tracer, format_trace_id

# ---- Tracer ----
tracer = trace.get_tracer("order-app")
provider = TracerProvider()
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
trace.set_tracer_provider(provider)

# ---- Meter (RED 指标) ----
reader = PeriodicExportingMetricReader(OTLPMetricExporter(), export_interval_millis=5000)
meter = metrics.get_meter("order-app")
meter_provider = MeterProvider(metric_readers=[reader])
metrics.set_meter_provider(meter_provider)

request_counter = meter.create_counter("http_requests_total", description="总请求数")
request_duration = meter.create_histogram("http_request_duration_seconds", description="请求延迟")

# ---- 日志（带 trace_id）----
logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("order")

app = Flask(__name__)
FlaskInstrumentor().instrument_app(app)


@app.route("/healthz")
def healthz():
    return "ok", 200


@app.route("/order", methods=["POST"])
def place_order():
    start = time.time()
    with tracer.start_as_current_span("place_order") as span:
        # 模拟业务：调用下游 + 处理
        user_id = request.json.get("user_id", "anon") if request.is_json else "anon"
        span.set_attribute("order.user_id", str(user_id))

        # 模拟一个下游调用 span（跨进程 context 会自动随 traceparent 传播）
        with tracer.start_as_current_span("call_payment") as child:
            time.sleep(random.uniform(0.01, 0.08))
            child.set_attribute("payment.method", "mock")

        # 偶发失败，制造错误率用于 SLO 告警
        failed = random.random() < 0.05
        dur = time.time() - start

        # 记录 RED 指标
        request_counter.add(1, {"route": "/order", "status": "500" if failed else "200"})
        request_duration.record(dur, {"route": "/order"})

        # 结构化日志带 trace_id（与 trace 关联）
        tid = format_trace_id(span.get_span_context().trace_id)
        log.info('{"level":"info","msg":"order placed","trace_id":"%s","user_id":"%s","duration_s":%.3f,"status":%d}'
                 % (tid, user_id, dur, 500 if failed else 200))

        if failed:
            return {"error": "payment failed"}, 500
        return {"order_id": "o-" + str(random.randint(1000, 9999))}, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
