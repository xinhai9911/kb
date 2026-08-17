---
title: etcd 与 Raft 共识实战
category: concepts
tags: [etcd, raft, consensus, kubernetes, distributed, key-value, active]
created: 2026-08-17
updated: 2026-08-17
summary: >-
    etcd 与 Raft 共识实战：etcd 作为 K8s 唯一事实源的角色、Raft 共识算法详解（Leader 选举/
    日志复制/成员变更）、etcd 数据模型（MVCC/revision/lease）、性能调优（心跳/选举超时/
    快照策略）、备份恢复与灾难恢复、常见故障模式（脑裂/网络分区/磁盘慢）。
    衔接 [[concepts/Kubernetes 核心架构与组件]]、[[concepts/分布式系统基础]]、[[concepts/Go 运行时与并发模型]]。
base_confidence: 0.85
lifecycle: draft
sources: []
---

# etcd 与 Raft 共识实战

> etcd 是 K8s 的「大脑」——所有集群状态都存在 etcd 里。etcd 挂了 = 集群不可用。
> 理解 etcd，等于理解 K8s 的「状态存储层」与「分布式一致性」。见 [[synthesis/Kubernetes 技术全景综述]]。

---

## 1. etcd 在 K8s 中的角色

```
kubectl ──▶ kube-apiserver ──▶ etcd（唯一事实源）
                                    │
                          所有资源的增删改查
                          （Pod/Service/ConfigMap/...）
```

- **唯一事实源**：K8s 不直接查 etcd 之外的任何存储。
- **Watch 机制**：apiserver 通过 watch 监听 etcd 变更，触发控制器 reconcile。
- **高可用**：3 或 5 节点集群，Raft 保证强一致（容忍 (n-1)/2 节点故障）。

---

## 2. Raft 共识算法

### 核心角色

| 角色 | 职责 |
|------|------|
| **Leader** | 接收所有写请求，复制日志到 Follower，心跳保活 |
| **Follower** | 接收 Leader 日志，投票选举 |
| **Candidate** | 选举过渡状态：Follower 超时未收心跳 → 变 Candidate → 发起投票 |

### Leader 选举流程

```
Follower A (超时未收心跳)
  │  变 Candidate，任期(Term)+1
  │  向所有节点发 RequestVote
  ▼
B 收到请求 → 检查：Term 更大 + 日志更新 → 投票给 A
C 收到请求 → 检查：已投票给 B → 拒绝
  │
  │  A 收到多数票 (≥ N/2+1)
  ▼
A 成为新 Leader，开始发心跳
```

### 日志复制

```
Client ──写──▶ Leader
               │  追加到本地日志
               │  发 AppendEntries 给所有 Follower
               ▼
Follower 写入日志 → 回复 ACK
               │
               │  Leader 收到多数 ACK
               ▼
Commit → 应用到状态机 → 返回客户端
```

> [!note] 日志 = 重放
> Raft 的核心思想：只要日志一致，状态机就一致。崩溃后从最后快照 + 后续日志重放即可恢复。

---

## 3. etcd 数据模型

### MVCC 与 Revision

etcd 用 **MVCC**（多版本并发控制，[[concepts/关系型数据库内核]] 同类思路）：
- 每次写操作递增全局 `revision`。
- Key 的每个版本带 `mod_revision`，可按版本查询历史。
- **Compact**（压缩）：删除旧版本，释放空间。

```
Key "pod/nginx"
  rev=1: Create       → value={status: pending}
  rev=2: Update       → value={status: running}
  rev=3: Delete       → (tombstone)
```

### Lease（租约）

类似 Redis 的 TTL（[[concepts/Redis 缓存与数据结构]]），etcd 的 Lease 用于：
- **自动过期**：Lease 到期 → 关联的 key 自动删除。
- **Keep-alive**：客户端定期续约，失联则 key 过期。
- K8s 用 Lease 做心跳：kubelet 续约 Node lease，超时则 Node 被标记 NotReady。

---

## 4. 性能调优

| 参数 | 默认值 | 建议 | 说明 |
|------|--------|------|------|
| `heartbeat-interval` | 100ms | 100-300ms | Leader 发心跳间隔 |
| `election-timeout` | 1000ms | 1000-3000ms | Follower 等多久没心跳变 Candidate |
| `snapshot-count` | 10000 | 5000-20000 | 多少次事务后触发快照 |
| `quota-backend-bytes` | 2GB | 4-8GB | 后端存储上限（超了要 compact） |

> [!warning] 磁盘是瓶颈
> etcd 对磁盘延迟极其敏感（<10ms）。用 SSD/NVMe，避免与高 IO 服务共盘。

---

## 5. 备份与灾难恢复

```bash
# 备份（生产必做）
ETCDCTL_API=3 etcdctl snapshot save /backup/etcd-$(date +%Y%m%d).db \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/etcd/ca.crt \
  --cert=/etc/etcd/server.crt \
  --key=/etc/etcd/server.key

# 恢复（灾难时）
etcdctl snapshot restore /backup/etcd-snapshot.db \
  --data-dir=/var/lib/etcd-restored
```

- **备份频率**：至少每小时，关键集群每 15 分钟。
- **跨地域备份**：备份文件存 S3/GCS + 异地副本。

---

## 6. 常见故障模式

| 故障 | 表现 | 处理 |
|------|------|------|
| **Leader 不可用** | apiserver 读写超时 | 等待自动选举（通常 3-5s）；检查磁盘/网络 |
| **磁盘慢** | 心跳丢失 → 频繁选举 | 换 SSD；检查 IO 争用 |
| **网络分区** | 少数派节点失联 | Raft 保证多数派一致，少数派拒绝服务 |
| **存储满** | 写入失败 | compact + defrag；扩容 quota |
| **脑裂** | 不会发生 | Raft 协议保证（多数派才选 Leader） |

---

## 7. 衔接

- K8s 架构：[[concepts/Kubernetes 核心架构与组件]]
- 分布式基础：[[concepts/分布式系统基础]]（CAP/Raft/Paxos）
- Go 运行时：[[concepts/Go 运行时与并发模型]]（etcd 全是 Go 写的）
- 存储：[[concepts/存储栈与io_uring]]
- 安全：[[concepts/Kubernetes 安全模型]]（etcd 加密/访问控制）

---

## 参考链接

**库内双链**
- [[concepts/Kubernetes 核心架构与组件]] — etcd 在 K8s 中的位置
- [[concepts/分布式系统基础]] — Raft/Paxos 共识理论
- [[concepts/Go 运行时与并发模型]] — etcd 的 Go 并发模型
- [[concepts/关系型数据库内核]] — MVCC 对照
- [[concepts/Redis 缓存与数据结构]] — Lease vs TTL 对照

**外部资料**
- etcd 官方文档（etcd.io/docs）
- Raft 论文（In Search of an Understandable Consensus Algorithm）
- 《etcd from Scratch》— etcd 内部实现
- K8s etcd 运维指南（kubernetes.io/docs/tasks/administer-cluster/configure-upgrade-etcd）
