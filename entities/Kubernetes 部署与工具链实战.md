---
title: Kubernetes 部署与工具链实战
category: entities
tags: [kubernetes, deployment, kubeadm, k3s, minikube, kind, containerd, active]
created: 2026-08-12
updated: 2026-08-12
summary: >-
    Kubernetes 集群部署实战：本地开发（minikube/kind/k3s）与生产
    （kubeadm / 托管云 / 发行版）的选型对比、kubeadm 建集群全流程、
    容器运行时（containerd/CRI-O）配置、节点加入与移除、
    kubeconfig 管理、升级与维护、裸机 vs 云上的差异。
base_confidence: 0.85
lifecycle: draft
---

# Kubernetes 部署与工具链实战

> 部署方式决定你踩坑的深度。**本地练手与生产环境选型完全不同**，先看清目标再动手。

## 1. 部署方式选型

| 方式 | 用途 | 特点 |
|------|------|------|
| **minikube** | 本地单节点 | 简单、跨平台（Windows/macOS/Linux），内置 addons，适合初学者 |
| **kind**（K8s in Docker） | CI/本地多节点 | 容器当节点，秒级启停，适合测试 CI 流水线 |
| **k3s**（Rancher） | 边缘/轻量生产 | 单二进制、省资源、内置 containerd+flannel，IoT/边缘首选 |
| **kubeadm** | 生产/自建 | 官方标准安装工具，可扩展，最接近生产形态 |
| **托管 K8s**（EKS/GKE/AKS） | 生产（云） | 控制面免运维，但网络/存储/安全要按云规范 |
| **发行版**（RKE2/Talos/OpenShift） | 生产（裸机） | 集成了 CNI/CSI/运维组件，省心但学习成本在发行版 |

- **学习路径建议**：minikube/kind 入门 → kubeadm 建一套真实集群 → 再上云或发行版。
- 现有知识库里有 GitOps / CI-CD 例子（[[entities/CI_CD 流水线实战]]），kind 是跑这些的最佳沙盒。

## 2. 本地开发环境（5 分钟起）

### 2.1 minikube（推荐入门）

```bash
# 需先装 Docker
minikube start --driver=docker --cpus=4 --memory=8g
kubectl get nodes
minikube dashboard          # 打开 Web UI
minikube addons enable ingress    # 常用插件
minikube stop
```

- Windows 用 `--driver=hyperv` 或 Docker Desktop 的 WSL2 后端。
- 常见问题：资源不足（调大 --cpus/--memory）、`--image-mirror-country=cn` 加速（国内）。

### 2.2 kind（多节点沙盒）

```bash
kind create cluster --name dev --config - <<'EOF'
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
- role: worker
- role: worker
EOF
kind get clusters
kind delete cluster --name dev
```

- 最适合跑 CI：镜像通过 `kind load docker-image <img>` 直接注入，无需 registry。

### 2.3 k3d（k3s 的 Docker 版）

- 一句话：k3s in Docker，介于 minikube 与 kind 之间，轻量快速。

## 3. kubeadm 建生产集群（标准流程）

### 3.1 前置条件（每台节点）

- Linux 节点：CPU≥2、内存≥2G、**主机名唯一**、`/etc/hosts` 解析、`swapoff -a`（K8s 1.24+ 要求 swap 关闭，swap 支持除外）。
- 开启内核模块：`overlay`、`br_netfilter`，配置 `net.bridge.bridge-nf-call-iptables=1`。
- 安装 **containerd**（或 CRI-O）+ kubeadm/kubelet/kubectl（锁版本，如 `apt install kubeadm=1.29.x kubelet=... kubectl=...`）。

### 3.2 初始化控制面

```bash
# 控制面节点
kubeadm init \
  --apiserver-advertise-address=10.10.0.10 \
  --pod-network-cidr=10.244.0.0/16 \
  --control-plane-endpoint=10.10.0.10:6443

# 按提示配置 kubectl
mkdir -p $HOME/.kube && sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config

# 安装 CNI（以 Calico 为例）
kubectl apply -f https://raw.githubusercontent.com/projectcalico/calico/.../calico.yaml

# 工作节点加入（kubeadm init 输出的命令）
kubeadm join 10.10.0.10:6443 --token <token> --discovery-token-ca-cert-hash sha256:<hash>
```

