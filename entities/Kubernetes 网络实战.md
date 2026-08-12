---
title: Kubernetes 网络实战（Service / Ingress / NetworkPolicy / 排障）
category: entities
tags: [kubernetes, network, service, ingress, networkpolicy, dns, coredns, troubleshooting, active]
created: 2026-08-12
updated: 2026-08-12
summary: >-
    Kubernetes 网络实战（厂商中立）：从网络模型三大约定出发，给出 Service 四种类型与可复用 YAML、
    CoreDNS 服务发现、Ingress 七层入口、NetworkPolicy 零信任网络，以及一套 Pod 间/Service/DNS 不通的排障清单
    （endpoint/iptables/ipvs/netshoot 抓包）。概念见 [[concepts/Kubernetes 网络模型]]，eBPF 数据面见 [[entities/Cilium 容器网络]]。
base_confidence: 0.85
lifecycle: draft
sources: []
---

# Kubernetes 网络实战（Service / Ingress / NetworkPolicy / 排障）

> 概念见 [[concepts/Kubernetes 网络模型]]；Cilium eBPF 数据面实战见 [[entities/Cilium 容器网络]]。
> 本文给**可直接用的配置与排障清单**，厂商中立（不绑定某 CNI）。

---

## 1. K8s 网络模型三大约定（一切设计的前提）

1. **每个 Pod 有独立 IP**，跨节点 Pod 之间**直接互通**（不经过 NAT）——靠 CNI 插件（Calico/Cilium/Flannel…）实现 overlay 或 underlay。
2. **同一 Pod 内所有容器共享网络命名空间**（同 `localhost`、同 IP、同端口空间）。
3. **Pod IP 是易变的**（重建就变），所以外部靠 **Service** 提供稳定的虚拟 IP + 负载均衡。

