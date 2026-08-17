---
aliases: ["Kubernetes Service Mesh"]
title: Kubernetes Service Mesh
category: concepts
tags: [kubernetes, service-mesh, istio, linkerd, sidecar, mTLS, traffic-management, active]
created: 2026-08-12
updated: 2026-08-12
summary: >-
    Service Mesh 全景：为什么需要（服务间流量治理）、Sidecar 模式、
    数据面/控制面架构、Istio 与 Linkerd 实现对比、流量管理
    （VirtualService/DestinationRule/熔断/重试/金丝雀）、mTLS 零信任
    与身份、可观测性、eBPF 新一代（Cilium Service Mesh）、
    Service Mesh 与 Gateway API/Ingress 的关系与选型。
base_confidence: 0.87
lifecycle: draft
---

# Kubernetes Service Mesh

> 先有 [[concepts/Kubernetes 网络模型]] 的南北向（Ingress），再看 Service Mesh 的**东西向**（服务间流量）。
> 一句话：**Service Mesh 把「服务间通信的治理」从业务代码里抽出来，下沉到基础设施层**。

## 1. 为什么需要 Service Mesh

微服务化后，服务间调用要面对一堆横切问题：

| 问题 | 传统解法 | Service Mesh 解法 |
|------|---------|------------------|
| 熔断/重试/超时 | 每个服务写一遍库 | 数据面自动注入，零代码 |
| 流量灰度/金丝雀 | 改网关/负载均衡 | 规则声明（VirtualService） |
| 服务间加密 | 各服务自己配 TLS | 自动 mTLS |
| 调用链追踪/指标 | 埋点 SDK | sidecar 自动上报 |
| 服务发现/负载均衡 | 各自实现 | 控制面下发 |

**核心洞察**：治理逻辑（熔断、重试、鉴权、可观测）是**与业务无关的通用能力**——不该重复写在每个服务的代码里，而是下沉为「网络代理」层，业务只管业务。

## 2. 核心架构：Sidecar 模式

```
┌───────────── Pod ─────────────┐
│  ┌───────────┐   ┌─────────┐ │
│  │ 业务容器   │──▶│ sidecar │ │──▶ 目标服务
│  │ (app)     │◀──│ (envoy) │ │◀──
│  └───────────┘   └─────────┘ │
└──────────────────────────────┘
  每个 Pod 注入一个 sidecar 代理，所有进出流量强制经过它
```

- **Sidecar 容器**（通常 Envoy）：与业务容器同 Pod、同网络命名空间，劫持/代理全部出入流量。
- 透明注入：通过 **MutatingWebhook**（[[concepts/Kubernetes Operator 与 CRD]] §4）给 Pod 自动注入 sidecar，业务代码零改动。
- 性能开销：每次调用多一跳（多 ~0.5-2ms 延迟），这是 Service Mesh 的主要代价。

### 2.1 数据面与控制面

| 面 | 组成 | 职责 |
|----|------|------|
| **数据面** | 每个 Pod 里的 sidecar 代理（Envoy） | 实际转发、负载均衡、熔断、mTLS、指标 |
| **控制面** | Istiod（Istio）/ Linkerd 控制器 | 下发配置、签发证书（mTLS）、服务发现、故障注入规则 |

控制面**不做数据转发**，只把「规则」下发到每个数据面代理（通过 xDS 协议）；代理按规则做事。

## 3. 主流实现对比

| 维度 | **Istio** | **Linkerd** | **Cilium Service Mesh** |
|------|----------|-------------|------------------------|
| 数据面 | Envoy（功能最强） | 自研轻量代理（Rust，资源占用小） | eBPF（无 sidecar） |
| 控制面 | istiod | linkerd-controller | 依赖 [[entities/Cilium 容器网络]] |
| 功能 | L4+L7、全特性 | L4+L7 核心、简洁 | L4 + 部分 L7（eBPF） |
| 资源开销 | 较高（每个 Pod 多一个 Envoy） | 较低 | 最低（无 sidecar） |
| 复杂度 | 学习曲线陡 | 简单易用 | 依赖 eBPF 内核版本 |
| 适用 | 大型、复杂治理需求 | 中小型、求稳 | 追求性能、不想背 sidecar |

- **Istio**：事实标准，功能最全（VirtualService、DestinationRule、故障注入、多集群）。
- **Linkerd**：CNCF 毕业项目，「简单 + 低资源」路线，主打易用。
- **Cilium**：eBPF 路线——没有 sidecar 代理，直接在 eBPF 数据路径上做 L4 策略与部分 L7，性能最好（对照 [[synthesis/eBPF 技术全景]]）。

## 4. 流量管理（Istio 为例）

### 4.1 关键 CRD

