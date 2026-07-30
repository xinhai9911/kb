# 可观测性示例工程（observability-examples）

本目录是 [[entities/可观测性接入实战]] 的可运行栈，配套 [[concepts/可观测性工程]]。
用 Docker Compose 一键拉起 **OpenTelemetry + Prometheus + Loki + Tempo + Grafana**，
并附带一个**已埋点的 Python 服务**演示 RED 指标、Trace 链路、结构化日志（带 trace_id）。

## 目录结构

```
observability-examples/
├── app/                    埋点示例服务
│   ├── app.py             # Flask + OTel：span / RED 指标 / 带 trace_id 日志
│   ├── requirements.txt
│   └── Dockerfile
├── otel-collector/otel-collector.yaml   # 接收 OTLP → 导出 metrics/traces
├── prometheus/prometheus.yml            # 拉取 collector 的 :8889
├── loki/loki-config.yaml                # 日志存储
├── tempo/tempo.yaml                     # 链路存储（OTLP 接收）
├── grafana/provisioning/                # 数据源 + RED 看板（自动加载）
├── docker-compose.yml                   # 一键拉起全栈
└── README.md
```

## 数据流

```
app --OTLP(gRPC:4317)--> otel-collector --metrics--> prometheus(拉 :9090)
                                     \--traces--> tempo(:3200)
app(stdout, JSON) --promtail--> loki(:3100)
grafana(:3000) 统一查 prometheus/loki/tempo，trace 与 log 用 trace_id 互跳
```

## 运行

```bash
cd Q:/AI/kb/projects/observability-examples
docker compose up -d            # 拉起全部组件

# 生成流量（另开终端）
while true; do
  curl -s -XPOST localhost:8080/order -H 'content-type: application/json' -d '{"user_id":"u1"}'
  sleep 0.2
done

# 打开 Grafana
open http://localhost:3000      # 匿名可进，已自动配数据源 + RED 看板
```

## 验证清单（MVP，对应 [[entities/可观测性接入实战]] §6）

1. **指标**：Grafana → RED 看板，看到 `http_requests_total` 的 Rate 曲线、
   Error 率（~5% 由 app 随机失败触发）、Duration 的 P95/P99。
2. **链路**：Grafana → Explore → Tempo，找到一条 `/order` trace，应含
   `place_order` → `call_payment` 两层 span（跨调用上下文传播）。
3. **日志**：Grafana → Explore → Loki，看到 `job=app` 的结构化 JSON 日志，
   每条带 `trace_id`；点 trace_id 可跳到对应 trace。
4. **告警（可选）**：在 Prometheus 加规则 `rate(http_requests_total{status="500"}[5m]) > 0.02`，
   配 Grafana 告警通道，即基于 SLO（[[concepts/可观测性工程]] §5）。

## 关键文件对照

| 你想看什么 | 文件 |
|-----------|------|
| 怎么埋点（手动 span / RED 指标 / 日志带 trace_id） | `app/app.py` |
| Collector 怎么接、往哪导 | `otel-collector/otel-collector.yaml` |
| Prometheus 抓什么 | `prometheus/prometheus.yml` |
| RED 看板 PromQL | `grafana/provisioning/dashboards/red-dashboard.json` |
| 日志怎么关联 trace | `app.py` 的日志格式 + `grafana/datasources.yaml` 的 `tracesToLogs` |

## 排错

| 现象 | 原因 | 解决 |
|------|------|------|
| 无 trace | collector 未导出到 tempo | 检查 `otel-collector.yaml` 的 `exporters.otlp` 与 tempo 端口 |
| 无指标 | prometheus 没拉到 :8889 | `docker compose logs prometheus` 看 target 状态 |
| 日志无 trace_id 跳转 | 日志缺 trace_id 字段或数据源未配 tracesToLogs | 检查 app.py 日志格式 |
| 端口冲突 | 本机已占 3000/8080/9090 | 改 compose 端口映射 |

## 与文档关系

- 原理：[[concepts/可观测性工程]]（三大支柱 / RED / SLO）
- 实战：[[entities/可观测性接入实战]]（本工程即其落地）
- 相关：[[concepts/韧性设计]]（熔断/限流指标也应上报）、[[concepts/eBPF 核心架构]]（底层无侵入可观测）

## 参考

- OpenTelemetry / Prometheus / Loki / Tempo / Grafana 官方文档
- [[entities/可观测性接入实战]]
- [[concepts/可观测性工程]]
