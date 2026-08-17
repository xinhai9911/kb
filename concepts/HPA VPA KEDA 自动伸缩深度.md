---
title: HPA/VPA/KEDA 自动伸缩深度
category: concepts
tags: [hpa, vpa, keda, autoscaling, kubernetes, metrics, active]
created: 2026-08-17
updated: 2026-08-17
summary: >-
    HPA/VPA/KEDA 自动伸缩深度：HPA 水平 Pod 伸缩（CPU/内存/自定义指标/行为配置）、
    VPA 垂直 Pod 伸缩（推荐/自动/Off 模式）、KEDA 事件驱动伸缩（Kafka lag/Prometheus/Cron
    /HTTP/缩到零）、Cluster Autoscaler 与 Karpenter 节点级伸缩、伸缩策略组合与避坑。
    衔接 [[concepts/Kubernetes 工作负载与调度]]、[[concepts/Kubernetes 高可用与自愈]]、[[concepts/FinOps 与云资源优化]]。
base_confidence: 0.85
lifecycle: draft
sources: []
---

# HPA/VPA/KEDA 自动伸缩深度

> 伸缩是 K8s 的核心能力：应对流量波动、节省成本。但 HPA/VPA/KEDA 各有适用场景，用错会「伸缩震荡」
> 或「伸缩无效」。本文深入三者原理与组合。见 [[concepts/Kubernetes 工作负载与调度]]。

---

## 1. HPA（Horizontal Pod Autoscaler）

### 基本原理

```
Metrics Server ←── 采集 ──▶ Pod 指标（CPU/内存）
      │
      ▼
HPA Controller ←── 计算 ──▶ 目标副本数
      │                      = ceil(当前副本数 × (当前值/目标值))
      ▼
Scale Deployment → 调整 replicas
```

### 配置示例

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: my-app-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: my-app
  minReplicas: 2
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70    # CPU 利用率 70% 时触发
    - type: Pods                    # 自定义 Pod 指标
      pods:
        metric:
          name: requests_per_second
        target:
          type: AverageValue
          averageValue: "1000"
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60   # 扩容稳定窗口
      policies:
        - type: Percent
          value: 100                   # 最多翻倍
          periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 300  # 缩容等 5 分钟（防震荡）
      policies:
        - type: Percent
          value: 10                    # 每次最多缩 10%
          periodSeconds: 60
```

### 行为配置（behavior）避坑

| 参数 | 作用 | 推荐值 |
|------|------|--------|
| `stabilizationWindowSeconds` | 窗口内最大/最小值决定伸缩 | 扩容 60s / 缩容 300s |
| `scaleUp.policies` | 限制扩容速度 | 每次最多翻倍 |
| `scaleDown.policies` | 限制缩容速度 | 每次最多缩 10-20% |

> [!warning] 缩容震荡
> 缩容太快 → 负载上升 → 立即扩容 → 又缩容 → 死循环。缩容窗口设 5 分钟+。

---

## 2. VPA（Vertical Pod Autoscaler）

### 三种模式

| 模式 | 行为 | 适合 |
|------|------|------|
| **Off**（默认） | 只推荐，不自动应用 | 评估阶段 |
| **Initial** | 只在 Pod 启动时应用推荐值 | 稳定工作负载 |
| **Auto** | 自动更新 Pod（重启应用） | 开发/测试 |

```yaml
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: my-app-vpa
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: my-app
  updatePolicy:
    updateMode: "Auto"
  resourcePolicy:
    containerPolicies:
      - containerName: my-app
        minAllowed:
          cpu: "100m"
          memory: "128Mi"
        maxAllowed:
          cpu: "4"
          memory: "8Gi"
        controlledResources: ["cpu", "memory"]
```

### VPA 与 HPA 的冲突

| 问题 | 原因 |
|------|------|
| VPA 调 CPU requests → HPA CPU 指标失真 | HPA 基于 (actual/target) 计算，target 变了 |
| VPA 重启 Pod → HPA 同时也在扩缩 | 两个控制器打架 |

**解决方案**：
1. HPA 用**自定义指标**（非 CPU），VPA 管 CPU/Memory。
2. 或 VPA 设 `updateMode: Off`，只用推荐值手动调。

---

## 3. KEDA（Kubernetes Event-Driven Autoscaling）

KEDA = **事件驱动伸缩**，弥补 HPA 只能基于 CPU/内存的短板：

```
外部事件源 (Kafka/Prometheus/Cron/HTTP)
      │
      ▼
