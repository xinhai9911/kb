---
title: Kubernetes 高可用与自愈
category: concepts
tags: [kubernetes, ha, self-healing, probe, rolling-update, etcd, active]
created: 2026-08-12
updated: 2026-08-12
summary: >-
    Kubernetes 高可用与自愈机制：探针（liveness/readiness/startup）、
    控制器自愈（容器/节点/状态级）、滚动更新与回滚、PodDisruptionBudget、
    控制面 HA（API Server 多副本 + etcd 集群 + 负载均衡）、
    etcd 备份恢复与 defrag、多集群与容灾、故障排查思路。
base_confidence: 0.87
lifecycle: draft
---

# Kubernetes 高可用与自愈

> **高可用不是「部署了 K8s 就自动有」**。K8s 提供机制，但拓扑、副本数、策略、备份都要你自己配。
> 分层理解：容器级自愈（kubelet）→ 应用级自愈（控制器）→ 节点级自愈（控制面）→ 集群级容灾。

## 1. 自愈的三个层次

| 层次 | 谁负责 | 自愈动作 |
|------|--------|---------|
| 容器崩溃 | kubelet | 按 restartPolicy 重启容器 |
| Pod 被删/节点故障 | ReplicaSet 控制器 | 在别的节点重建 Pod |
| 节点下线 | Node 控制器 + 调度器 | 驱逐 Pod 并重新调度 |
| 控制面组件挂 | systemd + HA 拓扑 | 多副本 + 负载均衡自动接管 |

## 2. 探针（Probes）—— 判断「健不健康」

三种探针，作用完全不同，别混用：

| 探针 | 判断 | 失败后果 |
|------|------|---------|
| **livenessProbe** | 进程还活着吗 | 重启容器（杀无赦） |
| **readinessProbe** | 能接流量吗 | 从 Service 后端摘除（不重启） |
| **startupProbe** | 启动完成了吗 | 未完成前不执行 liveness/readiness（保护慢启动应用） |

```yaml
livenessProbe:
  httpGet: {path: /healthz, port: 8080}
  initialDelaySeconds: 5
  periodSeconds: 10
  timeoutSeconds: 1
  failureThreshold: 3      # 连续失败 3 次才判死
readinessProbe:
  httpGet: {path: /ready, port: 8080}
  periodSeconds: 5
```

- 实现方式：`httpGet` / `tcpSocket` / `exec`（命令退出码）。
- 常见坑：探针路径返回 500 会被判不健康 → 反复重启；探针太激进（period 过短）打爆应用。

## 3. 滚动更新与回滚

### 3.1 滚动更新的可靠性参数

```yaml
spec:
  replicas: 5
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1        # 最多多出 1 个新副本
      maxUnavailable: 1  # 最多同时停 1 个旧副本
  minReadySeconds: 10     # 新副本 ready 后保持 10s 才算稳定
```

- `minReadySeconds` 防止「刚 ready 又崩」被误认为成功。
- **更新暂停**：`kubectl rollout pause`（金丝雀手动放量）；`resume` 恢复。
- 回滚：`kubectl rollout undo deployment/<name>`（回上一版）或 `--to-revision` 指定版本；历史版本 `--history-limit` 控制。

### 3.2 金丝雀 / 蓝绿

- **金丝雀**：Deployment 加 `rollout pause` 或拆两个 Deployment 按比例引流（配合 Ingress 权重 / Argo Rollouts）。
- **蓝绿**：两套环境 + 流量切换（Ingress 或 Service 切换）。

## 4. PodDisruptionBudget（PDB）—— 自愿中断保护

- 定义「自愿中断（voluntary disruption）」时最少保留多少副本：
  - 节点维护（`kubectl drain`）
  - 集群升级、descheduler、驱逐

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata: {name: web-pdb}
spec:
  minAvailable: 2        # 或 maxUnavailable: 1
  selector: {matchLabels: {app: web}}
