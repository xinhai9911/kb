---
title: Kubernetes 核心架构与组件
category: concepts
tags: [kubernetes, architecture, apiserver, etcd, kubelet, control-plane, active]
created: 2026-08-12
updated: 2026-08-12
summary: >-
    Kubernetes 架构的核心组件与职责边界：控制面（API Server / etcd /
    Scheduler / Controller Manager）与数据面（kubelet / kube-proxy /
    容器运行时 / CNI）。API 对象模型（GVK / spec-status / 资源分类）、
    Namespace 隔离、kubectl 与 API Server 的完整请求链路。
base_confidence: 0.88
lifecycle: draft
---

# Kubernetes 核心架构与组件

> 先读 [[synthesis/Kubernetes 技术全景综述]] 建立全局，再深入组件职责。

## 1. 控制面（Control Plane）

控制面是集群的「大脑」，决定集群应该是什么样。组件本身也是进程，可以多副本部署实现 HA。

### 1.1 kube-apiserver（一切交互的唯一入口）

- 提供 REST API（`/api/v1`、`/apis/apps/v1` 等），是**所有组件之间通信的中枢**。
- 请求链路：**认证 → 授权 → 准入（Admission）→ 持久化到 etcd → 返回**。
- 无状态，可水平扩展；`etcd` 才是真相（集群强一致的核心）。
- 负责：watch（客户端订阅变更）、资源版本/乐观锁（`resourceVersion`）、CRD 注册、聚合 API。

### 1.2 etcd（集群的真相库）

- 分布式键值存储，基于 **Raft 共识**（对照 [[concepts/分布式系统基础]]）。
- 存所有对象：Pod/Deployment/ConfigMap/Secret（默认明文，需 KMS 加密）等。
- 只有 API Server 能读写 etcd，其他组件一律走 API。
- 性能/容量敏感：`defrag`、`--max-request-bytes`、备份恢复策略是生产必备。

### 1.3 kube-scheduler（给新 Pod 选节点）

- 只负责**调度决策**，不执行——执行权在 kubelet。
- 两阶段：**过滤（Filtering）** 去掉不满足条件的节点 → **打分（Scoring）** 选最优。
- 约束来源：资源请求/限制、亲和性、污点容忍、数据局部性（卷）、拓扑分布约束。
- 可替换：自定义调度器 + 调度框架（Scheduling Framework）插件化。

### 1.4 kube-controller-manager（内置控制器集合）

一个进程里运行了全部内置控制器，每个控制器各管一种资源：

| 控制器 | 职责 |
|--------|------|
| ReplicaSet | 维持期望副本数 |
| Deployment | 协调 RS 的创建/滚动/回滚 |
| StatefulSet / DaemonSet / Job | 对应工作负载 |
| Node / Pod GC | 清理故障节点与孤儿 Pod |
| EndpointSlice | 维护 Service 的后端端点 |
| ServiceAccount / Token | 自动创建 SA 与令牌 |
| Namespace / GarbageCollector | 生命周期与级联删除 |

### 1.5 cloud-controller-manager

对接云厂商：负载均衡（LoadBalancer 类型）、节点/路由管理、块存储（CSI）。本地/裸机集群可无此组件。

## 2. 数据面（工作节点 Worker Node）

节点上跑实际负载的进程。

### 2.1 kubelet（节点上的「小控制面」）

- 通过 API Server **watch** 分配到本节点的 Pod，负责 Pod 全生命周期。
- 调用 **CRI** 启动/停止容器；调用 **CNI** 配置 Pod 网络；挂载卷。
- 「容器」在内核里到底是什么（Namespace/Cgroups/OverlayFS、运行时栈 docker→containerd→runc）见 [[concepts/容器原理与运行时]]。
- 定期上报节点与 Pod 状态（heartbeat），执行 liveness/readiness/startup 探针。

### 2.2 kube-proxy（Service 转发规则的执行者）

- 监听 Service/EndpointSlice 变更，把规则写入 iptables / IPVS / eBPF。
- 注意：kube-proxy **不做服务发现，只做数据面的转发规则**（详见 [[concepts/Kubernetes 网络模型]]）。
- Cilium 可完全替代 kube-proxy（用 eBPF 实现，性能更高）。

### 2.3 容器运行时（CRI）

