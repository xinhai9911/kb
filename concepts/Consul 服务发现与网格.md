---
title: Consul 服务发现与网格
category: concepts
tags: [consul, service-discovery, service-mesh, hashicorp, kv, health-check, active]
created: 2026-08-17
updated: 2026-08-17
summary: >-
    Consul 服务发现与网格：服务注册与发现（DNS/HTTP API）、健康检查（HTTP/TCP/Script/GRPC）、
    KV 存储（配置中心/Feature Flag）、Service Mesh（Envoy sidecar/mTLS）、多数据中心、
    与 K8s CoreDNS/Service 对比、与 etcd 定位对比。
    衔接 [[concepts/Kubernetes 网络模型]]、[[concepts/Kubernetes 服务 网格]]、[[concepts/etcd 与 Raft 共识实战]]。
base_confidence: 0.85
lifecycle: draft
sources: []
---

# Consul 服务发现与网格

> Consul 是 HashiCorp 的**服务发现 + 服务网格**方案，核心解决「服务在哪、状态如何、流量怎么管」。
> 与 K8s 原生的 CoreDNS/Service 互补，尤其适合非 K8s 或混合环境。见 [[synthesis/容器分布式技术全景综述]]。

---

## 1. 服务注册与发现

### 两种模式

| 模式 | 机制 | 适合 |
|------|------|------|
| **Self-Registration** | 服务自己调 Consul API 注册 | 简单场景 |
| **Registrator** | Sidecar 自动从 K8s/Docker 注册 | K8s/容器环境 |

```
服务启动 → PUT /v1/agent/service/register
           {name: "order-service", address: "10.0.1.5", port: 8080}

消费者查询 → GET /v1/catalog/service/order-service
             或 DNS: order-service.service.consul
```

### DNS 发现

```bash
# Consul 内置 DNS 服务器（默认 8600 端口）
dig @127.0.0.1 -p 8600 order-service.service.consul SRV

# 返回健康实例的 IP:Port
# K8s 中可配 CoreDNS 转发 .consul 域到 Consul
```

---

## 2. 健康检查

| 类型 | 检查方式 | 示例 |
|------|----------|------|
| **HTTP** | GET 指定路径，2xx = 健康 | `GET /healthz` |
| **TCP** | 端口可达 = 健康 | `connect: db.consul:5432` |
| **Script** | 执行脚本，exit 0 = 健康 | `check_redis.sh` |
| **GRPC** | gRPC 健康检查协议 | 内置 Health 服务 |
| **TTL** | 服务定期续约，超时 = 不健康 | 适合无法主动检查的场景 |

```
健康状态：
  passing (绿) → 正常接收流量
  warning (黄) → 仍接收流量但告警
  critical (红) → 从负载均衡中摘除
```

---

## 3. KV 存储

Consul 的 KV 可当**轻量配置中心**：
```bash
# 写入
consul kv put config/redis/max-connections 100

# 读取
consul kv get config/redis/max-connections

# Watch（监听变更）
consul watch -type=keyprefix -prefix=config/ redis/ /reload.sh
```

- **用例**：Feature Flag、动态配置、分布式锁。
- **对比 etcd**（[[concepts/etcd 与 Raft 共识实战]]）：Consul KV 更偏向「配置/发现」，etcd 更偏向「K8s 状态存储」。

---

## 4. Service Mesh（Consul Connect）

Consul 的 Service Mesh 功能：
- **mTLS**：自动为服务间通信加密（零信任）。
- **Intent**：声明式访问控制（Service A 可以调 Service B）。
- **Sidecar Proxy**：默认用 Envoy（[[concepts/Kubernetes 服务 网格]] 同款）。

```
Service A ──▶ Sidecar (Envoy) ═══mTLS═══▶ Sidecar (Envoy) ──▶ Service B
              │                                           │
              └── Consul 注册 ←── 健康检查 ──→ Consul 注册
```

---

## 5. 多数据中心

Consul 原生支持多数据中心：
- **WAN Gossip**：跨 DC 的成员发现与故障检测。
- **Local DC 优先**：请求优先路由到本地 DC，本地无健康实例再跨 DC。
- **与 K8s 多集群**（[[concepts/多集群管理与联邦]]）互补。

---

## 6. Consul vs K8s 原生

| 功能 | Consul | K8s 原生 |
|------|--------|----------|
| 服务发现 | DNS + HTTP API | CoreDNS + Service |
| 健康检查 | 4 种类型 | Liveness/Readiness Probe |
| KV 存储 | ✅ 内置 | ConfigMap（非 watch 原生）|
| Service Mesh | ✅ Consul Connect | Istio/Linkerd/Cilium |
| 多数据中心 | ✅ 原生 | 需 Federation/Submariner |
| 非 K8s 环境 | ✅ VM/裸机 | ❌ 仅 K8s |

> 选型：纯 K8s → 用 K8s 原生 + Istio/Cilium；混合环境（VM+K8s）→ Consul。

---

## 7. 衔接

- K8s 网络：[[concepts/Kubernetes 网络模型]]
- Service Mesh：[[concepts/Kubernetes 服务 网格]]
- etcd 对照：[[concepts/etcd 与 Raft 共识实战]]
- 安全：[[concepts/Kubernetes 安全模型]]（mTLS/零信任）
- 多集群：[[concepts/多集群管理与联邦]]

---

## 参考链接

**库内双链**
- [[concepts/Kubernetes 网络模型]] — K8s 原生服务发现
- [[concepts/Kubernetes 服务 网格]] — Istio/Linkerd 对照
- [[concepts/etcd 与 Raft 共识实战]] — KV 存储对照
- [[concepts/多集群管理与联邦]] — 多 DC 场景
- [[concepts/Kubernetes 安全模型]] — mTLS/零信任

**外部资料**
- Consul 官方文档（developer.hashicorp.com/consul）
- Consul Connect（Service Mesh）文档
- 《Service Mesh with Consul》
