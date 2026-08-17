---
title: NATS 轻量消息系统
category: concepts
tags: [nats, messaging, jetstream, edge, iot, cncf, active]
created: 2026-08-17
updated: 2026-08-17
summary: >-
    NATS 轻量消息系统：Core NATS（Pub/Sub、Request-Reply）、JetStream（持久化/流/消费者/
    Exactly-Once）、NATS 架构（超级集群/Leaf Node/边缘连接）、与 Kafka/RabbitMQ 定位对比
    （超低延迟 vs 高吞吐 vs 灵活路由）、K8s 原生部署（nats-operator）。
    衔接 [[concepts/Kafka 消息队列与流处理]]、[[concepts/RabbitMQ 消息代理]]、[[concepts/分布式系统基础]]。
base_confidence: 0.85
lifecycle: draft
sources: []
---

# NATS 轻量消息系统

> NATS 是 CNCF 毕业项目，定位**超轻量、超低延迟**的消息系统。Core NATS 零持久化换极致性能，
> JetStream 补齐持久化与流语义。对比 [[concepts/Kafka 消息队列与流处理]]、[[concepts/RabbitMQ 消息代理]]。

---

## 1. NATS 定位

| 特性 | NATS | Kafka | RabbitMQ |
|------|------|-------|----------|
| **延迟** | 微秒级 | 毫秒级 | 微秒级 |
| **吞吐** | 千万级/秒 | 百万级/秒 | 万级/秒 |
| **持久化** | 可选（JetStream） | 强制 | 可选 |
| **模型** | Pub/Sub + Request-Reply | 日志流 | 消息代理 |
| **复杂度** | 极低（单 binary） | 高（ZooKeeper/KRaft） | 中 |
| **适合** | 边缘/IoT/微服务通信 | 事件流/大数据 | 任务队列/RPC |

---

## 2. Core NATS

### 三种消息模式

| 模式 | 行为 |
|------|------|
| **Pub/Sub** | 发布-订阅，所有订阅者收到所有消息（广播） |
| **Queue Group** | 负载均衡：同一 group 内只有一个消费者收到消息 |
| **Request-Reply** | 同步调用：发送请求，等待回复（配超时） |

```
# Pub/Sub
PUB orders.order.created _INBOX.xxx\r\n{data}\r\n
SUB orders.order.created 1\r\n

# Queue Group（负载均衡）
SUB orders.processing worker-group\r\n
SUB orders.processing worker-group\r\n
# → 消息只发给其中一个 worker

# Request-Reply
PUB orders.validate _INBOX.abc\r\n{data}\r\n
SUB _INBOX.abc 1\r\n
# → 等待回复（配 timeout）
```

### 通配符

| 通配符 | 规则 | 示例 |
|--------|------|------|
| `*` | 匹配一个层级 | `orders.*.created` 匹配 `orders.order.created` |
| `>` | 匹配一个或多个层级 | `orders.>` 匹配 `orders.order.created.v2` |

---

## 3. JetStream（持久化层）

JetStream 是 NATS 的持久化扩展，补齐了 Core NATS 的「消息不落地」短板：

| 概念 | 说明 |
|------|------|
| **Stream** | 持久化消息存储（类 Kafka Topic），支持多种存储后端 |
| **Consumer** | 消费 Stream 中的消息（Pull/Push） |
| **Ack Policy** | `AckExplicit`（逐条确认）/ `AckAll`（确认到某条之前全部）/ `AckNone`（不需确认） |
| **Delivery Policy** | `All`（从头）/ `New`（新消息）/ `StartSequence` / `StartTime` |
| **Replay Policy** | `Instant`（立即）/ `Original`（按原始时间间隔重放） |

```
Stream "ORDERS"
  ├── 消息 1 (seq=1, data=order.created)
  ├── 消息 2 (seq=2, data=order.paid)
  └── 消息 3 (seq=3, data=order.shipped)

Consumer "order-processor" (Pull, AckExplicit)
  → 拉取消息 → 处理 → ACK → Stream 记录已消费位点
```

> [!note] Exactly-Once 语义
> JetStream 通过 **dedup（去重）** + **AckExplicit** 实现 At-Least-Once；配合客户端去重（`Nats-Msg-Id` header）可实现 Exactly-Once。

---

## 4. 架构

```
超级集群（Super-Cluster）
  ├── Cluster A（3 节点）←── Gateway ──→ Cluster B（3 节点）
  │       │                                    │
  │   Leaf Node                              Leaf Node
  │   (边缘站点)                             (边缘站点)
  │       │                                    │
  │   IoT 设备 / 边缘应用                  IoT 设备 / 边缘应用
```

- **Super-Cluster**：跨地域集群互联，自动路由。
- **Leaf Node**：轻量边缘节点，连接到中心集群（低资源消耗）。
- **Gateway**：集群间消息路由。

---

## 5. K8s 部署

```yaml
# nats-operator 或 Helm chart
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: nats
spec:
  chart:
    spec:
      chart: nats
      sourceRef:
        kind: HelmRepository
        name: nats
  values:
    nats:
      jetstream:
        enabled: true
        fileStorage:
          size: 10Gi
    cluster:
      enabled: true
      replicas: 3
```

---

## 6. 衔接

- Kafka 对照：[[concepts/Kafka 消息队列与流处理]]
- RabbitMQ 对照：[[concepts/RabbitMQ 消息代理]]
- 分布式基础：[[concepts/分布式系统基础]]
- 边缘/多集群：[[concepts/多集群管理与联邦]]
- K8s 部署：[[concepts/Kubernetes 工作负载与调度]]

---

## 参考链接

**库内双链**
- [[concepts/Kafka 消息队列与流处理]] — Kafka 定位对照
- [[concepts/RabbitMQ 消息代理]] — RabbitMQ 定位对照
- [[concepts/分布式系统基础]] — 消息一致性背景
- [[concepts/多集群管理与联邦]] — NATS 超级集群与边缘场景

**外部资料**
- NATS 官方文档（docs.nats.io）
- JetStream 设计文档
- CNCF NATS 项目页（github.com/nats-io/nats-server）
