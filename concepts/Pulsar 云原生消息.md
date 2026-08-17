---
title: Pulsar 云原生消息
category: concepts
tags: [pulsar, messaging, streaming, apache, tiered-storage, active]
created: 2026-08-17
updated: 2026-08-17
summary: >-
    Pulsar 云原生消息：架构（Broker + BookKeeper + ZooKeeper 三层分离）、Topic 与 Partition、
    订阅模式（Exclusive/Shared/Failover/Key_Shared）、分层存储（Tiered Storage 原生支持）、
    跨地域复制（Geo-Replication）、与 Kafka 定位对比（计算存储分离 vs 一体）。
    衔接 [[concepts/Kafka 消息队列与流处理]]、[[concepts/RabbitMQ 消息代理]]、[[concepts/分布式系统基础]]。
base_confidence: 0.83
lifecycle: draft
sources: []
---

# Pulsar 云原生消息

> Apache Pulsar 是**计算存储分离**的云原生消息/流平台。Broker 无状态、BookKeeper 存储可独立扩展，
> 原生支持多租户与跨地域复制。对比 [[concepts/Kafka 消息队列与流处理]]。

---

## 1. 架构：三层分离

```
Producer ──▶ Broker（无状态）──▶ BookKeeper（存储层）
                  │                     │
             Topic 路由             Ledger 持久化
                  │                     │
              ZooKeeper（元数据）    Tiered Storage（冷数据下沉）
```

| 组件 | 职责 |
|------|------|
| **Broker** | 无状态，接收/路由消息，不存数据 |
| **BookKeeper (Bookie)** | 存储层，写 Ledger（追加写日志段） |
| **ZooKeeper** | 元数据管理（Topic 分配、Broker 负载均衡） |
| **Tiered Storage** | 冷数据自动下沉到 S3/GCS/HDFS（成本低） |

> [!note] vs Kafka 架构
> Kafka 的 Broker 既计算又存储（耦合）；Pulsar 计算存储分离，可独立扩缩。

---

## 2. Topic 与 Partition

- **Topic**：逻辑消息流，可设置多副本（replication factor）。
- **Partition**：Topic 的水平分片（类 Kafka Partition）。
- **Ledger**：BookKeeper 的存储单元，一个 Partition 由多个 Ledger 组成。

```
Topic: orders (3 分区, RF=3)
  Partition 0: Ledger-1 → Bookie A, B, C
  Partition 1: Ledger-2 → Bookie B, C, D
  Partition 2: Ledger-3 → Bookie A, C, D
```

---

## 3. 四种订阅模式

| 模式 | 行为 | 适合 |
|------|------|------|
| **Exclusive** | 一个 Consumer 独占 | 点对点 |
| **Shared** | 多 Consumer 轮询（类 RabbitMQ） | 任务队列 |
| **Failover** | 主备切换（一个 Consumer 接管） | 高可用消费 |
| **Key_Shared** | 相同 Key 的消息发给同一 Consumer（类 Kafka 分区有序） | 有序消费 |

---

## 4. 跨地域复制（Geo-Replication）

Pulsar **原生**支持跨 DC 复制（不需外部工具）：
```
DC-A (Broker+BookKeeper) ◄──Geo-Replication──► DC-B (Broker+BookKeeper)
         │                                              │
    Producer A                                    Consumer B
    发到本地 Topic                               从本地读取
```

- **异步复制**：消息写入本地 DC 后即返回 ACK，后台异步复制到其他 DC。
- **配置简单**：`pulsar-admin topics create persistent://public/default/orders --replication 3`

> 对比 Kafka 的 MirrorMaker（需要额外组件），Pulsar 的 Geo-Replication 是内置能力。

---

## 5. Pulsar vs Kafka

| 维度 | Pulsar | Kafka |
|------|--------|-------|
| **架构** | 计算存储分离 | 计算存储耦合 |
| **延迟** | 毫秒级 | 毫秒级 |
| **吞吐** | 百万级/秒 | 百万级/秒 |
| **多租户** | ✅ 原生（Tenant/Namespace）| ❌ 需额外管理 |
| **跨地域复制** | ✅ 内置 | MirrorMaker（外部）|
| **冷数据** | ✅ Tiered Storage（自动下沉）| 需 Kafka Connect + 外部存储 |
| **生态** | 较新，社区增长中 | 最成熟，工具丰富 |
| **运维复杂度** | 高（Broker+BK+ZK 三组件）| 中（Broker+KRaft/ZK）|

> 选型：已有 Kafka 生态 → 继续 Kafka；新项目+多租户+跨地域需求 → Pulsar。

---

## 6. 衔接

- Kafka 对照：[[concepts/Kafka 消息队列与流处理]]
- RabbitMQ/NATS 对照：[[concepts/RabbitMQ 消息代理]]、[[concepts/NATS 轻量消息系统]]
- 分布式基础：[[concepts/分布式系统基础]]
- K8s 部署：[[concepts/Kubernetes 工作负载与调度]]
- 存储：[[concepts/Kubernetes 存储体系]]

---

## 参考链接

**库内双链**
- [[concepts/Kafka 消息队列与流处理]] — Kafka 定位对照
- [[concepts/RabbitMQ 消息代理]] — RabbitMQ 对照
- [[concepts/NATS 轻量消息系统]] — NATS 对照
- [[concepts/分布式系统基础]] — 消息一致性
- [[concepts/Kubernetes 存储体系]] — BookKeeper/Tiered Storage

**外部资料**
- Apache Pulsar 官方文档（pulsar.apache.org）
- 《Apache Pulsar: Event Streaming at Scale》
- StreamNative 博客（pulsar 技术深度文章）