```

- 用途：保证**集群升级/节点维护**时核心服务仍有可用副本。
- ⚠️ PDB 只保护「自愿中断」，不保护节点宕机等非自愿中断。

## 5. 控制面高可用（HA）

```
        VIP / LB
           │
   ┌───────┼───────┐
 apiserver  apiserver  apiserver   （无状态，多个）
   │        │        │
   └─── etcd 集群 ───┘            （3/5 节点，Raft 多数派）
        scheduler ×3（选主，active-standby）
   controller-manager ×3（选主，active-standby）
```

- **API Server**：无状态可水平扩展，前端用 VIP/LB 分发。
- **etcd**：奇数节点（3/5），**Raft 多数派**（对照 [[concepts/分布式系统基础]]）；网络分区下少数派只读拒绝写。
- **Scheduler / Controller-manager**：多副本但**只有 leader 干活**（基于 etcd 租约选主，`--leader-elect`）。
- 裸机部署 HA：keepalived/HAProxy 或 kube-vip；云上可用云 LB。

## 6. etcd 运维要点

- **备份**：etcd 快照（`etcdctl snapshot save`）→ 定期传到异地；`restore` 恢复。
- **容量**：`--quota-backend-bytes`（默认 2GB）；watch 事件积压、key 太多会撑爆。
- **defrag**：频繁更新导致存储碎片 → `etcdctl defrag`（在线/离线）。
- 冷备份策略：**etcd + 对象级备份**（数据库用 Velero 等）双保险。

## 7. 多集群与容灾

| 维度 | 手段 |
|------|------|
| 区域容灾 | 多集群（每个可用区一个集群）+ 跨集群流量（Global LoadBalancer） |
| 数据容灾 | 数据库跨区复制 + 卷快照异地；etcd 备份异地 |
| 配置容灾 | GitOps（ArgoCD）从 Git 声明一键重建 |
| 联邦 | KubeFed / 各厂商多集群管理（一般不直接用联邦，用 GitOps 更简单） |

## 8. 故障排查思路（先看状态再动手）

```
Pod 不 Ready
  ├─ kubectl get pods -o wide          （看所在节点/phase）
  ├─ kubectl describe pod <name>       （看 Events：拉镜像失败/调度失败/OOMKilled…）
  ├─ kubectl logs <name> -f            （看应用日志；多容器用 -c）
  ├─ kubectl exec -it <name> -- sh     （进去诊断）
  └─ kubectl get events --sort-by=.lastTimestamp
节点异常
  ├─ kubectl get nodes -o wide         （Ready 状态）
  ├─ kubectl describe node <node>      （看污点/资源压力）
  └─ systemctl status kubelet          （节点上查 kubelet）
```

- 常见定位：**调度失败**（Events 的 FailedScheduling）→ 资源/污点/亲和；**CrashLoopBackOff** → 探针/启动参数；**ImagePullBackOff** → 镜像名/凭证。
- 完整调试详见 [[entities/kubectl 与日常运维实战]]。

## 9. 常见误区

- ❌ 「单副本部署也叫高可用」—— 副本数 <2 + 无反亲和 = 节点一挂全挂。
- ❌ 「readiness 挂了就重启」—— readiness 只摘流量不重启；要重启用 liveness。
- ❌ 「PDB 能防止宕机丢副本」—— PDB 只管自愿中断；节点宕机得靠反亲和 + 多副本。
- ❌ 「etcd 3 副本就行，不用备份」—— 副本防故障不防误删/灾难，备份是底线。

## 来源

- [[sources/Kubernetes 学习来源]]

## 相关文档

- [[concepts/Kubernetes 工作负载与调度]]
- [[concepts/Kubernetes 声明式模型与控制器]]
- [[concepts/分布式系统基础]]
- [[entities/kubectl 与日常运维实战]]
- [[entities/Kubernetes 部署与工具链实战]]
