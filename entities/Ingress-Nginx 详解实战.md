---
title: Ingress-Nginx 详解实战
category: entities
tags: [kubernetes, ingress, nginx, ingress-controller, traffic, active]
created: 2026-08-12
updated: 2026-08-12
summary: >-
    Ingress-Nginx 控制器详解：Ingress 资源与 Controller 的分工、
    架构（nginx controller 的监听/生成/热加载）、部署方式
    （Helm/裸机 LoadBalancer）、注解大全（rewrite/limit/SSL 重定向/
    跨域/canary）、TLS 与证书管理、常用坑（类型不匹配/重定向 308/
    proxy 参数/rewrite）、与 Gateway API 的关系、调试与监控。
base_confidence: 0.85
lifecycle: draft
---

# Ingress-Nginx 详解实战

> **Ingress 资源是「声明」，Ingress Controller 是「实现」**。只 apply 一个 Ingress 而没有 Controller，什么都不发生。
> 本文以最常见的 **ingress-nginx**（K8s 社区项目）为例，讲透原理与实战。

## 1. Ingress 与 Controller 的分工

| 对象 | 角色 | 例子 |
|------|------|------|
| **Ingress 资源** | 声明路由规则（host/path/TLS） | 只是 YAML，不干活的声明 |
| **IngressClass** | 声明用哪个 Controller 实现（`ingressClassName`） | 多控制器时选择 |
| **Ingress Controller** | 真正接收流量并转发的进程 | ingress-nginx（Nginx 内核）/ Traefik / HAProxy / 云 LB Controller |

```
客户端 → 负载均衡器/LB Service → ingress-nginx Pod（Nginx 进程）
        → 按 Ingress 规则（host + path）→ 后端 Service → Pod
```

## 2. 架构与工作原理

### 2.1 ingress-nginx 的核心循环

```
ingress-nginx Controller（Deployment）
  │
  ├─ 监听集群 Ingress / Service / EndpointSlice / Secret 变更（informer）
  ├─ 把 Ingress 规则翻译成 Nginx 配置（生成 nginx.conf 片段）
  ├─ 校验配置 → 热加载（nginx -s reload，或 Lua 动态重载）
  └─ 暴露入口：LoadBalancer / NodePort / HostPort（裸机）
```

- Controller 通过 **informer**（[[concepts/Kubernetes 声明式模型与控制器]] §3）监听，比 Nginx 原生 reload 更聪明：很多变更走 **Lua 脚本动态路由**（nginx-ingress 用 OpenResty）而不必 reload。
- **IngressClass**（`ingressClassName: nginx`）：1.19+ 标准方式，标记 Ingress 归属哪个 Controller；集群里可同时跑 ingress-nginx 与 Traefik。

### 2.2 入口暴露方式

| 方式 | 场景 | 说明 |
|------|------|------|
| **LoadBalancer**（推荐云上） | 云上 | 云 LB → Controller Pod |
| **NodePort** | 裸机/本地 | 每节点开 `<nodeIP>:<port>` → Controller |
| **MetalLB + LoadBalancer** | 裸机/本地 | 给 NodePort 一个 VIP（推荐本地用） |
| HostPort / hostNetwork | 边缘/单机 | Controller Pod 直贴节点端口 |

## 3. 部署（Helm，最快路径）

```bash
# 1. 添加仓库并安装
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx \
  -n ingress-nginx --create-namespace \
  --set controller.service.type=LoadBalancer \
  --set controller.service.annotations."metallb\.universe\.tf/address-pool"=default

# 2. 等待外部 IP
kubectl get svc -n ingress-nginx ingress-nginx-controller

# 3. 一个最小 Ingress 示例
kubectl apply -f - <<'EOF'
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: web
spec:
  ingressClassName: nginx
  rules:
  - host: app.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: web
            port:
              number: 80
EOF
```

- 本地/裸机没云 LB 时：`--set controller.service.type=NodePort` 或装 MetalLB。
- 验证：`curl -H "Host: app.example.com" http://<ingress-ip>/`。

## 4. 注解大全（ingress-nginx 特有能力）

Ingress 的**通用**能力有限（host/path/TLS），**丰富功能全靠注解**：

| 类别 | 注解 | 说明 |
|------|------|------|
| 重写 | `nginx.ingress.kubernetes.io/rewrite-target: /$2` | 去掉前缀路径再转发 |
| 路径捕获 | `nginx.ingress.kubernetes.io/use-regex: "true"` | 正则路径（capture group 配合 rewrite） |
| 限流 | `nginx.ingress.kubernetes.io/limit-rps: "10"` / `limit-connections` | 每 IP 速率/连接限制 |
| SSL 重定向 | `nginx.ingress.kubernetes.io/ssl-redirect: "true"` | 强制 HTTPS |
| 代理参数 | `nginx.ingress.kubernetes.io/proxy-connect-timeout` / `proxy-read-timeout` | 调整后端超时 |
| 跨域 | `nginx.ingress.kubernetes.io/enable-cors: "true"` + `cors-allow-origin` | 浏览器 CORS |
| 会话保持 | `nginx.ingress.kubernetes.io/affinity: cookie` | 粘性会话 |
| 认证 | `nginx.ingress.kubernetes.io/auth-type: basic` + `auth-secret` | 简单基础认证 |
| 灰度 | `nginx.ingress.kubernetes.io/canary: "true"` + `canary-weight: "10"` | 金丝雀（见 §6） |
| 白名单 | `nginx.ingress.kubernetes.io/whitelist-source-range: "10.0.0.0/8"` | IP 访问控制 |