- `--pod-network-cidr` 必须与 CNI 插件要求的网段一致（Calico 默认 192.168.0.0/16；Flannel 10.244.0.0/16）。
- 高可用：多控制面节点 + `--control-plane-endpoint`（VIP/LB）+ etcd 奇数副本（[[concepts/Kubernetes 高可用与自愈]]）。
- 验证：`kubectl get nodes`、`kubectl get pods -n kube-system`。

### 3.3 常见坑

- 节点 NotReady：CNI 没装 / CNI 网段与 `--pod-network-cidr` 不一致 / containerd 的 `config.toml` 没配 `SystemdCgroup=true`。
- join 失败 token 过期：`kubeadm token create --print-join-command` 重新生成。
- 升级顺序：先 `kubeadm upgrade plan` 看版本 → 控制面 → 工作节点 → CNI 等 addon。

## 4. 容器运行时配置（containerd）

```toml
# /etc/containerd/config.toml
[plugins."io.containerd.grpc.v1.cri"]
  systemd_cgroup = true        # 与 kubelet 的 cgroup driver 一致（重要！）
  [plugins."io.containerd.grpc.v1.cri".registry.mirrors]
    [plugins."io.containerd.grpc.v1.cri".registry.mirrors."docker.io"]
      endpoint = ["https://mirror.gcr.io"]   # 国内镜像加速
```

- kubelet 的 `--cgroup-driver` 必须与 containerd 的 `systemd_cgroup` 一致，否则 kubelet 报错。
- `ctr` 是 containerd 的命令行工具；`nerdctl` 提供类 docker 体验。

## 5. kubeconfig 与上下文管理

```bash
kubectl config get-contexts                  # 列出上下文
kubectl config use-context kind-dev          # 切换
kubectl config set-context --current --namespace=prod   # 默认命名空间
kubectl config view                          # 查看配置（注意不要泄露证书）
```

- 多集群（云上 + 本地 + kind）用 `kubectl config rename-context` 起清晰名字。
- 生产建议：不同环境用不同 kubeconfig 文件，`KUBECONFIG` 环境变量合并。

## 6. 裸机 vs 云上的差异

| 项 | 裸机/本地 | 云上（EKS/GKE/AKS） |
|----|-----------|---------------------|
| 控制面 | 自建 HA（kubeadm + keepalived/HAProxy/kube-vip） | 云托管（免运维） |
| LoadBalancer | MetalLB（BGP/L2） | 云 LB（自动创建） |
| Ingress | 自装 ingress-nginx | 云 LB + ingress |
| 存储 | local-path / NFS / 自建 CSI | 云磁盘/文件存储 CSI |
| 节点池 | 手动加/删 | 托管节点组自动扩缩容（Cluster Autoscaler） |
| 升级 | 手动 kubeadm 升级 | 云控制台一键 |

## 7. 维护操作速查

```bash
# 排空/维护/恢复节点
kubectl drain <node> --ignore-daemonsets --delete-emptydir-data
kubectl uncordon <node>
# 查看证书/集群健康
kubeadm certs check-expiration
kubectl get --raw /healthz
kubectl get cs        # 组件状态（部分版本已废弃，用健康端点）
```

## 8. 常见误区

- ❌ 「minikube 配置 = 生产配置」—— 生产要考虑 HA、网络策略、存储、安全。
- ❌ 「kubeadm init 一把梭」—— 前置内核参数/运行时配置漏掉就是 NotReady 连串问题。
- ❌ 「装了 CNI 就行」—— CNI 网段与 pod-network-cidr 要一致，Flannel 不支持 NetworkPolicy。
- ❌ 「swap 关了就行，不用配 cgroup」—— kubelet 与 containerd 的 cgroup driver 必须一致。

## 相关文档

- [[concepts/Kubernetes 核心架构与组件]]
- [[concepts/Kubernetes 网络模型]]
- [[concepts/Kubernetes 高可用与自愈]]
- [[entities/kubectl 与日常运维实战]]
- [[entities/Helm 包管理实战]]
- [[sources/Kubernetes 学习来源]]