| CRD | 作用 |
|-----|------|
| **VirtualService** | 定义路由规则：host + 权重 + 匹配（header/uri/方法） |
| **DestinationRule** | 定义**目标集群**的负载均衡、连接池、TLS、熔断、子集 |
| **ServiceEntry** | 把网格外服务纳入（出站外部依赖） |
| **Gateway** | 网格**入口**（南北向，可配合 Ingress/Gateway API） |

### 4.2 金丝雀发布示例

```yaml
# 1. 定义两个版本子集
apiVersion: networking.istio.io/v1
kind: DestinationRule
metadata: {name: reviews-ds}
spec:
  host: reviews
  subsets:
  - {name: v1, labels: {version: v1}}
  - {name: v2, labels: {version: v2}}
---
# 2. 按权重分流
apiVersion: networking.istio.io/v1
kind: VirtualService
metadata: {name: reviews}
spec:
  hosts: [reviews]
  http:
  - route:
    - destination: {host: reviews, subset: v1}
      weight: 90
    - destination: {host: reviews, subset: v2}
      weight: 10
```

- 改 `weight` 就完成 90/10 → 50/50 → 100/0，**无需重建 Pod**。
- 熔断/重试/超时：写在 DestinationRule 的 `trafficPolicy`（`connectionPool`、`outlierDetection`、`retries`）。

## 5. mTLS 与零信任

- Service Mesh 自动给**每对服务**签发短期证书，服务间通信走 **mTLS**（双向 TLS）。
- 身份：SPIFFE ID（`spiffe://cluster.local/ns/<ns>/sa/<sa>`）——基于 ServiceAccount 而不是 IP（IP 会变，SA 稳定）。
- 收益：东西向流量默认加密 + 身份认证，是「零信任」的基础（对照 [[concepts/Kubernetes 安全模型]] 的 NetworkPolicy——那是 L3/4 的访问控制，mTLS 是加密 + 认证）。

## 6. 可观测性

| 能力 | 手段 |
|------|------|
| 调用链追踪 | sidecar 自动注入 trace 头（W3C traceparent），接 Jaeger/Tempo |
| 指标 | Prometheus 指标（请求数/延迟分布/错误率）自动暴露 |
| 拓扑 | Kiali（Istio）可视化服务依赖图 |
| 故障注入 | VirtualService 的 `fault: {delay: {fixedDelay: 5s}}` 做混沌实验 |

- 好处：**零埋点**拿到全链路可观测——这正是 [[concepts/可观测性工程]] 里「自动探针」的极致形态。

## 7. Service Mesh vs Gateway API / Ingress

| 关注点 | Ingress-nginx | Gateway API | Service Mesh |
|--------|---------------|-------------|--------------|
| 方向 | 南北向（外部→集群） | 南北向（标准接口） | 东西向（服务↔服务）+ 南北向 |
| 数据面 | Nginx/HAProxy | 各实现 | Envoy / Linkerd / eBPF |
| 治理能力 | 路由/TLS/限流 | 路由/TLS（HTTPRoute） | + 熔断/重试/mTLS/故障注入/追踪 |
| 定位 | 入口网关 | 入口标准 | 网格级服务治理 |

- **并存关系**：Ingress 管外部入口，Service Mesh 管内部调用；两者常组合（外部 → Ingress → 服务 → Mesh 内治理）。
- Gateway API 是入口标准化的方向，Service Mesh 也可实现 Gateway API 资源。

## 8. 选型建议

| 场景 | 建议 |
|------|------|
| 大型多团队、复杂治理 | Istio（功能全、社区大） |
| 中小规模、想快速落地 | Linkerd（简单、低开销） |
| 已有 Cilium 且追求性能 | Cilium Service Mesh（eBPF、无 sidecar） |
| 只是做入口 | 不需要 Mesh，用 Ingress-nginx + Gateway API |

## 9. 常见误区

- ❌ 「Service Mesh = 网关」—— 网关管南北向，Mesh 管东西向（也能管南北向但不是核心）。
- ❌ 「上了 Mesh 就自动熔断」—— 要写 VirtualService/DestinationRule 规则，默认只是转发。
- ❌ 「Sidecar 是免费的」—— 每个 Pod 多一个代理，资源、延迟、排障复杂度都增加。
- ❌ 「Mesh 替代了 NetworkPolicy」—— 加密/认证 ≠ 授权；NetworkPolicy 仍是 L3/4 隔离的第一道门。

## 来源

- [[sources/Kubernetes 学习来源]]

## 相关文档

- [[concepts/Kubernetes 网络模型]]
- [[entities/Ingress-Nginx 详解实战]]
- [[entities/Cilium 容器网络]]
- [[synthesis/eBPF 技术全景]]
- [[concepts/Kubernetes 安全模型]]
- [[concepts/认证授权 OAuth2 OIDC JWT]] — mTLS 身份认证与 OAuth2/OIDC 的关系
