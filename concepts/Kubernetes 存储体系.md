---
title: Kubernetes 存储体系
category: concepts
tags: [kubernetes, storage, pv, pvc, storageclass, csi, stateful, active]
created: 2026-08-12
updated: 2026-08-12
summary: >-
    Kubernetes 存储抽象：卷类型与生命周期、PV/PVC/StorageClass
    三层抽象（绑定/动态供给/回收策略）、CSI 插件机制、
    本地存储与临时卷、有状态应用的存储模式（StatefulSet + PVC）、
    数据备份与快照（VolumeSnapshot）、存储性能与选型。
base_confidence: 0.87
lifecycle: draft
---

# Kubernetes 存储体系

> 核心问题：**Pod 是临时的（会重建），数据不能跟着 Pod 死**。存储抽象把「持久化的数据」从「易变的 Pod」中解耦出来。

## 1. 存储抽象的分层

| 抽象 | 角色 | 类比 |
|------|------|------|
| **Volume** | Pod 内挂载的目录（生命周期随 Pod） | 「移动硬盘接口」 |
| **PV**（PersistentVolume） | 集群级存储资源（独立于 Pod 存在） | 「一块已买好的硬盘」 |
| **PVC**（PersistentVolumeClaim） | 用户对存储的「请求」（声明需求） | 「我要一块 10G 的盘」 |
| **StorageClass** | 动态供给的「模板」（按需创建 PV） | 「硬盘经销商」 |

## 2. 卷类型（Volume）

### 2.1 临时卷（生命周期 = Pod）

- `emptyDir`：Pod 运行时共享目录（同 Pod 多容器通信、缓存），Pod 删除即清空。
- `configMap` / `secret` / `downwardAPI`：把配置挂成文件，更新后（约分钟级）自动同步。

### 2.2 持久卷（生命周期 > Pod）

- `hostPath`：挂宿主机目录（仅单节点测试，不建议生产）。
- `local`：本地磁盘（绑定到节点，需配合调度约束）。
- 云存储 / NFS / Ceph / GlusterFS：通过 CSI 接入（见 §5）。

## 3. PV / PVC / StorageClass 核心机制

### 3.1 绑定（Binding）

```
PVC 声明：storageClassName: standard, 10Gi, ReadWriteOnce
  │
  ├─ 匹配现有 PV（容量 ≥10Gi、访问模式匹配、storageClass 匹配）
  │     → 绑定（一对一，PVC 与 PV 从此唯一对应）
  │
  └─ 无匹配且指定了 StorageClass → 触发【动态供给】→ 自动创建 PV → 绑定
```

- PVC 与 PV 是**一对一绑定**；绑定后该 PV 不再给别人用。
- 访问模式：`ReadWriteOnce`（单节点读写，块存储默认）、`ReadOnlyMany`、`ReadWriteMany`（共享，NFS/CephFS）、`ReadWriteOncePod`（1.22+，单 Pod）。

### 3.2 动态供给（Dynamic Provisioning）

- **StorageClass** 声明了「用什么后端、什么参数」去自动创建 PV。

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: fast
provisioner: kubernetes.io/aws-ebs   # 或 ebs.csi.aws.com / csi-hostpath / nfs…
parameters:
  type: gp3
  fsType: ext4
reclaimPolicy: Delete                  # Delete / Retain
volumeBindingMode: Immediate          # Immediate / WaitForFirstConsumer
```

- `reclaimPolicy`：PVC 删除后，PV 怎么处理——`Delete`（连后端一起删，云盘默认）/ `Retain`（保留 PV 与数据，需人工处理）。
- `volumeBindingMode`：`Immediate`（立即分配）/ `WaitForFirstConsumer`（等 Pod 调度后分配，**本地卷/跨区卷必用**，避免调度与存储冲突）。

## 4. 生命周期流程

```
用户写 PVC
  │
  ├─ 动态供给：StorageClass → 控制器调 CSI → 创建后端卷 → 建 PV
  │
  ├─ 绑定：PVC 绑定到 PV
  │
  ├─ Pod 引用 PVC → kubelet 调 CSI 挂载到节点 → 挂进容器目录
  │
  ├─ 使用期：应用读写
  │
  └─ 删除：Pod 删（卷卸载）→ PVC 删 → 按 reclaimPolicy 处理 PV（Delete/Retain）