### 4.1 rewrite-target 的经典坑

```yaml
# 前端访问 /api/v1/xxx → 后端期望 /v1/xxx（去掉 /api 前缀）
metadata:
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /$2
spec:
  rules:
  - host: app.example.com
    http:
      paths:
      - path: /api(/|$)(.*)     # 捕获第二个括号作为 $2
        pathType: ImplementationSpecific
        backend: {service: {name: api, port: {number: 8080}}}
```

- ⚠️ 用了 `rewrite-target` 时 path 必须用**正则 + ImplementationSpecific**，否则不会捕获组。
- 常见坑：不写 rewrite-target 时 Nginx 会把 `path` 原样传给后端（`proxy_pass` 不带 `location`），于是后端收到 `/api/v1/xxx` 而非 `/v1/xxx`。

## 5. TLS 与证书管理

```yaml
metadata:
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
  - hosts: [app.example.com]
    secretName: app-example-com-tls
  rules:
  - host: app.example.com
    ...
```

- **cert-manager**：自动签发/续期（Let's Encrypt / 内部 CA），证书存 Secret，Controller 挂载。
- 手动：先 `kubectl create secret tls <name> --cert=... --key=...`，再在 `tls.secretName` 引用。
- 强制 HTTPS：`ssl-redirect: "true"`（有 TLS 段时默认开启）；HTTP→HTTPS 由 `HSTS` 注解增强。

## 6. 金丝雀发布（canary）

用两个 Ingress 按权重分流（同一 host/path，其中一个标 canary）：

```yaml
# 主版本
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata: {name: web-main}
spec:
  ingressClassName: nginx
  rules:
  - host: app.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend: {service: {name: web-v1, port: {number: 80}}}
---
# 金丝雀（流量 10% → v2）
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: web-canary
  annotations:
    nginx.ingress.kubernetes.io/canary: "true"
    nginx.ingress.kubernetes.io/canary-weight: "10"
spec:
  ingressClassName: nginx
  rules:
  - host: app.example.com
    http:
      paths:
    - path: /
      pathType: Prefix
      backend: {service: {name: web-v2, port: {number: 80}}}
```

- `canary-weight` 按百分比；`canary-by-header` / `canary-by-cookie` 可按用户/请求头精准分流。
- 这是 Controller 级金丝雀，**与 Service Mesh**（[[concepts/Kubernetes Service Mesh]] §4）的权重路由是不同的实现路径。

## 7. 常见坑与排查

| 现象 | 原因 | 处理 |
|------|------|------|
| 访问返回 **404** | 后端 Service 端口/选择器不匹配；pathType 不匹配 | `kubectl get endpoints <svc>` 看是否有后端；`kubectl describe ingress` |
| 返回 **502** | 后端 Pod 没就绪（readiness 失败）或探针端口错 | 查 Pod readiness、`kubectl get endpoints` |
| 返回 **503** | 后端无可用端点；或 limit 触发 | 查 endpoints；看 controller 日志 |
| **308 永久重定向** | 有 TLS 段 + `ssl-redirect` 开启，HTTP 被重定向 HTTPS | 用 https 访问，或关 `ssl-redirect` |
| 路径**多/少了一段** | rewrite-target 没配或配错 | 检查 path 捕获组与 `rewrite-target` |
| **404 但 Ingress 正常** | `ingressClassName` 没写，或 Controller 没监听该 IngressClass | `kubectl get ingressclass`；确认 `ingressClassName` |
| **跨域失败** | CORS 注解没配 | 加 `enable-cors` + `cors-allow-origin` |
| 慢请求被切断 | `proxy-read-timeout` 默认 60s 太短 | 按业务调大 |

**排查命令**：

```bash
kubectl describe ingress web                      # 看规则与 controller 是否采纳
kubectl get endpoints <svc>                       # 后端是否真实存在
kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx   # controller 日志
kubectl exec -it <ingress-pod> -n ingress-nginx -- cat /etc/nginx/nginx.conf | grep web   # 看生成配置
```

## 8. 监控与扩展

- Controller 自带 Prometheus 指标（`/metrics`）：请求数、延迟、upstream 状态。
- Dashboard 化：Grafana 官方 ingress-nginx dashboard（[[concepts/可观测性工程]]）。
- 上游探活：健康检查由后端 **readinessProbe** 决定，Controller 只转发到 ready 的 Pod。

## 9. Ingress-nginx vs Gateway API

| 维度 | Ingress-nginx（Ingress API） | Gateway API |
|------|------------------------------|-------------|
| 资源 | Ingress + 大量注解 | GatewayClass / Gateway / HTTPRoute |
| 表达能力 | 靠注解（非标准） | 标准化的路由/策略字段 |
| 多实现 | 注解不可移植 | 跨实现可移植 |
| 演进 | 稳定但扩展靠注解 | 1.0 起成为方向，Controller 多已兼容 |

- 现状：ingress-nginx 已支持 Gateway API（作为其实现之一）；新项目可关注 Gateway API，但 Ingress + 注解仍是存量主流。

## 相关文档

- [[concepts/Kubernetes 网络模型]]
- [[concepts/Kubernetes Service Mesh]]
- [[concepts/Kubernetes 高可用与自愈]]
- [[entities/Helm 包管理实战]]
- [[entities/kubectl 与日常运维实战]]
- [[projects/k8s-kind-examples/README]]
- [[sources/Kubernetes 学习来源]]
