---
title: 分布式存储 Rook/Ceph/Longhorn
category: concepts
tags: [rook, ceph, longhorn, storage, csi, distributed, kubernetes, active]
created: 2026-08-17
updated: 2026-08-17
summary: >-
    分布式存储 Rook/Ceph/Longhorn：为什么 K8s 需要分布式存储（本地卷不跨节点）、
    Rook Operator 部署 Ceph（RBD 块存储/CephFS 文件存储/Object Gateway）、Longhorn 轻量
    分布式块存储（Replicated Volume）、OpenEBS、选型对比、性能与运维考量。
    衔接 [[concepts/Kubernetes 存储体系]]、[[concepts/Kubernetes Operator 与 CRD]]、[[concepts/分布式系统基础]]。
base_confidence: 0.85
lifecycle: draft
sources: []
---

# 分布式存储 Rook/Ceph/Longhorn

> K8s 的 PV/PVC 只是抽象，底层存什么需要 CSI 实现。本地卷（hostPath/local）挂了数据就丢，
> 分布式存储解决「数据跨节点复制」问题。见 [[concepts/Kubernetes 存储体系]]。

---

## 1. 为什么需要分布式存储

| 本地存储 | 分布式存储 |
|----------|------------|
| 数据在单节点，节点挂了数据丢 | 数据多副本跨节点，节点挂了不丢 |
| 无法跨节点共享 | 多 Pod 可同时读写（RWX） |
| 扩容需手动迁移 | 自动扩缩容 |

**典型场景**：数据库（MySQL/PG）、有状态应用（Kafka/Redis）、日志存储。

---

## 2. Rook + Ceph（重量级方案）

Rook 是 K8s Operator（[[concepts/Kubernetes Operator 与 CRD]]），自动化部署和管理 Ceph 集群：

```
┌─────────────────────────────────────────┐
│  K8s Cluster                            │
│  ┌─────────────────────────────────┐    │
│  │  Rook Operator                  │    │
│  │  ├── CephCluster CRD           │    │
│  │  ├── CephBlockPool CRD         │    │
│  │  └── CephFilesystem CRD        │    │
│  └─────────────────────────────────┘    │
│           │ 管理                         │
│  ┌─────────────────────────────────┐    │
│  │  Ceph Cluster (3+ OSD 节点)     │    │
│  │  ├── RBD (块存储)              │    │
│  │  ├── CephFS (文件存储)          │    │
│  │  └── RGW (对象存储/S3)          │    │
│  └─────────────────────────────────┘    │
└─────────────────────────────────────────┘
```

### Ceph 存储类型

| 类型 | 接口 | 适合 |
|------|------|------|
| **RBD (Block)** | 块设备，CSI 挂载 | 数据库、Kafka |
| **CephFS** | 文件系统（POSIX）| 多 Pod 共享文件（RWX）|
| **RGW (Object)** | S3 兼容 API | 图片/视频/备份 |

```yaml
# StorageClass 使用 Ceph RBD
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: ceph-rbd
provisioner: rook-ceph.rbd.csi.ceph.com
parameters:
  clusterID: rook-ceph
  pool: replicapool
  imageFeatures: layering
reclaimPolicy: Retain
allowVolumeExpansion: true
```

---

## 3. Longhorn（轻量方案）

Longhorn 是 CNCF 沙箱项目（原 Rancher），定位**轻量分布式块存储**：
- **Replicated Volume**：数据自动复制到多个节点（默认 3 副本）。
- **快照与备份**：支持增量快照 + S3 备份。
- **UI**：内置 Web UI 管理卷。

```
Pod → PVC → CSI Driver → Longhorn Manager
                              │
                    ┌─────────┼─────────┐
                    ▼         ▼         ▼
                Node A     Node B     Node C
                (副本1)    (副本2)    (副本3)
```

### Longhorn vs Rook/Ceph

| 维度 | Longhorn | Rook/Ceph |
|------|----------|-----------|
| **复杂度** | 低（单 Helm 安装）| 高（多组件）|
| **性能** | 中（Replicated）| 高（Ceph 原生优化）|
| **功能** | 块存储 | 块/文件/对象 |
| **运维** | 简单 | 复杂（需 Ceph 知识）|
| **适合** | 中小集群、边缘 | 大规模、企业级 |

---

## 4. OpenEBS

OpenEBS 是另一个 K8s 原生分布式存储方案：
- **Maya**：本地 PV + 复制（类 Longhorn）。
- **cStor**：基于 ZFS 的分布式存储。
- **Jiva**：轻量复制卷。

> OpenEBS 在 CNCF 沙箱，社区活跃度不如 Longhorn/Rook，但 ZFS 能力强。

---

## 5. 选型建议

| 场景 | 推荐 |
|------|------|
| 小型集群 / 边缘 / 快速上手 | **Longhorn** |
| 大规模 / 企业级 / 需要对象存储 | **Rook/Ceph** |
| 已有 ZFS / 需要高级快照 | **OpenEBS** |
| 云厂商托管 | **EBS/EFS/PD**（CSI 直接用）|

> [!tip] 云上优先用托管存储
> AWS EBS/GCP PD/Azure Disk 性能好、运维省，优先用。分布式存储适合自建/混合云场景。

---

## 6. 衔接

- K8s 存储：[[concepts/Kubernetes 存储体系]]（PV/PVC/CSI/StorageClass）
- Operator：[[concepts/Kubernetes Operator 与 CRD]]（Rook 是典型 Operator）
- 分布式基础：[[concepts/分布式系统基础]]（Ceph 的 CRUSH 算法/一致性）
- 数据库：[[concepts/关系型数据库内核]]（数据库对存储性能敏感）

---

## 参考链接

**库内双链**
- [[concepts/Kubernetes 存储体系]] — PV/PVC/CSI 基础
- [[concepts/Kubernetes Operator 与 CRD]] — Rook Operator 原理
- [[concepts/分布式系统基础]] — Ceph CRUSH 算法
- [[concepts/关系型数据库内核]] — 数据库存储需求
- [[synthesis/容器分布式技术全景综述]] — 全景地图

**外部资料**
- Rook 官方文档（rook.io）
- Ceph 官方文档（docs.ceph.com）
- Longhorn 文档（longhorn.io）
- OpenEBS 文档（openebs.io）