```

## 5. CSI（Container Storage Interface）

- **CSI 是存储厂商接入 K8s 的标准接口**：任何存储实现 CSI 插件即可被 K8s 使用。
- 组件：
  - **CSI Controller**（Deployment）：负责创建/删除卷、快照。
  - **CSI Node**（DaemonSet）：负责把卷挂载到节点。
  - **VolumeSnapshot / VolumeGroupSnapshot**（1.20+）：快照与组快照，备份的底层能力。

| CSI 实现 | 后端 |
|---------|------|
| 云厂商 CSI（aws-ebs / azure-disk / gce-pd） | 云块存储 |
| `csi-hostpath`（测试） | 宿主机目录 |
| NFS / Ceph RBD+CephFS / GlusterFS | 共享存储 |
| 本地卷 CSI（local） | 本地 SSD |

## 6. 有状态应用的存储模式

### 6.1 StatefulSet + PVC（volumeClaimTemplates）

```yaml
apiVersion: apps/v1
kind: StatefulSet
spec:
  volumeClaimTemplates:        # 每个副本自动生成一个 PVC
  - metadata: {name: data}
    spec:
      accessModes: [ReadWriteOnce]
      storageClassName: fast
      resources: {requests: {storage: 10Gi}}
```

- 每个 Pod 绑定**独立 PVC**：`data-<statefulset>-0`、`data-<statefulset>-1`…
- 删除 StatefulSet **不会自动删 PVC**（`persistentVolumeClaimRetentionPolicy` 1.23+ 可配置）——因为数据可能还要用。
- 主从/分片拓扑：每副本一个卷，配合 Operator 管理（[[concepts/Kubernetes Operator 与 CRD]]）。

### 6.2 常见问题

- 挂到错误节点：本地卷必须 `volumeBindingMode: WaitForFirstConsumer` + 节点亲和，否则调度与存储打架。
- 误删 PVC → 数据没了（`Delete` 策略）；生产数据库建议 `Retain` + 独立备份。

## 7. 快照与备份

- **VolumeSnapshot**：对卷打一致性快照（需 CSI 支持），是数据库备份/恢复的基础。
- **VolumeSnapshotClass**：快照的 StorageClass（指定快照后端）。
- 常用工具：Velero（K8s 级备份，含 etcd 与对象）；数据库级备份由各自 Operator 处理。

## 8. 选型建议

| 场景 | 推荐 |
|------|------|
| 无状态服务 | 不用持久卷，用 emptyDir 即可 |
| 缓存（Redis） | 云块盘 / 本地 SSD（local + WaitForFirstConsumer） |
| 数据库（高可用） | 云盘 Retain + 快照 + Operator 自动化 |
| 共享只读 / 共享读写 | NFS / CephFS（ReadWriteMany） |
| 开发测试 | csi-hostpath / local / minikube 默认 storageclass |

## 9. 常见误区

- ❌ 「PVC 绑定一个 PV 后还能换」—— 一对一锁定，删除重建才可能换。
- ❌ 「StorageClass 的 Delete 策略安全」—— PVC 一删，PV 和后端卷全没了。
- ❌ 「local 卷可以随便调度」—— 本地卷绑定节点，必须用 WaitForFirstConsumer + 亲和，节点挂了数据在该节点。

## 来源

- [[sources/Kubernetes 学习来源]]

## 相关文档

- [[concepts/Kubernetes 工作负载与调度]]
- [[concepts/Kubernetes 高可用与自愈]]
- [[concepts/Kubernetes Operator 与 CRD]]
- [[entities/kubectl 与日常运维实战]]
