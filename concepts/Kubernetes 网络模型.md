---
title: Kubernetes 网络模型
category: concepts
tags: [kubernetes, networking, cni, service, kube-proxy, ingress, cilium, ebpf, active]
created: 2026-08-12
updated: 2026-08-12
summary: >-
    Kubernetes 网络核心：Pod 网络模型（每 Pod 一 IP）、CNI 插件、
    Service 四种类型与实现（ClusterIP/NodePort/LoadBalancer/Headless）、
    kube-proxy 的 iptables/IPVS/eBPF 三种模式、DNS 与服务发现、
    Ingress 与 Gateway API、NetworkPolicy 微隔离、多 CNI。
    重点对照 Cilium/eBPF 理解高性能数据面。
base_confidence: 0.88
lifecycle: draft
---

# Kubernetes 网络模型

> K8s 网络有四个基本要求：① 每 Pod 一个独立 IP；② 容器间直接通信（无需 NAT）；③ 节点与 Pod 互通；④ 与外部网络互通。
> 前三条由 **CNI** 解决，`Service`/`Ingress` 解决「Pod IP 会变」的访问问题。

## 1. Pod 网络模型与 CNI

### 1.1 每 Pod 一 IP（flat network）

- 每个 Pod 分配**集群内全局唯一 IP**，Pod 之间无需 NAT 直接访问。
- Pod IP 不持久：重建即换，所以**永远不要用 Pod IP 对外暴露**。

### 1.2 CNI 插件的工作

```
kubelet 创建 Pod
  → 调 CNI 插件
  → 创建网络命名空间（pause 容器承载）
  → 建 veth pair（一头进 Pod，一头在宿主机）
  → 配 IP / 路由 / 规则
  → 打通：VXLAN 隧道 / BGP / 直接路由 / eBPF
```

| CNI 实现 | 数据面原理 | 特点 |
|---------|-----------|------|
| **Flannel** | VXLAN 叠加网络 | 简单，性能一般，无 NetworkPolicy |
| **Calico** | BGP 全路由 + iptables（可 eBPF 模式） | 性能好，支持 NetworkPolicy |
| **Cilium** | eBPF（+ 可选 VXLAN/BGP/云原生路由） | 高性能，内建 NetworkPolicy + 可观测（[[entities/Cilium 容器网络]]） |
| Weave / 其他 | VXLAN / IPIP | 兼容简单场景 |

- CNI 是接口：实现可插拔，与 [[concepts/eBPF 核心架构]] 联动理解 Cilium 的优势。

## 2. Service：稳定访问入口

Pod 会死会重建，Service 提供**稳定 IP + 服务发现 + 负载均衡**。

### 2.1 四种类型

| 类型 | 访问范围 | 说明 |
|------|---------|------|
| **ClusterIP**（默认） | 集群内 | 分配集群内虚拟 IP，Pod 通过它互相访问 |
| **NodePort** | 集群外 | 每个节点开 `<NodeIP>:<port>` 转发到 Service |
| **LoadBalancer** | 公网 | 云厂商 LB → NodePort → Service（裸机用 MetalLB） |
| **Headless**（`clusterIP: None`） | DNS 直连 | 不分配虚拟 IP，返回所有后端 IP，配合 StatefulSet |

### 2.2 组成与选择器

```
Service (ClusterIP)
   selector: app=web      ← 靠 label 选后端 Pod
   port: 80               ← 客户端访问的端口
   targetPort: 8080       ← 转发到 Pod 的端口
        │
        ▼
  EndpointSlice（1.21+，替代 Endpoints）
     [Pod IP:8080, Pod IP:8080, ...]   ← 由控制器实时维护
```

- 后端由 **EndpointSlice 控制器**根据 selector 实时同步；Pod 变动（扩缩/重建）自动反映。
- 无 selector 的 Service 可手动指向外部地址（把外部服务接进集群）。

## 3. kube-proxy 的实现模式

Service 的虚拟 IP 需要**数据面**把流量转给后端 Pod，kube-proxy 管这件事：