KEDA Scaler ←── 获取指标 ──▶ ScaledObject
      │                        │
      │                        ├── minReplicas: 0  (可缩到零！)
      │                        └── maxReplicas: 100
      ▼
HPA Controller ←── 标准 HPA 机制伸缩
```

### 常见 Scaler

| Scaler | 指标 | 场景 |
|--------|------|------|
| **kafka** | Consumer lag | 消费者积压时扩容 |
| **prometheus** | 自定义 Prometheus 指标 | 任意业务指标 |
| **cron** | 时间表达式 | 定时扩容（高峰期预热）|
| **http** | HTTP 请求速率 | 外部 API 调用 |
| **redis** | 队列长度 | Redis Stream/LPUSH |
| **rabbitmq** | 队列长度 | RabbitMQ 消费积压 |

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: kafka-consumer-scaler
spec:
  scaleTargetRef:
    name: kafka-consumer
  minReplicaCount: 0        # 可以缩到零！
  maxReplicaCount: 50
  triggers:
    - type: kafka
      metadata:
        bootstrapServers: kafka:9092
        consumerGroup: my-group
        topic: orders
        lagThreshold: "100"  # 积压超过 100 条时扩容
    - type: cron
      metadata:
        start: "0 8 * * *"    # 早 8 点扩容
        end: "0 20 * * *"     # 晚 8 点缩容
        desiredReplicas: "10"
```

> [!note] 缩到零（Scale to Zero）
> KEDA 独有能力：无事件时缩到 0 Pod，有事件时秒级拉起。HPA 最少 1 副本。

---

## 4. 节点级伸缩

| 工具 | 原理 | 特点 |
|------|------|------|
| **Cluster Autoscaler** | Pod 调度不下 → 加节点；节点空闲 → 删节点 | 经典，基于 ASG/MIG |
| **Karpenter** | 直接创建 EC2 实例（不走 ASG），按需选实例类型 | AWS 原生，更快更灵活 |

```
Pod Pending (资源不足)
  │
  ▼
Cluster Autoscaler / Karpenter
  │
  ▼
创建新节点 ←── 选择实例类型（按价格/可用区/GPU 等）
  │
  ▼
Pod 调度到新节点
```

---

## 5. 伸缩策略组合

| 组合 | 场景 |
|------|------|
| **HPA + Cluster Autoscaler** | 标准 Web 应用（Pod 级 + 节点级）|
| **HPA + KEDA** | 事件驱动（Kafka/消息队列消费者）|
| **VPA (Off) + HPA** | 先用 VPA 推荐值手动调，HPA 管弹性 |
| **KEDA (Scale to Zero)** | 低频服务/定时任务/边缘 |
| **Karpenter + HPA** | AWS 上的弹性最佳实践 |

---

## 6. 衔接

- K8s 工作负载：[[concepts/Kubernetes 工作负载与调度]]
- K8s 高可用：[[concepts/Kubernetes 高可用与自愈]]
- FinOps：[[concepts/FinOps 与云资源优化]]（伸缩与成本）
- Redis：[[concepts/Redis 缓存与数据结构]]（KEDA Redis Scaler）
- Kafka：[[concepts/Kafka 消息队列与流处理]]（KEDA Kafka Scaler）

---

## 参考链接

**库内双链**
- [[concepts/Kubernetes 工作负载与调度]] — Deployment/ReplicaSet 基础
- [[concepts/Kubernetes 高可用与自愈]] — PDB/健康检查
- [[concepts/FinOps 与云资源优化]] — 伸缩与成本优化
- [[concepts/Kafka 消息队列与流处理]] — KEDA Kafka Scaler
- [[concepts/Redis 缓存与数据结构]] — KEDA Redis Scaler

**外部资料**
- HPA 文档（kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale）
- VPA 文档（github.com/kubernetes/autoscaler/tree/master/vertical-pod-autoscaler）
- KEDA 文档（keda.sh）
- Karpenter 文档（karpenter.sh）