> [!note] 与原理篇呼应
> 第 1 条成立，全靠容器 Network Namespace（[[concepts/容器原理与运行时#2. 基石一：Namespace]]）被 CNI 正确配置——每个 Pod 一个独立 `net` namespace，并通过 CNI 把各节点的 Pod 网络打通。

---

## 2. Service：稳定的访问入口

Service 把「一组动态 Pod（由 label selector 选定）」聚合为一个不变的虚拟 IP（ClusterIP），并做负载均衡。

### 2.1 四种类型

| 类型 | 访问范围 | 典型用途 |
|---|---|---|
| `ClusterIP` | 仅集群内 | 内部服务互访（默认） |
| `NodePort` | 任意节点 IP:端口 | 临时暴露 / 开发 |
| `LoadBalancer` | 云厂商外部 LB | 生产对外暴露 |
| `ExternalName` | 映射到外部 DNS 名 | 把外部服务当内部 Service |

### 2.2 可复用 YAML

```yaml
apiVersion: v1
kind: Service
metadata: { name: web, namespace: prod }
spec:
  selector: { app: web }          # 选中的 Pod
  ports:
  - port: 80                       # Service 端口
    targetPort: 8080               # Pod 容器端口
    protocol: TCP
  type: ClusterIP
  # sessionAffinity: ClientIP      # 需要会话粘滞时开启
  # externalTrafficPolicy: Local   # NodePort/LB 保留客户端真实 IP（但可能负载不均）
```

**Headless Service**（StatefulSet 用，直接返回 Pod IP 而非 VIP）：
```yaml
spec:
  clusterIP: None      # 无 VIP，DNS 返回各 Pod A 记录
```

> [!tip] Service 不通先查 Endpoints
> `kubectl get endpoints web` 若为空，说明 selector 没匹配到任何就绪 Pod——这是 Service 不通的**头号原因**。

---

## 3. DNS 与服务发现（CoreDNS）

K8s 内置 CoreDNS，Pod 内默认用集群 DNS 解析：

| 域名写法 | 解析到 |
|---|---|
| `web` | 同命名空间的 `web` Service |
| `web.prod` | `web.prod.svc.cluster.local` |
| `web.prod.svc` | 同上（省略后缀） |
| `web.prod.svc.cluster.local` | 完整 FQDN |

> Headless Service 还能解析出每个 Pod：`web-0.web.prod.svc...`（StatefulSet 稳定网络标识）。

---

## 4. Ingress：七层（HTTP）统一入口

LoadBalancer 是四层（IP:端口）。**Ingress** 在七层做基于「域名/路径」的路由，通常配一个 Ingress Controller（nginx/Contour/Cilium…）。

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: app-ingress
  namespace: prod
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  tls:
  - hosts: [app.example.com]
    secretName: app-tls            # TLS 证书（见 [[concepts/Kubernetes 核心架构与组件]] Secret）
  rules:
  - host: app.example.com
    http:
      paths:
      - path: /api
        pathType: Prefix
        backend: { service: { name: api, port: { number: 80 } } }
      - path: /
        pathType: Prefix
        backend: { service: { name: web, port: { number: 80 } } }
```

> [!warning] Ingress ≠ LoadBalancer
> Ingress 是「路由规则」，**必须有一个 Ingress Controller 在跑**才生效；它本身不提供外部 IP。外部流量通常：客户端 → 云 LB → Ingress Controller(Service NodePort/LoadBalancer) → Ingress 规则 → 后端 Service。

---

## 5. NetworkPolicy：零信任网络

K8s 网络**默认全通**（任何 Pod 能访问任何 Pod）。生产应改成**默认拒绝、按需放行**。

```yaml
# 只允许 frontend 命名空间访问 backend 的 8080
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata: { name: backend-allow-frontend, namespace: prod }
spec:
  podSelector: { matchLabels: { app: backend } }   # 受保护的目标 Pod
  policyTypes: [Ingress]
  ingress:
  - from:
    - namespaceSelector: { matchLabels: { kubernetes.io/metadata.name: frontend } }
    ports:
    - { protocol: TCP, port: 8080 }
# 出站也可控：policyTypes: [Egress] + egress: [...]
```

> [!caution] NetworkPolicy 需要 CNI 支持
> 不是所有 CNI 都实现它。Calico/Cilium 支持；纯 overlay（如早期 flannel 默认）**不生效**——规则写了也不拦。详见 CNI 文档（[[entities/Cilium 容器网络]]）。

---

## 6. 排障清单（网络不通时按顺序查）

### 6.1 Pod 间不通
```bash
kubectl get pod -o wide             # 看 Pod IP、节点
kubectl exec -it <pod> -- ping <对端PodIP>   # 基础连通
# 跨节点不通 → CNI/路由问题（查节点路由、CNI 日志）
```

### 6.2 Service 不通
```bash
kubectl get svc web                 # 看 ClusterIP/端口
kubectl get endpoints web           # 关键！为空=selector 没匹配到就绪 Pod
kubectl describe svc web            # 看 selector、sessionAffinity
# 从同 ns Pod 内 curl <service>:<port>
```

### 6.3 DNS 不通
```bash
kubectl exec -it <pod> -- nslookup web.prod
kubectl get pods -n kube-system | grep coredns     # CoreDNS 是否 Running
kubectl logs -n kube-system <coredns-pod>          # 看解析错误
# 检查 Pod 的 /etc/resolv.conf 是否指向集群 DNS
```

### 6.4 抓包定位（netshoot 利器）
```bash
# 起一个带全套网络工具（tcpdump/curl/ip/nslookup）的临时 Pod
kubectl run netshoot --rm -it --image=nicolaka/netshoot -- /bin/bash
# 在问题 Pod 所在节点用 tcpdump 抓对应 Pod IP
# 或进目标 Pod：kubectl exec -it <pod> -- tcpdump -i any port 8080
```

### 6.5 看数据面规则
```bash
# 默认 kube-proxy 用 iptables 或 ipvs 实现 Service 转发
iptables-save | grep <service-ip>            # iptables 模式看规则
ipvsadm -Ln                                 # ipvs 模式看虚拟服务
# Cilium/eBPF 模式则走 eBPF，不依赖 iptables（见 [[entities/Cilium 容器网络]]）
```

---

## 7. 速查命令

```bash
kubectl get svc,endpoints,ingress,networkpolicy -A
kubectl describe svc <svc>                   # selector / 端口 / 事件
kubectl get networkpolicy -n prod            # 当前命名空间策略
kubectl exec -it <pod> -- curl -s <svc>:<port>/health
kubectl logs -n kube-system -l k8s-app=kube-dns   # CoreDNS 日志
```

---

## 参考链接

**库内双链**
- [[concepts/Kubernetes 网络模型]] — Service/DNS/Ingress/NetworkPolicy 概念原理
- [[entities/Cilium 容器网络]] — eBPF 数据面实现与高级网络策略
- [[concepts/Kubernetes 核心架构与组件]] — kube-proxy/Service 实现、Secret(TLS)
- [[concepts/容器原理与运行时]] — Network Namespace 是 Pod 网络的基础
- [[entities/容器可观测落地]] — 网络层追踪/cAdvisor 关联排障
- [[entities/容器实战]] — `kubectl exec`/进容器手查基础

**外部资料**
- Kubernetes 官方：Services / Ingress / NetworkPolicy 文档
- CoreDNS 文档（重写规则、自定义 hosts）
- 各 CNI 文档（Calico/Cilium/Flannel 的策略与数据面差异）
- nicolaka/netshoot 镜像（排障瑞士军刀）
