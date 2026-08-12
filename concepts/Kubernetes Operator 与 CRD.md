---
title: Kubernetes Operator 与 CRD
category: concepts
tags: [kubernetes, operator, crd, controller, webhook, custom-resource, active]
created: 2026-08-12
updated: 2026-08-12
summary: >-
    Kubernetes 扩展机制：CRD（自定义资源定义）与聚合 API、
    Operator 模式（把运维知识程序化）、controller-runtime / kubebuilder
    开发栈、控制循环与 Webhook（变更/校验）、Operator 成熟度模型
    （Capability Levels）、生态示例（etcd/Prometheus/ArgoCD）、
    何时该写 Operator 与常见反模式。
base_confidence: 0.87
lifecycle: draft
---

# Kubernetes Operator 与 CRD

> **Operator = CRD（声明新资源） + Controller（自动对账）**。
> 它把「DBA / SRE 的人工运维手册」编译成程序：申请、扩容、备份、升级、故障自愈全自动。

## 1. CRD（Custom Resource Definition）

- 在 K8s API 里**定义一种新对象类型**，行为如同内置资源：支持 `kubectl get`、RBAC、审计、Webhook。

```yaml
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: mongodbs.example.com        # 必须 <plural>.<group>
spec:
  group: example.com
  scope: Namespaced                 # Namespaced / Cluster
  names:
    plural: mongodbs
    singular: mongodb
    kind: MongoDB
    shortNames: [mg]
  versions:
  - name: v1
    served: true
    storage: true
    schema:
      openAPIV3Schema:
        type: object
        properties:
          spec:
            type: object
            properties:
              version: {type: string}
              replicas: {type: integer}
```

- CRD 对象存 etcd，schema 用 **OpenAPI v3** 描述，实现**结构校验**（不符合 schema 直接拒绝）。
- 相比**聚合 API**（把外部服务挂到 API Server）：CRD 简单、无需自建服务，适合多数场景；聚合 API 适合复杂子资源与性能要求。

## 2. Operator 模式

### 2.1 为什么需要 Operator

- 无状态应用（Deployment 就能管）；**有状态应用**（数据库/消息队列）需要「懂业务的控制器」：
  - 部署主从、选举、分片
  - 扩容/缩容（重建数据副本）
  - 备份/恢复、升级/回滚（带停机窗口管理）
  - 故障检测与自愈（脑裂处理）
- 例子：etcd-operator、prometheus-operator、mysql/redis-operator、ArgoCD、Kong。

### 2.2 一个 CR + 一个 Controller

```
用户写：
  apiVersion: example.com/v1
  kind: MongoDB
  spec: {version: "5.0", replicas: 3}
        │
        ▼
Operator 的 Controller（watch MongoDB 资源）
  ├─ 创建对应的 StatefulSet / PVC / ConfigMap / Service
  ├─ 实时对账：期望 replicas vs 实际 → 扩缩容
  ├─ 处理版本升级：滚动 + 备份 + 切换
  ├─ 状态回写：status.readyMembers、status.phase
  └─ 处理删除：清理资源（finalizer）
```

- 用户的「运维意图」变成「资源对象」，Operator 保证系统持续向该意图收敛。

## 3. 开发栈（生产标准）

| 组件 | 作用 |
|------|------|
| **client-go** | 与 API Server 通信 |
| **controller-runtime** | 控制器框架：Manager / Reconcile / Cache / Client |
| **kubebuilder / Operator SDK** | 脚手架：生成 CRD、Controller、Webhook 骨架 |
| **webhook** | 校验（Validating）与变更（Mutating）请求 |
| **finalizer** | 清理外部资源（删除前钩子） |

典型目录：

```
project/
├─ api/v1/            # CRD 类型定义（Go struct）
│   ├─ mongodb_types.go
│   └─ groupversion_info.go
├─ controllers/       # 控制器
│   └─ mongodb_controller.go   # Reconcile 主逻辑
├─ internal/          # 业务封装（建 STS、备份、升级）
├─ config/crd/        # 生成的 CRD manifest
└─ main.go
```

核心接口（controller-runtime）：

```go
func (r *MongoDBReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
    // 1. 取 CR
    // 2. 对账：比较期望（spec）与实际（Status）
    // 3. 有差异 → 创建/更新/删除下属资源
    // 4. 回写 status
    // 5. 设置 finalizer / ownerReferences
    return ctrl.Result{RequeueAfter: 30 * time.Second}, nil  // 周期再对账
}
```

## 4. Webhook（准入）

- **MutatingWebhook**：在对象写入前**修改**（注入默认值、加 label、注入 sidecar）。
- **ValidatingWebhook**：在对象写入前**校验**（业务规则，如「副本数必须为奇数」）。
- 触发时机在认证/授权之后、持久化之前（见 [[concepts/Kubernetes 安全模型]] §7）。
- 开发注意：webhook 证书管理（通常用 cert-manager）、幂等（重复注入不重复）。

## 5. Operator 成熟度模型（Capability Levels）

| Level | 名称 | 能力 |
|-------|------|------|
| L1 | Basic Install | 安装 |
| L2 | Seamless Upgrades | 平滑升级补丁 |
| L3 | Full Lifecycle | 生命周期（备份/恢复/存储） |
| L4 | Deep Insights | 指标/日志/分析集成 |
| L5 | Auto Pilot | 自动化扩缩容、异常自愈、调优 |

- 大多数生产 Operator 目标在 **L3**；L5 很少（需要强领域数据）。

## 6. 反模式与何时不该写 Operator

- ❌ 无状态应用写 Operator —— Deployment + ConfigMap 就够，Operator 是过度设计。
- ❌ 复制已有成熟 Operator 的功能（数据库选型前先查有无现成 Operator）。
- ❌ Operator 里硬编码业务逻辑、不复用内置资源（应组合 Deployment/STS/PVC）。
- ⚠️ 必须处理：升级兼容（CRD 多版本转换）、finalizer 清理、leader election（高可用部署时多副本只有一个干活）、被删除时不留孤儿资源。

## 7. 生态实例

| Operator | 管理对象 |
|----------|---------|
| Prometheus Operator | Prometheus/Alertmanager 实例与监控目标 |
| ArgoCD Operator | 应用与 GitOps 仓库 |
| etcd / ZooKeeper / Kafka Operator | 对应分布式系统集群 |
| Cloud 厂商 Operator | 云数据库/存储实例（AWS RDS、Terraform Operator） |
| Nginx Ingress Controller | 用 CRD 表达更复杂的路由 |

## 8. 学习路径

1. 手写一个 CRD + 简单 controller（kubebuilder scaffold，`make run`）。
2. 加 status 回写与 finalizer。
3. 加 Validating/Mutating webhook。
4. 模拟一个「数据库 Operator」：CR 管理 StatefulSet + 备份 Job。
5. 理解 OLM / Helm（打包分发，[[entities/Helm 包管理实战]]）。

## 来源

- [[sources/Kubernetes 学习来源]]

## 相关文档

- [[concepts/Kubernetes 声明式模型与控制器]]
- [[concepts/Kubernetes 核心架构与组件]]
- [[entities/Helm 包管理实战]]
- [[concepts/分布式系统基础]]
