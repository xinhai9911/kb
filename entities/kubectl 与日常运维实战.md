---
title: kubectl 与日常运维实战
category: entities
tags: [kubernetes, kubectl, ops, debugging, troubleshooting, active]
created: 2026-08-12
updated: 2026-08-12
summary: >-
    kubectl 日常运维实战：资源操作三件套（get/describe/apply）、
    上下文管理、日志与 exec、常用速查命令表、故障排查分层
    （Pod/节点/控制面）、Pod 无法启动的 6 类经典问题定位、
    events 与条件解读、kubectl 高级用法（dry-run/JSONPath/label 选择器）。
base_confidence: 0.85
lifecycle: draft
---

# kubectl 与日常运维实战

> 运维 K8s 90% 的动作是**看清状态 → 定位偏差 → 声明修复**。掌握 `get/describe/logs/exec/apply` 就够应付日常。

## 1. 资源操作三件套

| 命令 | 作用 | 常见用法 |
|------|------|---------|
| `kubectl get` | 查看当前状态（快照） | `get pods -o wide` / `get all -n prod` |
| `kubectl describe` | 查看详细状态 + **Events** | `describe pod <name>`（排障第一手资料） |
| `kubectl apply` | 声明式变更 | `apply -f deploy.yaml` / `apply -f dir/` / `apply -k dir/` |
| `kubectl delete` | 删除 | `delete pod x --force`（慎用，跳过 finalizer） |
| `kubectl edit` | 就地编辑（修改即生效） | `edit deployment web` |

## 2. 常用速查表

```bash
# 资源与命名空间
kubectl get nodes,pods,svc,deployments -n <ns> -o wide
kubectl get ns
kubectl get events -n <ns> --sort-by=.lastTimestamp
kubectl get pod <name> -o yaml        # 看完整 spec/status

# 日志与交互
kubectl logs <pod> -f                 # 跟随日志
kubectl logs <pod> -c <container>     # 多容器 Pod 指定容器
kubectl logs --previous <pod>         # 看上一容器实例的日志（崩溃复盘）
kubectl exec -it <pod> -- sh          # 进 Pod 诊断

# 运维操作
kubectl rollout status deploy/<name>
kubectl rollout history deploy/<name>
kubectl rollout undo deploy/<name>    # 回滚
kubectl drain / cordon / uncordon <node>
kubectl scale deploy/<name> --replicas=5
kubectl top node / top pod            # 资源用量（需 metrics-server）
```

## 3. 上下文与多集群

```bash
kubectl config get-contexts
kubectl config use-context <name>
kubectl config current-context
kubectl config set-context --current --namespace=prod
```

- ⚠️ 每次操作前确认 context 与 namespace，误操作 `delete` 在 prod 上下文里是不可逆的。

## 4. 高级用法

```bash
# dry-run：不落盘预览
kubectl apply -f x.yaml --dry-run=server -o yaml

# JSONPath 过滤（脚本友好）
kubectl get pods -o jsonpath='{.items[*].metadata.name}'

# label 选择器（get/delete/scale 都支持）
kubectl get pods -l app=web,env=prod
kubectl delete pods -l app=old --grace-period=0

# 别名（日常推荐）
alias k='kubectl'
alias kgp='kubectl get pods -o wide'
alias kd='kubectl describe'
```

## 5. 故障排查分层

### 5.1 第一层：Pod 状态

| 状态 | 含义 | 常见原因 |
|------|------|---------|
| `Pending` | 还没调度/启动 | 资源不足、污点不容忍、PVC 绑定失败 |
| `ContainerCreating` | 正在创建 | 拉镜像慢/失败、CNI 问题、卷挂载失败 |
| `Running`（Ready 0/1） | 在跑但没就绪 | readiness 探针失败、端口错 |
| `CrashLoopBackOff` | 反复崩溃 | 启动命令错、配置错、探针误杀 |
| `ImagePullBackOff` | 镜像拉取失败 | 镜像名/标签错、私有仓库凭证、网络 |
| `Evicted` | 被驱逐 | 资源压力（内存/磁盘） |
| `Terminating` | 卡在删除 | finalizer 未清、volume 未卸载 |
| `Completed` / `Error` | Job 结束 | — |

### 5.2 定位套路（Pod 问题）

```
1. kubectl get pods -o wide         → 看 phase、节点
2. kubectl describe pod <name>      → 读 Events（最关键！）
3. kubectl logs <pod> -f / --previous  → 看应用日志
4. kubectl exec -it <pod> -- sh     → 进容器诊断（网络/配置）
5. kubectl get events -A --sort-by=.lastTimestamp
```

**典型场景速查**：

- **FailedScheduling**：Events 里给出原因——`Insufficient cpu/memory`、`didn't match node selector`、`tainted nodes`、PVC 未绑定。
- **CrashLoopBackOff**：`describe` 里 `Last State: Terminated Reason: Error/OOMKilled`；`logs --previous` 看上次崩溃输出。
- **ImagePullBackOff**：检查镜像名（含 tag）、`imagePullSecrets`、私有仓库地址可达性。
- **探针误杀**：`Restart Count` 一直涨、`kubectl describe` 显示探针失败 → 调 `initialDelaySeconds`/`failureThreshold`/超时。
- **readiness 失败但容器健康**：端口或路径不对；探针访问的端口没监听在 `0.0.0.0`。

### 5.3 第二层：节点 / 控制面

```bash
# 节点
kubectl get nodes -o wide            # Ready 状态、内部 IP
kubectl describe node <node>         # 污点、压力（MemoryPressure/DiskPressure）、可分配资源
kubectl get events -A | grep -i node
# 控制面组件（本机）
sudo systemctl status kubelet
sudo journalctl -u kubelet -f
kubectl get --raw /healthz           # API Server 健康
kubectl get componentstatuses        # 部分版本已弃用
```

- **Node NotReady**：先看节点上 kubelet 日志；网络（CNI）或容器运行时挂了常见。
- **API Server 慢/不可用**：看 etcd 健康（`etcdctl endpoint health`）、负载、证书过期（`kubeadm certs check-expiration`）。
- **证书过期**：kubeadm 集群 1 年默认——`kubeadm certs renew all` + 重启组件（这是生产最经典的隐性事故）。

## 6. 排障效率技巧

- **先 describe 后 logs**：describe 的 Events 往往直接给出根因，比猜日志快。
- **善用 `-o wide` / `-o yaml`**：yaml 里 status 是权威事实，别靠猜。
- **看事件要排序**：`--sort-by=.lastTimestamp`，倒序看最近发生的事。
- **多容器 Pod**：任何命令都带 `-c <container>`。
- **长期故障**：监控 + 审计日志（[[concepts/可观测性工程]]）比事后 describe 更可靠。

## 7. 常见误区

- ❌ 「`kubectl logs` 看不到东西 = 没日志」—— 可能日志打到了 stdout 之外、或容器已重启（用 `--previous`）。
- ❌ 「`kubectl delete pod` 就能解决 CrashLoop」—— 控制器会立刻重建，病根在镜像/配置/探针。
- ❌ 「只看 `kubectl get` 的 phase」—— 同一 phase 下可能探针在持续失败，必须看 conditions。
- ❌ 「`--force --grace-period=0` 随便用」—— 会跳过 finalizer，可能留下云资源/数据残留。

## 相关文档

- [[concepts/Kubernetes 高可用与自愈]]
- [[concepts/Kubernetes 工作负载与调度]]
- [[concepts/Kubernetes 声明式模型与控制器]]
- [[entities/Kubernetes 部署与工具链实战]]
- [[sources/Kubernetes 学习来源]]