- K8s 通过 **CRI（Container Runtime Interface）** 与运行时解耦：containerd / CRI-O。
- Docker 的 dockershim 已在 1.24 移除；现在统一走 containerd 或 CRI-O。
- 运行时负责：拉镜像、创建/销毁容器、cgroups 资源隔离、执行探针与 exec。

### 2.4 CNI 插件

- 给每个 Pod 分配独立 IP 并打通网络（Calico / Cilium / Flannel）。
- 工作流程：kubelet 在创建 Pod 时调用 CNI，插件创建虚拟网卡、配 IP、建路由。

## 3. API 对象模型

### 3.1 GVK（Group / Version / Kind）

| 维度 | 含义 | 例子 |
|------|------|------|
| Group | 资源归属的 API 组 | 核心组 `""` / `apps` / `batch` / `networking.k8s.io` |
| Version | 演进版本 | `v1` / `apps/v1` / `v1beta1` |
| Kind | 对象类型 | Pod / Deployment / Service |

### 3.2 通用字段结构

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web                # 对象名（同命名空间内唯一）
  namespace: prod          # 归属命名空间
  labels:                  # 选择器用的标签
    app: web
  annotations:             # 非标识性元数据（给工具读）
    description: "x"
spec:                      # 期望状态（用户声明）
  replicas: 3
status:                    # 实际状态（控制器写入）
  readyReplicas: 3
```

### 3.3 三类字段的角色

- **spec**：期望状态，由用户声明。
- **status**：实际状态，由控制器对账后写入。用户/外部一般只读。
- **metadata**：身份（name/namespace）、分组（labels/annotations）、变更管理（`resourceVersion`、`generation`、`finalizers`、`ownerReferences`）。

### 3.4 资源分类

- **Namespaced**：Pod/Deployment/Service/ConfigMap…（归属某命名空间）
- **Cluster-scoped**：Node、Namespace、ClusterRole、PV（集群级资源）
- **List 类**：PodList 等，Watch 用。
- **子资源**：`/pods/{name}/exec`、`/status`、`/scale`——不是独立对象，是端点。

## 4. Namespace（逻辑隔离）

- 划分资源空间：同名资源可在不同 Namespace 共存。
- 默认四类：`default`、`kube-system`（系统组件）、`kube-public`（公共只读）、`kube-node-lease`（节点心跳）。
- 配额：`ResourceQuota` 限制总用量，`LimitRange` 限制单对象范围。
- ⚠️ Namespace 是**逻辑**隔离，不是安全隔离——跨 Namespace 的访问控制要靠 RBAC + NetworkPolicy。

## 5. 一次完整的请求链路（kubectl → Pod 运行）

```
kubectl apply -f deploy.yaml
  │  (1) 认证：kubeconfig 里的证书/token
  ▼
kube-apiserver
  │  (2) 授权：RBAC 检查是否有权限
  │  (3) 准入：MutatingWebhook（默认值注入）→ ValidatingWebhook（校验）
  │  (4) 持久化：写入 etcd
  ▼
kube-controller-manager
  │  (5) Deployment 控制器 → 创建 ReplicaSet
  │  (6) ReplicaSet 控制器 → 创建 Pod（spec 不含 nodeName）
  ▼
kube-scheduler
  │  (7) 过滤+打分 → 选出节点 → 把 nodeName 写回 Pod
  ▼
kubelet（目标节点）
  │  (8) watch 到新 Pod → 调 CRI 启动容器 → 调 CNI 配网络 → 挂卷
  │  (9) 定期上报 status，执行探针
  ▼
Pod 进入 Running/Ready
```

## 6. 关键设计结论

- **职责单一、松耦合**：每个组件只做一件事，靠 API + watch 通信，组件可独立替换。
- **API Server 是唯一上帝**：其他组件不直接连 etcd，不直接通信，全走 API。
- **控制器做闭环**：声明式 + 对账循环保证自愈（详见 [[concepts/Kubernetes 声明式模型与控制器]]）。
- **节点只执行、不决策**：调度和状态判定都在控制面，节点故障不影响控制面运行。

## 来源

- [[sources/Kubernetes 学习来源]]

## 相关文档

- [[concepts/Kubernetes 声明式模型与控制器]]
- [[concepts/Kubernetes 工作负载与调度]]
- [[concepts/Kubernetes 网络模型]]
- [[entities/Kubernetes 部署与工具链实战]]
- [[entities/kubectl 与日常运维实战]]
