---
title: Kafka 消息队列与流处理
category: concepts
tags: [kafka, messaging, stream, event-driven, partition, replication, exactly-once, distributed, active]
created: 2026-08-12
updated: 2026-08-12
summary: >-
    Kafka 消息队列与流处理：为什么分布式系统需要异步消息（解耦/削峰/事件溯源）、核心模型
    （Topic/Partition/Offset、Producer/Consumer Group、Broker/Controller/ISR）、追加写日志为何快
    （page cache + 零拷贝）、高可用与一致性（副本/ISR/acks/exactly-once、KRaft 替代 ZK）、
    消费位移与再均衡、与 RabbitMQ/Pulsar 对比、Kafka Streams 流处理、在 K8s 上运行（Strimzi）。
    衔接 [[concepts/分布式系统基础]]、[[entities/微服务拆分实战]]、[[concepts/架构风格演进]]。
base_confidence: 0.85
lifecycle: draft
sources: []
---

# Kafka 消息队列与流处理

> 本文是「分布式系统实战栈」的第一块。异步消息在 [[concepts/架构风格演进]] 的事件驱动风格、
> [[entities/微服务拆分实战]] 的异步事件解耦里被反复引用，但一直缺独立笔记。原理衔接 [[concepts/分布式系统基础]]。

---

## 1. 为什么分布式系统需要消息队列

微服务之间若全用**同步 RPC**（一个调一个），会链式耦合、互相拖垮、无法削峰。消息队列把「调用」变成「发事件」：

| 能力 | 说明 | 对应分布式痛点 |
|---|---|---|
| **异步解耦** | 生产者发完即走，消费者按自己节奏处理 | 服务间不直接依赖（[[entities/微服务拆分实战]]） |
| **削峰填谷** | 突发流量先堆积在队列，后端按能力消费 | 防雪崩（[[concepts/韧性设计]]） |
| **事件溯源** | 日志即真相，可回放重建状态 | 审计/重算 |
| **流处理** | 对实时数据流做聚合/关联 | 实时指标/告警 |

> 消息队列是「事件驱动架构」的骨架（[[concepts/架构风格演进]] §3）。它把「请求-响应」变成「发布-订阅」。

---

## 2. 核心模型

```
Producer ──produce──▶  Topic (按 key 哈希到 Partition)
                          │
            ┌─────────────┼─────────────┐
         Partition-0   Partition-1   Partition-2   (每个 Partition 是一个有序日志)
            │             │             │
         Consumer      Consumer      Consumer       (同一 Consumer Group 内，分区均分给成员)
         Group A       Group A       Group A
```

| 概念 | 含义 |
|---|---|
| **Topic** | 逻辑主题（一类消息） |
| **Partition** | Topic 的物理分片；**并行单位 + 顺序单位**（分区内严格有序，跨分区无序） |
| **Offset** | 消息在分区日志里的位点（单调递增） |
| **Producer** | 生产者；按 `key` 哈希决定落到哪个分区（同 key 必落同分区 → 保序） |
| **Consumer Group** | 一组消费者**共同消费**一个 Topic；分区被均分给组内成员（一个分区同时只被一个成员消费） |
| **Broker** | 服务节点；存分区副本 |
| **Controller** | 集群管理者（选主、分区再均衡）；旧版靠 ZooKeeper，新版用内置 **KRaft** |
| **ISR** | In-Sync Replicas，与 Leader 保持同步的副本集合 |

> [!note] 顺序性要点
> Kafka 只保证**分区内**有序。要「同一用户的订单按序处理」，就用 `user_id` 当 key —— 该用户所有消息进同一分区，自然有序。

---

## 3. 为什么 Kafka 这么快：追加写日志

Kafka 的存储本质是**每个分区一个只追加的日志文件（append-only log）**：

- **顺序写盘 >> 随机写**：Producer 写是顺序 append，磁盘吞吐极高。
- **Page Cache 而非 JVM 堆**：数据走操作系统页缓存，Broker 几乎不自己管内存，GC 压力小。
- **零拷贝发送**：Consumer 读时 `sendfile` 直接把页缓存数据拷到 socket，**绕过用户态**（不进应用内存、少一次拷贝）。
- **分批 + 压缩**：Producer 批量发、可 Snappy/LZ4 压缩，网络与磁盘双省。

> 对比数据库「随机读写 + 复杂索引」，Kafka 用「极简日志结构」换来了吞吐。这思路和 [[concepts/存储栈与io_uring]] 的 IO 优化同源。

---

## 4. 高可用与一致性

### 4.1 副本与 ISR

每个分区有 1 个 **Leader**（处理读写）+ N 个 **Follower**（从 Leader 拉取复制）。只有 **ISR** 里的副本才算「同步」。

