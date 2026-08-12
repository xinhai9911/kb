---
title: Kubernetes 工作负载与调度
category: concepts
tags: [kubernetes, workload, pod, deployment, scheduler, affinity, taint, active]
created: 2026-08-12
updated: 2026-08-12
summary: >-
    工作负载（Pod/Deployment/StatefulSet/DaemonSet/Job/CronJob）的
    语义与选型、Pod 生命周期（phase/restartPolicy/初始化/钩子）、
    资源管理与 QoS 等级、调度流程（过滤/打分）、亲和性反亲和、
    污点容忍、拓扑分布约束、节点管理。
base_confidence: 0.88
lifecycle: draft
---

# Kubernetes 工作负载与调度

> 工作负载对象定义了「要跑什么、跑几个、怎么更新」。调度器决定了「跑在哪」。

## 1. Pod：最小调度单元

- Pod 是 K8s **调度的最小单元**，一个 Pod 内可多个容器**共享网络命名空间与存储卷**。
- Pod 内两个特殊容器角色：
  - **pause / sandbox 容器**：占位，先创建，建立共享网络命名空间。
  - **Sidecar / init 容器**：init 先于主容器串行执行（如等 DB、拉配置），sidecar 常驻并行（如日志收集、代理）。
- 理解：**调度单元 = Pod，不是容器**。多容器 Pod 要么同节点共生死，要么都不存在。

### 1.1 Pod 生命周期（phase）

```
Pending → Running → Succeeded / Failed
              └──→ CrashLoopBackOff / Evicted / Unknown...
```

- `phase` 是大阶段；`containerStatuses`、`conditions`（PodReady、ContainersReady、PodScheduled、Initialized）给出细节。
- **restartPolicy**：`Always`（Deployment 默认）/ `OnFailure`（Job）/ `Never`。
- **probes 探针**：详见 [[concepts/Kubernetes 高可用与自愈]]。

## 2. 工作负载控制器选型

| 控制器 | 语义 | 适用场景 |
|--------|------|---------|
| **Deployment** | 无状态，滚动更新，副本可任意替换 | Web/API 服务、微服务 |
| **StatefulSet** | 有状态：稳定网络标识 + 稳定存储 + 顺序部署/缩容 | 数据库、Redis、ZooKeeper、消息队列 |
| **DaemonSet** | 每个节点跑一个 | 日志采集（Fluentd）、节点监控（node-exporter）、CNI/代理 |
| **Job** | 一次性任务，成功即完成 | 批处理、迁移脚本 |
| **CronJob** | 定时任务（cron 表达式） | 定期备份、清理 |

### 2.1 Deployment 的组成与滚动

```
Deployment → 管理 ReplicaSet → 管理 Pod
```

- 滚动更新策略：`maxUnavailable`（允许同时不可用的副本数，默认 25%）、`maxSurge`（允许超出期望数的临时副本，默认 25%）。
- 更新时创建新 RS 并逐步伸缩；**回滚** = 切回旧 RS（`kubectl rollout undo`）。
- 无状态判断：**数据可重建、副本可互换** → 用 Deployment。

### 2.2 StatefulSet 的关键点

- 稳定网络标识：`{statefulset}-{0..n}` 顺序命名；headless Service 提供稳定 DNS。
- 稳定存储：每个副本绑定独立 PVC（`volumeClaimTemplates`）。
- 顺序保证：滚动更新按序（0→n）；缩容时先删尾（n→0）。
- 有状态难点：主从选举、数据备份、故障恢复——常交给 Operator（[[concepts/Kubernetes Operator 与 CRD]]）。

### 2.3 DaemonSet / Job / CronJob

- **DaemonSet**：默认每节点一个；更新用 `maxUnavailable` / `minReadySeconds`；适合平台类守护进程。
- **Job**：`completions`（总完成数）、`parallelism`（并发）、`backoffLimit`（重试上限）。失败会新建 Pod 重试。
- **CronJob**：`schedule` 用标准 cron；`concurrencyPolicy`（Allow/Forbid/Replace）、`startingDeadlineSeconds`。

## 3. 资源管理与 QoS

### 3.1 requests / limits

| 字段 | 含义 | 作用 |
|------|------|------|
| `resources.requests` | 最小保证 | 调度依据（节点可分配量 - 已请求） |
| `resources.limits` | 上限 | CPU 节流、内存 OOM 杀 |

- **CPU**：可压缩资源，超限节流（throttle），单位 m（millicore，1 核 = 1000m）。
- **内存**：不可压缩资源，超限触发 OOMKilled（kubelet 依据 QoS 等级杀）。
- ⚠️ 内存只设 limit 不设 request 时，K8s 默认 request = limit（导致调度过量）。