| 模式 | 原理 | 性能/复杂度 |
|------|------|------------|
| **userspace**（已废弃） | 用户态代理 | 最慢 |
| **iptables**（默认） | NAT 规则（随机选后端） | 中等；规则多时 O(N) 遍历，无连接保持 |
| **IPVS** | 内核 L4 负载均衡（哈希表） | 快，支持多种调度算法（rr/wrr/lc），规则 O(1) |
| **eBPF**（Cilium 等） | 内核 eBPF 程序直接转发 | 最快，可做 L7，替代 kube-proxy（见 [[entities/Cilium 容器网络]]） |

- iptables 模式下每个后端轮换会导致 **conntrack 连接打散**（新连接随机选后端），IPVS/eBPF 更稳。
- **clusterIP 的实现细节**：`KUBE-SVC-*` 链做选择，`KUBE-SEP-*` 链做 DNAT。

## 4. DNS 与服务发现

- 集群 DNS（CoreDNS）提供：`<service>.<namespace>.svc.cluster.local`。
- Headless Service + StatefulSet：`<podname>.<headless-svc>.<ns>.svc.cluster.local`。
- 应用间调用**用服务名而非 IP**，天然实现服务发现。

## 5. Ingress 与 Gateway API（南北向）

### 5.1 Ingress（七层入口）

```
客户端 → Ingress Controller（Nginx/Traefik/HAProxy…）
              → 按 host/path 路由 → Service → Pod
```

- Ingress **资源**定义路由规则（host、path、TLS），**Ingress Controller** 是实现（Nginx 等）。
- ⚠️ 只有装了 Controller 才有用；裸机/本地需额外部署（如 ingress-nginx）。
- 深入实战（注解/rewrite/金丝雀/常见坑）：[[entities/Ingress-Nginx 详解实战]]；可运行示例见 [[projects/k8s-kind-examples/README]]。

### 5.2 Gateway API（Ingress 的后继）

- 面向服务网格/多协议的下一代入口标准：`Gateway`、`GatewayClass`、`HTTPRoute`。
- 与 Service Mesh（[[concepts/Kubernetes Service Mesh]]）更贴近，表达能力更强。

## 6. NetworkPolicy（东西向微隔离）

- **默认全通**：没有 NetworkPolicy 时，所有 Pod 可互相访问。
- NetworkPolicy 定义「允许谁访问谁」（selector + ipBlock + ports），由 **CNI 实现**（Calico/Cilium 支持，Flannel 不支持）。

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-frontend
spec:
  podSelector: {matchLabels: {app: backend}}
  ingress:
  - from:
    - podSelector: {matchLabels: {app: frontend}}
    ports: [{protocol: TCP, port: 8080}]
```

- 安全等级：**默认拒绝 + 白名单**是最佳实践（配合 [[concepts/Kubernetes 安全模型]]）。

## 7. 端到端流量路径总览

```
外部用户
  │  (1) 公网 → LoadBalancer / Ingress Controller
  ▼
Node
  │  (2) iptables/IPVS/eBPF：KUBE-SVC 链 → DNAT 到某个后端 Pod IP
  ▼
Pod 网络（CNI）
  │  (3) 宿主机路由/VXLAN/eBPF 转发
  ▼
Pod（容器网络命名空间） → 进程
```

## 8. 常见误区

- ❌ 「Service 就是负载均衡器」—— 默认是 iptables/IPVS 的 L4 转发，不是 L7 LB；七层入口是 Ingress。
- ❌ 「kube-proxy 做服务发现」—— 服务发现是 DNS；kube-proxy 只改数据面规则。
- ❌ 「NetworkPolicy 默认就隔离」—— 默认全通，必须显式写 Policy。
- ❌ 「Pod 间直接通信要配端口映射」—— 模型里 Pod 天然互通，无需映射。

## 来源

- [[sources/Kubernetes 学习来源]]

## 相关文档

- [[entities/Cilium 容器网络]]
- [[concepts/eBPF 核心架构]]
- [[synthesis/eBPF 技术全景]]
- [[entities/Ingress-Nginx 详解实战]]
- [[concepts/Kubernetes Service Mesh]]
- [[concepts/Kubernetes 安全模型]]
- [[concepts/Kubernetes 工作负载与调度]]
- [[concepts/HTTP2 与 HTTP3(QUIC)]] — Ingress/gRPC 底层传输协议
- [[projects/k8s-kind-examples/README]]
