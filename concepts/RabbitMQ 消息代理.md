---
title: RabbitMQ 消息代理
category: concepts
tags: [rabbitmq, amqp, message-broker, queue, exchange, clustering, active]
created: 2026-08-17
updated: 2026-08-17
summary: >-
    RabbitMQ 消息代理：AMQP 模型（Exchange/Queue/Binding）、四种 Exchange 类型（Direct/
    Fanout/Topic/Headers）、消息确认与持久化、集群与镜像队列（经典）/Quorum 队列（现代）、
    与 Kafka 的定位对比（路由灵活 vs 高吞吐日志）、Stream 协议（类 Kafka 语义）。
    衔接 [[concepts/Kafka 消息队列与流处理]]、[[concepts/分布式系统基础]]、[[concepts/韧性设计]]。
base_confidence: 0.85
lifecycle: draft
sources: []
---

# RabbitMQ 消息代理

> RabbitMQ 是最老牌的**消息代理**（broker），核心优势是**路由灵活**——多种 Exchange 类型
> 让消息可以按规则分发到不同队列。对比 [[concepts/Kafka 消息队列与流处理]] 的「日志流」思路。

---

## 1. AMQP 模型

```
Producer → Exchange ──Binding──▶ Queue → Consumer
              │
              └── 根据 Exchange 类型 + Routing Key 决定发到哪个队列
```

| 组件 | 职责 |
|------|------|
| **Producer** | 发消息，指定 Exchange + Routing Key |
| **Exchange** | 接收消息，按规则路由到队列 |
| **Binding** | Exchange 与 Queue 的绑定关系（含 Routing Key 模式） |
| **Queue** | 存储消息，等消费者来取 |
| **Consumer** | 从 Queue 拉/推消息，处理后 ACK |

---

## 2. 四种 Exchange 类型

| 类型 | 路由规则 | 典型场景 |
|------|----------|----------|
| **Direct** | Routing Key 精确匹配 | 点对点：`order.created` → 订单队列 |
| **Fanout** | 广播到所有绑定队列（忽略 Key） | 事件广播：一条消息通知多个服务 |
| **Topic** | 通配符匹配（`*` 一个词、`#` 零或多个词） | 灵活路由：`order.*.failed` → 告警队列 |
| **Headers** | 按消息头属性匹配（不常用） | 复杂条件路由 |

```
Direct:  Exchange "orders" ──key="order.created"──▶ Queue: order-service
                      ──key="order.failed"──────▶ Queue: alert-service

Topic:   Exchange "events" ──key="order.*.failed"──▶ Queue: all-failures
                      ──key="#.failed"──────────▶ Queue: dead-letter
```

---

## 3. 消息确认与持久化

```
Producer → Exchange → Queue（持久化到磁盘）
                         │
                    Consumer 处理完 → ACK
                         │
                    未 ACK → 消息重新入队（Redelivery）
```

- **Publisher Confirm**：生产者等 Broker 确认已接收/持久化。
- **Consumer ACK**：消费者处理完手动确认（`autoAck: false`）。
- **Dead Letter Exchange（DLX）**：消费失败/NACK 的消息路由到死信队列，方便重试或排查。

---

## 4. 集群与高可用

### Quorum 队列（推荐，RabbitMQ 3.8+）

基于 **Raft 共识**（[[concepts/分布式系统基础]]）的复制队列：
- 数据在多数节点上持久化后才 ACK。
- 自动故障转移（Leader 挂了，Follower 接管）。
- 比镜像队列更可靠、性能更好。

```
Node A (Leader) ──复制──▶ Node B (Follower)
              ──复制──▶ Node C (Follower)
              │
              │ 多数派 (2/3) 写入成功
              ▼
           消息确认
```

### 集群架构

- **普通集群**：元数据同步，队列数据只在创建节点（不跨节点复制）。
- **Quorum 队列**：数据跨节点复制（推荐生产使用）。
- **Federation/Shovel**：跨数据中心/跨云同步。

---

## 5. RabbitMQ vs Kafka

| 维度 | RabbitMQ | Kafka |
|------|----------|-------|
| **模型** | 消息代理（Broker） | 分布式日志 |
| **路由** | Exchange + Binding（灵活） | Topic + Partition（固定） |
| **消费模式** | Push（Broker 推给 Consumer） | Pull（Consumer 自己拉） |
| **消息回放** | 不支持（消费即删） | 支持（日志保留） |
| **吞吐** | 万级/秒 | 百万级/秒 |
| **延迟** | 微秒级 | 毫秒级 |
| **适合** | 任务队列/RPC/复杂路由 | 事件流/日志/大数据 |

> 选型：需要灵活路由/任务队列/RPC → RabbitMQ；需要高吞吐/事件溯源/流处理 → Kafka。

---

## 6. RabbitMQ Stream（类 Kafka 语义）

RabbitMQ 3.9+ 引入 Stream 协议：
- **日志语义**：消息持久化，支持回放（类 Kafka）。
- **高吞吐**：比传统队列高 10 倍+。
- **超 Consumer**：Consumer 从任意 offset 读取。
- **定位**：在 RabbitMQ 生态内提供 Kafka 级能力，适合已有 RabbitMQ 的团队。

---

## 7. 衔接

- Kafka 对照：[[concepts/Kafka 消息队列与流处理]]
- 分布式基础：[[concepts/分布式系统基础]]（Raft/一致性）
- 韧性：[[concepts/韧性设计]]（重试/死信/降级）
- 微服务：[[entities/微服务拆分实战]]（异步解耦）
- K8s 部署：[[concepts/Kubernetes 工作负载与调度]]（StatefulSet 部署 RabbitMQ）

---

## 参考链接

**库内双链**
- [[concepts/Kafka 消息队列与流处理]] — Kafka 对照
- [[concepts/分布式系统基础]] — Raft 共识/Quorum 队列基础
- [[concepts/韧性设计]] — 重试/死信/降级模式
- [[entities/微服务拆分实战]] — 异步事件驱动
- [[synthesis/容器分布式技术全景综述]] — 全景地图

**外部资料**
- RabbitMQ 官方文档（rabbitmq.com）
- AMQP 0-9-1 协议规范
- 《RabbitMQ in Depth》— 内部实现与集群运维
