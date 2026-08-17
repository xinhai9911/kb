---
title: Kubernetes 技术全景综述
category: synthesis
tags: [kubernetes, container, orchestration, cloud-native, synthesis, active]
created: 2026-08-12
updated: 2026-08-17
summary: >-
    Kubernetes（K8s）技术全景：核心设计哲学（声明式/控制循环）、
    分层架构、十大核心概念、网络/存储/安全/高可用四大支柱、
    生态全景（CRI/CNI/CSI/Operator/Helm/Gateway API）、学习路径与
    常见误区。配套概念/实体文档为学习地图。
    衔接 Go 运行时、GitOps、认证授权、HTTP/2&3 等。
base_confidence: 0.92
lifecycle: review
---

# Kubernetes 技术全景综述

> Kubernetes 的本质不是「容器编排」，而是**用声明式 API + 控制循环，把数据中心当作一台电脑来编程**。
> 配合 [[concepts/Kubernetes 核心架构与组件]]、[[concepts/Kubernetes 网络模型]]、[[entities/Cilium 容器网络]]。
> 前置：「容器到底是什么」见 [[concepts/容器原理与运行时]]；系统性学习地图见 [[synthesis/容器分布式技术全景综述]]。

## 1. 一句话定位

K8s 是一个**开源容器编排平台**，解决三类问题：

| 问题 | 传统解法 | K8s 解法 |
|------|---------|---------|
| 进程部署到哪台机器 | 运维手写脚本 | Scheduler 自动调度 + 亲和性约束 |
| 进程挂了谁拉起来 | supervisor/systemd | ReplicaSet 控制循环自愈 |
| 多个副本如何对外暴露 | 手工配负载均衡 | Service + kube-proxy / 数据面 |
| 配置与密钥如何管理 | 环境变量/配置文件 | ConfigMap / Secret |
| 新版本如何发布 | 手动操作 | Deployment 滚动更新/回滚 |

## 2. 核心设计哲学

K8s 的架构选择都源于这四条铁律：

1. **声明式（Declarative）**：只描述「想要的状态」(`spec`)，不描述「怎么到达」(`status` 是实际状态，由控制器写入)。
2. **控制循环（Reconcile Loop）**：控制器持续比较 `spec` 与 `status`，发现偏差就驱动现状向目标收敛。
3. **API 为中心**：一切皆对象，所有交互走 `kube-apiserver` 的 REST API；`etcd` 是唯一的真理源（source of truth）。
4. **自愈（Self-healing）**：失败是常态，系统默认在后台不断修复漂移，而不是等人工介入。

> 推论：你在 K8s 里**永远不要直接跑进程，而是声明期望**。系统保证「当前状态 → 期望状态」。

## 3. 分层架构速览

```
┌──────────────────────────────────────────────────────────┐
│  客户端层：kubectl / 各类 Client / 控制面板(Dashboard)      │
├──────────────────────────────────────────────────────────┤
│  控制面 Control Plane                                      │
│  ├─ kube-apiserver  ── 唯一入口，REST API + 认证/授权/准入   │
│  ├─ etcd           ── 键值存储，集群所有状态的真相           │
│  ├─ kube-scheduler  ── 为新 Pod 选节点                     │
│  ├─ kube-controller-manager ── 运行全部内置控制器            │
│  └─ cloud-controller-manager ── 对接云厂商（LB/存储/节点）    │
├──────────────────────────────────────────────────────────┤
│  数据面 Data Plane（工作节点）                              │
│  ├─ kubelet        ── 节点上的「小大脑」，负责 Pod 生命周期   │
│  ├─ kube-proxy     ── 实现 Service 的转发规则（iptables/IPVS）│
│  ├─ 容器运行时     ── containerd / CRI-O（符合 CRI 接口）     │
│  └─ CNI 插件       ── 给 Pod 配置网络（Calico/Cilium/Flannel）│
└──────────────────────────────────────────────────────────┘
```

