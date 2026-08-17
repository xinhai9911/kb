---
title: FinOps 与云资源优化
category: concepts
tags: [finops, cost, optimization, kubernetes, autoscaling, spot, active]
created: 2026-08-17
updated: 2026-08-17
summary: >-
    FinOps 与云资源优化：FinOps 框架（Inform/Optimize/Operate）、K8s 资源 Requests/Limits 配置
    与 VPA 自动调优、HPA/KEDA 弹性伸缩成本模型、Spot/抢占式实例降本、Cluster Autoscaler 与
    Karpenter 节点级伸缩、云账单分析与告警、容器资源效率指标（CPU/Memory 利用率）。
    衔接 [[concepts/Kubernetes 工作负载与调度]]、[[concepts/Kubernetes 高可用与自愈]]、[[concepts/韧性设计]]。
base_confidence: 0.85
lifecycle: draft
sources: []
---

# FinOps 与云资源优化

> K8s 集群是云成本的大头：Pod Requests/Limits 配错 = 浪费 30-60% 云账单。
> FinOps 不只是「省钱」，是「花得明白」。见 [[synthesis/容器分布式技术全景综述]]。

---

## 1. FinOps 框架

FinOps = Finance + DevOps，三个阶段循环：

| 阶段 | 目标 | 关键动作 |
|------|------|----------|
| **Inform（可见）** | 知道钱花在哪 | 账单分拆（按团队/集群/命名空间）、成本仪表盘、预算告警 |
| **Optimize（优化）** | 减少浪费 | 资源调优、Spot 实例、预留实例/ Savings Plan |
| **Operate（运营）** | 持续治理 | 自动化策略、异常检测、成本文化 |

---

## 2. K8s 资源配置（最大浪费源）

### Requests vs Limits

```yaml
resources:
  requests:
    cpu: "500m"      # 调度依据：保证至少 0.5 核
    memory: "256Mi"  # 调度依据：保证至少 256MB
  limits:
    cpu: "1000m"     # 硬上限：超过被 throttle
    memory: "512Mi"  # 硬上限：超过被 OOMKill
```

**常见错误**：
| 错误 | 后果 |
|------|------|
| Requests 设太高 | Pod 占着资源不用，集群利用率低（钱浪费） |
| Limits 设太低 | 正常负载被 throttle/OOMKill |
| 不设 Requests | 调度器无依据，可能集中在少数节点 |

### VPA（Vertical Pod Autoscaler）自动调优

VPA 根据历史用量**自动调整** Requests/Limits：
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
    updateMode: "Auto"  # 自动重启 Pod 应用新配置
```

> [!warning] VPA 与 HPA 冲突
> VPA 调 CPU requests 会影响 HPA 的 CPU 指标计算。二选一或用 KEDA 基于外部指标。

---

## 3. 弹性伸缩与成本

| 工具 | 层级 | 作用 |
|------|------|------|
| **HPA** | Pod 级 | 根据 CPU/内存/自定义指标扩缩 Pod 副本数 |
| **KEDA** | Pod 级 | 基于外部指标（Kafka lag、Prometheus、Cron）触发伸缩，支持缩到 0 |
| **VPA** | Pod 级 | 调整单个 Pod 的 Requests/Limits |
| **Cluster Autoscaler** | 节点级 | Pod 调度不下时自动加节点，空闲时缩容 |
| **Karpenter** | 节点级 | AWS 原生，比 CA 更快（直接创建 EC2，不走 ASG） |

**成本公式**：
```
集群成本 ≈ Σ(节点数 × 实例单价) + 网络/存储附加
利用率 = 实际使用 / Requests 分配（目标 60-70%）
```

---

## 4. Spot / 抢占式实例（降本 60-90%）

Spot 实例是云厂商的闲置资源，价格是 On-Demand 的 10-40%，但可能被回收（2 分钟通知）。

**适用场景**：无状态工作负载、批处理、CI runner、开发测试。
**不适用**：有状态服务、单副本、对中断敏感的工作负载。

```yaml
# Karpenter Spot 节点池
apiVersion: karpenter.sh/v1alpha5
kind: Provisioner
spec:
  requirements:
    - key: karpenter.sh/capacity-type
      operator: In
      values: ["spot", "on-demand"]  # Spot 优先，不足时 On-Demand 兜底
```

---

## 5. 云账单分析

| 工具 | 说明 |
|------|------|
| **Kubecost** | K8s 原生成本监控，按 namespace/controller/Pod 分拆成本 |
| **OpenCost** | Kubecost 的开源核心，CNCF 项目 |
| **Cloud** | AWS Cost Explorer / GCP Billing / Azure Cost Management |
| **Kubectl-cost** | CLI 工具，快速查看 namespace 级成本 |

---

## 6. 衔接

- K8s 工作负载：[[concepts/Kubernetes 工作负载与调度]]（Requests/Limits/调度）
- 自动伸缩：[[concepts/Kubernetes 高可用与自愈]]（HPA/PDB）
- 韧性：[[concepts/韧性设计]]（限流/降级与资源节约的关系）
- 基础设施：[[concepts/基础设施即代码 Terraform]]（云资源编排）

---

## 参考链接

**库内双链**
- [[concepts/Kubernetes 工作负载与调度]] — 资源配置与调度
- [[concepts/Kubernetes 高可用与自愈]] — HPA/PDB/自动伸缩
- [[concepts/韧性设计]] — 限流降级与成本的关系
- [[concepts/基础设施即代码 Terraform]] — 云资源编排
- [[synthesis/容器分布式技术全景综述]] — 全景地图

**外部资料**
- FinOps Foundation（finops.org）
- Kubecost / OpenCost 文档
- Karpenter 文档（karpenter.sh）
- AWS Spot Instance Advisor