| 生产者 `acks` | 语义 | 风险 |
|---|---|---|
| `0` | 发完不等确认 | 可能丢，最快 |
| `1` | Leader 写入即确认 | Leader 挂可丢 |
| `all`(=-1) | ISR 全部写入确认 | 最稳（仍可能 Leader 已 ACK 但未同步 Follower 前极端脑裂） |

### 4.2 投递语义（经典三选一）

| 语义 | 含义 | 实现 |
|---|---|---|
| At-most-once | 最多一次，可能丢 | ack=0 / 不重试 |
| At-least-once | 至少一次，可能重复 | ack=all + 重试（**默认**） |
| Exactly-once | 精确一次 | Producer 幂等 + 事务 + 消费位移与处理原子提交 |

> **Exactly-once 不是「消息只发一次」**，而是「处理结果不重不漏」：靠 Producer 幂等（PID+序列号去重）+ 事务（把「写消息」和「提交位移」绑成原子，[[concepts/分布式系统基础]] 幂等性）。

### 4.3 共识：KRaft 替代 ZooKeeper

旧版 Kafka 用 ZooKeeper 做 Controller 选举/元数据，运维重。新版 **KRaft** 用内置 Raft 共识管理元数据与选主——这正是 [[concepts/分布式系统基础]] 里 Raft 的工程落地。

---

## 5. 消费：位移提交与再均衡

- **位移（offset）提交**：消费者处理完后把「读到哪了」提交到内部 topic `__consumer_offsets`。提交太早→重复消费；太晚→漏消费。
- **再均衡（Rebalance）**：组成员变化（扩缩/宕机）时，分区重新分配，期间消费暂停。应尽量短（Cooperative Rebalance 增量再均衡）。
- **消费幂等**：下游处理要能扛重复（at-least-once 默认会重），如「用消息 key 做去重」（[[concepts/分布式系统基础]] 幂等）。

> [!warning] 重复消费是常态
> Kafka 默认 at-least-once。业务侧必须**幂等**（唯一键/去重表/乐观锁），不能假设「收到一次」。这是分布式系统铁律（[[concepts/分布式系统基础]]）。

---

## 6. Kafka vs 其他消息系统

| 维度 | Kafka | RabbitMQ | Pulsar |
|---|---|---|---|
| 模型 | 分区日志（拉模式） | 队列（推模式，路由交换） | 分区日志+分层存储 |
| 顺序 | 分区内严格有序 | 队列内有序 | 分区内有序 |
| 吞吐 | 极高（百万/s） | 中（万/s） | 高 |
| 延迟 | 较低（非极低） | 低 | 低 |
| 场景 | 日志/事件流/大数据管道 | 任务队列/RPC 解耦 | 云原生多租户流 |
| 存储 | 本地磁盘+保留期 | 内存/磁盘 | BookKeeper 分层 |

> 选型直觉：**高吞吐事件流/日志**选 Kafka；**低延迟任务路由**选 RabbitMQ；**多租户云原生**选 Pulsar。

---

## 7. 流处理（Kafka Streams / Flink）

Kafka 不只是队列，更是**流平台**：

- **Kafka Streams**：库（非独立集群），在消费者内做窗口聚合、join、状态表（table-table join = 流表双关）。
- **Kafka Connect**：把外部系统（DB/ES/S3）与 Kafka 互导（CDC 变更捕获）。
- **Flink**：独立流计算引擎，消费 Kafka 做复杂事件处理/CEP。

典型链路：`DB → Debezium(CDC) → Kafka → Flink 聚合 → Kafka → 下游服务/OLAP`。

---

## 8. 与云原生衔接（在 K8s 上跑）

- **Strimzi**：K8s Operator，用 CRD（`Kafka`/`KafkaTopic`/`KafkaUser`）声明式管理集群（见 [[concepts/Kubernetes Operator 与 CRD]]、[[synthesis/容器分布式技术全景综述]]）。
- Broker 用 `StatefulSet` + PV 保证稳定网络标识与持久化（[[concepts/Kubernetes 存储体系]]）。
- 客户端用 `Service` 发现 Bootstrap 地址。

---

## 参考链接

**库内双链**
- [[concepts/分布式系统基础]] — CAP/共识(Raft)/幂等/事务，本文一致性的地基
- [[entities/微服务拆分实战]] — 异步事件解耦、Saga 最终一致
- [[concepts/架构风格演进]] — 事件驱动架构风格
- [[concepts/韧性设计]] — 削峰/重试/幂等/背压
- [[concepts/存储栈与io_uring]] — 顺序写/页缓存/零拷贝的 IO 视角
- [[concepts/Kubernetes Operator 与 CRD]]、[[synthesis/容器分布式技术全景综述]] — K8s 上运行
- [[concepts/Kubernetes 存储体系]] — StatefulSet/PV 持久化

**外部资料**
- Kafka 官方文档（Apache Kafka / Confluent）
- 《Kafka 权威指南》《Designing Event-Driven Systems》
- KRaft 与 Raft 文档