## 4. 十大核心概念（导航）

| # | 概念 | 一句话 | 详情文档 |
|---|------|--------|---------|
| 1 | Pod | 最小的调度/运行单元，一组共享网络的容器 | [[concepts/Kubernetes 工作负载与调度]] |
| 2 | Deployment | 无状态应用的声明式发布/滚动更新 | 同上 |
| 3 | Service | 稳定的访问入口（ClusterIP/NodePort/LB/Headless） | [[concepts/Kubernetes 网络模型]] |
| 4 | Ingress / Gateway | 七层南北向流量入口 | 同上 |
| 5 | ConfigMap/Secret | 配置与密钥解耦 | [[concepts/Kubernetes 安全模型]] |
| 6 | PV/PVC/StorageClass | 存储抽象与动态供给 | [[concepts/Kubernetes 存储体系]] |
| 7 | Namespace | 逻辑隔离/多租户边界 | [[concepts/Kubernetes 核心架构与组件]] |
| 8 | NetworkPolicy | 微隔离（东西向访问控制） | [[concepts/Kubernetes 网络模型]] |
| 9 | RBAC/SA | 权限模型 | [[concepts/Kubernetes 安全模型]] |
| 10 | CRD/Operator | 扩展 API 与应用生命周期自动化 | [[concepts/Kubernetes Operator 与 CRD]] |

## 5. 四大支柱

- **网络**：每个 Pod 有独立 IP（CNI 扁平网络）；Service 做服务发现与负载均衡；Ingress/Gateway 管南北向；服务间治理（熔断/重试/mTLS/金丝雀）用 Service Mesh（[[concepts/Kubernetes 服务 网格]]）。对照 [[concepts/eBPF 核心架构]] 理解 Cilium 用 eBPF 替代 iptables 的高性能数据面。
- **存储**：PV（存储资源）/ PVC（存储请求）/ StorageClass（动态供给模板），CSI 让存储厂商插件化接入。
- **安全**：RBAC 授权 + ServiceAccount 身份 + NetworkPolicy 微隔离 + 准入控制（安全上下文、PSS）+ Secret 加密。
- **高可用**：控制器自愈、健康检查（liveness/readiness/startup）、滚动更新与回滚、控制面多副本 + etcd 集群。

## 6. 生态全景（接口与插件化）

K8s 的威力在于**用标准接口把实现做成插拔**：

| 接口 | 全称 | 作用 | 常见实现 |
|------|------|------|---------|
| CRI | Container Runtime Interface | 容器运行时 | containerd / CRI-O / (Docker 需 dockershim，已废弃) |
| CNI | Container Network Interface | Pod 网络 | Calico / Cilium / Flannel / Weave |
| CSI | Container Storage Interface | 存储 | 各云厂商 CSI / 本地卷 / NFS |
| CDI / Device Plugin | — | 异构设备（GPU/NIC） | NVIDIA / 网卡 / FPGA 插件 |
| CRD + Operator | — | 扩展自定义资源 | 各类 Operator（详见下文） |

> K8s 自己不实现网络、存储、负载均衡、日志监控——它只定义接口，生态实现细节。

## 7. 扩展机制

- **CRD**：自定义资源定义，往 API 里加新对象类型（如 `VirtualService`、`Prometheus`）。
- **Operator**：把「人工运维知识」写成控制器程序——通过 CRD 描述应用集群，控制器自动部署/扩缩容/备份/升级（[[concepts/Kubernetes Operator 与 CRD]]）。
- **Webhook**：准入（Admission）在写入前改/拦请求（校验 + 变更），是策略强制与默认值注入的关键点。
- **聚合 API**：把外部服务挂到 API Server 上（如 metrics-server）。

## 8. 与现有知识库的关联