### 3.2 QoS 等级（OOM 优先级）

| QoS | 判定 | OOM 优先级 |
|-----|------|-----------|
| **Guaranteed** | 全部容器 request == limit | 最低（最不易被杀） |
| **Burstable** | 部分容器有 request/limit 且不等 | 中 |
| **BestEffort** | 无任何 request/limit | 最高（最易被杀） |

> 核心业务（DB 等）应设为 Guaranteed；临时任务可 BestEffort。

### 3.3 LimitRange 与 ResourceQuota

- **LimitRange**：限制单个对象的最小/最大 request 与 limit（防止某容器吃光节点）。
- **ResourceQuota**：限制整个 Namespace 的总资源与对象数量。

## 4. 调度流程

```
新 Pod（无 nodeName）
  │
  ├─ 过滤阶段 Filtering（预选）
  │   ├─ 资源足够（request ≤ 可分配）
  │   ├─ 节点未 NotReady/未污点不容忍
  │   ├─ 端口不冲突、hostPort 唯一
  │   ├─ 卷可用（PVC 可挂载到该节点）
  │   └─ 亲和性/反亲和性满足
  │
  ├─ 打分阶段 Scoring（优选）
  │   ├─ 资源平衡（least-requested / 装箱 balanced）
  │   ├─ 拓扑分布（跨区 spread）
  │   ├─ 亲和性偏好（preferredDuringScheduling）
  │   └─ 数据局部性（卷在节点上）
  │
  └─ 选中 → 写回 nodeName → kubelet 拉起
```

- **绑定失败处理**：调度器会 retry；节点没就绪则 Pod 一直 Pending。
- 调度框架（Scheduling Framework）可插件化扩展：自定义 filter/score/queueSort。

## 5. 节点选择三件套

### 5.1 nodeSelector / nodeName

- `nodeSelector`：按 label 匹配（`disktype: ssd`），简单但能力有限。
- `nodeName`：直接指定节点（绕过调度器，一般不直接用）。

### 5.2 亲和性（affinity / anti-affinity）

| 字段 | 语义 |
|------|------|
| `nodeAffinity.requiredDuringScheduling` | 硬性：节点必须满足 label |
| `nodeAffinity.preferredDuringScheduling` | 软性：尽量满足，按权重打分 |
| `podAffinity` | 与「哪些 Pod」同节点/同域 |
| `podAntiAffinity` | 与「哪些 Pod」**不同**节点/域 |

- 典型用法：副本跨可用区（`topologyKey: topology.kubernetes.io/zone`）；主从不同节点。

### 5.3 污点与容忍（Taints & Tolerations）

- **Taint（污点）** 打在节点上：`key=value:effect`，effect 三类：
  - `NoSchedule`：不调度新 Pod（已存在的不驱逐）
  - `PreferNoSchedule`：尽量不调度
  - `NoExecute`：不调度且驱逐已有 Pod
- **Toleration（容忍）** 打在 Pod 上：容忍某个污点，才允许被调度到该节点。
- 内置污点：`node.kubernetes.io/not-ready`、`node.kubernetes.io/unreachable`、`node.kubernetes.io/disk-pressure` 等，控制器自动打。

### 5.4 topologySpreadConstraints（拓扑分布约束）

- 强制/偏好把 Pod 均匀打散到 zone、region、节点，避免全部挤一个可用区。
- 是「高可用部署」的官方手段（配合 podAntiAffinity）。

## 6. 节点管理与驱逐

- 节点状态：Ready / NotReady / Unknown（由节点心跳与 lease 判定）。
- **污点驱逐**：节点异常时控制器打 `NoExecute` 污点，Pod 超过 `tolerationSeconds` 被驱逐。
- **资源压力驱逐**：磁盘/内存不足时 kubelet 按 QoS 等级优先杀低等级 Pod。
- 排空节点：`kubectl drain`（先驱逐再排空）；`uncordon` 恢复调度。

## 7. 常见误区

- ❌ 「Pod 挂一个容器，Pod 就代表那个进程」—— Pod 是单元，里面可以有 init/sidecar。
- ❌ 「Deployment 适合一切」—— 有状态服务用 StatefulSet；每节点一个的用 DaemonSet。
- ❌ 「设了 limit 就安全」—— 内存超限照样 OOMKilled；要 Guaranteed 才最稳。
- ❌ 「污点=节点不能跑」—— 是「除非有容忍，否则不调度」，容忍可放行。

## 来源

- [[sources/Kubernetes 学习来源]]

## 相关文档

- [[concepts/Kubernetes 声明式模型与控制器]]
- [[concepts/Kubernetes 高可用与自愈]]
- [[concepts/Kubernetes 存储体系]]
- [[entities/kubectl 与日常运维实战]]
