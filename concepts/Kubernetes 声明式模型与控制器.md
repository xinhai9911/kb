---
title: Kubernetes 声明式模型与控制器
category: concepts
tags: [kubernetes, declarative, controller, reconcile, finalizer, active]
created: 2026-08-12
updated: 2026-08-12
summary: >-
    Kubernetes 的核心思想：声明式 API 与 Reconcile 控制循环。
    spec/status 对账、控制器模式、client-go informer/watch、
    版本与乐观锁、finalizer、ownerReferences 与级联删除、
    apply 与 server-side apply、水平扩展的 event-driven 与 level-driven。
base_confidence: 0.88
lifecycle: draft
---

# Kubernetes 声明式模型与控制器

> K8s 与 Docker 编排（compose）最本质的区别：**Docker 描述步骤（怎么做），K8s 描述状态（要什么）。**
> 这是理解一切控制器行为的前提。

## 1. 声明式 vs 命令式

| | 命令式（Imperative） | 声明式（Declarative） |
|---|---|---|
| 用户提交 | 操作序列：`run`、`scale`、`delete` | 期望状态：`spec` |
| 谁负责执行 | 用户/脚本逐步调 API | 控制器持续对账 |
| 网络抖动重试 | 用户自己处理 | 控制器天然重试 |
| 漂移处理 | 不处理 | 自动收敛回期望状态 |

- `kubectl run` 是命令式；`kubectl apply -f` 是声明式。
- K8s 官方推荐**尽量用声明式**（apply / Helm / GitOps），因为它可回放、可审计、可自愈。

## 2. 控制循环（Reconcile Loop）

控制器的工作不是「创建完就结束」，而是**永远在跑**：

```
期望状态 (spec)   ──────┐
                        ├──▶ 控制器比较 ──▶ 有差异 ──▶ 执行变更使现状趋近期望
实际状态 (status) ──────┘        │
                                └── 无差异 ──▶ 什么都不做（等待下次事件）
```

- **Level-driven vs Edge-driven**：K8s 是 level-driven——只看「当前层级」与「期望层级」的差值，不管中间经过哪些边沿事件。所以控制器天然抗丢事件、抗重复事件（reconcile 一遍即可）。
- 控制器**幂等**：重复执行效果相同，这才能安全重试。

### 2.1 一个简化版 Reconcile（伪代码）

```
func Reconcile(pod) {
  rs := rsController.getReplicaSetFor(pod)
  current := countPodsMatching(rs.selector)
  if current < rs.spec.replicas {
      createPod(rs.template)        // 少了就补
  } else if current > rs.spec.replicas {
      deletePod(excessPod)           // 多了就删
  }
  // 还有：Pod 版本不符就滚动；Pod 病态就重建……
}
```

## 3. 控制器模式的完整组成

| 组件 | 作用 |
|------|------|
| **client-go** | 官方客户端库，负责与 API Server 通信 |
| **Informer** | 本地缓存 + watch：订阅资源变更，减少 API 压力 |
| **WorkQueue** | 去重/限速队列，把事件变成待处理任务 |
| **Reconciler** | 核心业务逻辑：比较 spec/status，执行变更 |
| **EventRecorder** | 把操作结果写入 Event 对象（`kubectl describe` 可见） |

### 3.1 Informer 的机制

- 首次 **List** 全量缓存，之后 **Watch** 增量。
- 客户端发起了 `watch` 就订阅了变更流，本地维护一份「镜像」。
- **Resync**（周期重列）兜底：即使漏了 watch 事件，也会周期性全量对账。
- 好处：控制器读本地缓存，不把 etcd 打爆；对账天然幂等。

## 4. 版本与并发控制

### 4.1 resourceVersion（乐观锁）

- 每个对象有个 `resourceVersion`，每次写都递增。
- 并发写冲突：A 读到 v1，B 也读到 v1，A 写成功（v2），B 再写报 **409 Conflict**——B 必须重读再改（乐观并发控制）。
- 防止「last-write-wins」静默覆盖。

### 4.2 apply 与 Server-Side Apply（SSA）

- **kubectl apply**：计算「目标清单 vs 集群现状」的补丁（三路合并），只改动有差异的字段。
- **SSA**（1.16+）：把「声明」本身记录在对象上（`managedFields`），多客户端（比如团队+GitOps）可以声明同一对象的不同字段而不互相覆盖——解决了「客户端 A 删掉客户端 B 的字段」问题。
- GitOps（ArgoCD）现在都基于 SSA 或 server-side diff。

## 5. finalizer（终结器）

**用途**：在删除对象前，给外部系统（存储、DNS、云资源）一个清理机会。

```
Deployment 删除请求
  │  (1) 检查 metadata.finalizers（如 "kubernetes.io/pvc-protection"）
  │  (2) 有 finalizer → 对象标记 DeletionTimestamp，但【不真正删除】
  │  (3) 控制器看到删除标记，执行清理逻辑（卸载卷/删外部资源）
  │  (4) 清理完成后，控制器移除自己的 finalizer
  ▼
  (5) 没有 finalizer 了 → 对象被真正删除
```

- 常见坑：**对象卡在 Terminating** = finalizer 没有控制器去移除，通常因为控制器没装/崩了。
- 手动强制删除（`--force --grace-period=0`）会**跳过 finalizer**，可能导致云资源残留。

## 6. ownerReferences 与级联删除

- **ownerReferences** 标记对象的父对象：RS → Deployment，Pod → RS，PVC → StatefulSet。
- 级联删除：删父对象时，垃圾回收器（GC）按 ownerReferences 级联删子对象。
- **级联（Cascade）**：前台（先删子再父）/ 后台（先父后子，默认）/ **孤儿（Orphan）**：只删父，子变孤儿。
- 这也是「删了 Deployment 但 Pod 还在」或「Pod 被重建」现象背后的机制。

## 7. 三种变更手段对比

| 手段 | 方式 | 使用场景 |
|------|------|---------|
| `kubectl create` | 直接 POST 新建 | 一次性创建 |
| `kubectl replace` | 整体替换 | 全量更新（少用） |
| `kubectl apply` / `patch` | 局部三路合并 | 日常声明式变更（推荐） |

## 8. 常见误区

- ❌ 「控制器只在事件发生时运行」—— informer 只是触发，reconcile 是持续的对账闭环，还有 resync。
- ❌ 「Pod 卡 Terminating 就删不掉」—— 先查 finalizer 归属，通常是控制器没清理。
- ❌ 「apply 会覆盖别人的字段」—— 普通 apply 会；SSA 用 managedFields 避免覆盖，多团队协作必须用 SSA。

## 来源

- [[sources/Kubernetes 学习来源]]

## 相关文档

- [[concepts/Kubernetes 核心架构与组件]]
- [[concepts/Kubernetes Operator 与 CRD]]
- [[entities/Helm 包管理实战]]
- [[concepts/分布式系统基础]]