- [[entities/Cilium 容器网络]] — 用 eBPF 实现的 CNI 与数据面，直接替代 kube-proxy。
- [[concepts/eBPF 核心架构]] / [[synthesis/eBPF 技术全景]] — Cilium 的底层技术。
- [[concepts/Linux 内存管理]] / [[concepts/Linux 内核网络栈]] — 理解 kubelet 的资源管理、容器网络命名空间。
- [[concepts/分布式系统基础]] — etcd 依赖 Raft 共识；控制器循环是分布式系统里「对账」的典型。
- [[concepts/可观测性工程]] / [[concepts/韧性设计]] — K8s 健康检查、探针、滚动更新都是这两个主题的容器化实例。
- [[entities/CI_CD 流水线实战]] — K8s 是 CI/CD 的部署目标；Helm 与 GitOps（ArgoCD）是发布载体。
- [[concepts/Go 运行时与并发模型]] — K8s/etcd/Cilium 全是 Go 写的，理解运行时即理解并发与内存行为。
- [[entities/GitOps 与 ArgoCD 实战]] — 声明式交付进 K8s，Git 为唯一事实源。
- [[concepts/认证授权 OAuth2 OIDC JWT]] — K8s OIDC 集成、ServiceAccount/RBAC 认证授权原理。
- [[concepts/HTTP2 与 HTTP3(QUIC)]] — Ingress/gRPC 底层传输协议，现代微服务通信基础。
- [[concepts/基础设施即代码 Terraform]] — 云上拉起 K8s 集群的 IaC 工具，与 GitOps 互补。

## 9. 学习路径（建议顺序）

1. **容器基础**：镜像、容器运行时、命名空间/ cgroups（对照 [[concepts/Linux 内存管理]]）。
2. **单机 K8s**：minikube/kind 跑起来，掌握 `kubectl` 与核心对象（Pod→Deployment→Service）。
3. **控制面原理**：API Server + etcd + 控制器循环，理解「声明式」。
4. **网络深入**：CNI、Service 的实现（iptables → IPVS → eBPF），对照 Cilium。
5. **存储与有状态应用**：PV/PVC/CSI，StatefulSet 实战（数据库）。
6. **安全**：RBAC、NetworkPolicy、Secret、准入控制。
7. **扩展与自动化**：Helm、CRD、写一个 Operator。
8. **生产化**：HA 控制面、多集群、GitOps（ArgoCD）、可观测性。

## 10. 常见误区

- ❌ 「K8s = Docker」—— K8s 管编排，运行时已被 CRI 抽象掉，Docker 只是历史形态之一。
- ❌ 「Pod 是容器的升级版」—— Pod 是「调度单元」，容器是「运行单元」，两者粒度不同。
- ❌ 「有 Service 就有负载均衡」—— Service 默认是 iptables 转发，不是 L4/L7 LB；Ingress 才是七层入口。
- ❌ 「部署了 K8s 就高可用」—— 高可用要自己配：多副本 + 健康检查 + 反亲和 + 控制面 HA。
- ❌ 「直接用 IP 访问 Pod」—— Pod IP 会随重建变化，永远通过 Service/DNS 访问。

## 来源

- [[sources/Kubernetes 学习来源]]

## 相关文档

- [[concepts/Kubernetes 核心架构与组件]]
- [[concepts/Kubernetes 声明式模型与控制器]]
- [[concepts/Kubernetes 工作负载与调度]]
- [[concepts/Kubernetes 网络模型]]
- [[concepts/Kubernetes 存储体系]]
- [[concepts/Kubernetes 安全模型]]
- [[concepts/Kubernetes 高可用与自愈]]
- [[concepts/Kubernetes Operator 与 CRD]]
- [[concepts/Kubernetes 服务 网格]]
- [[entities/Kubernetes 部署与工具链实战]]
- [[entities/kubectl 与日常运维实战]]
- [[entities/Helm 包管理实战]]
- [[entities/Ingress-Nginx 详解实战]]
- [[projects/k8s-kind-examples/README]]
