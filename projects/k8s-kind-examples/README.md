---
project: true
topic: Kubernetes kind 集群
stack: Docker + kind + kubectl + Helm
deps: docker、kind、kubectl、helm（见下文）
run: "`bash scripts/01-kind-create.sh`"
docs: "Kubernetes 技术全景综述 / Kubernetes 工作负载与调度 / Kubernetes 网络模型 / Ingress-Nginx 详解实战"
updated: 2026-08-12
---

# Kubernetes kind 集群示例工程（k8s-kind-examples）

本目录是一个**可一键运行**的本地 K8s 沙盒：用 [kind](https://kind.sigs.k8s.io/)（K8s in Docker）拉起一个
3 节点集群，部署一个带探针/ConfigMap/Ingress 的示例应用，并写脚本演示
**负载均衡 / 滚动更新 / readiness 摘流 / ConfigMap 更新**四大核心机制。

配套文档：[[synthesis/Kubernetes 技术全景综述]]、[[concepts/Kubernetes 工作负载与调度]]、
[[concepts/Kubernetes 网络模型]]、[[entities/Ingress-Nginx 详解实战]]。

## 目录结构

```
k8s-kind-examples/
├── app/
│   ├── app.py            # 最小 Flask 服务（/ /healthz /ready /version，支持 FAIL_READY）
│   ├── requirements.txt
│   └── Dockerfile
├── manifests/
│   ├── 01-configmap.yaml # 配置与代码解耦（GREETING / APP_VERSION）
│   ├── 02-deployment.yaml# 3 副本 + 三类探针 + 资源限制 + 非 root 安全上下文
│   ├── 03-service.yaml   # ClusterIP Service（稳定入口 + 负载均衡）
│   └── 04-ingress.yaml   # ingress-nginx 七层入口（rewrite 演示）
├── scripts/
│   ├── 01-kind-create.sh # 一键建集群 + 装 ingress-nginx + 部署 + 验证
│   ├── 02-scenarios.sh   # 演示负载均衡/滚动更新/readiness/ConfigMap
│   └── 03-kind-destroy.sh# 一键销毁
└── README.md
```

## 前置依赖

| 工具 | 用途 | 安装 |
|------|------|------|
| Docker | 容器运行时（kind 节点） | 见 Docker 官方 |
| [kind](https://kind.sigs.k8s.io/) | Docker 内建 K8s 集群 | `go install sigs.k8s.io/kind@latest` 或 brew/choco |
| kubectl | 操作集群 | `curl -LO .../kubectl` 或包管理器 |
| [helm](https://helm.sh/) | 装 ingress-nginx | 包管理器 / 官方脚本 |

> [!info] 平台说明
> Windows：用 **WSL2 + Docker Desktop（WSL2 后端）**，脚本在 WSL 的 bash 里运行。
> 国内网络：如镜像拉取慢，可在 `01-kind-create.sh` 前配置 Docker 镜像加速。

## 快速开始

```bash
bash scripts/01-kind-create.sh        # 一键：建集群 + 部署 + 验证
bash scripts/02-scenarios.sh          # 演示四大核心机制
bash scripts/03-kind-destroy.sh       # 销毁
```

### 验证 Ingress（手动）

```bash
INGRESS_PORT=$(kubectl get svc -n ingress-nginx ingress-nginx-controller \
  -o jsonpath='{.spec.ports[?(@.name=="http")].nodePort}')
NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[0].address}')

# 七层入口 + rewrite（/demo/ 前缀被去掉再转发到后端）
curl -H 'Host: demo.example.com' "http://$NODE_IP:$INGRESS_PORT/demo/"
```

## 脚本演示了什么

| 场景 | 脚本 | 对应文档 |
|------|------|---------|
| Service 负载均衡（Pod 名轮换） | 02-scenarios.sh 场景 1 | [[concepts/Kubernetes 网络模型]] §2 |
| 滚动更新（tag 变化 → 逐个替换） | 场景 2 | [[concepts/Kubernetes 高可用与自愈]] §3 |
| readiness 摘流（FAIL_READY=true 被摘出） | 场景 3 | [[concepts/Kubernetes 高可用与自愈]] §2 |
| ConfigMap 更新（改配置重建生效） | 场景 4 | [[concepts/Kubernetes 核心架构与组件]] §3.2 |

## 手动排查示例

```bash
kubectl get pods -n demo -o wide                 # 看 phase 与节点
kubectl describe pod -n demo -l app=web | tail   # 看 Events（排障第一手资料）
kubectl logs -n demo -l app=web                  # 看应用日志
kubectl get endpoints -n demo web                # 看 Service 后端是否就绪
kubectl get svc -n ingress-nginx                 # 看 Ingress 入口
```

## 常见坑

- **ingress 404**：Ingress 里 `ingressClassName: nginx` 是否匹配已装的 Controller；`kubectl describe ingress -n demo web` 看是否被采纳。
- **镜像 ImagePullBackOff**：本地注入的镜像需 `imagePullPolicy: IfNotPresent`；重新构建后记得重新 `kind load`。
- **NodePort 访问不通**：kind 的 worker 节点 IP 需从 `kubectl get nodes` 取；确认端口取自 ingress-nginx-controller。
- **镜像构建慢**：先用 `docker pull python:3.11-slim` 预热，或用 Docker 镜像加速。

## 相关文档

- [[synthesis/Kubernetes 技术全景综述]]
- [[concepts/Kubernetes 核心架构与组件]]
- [[concepts/Kubernetes 工作负载与调度]]
- [[concepts/Kubernetes 网络模型]]
- [[concepts/Kubernetes 高可用与自愈]]
- [[entities/Ingress-Nginx 详解实战]]
- [[entities/kubectl 与日常运维实战]]
- [[entities/Kubernetes 部署与工具链实战]]
