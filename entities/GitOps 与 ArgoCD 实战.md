---
title: GitOps 与 ArgoCD 实战
category: entities
tags: [gitops, argocd, flux, cd, kubernetes, declarative, sync, active]
created: 2026-08-12
updated: 2026-08-17
summary: >-
    GitOps 与 ArgoCD 实战：Git 为唯一事实源、自动同步声明式交付。对比 CI/CD（[[concepts/CI_CD与测试策略]]）、
    声明式哲学（[[concepts/Kubernetes 声明式模型与控制器]]）；ArgoCD 的 Application/AppProject、sync/health/diff、
    PR 预览、回滚；ApplicationSet 多应用生成、多集群管理、渐进式交付（Argo Rollouts canary/blue-green）；
    Flux 对照；与 [[synthesis/容器分布式技术全景综述]] 的衔接（Git 里即集群期望状态）。
base_confidence: 0.85
lifecycle: review
sources: []
---

# GitOps 与 ArgoCD 实战

> 原理见 [[concepts/Kubernetes 声明式模型与控制器]]（声明式 + 控制循环）。本文给 GitOps 的落地模式。

---

## 1. 什么是 GitOps

**Git 仓库 = 集群期望状态的唯一事实源**。一个控制器持续把「Git 里的 manifests」同步到「集群实际状态」，漂移自动修复——和 K8s 自身的 reconcile 循环同构，只是把「期望」放在 Git 而非 etcd。

| 对比 | 传统 CI/CD 推式 | GitOps 拉式 |
|---|---|---|
| 触发 | 流水线 `kubectl apply` 推到集群 | 集群内控制器**拉** Git 并同步 |
| 事实源 | 流水线脚本 | Git 仓库 |
| 回滚 | 重跑旧流水线 | `git revert` + 自动同步 |
| 凭证 | CI 需集群 kubeconfig | 集群内控制器有凭据，CI 无需 |

> [!note] 与 K8s 哲学同源
> K8s 是「声明式 + 控制循环」（[[synthesis/Kubernetes 技术全景综述]]）；GitOps 把同一思想**外推到 Git**——Git 是「期望」的存放地，集群是「现状」，ArgoCD 是跨两者的调和器。

---

## 2. ArgoCD 核心概念

| 概念 | 含义 |
|---|---|
| **Application** | 一个被同步的资源集（指向某 Git 路径 + 某集群/Namespace） |
| **AppProject** | 多租户隔离：限制可部署的集群/命名空间/Repo |
| **sync** | 把 Git 状态应用到集群；可自动或手动（PR 评审后） |
| **health** | 资源健康度（Pod Ready？CRD 就绪？） |
| **diff** | Git 期望 vs 集群现状的差异展示 |
| **sync wave** | 控制同步顺序（如先建 CRD 再建依赖它的资源） |

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: web-prod
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/org/gitops.git
    path: apps/web/overlays/prod     # Kustomize/Helm 路径
    targetRevision: main
  destination:
    server: https://kubernetes.default.svc
    namespace: prod
  syncPolicy:
    automated: { prune: true, selfHeal: true }   # 自动同步 + 漂移自愈 + 删孤儿
```

> `selfHeal: true` 让「有人手改集群」时被 Git 覆盖回期望——这正是 GitOps 的纪律。

---

## 3. 工作流（PR 预览 + 合并即上线）

```
开发者提 PR → ArgoCD 预览 Application 显示 diff → 评审合并
   │
   ▼ 合并到 main
ArgoCD 检测到 Git 变更 → 自动 sync → 集群收敛到新期望
```

- **回滚**：`git revert` 提交 → ArgoCD 自动同步回旧版本（比重跑流水线稳）。
- **密钥**：不放 Git 明文；用 Sealed Secrets / External Secrets / Vault（[[concepts/容器安全]]）。

---

## 4. ApplicationSet（多应用生成）

当需要为多个环境/微服务批量创建 Application 时，用 `ApplicationSet` 自动生成：
```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: web-apps
spec:
  generators:
    - list:
        elements:
          - env: dev
            cluster: https://dev-cluster
          - env: staging
            cluster: https://staging-cluster
          - env: prod
            cluster: https://prod-cluster
  template:
    metadata:
      name: 'web-{{env}}'
    spec:
      project: default
      source:
        repoURL: https://github.com/org/gitops.git
        path: 'apps/web/overlays/{{env}}'
      destination:
        server: '{{cluster}}'
        namespace: '{{env}}'
```

> 一个 ApplicationSet 自动生成 dev/staging/prod 三个 Application，新增环境只需加一个 element。

---

## 5. 多集群管理

ArgoCD 可注册多个集群（`argocd cluster add <context>`），一个 ArgoCD 实例同步多个集群：
- **集群注册**：`argocd cluster add` 写入 ServiceAccount + kubeconfig。
- **Application 指定目标**：`spec.destination.server` 指向不同集群。
- **AppProject 隔离**：限制团队只看到/部署自己的集群和命名空间。

---

## 6. Flux（对照）

Flux 是 CNCF 另一 GitOps 实现，理念相同，更「K8s 原生」：用 `GitRepository`/`Kustomization` 等 CRD 声明同步，体积小、与 controller-runtime 生态一致。ArgoCD 偏「带 UI 的平台」，Flux 偏「轻量工具集」。

| 对比 | ArgoCD | Flux |
|---|---|---|
| UI | 内置 Web UI | 无（Kubernetes 原生 CRD） |
| 多集群 | 强（ApplicationSet + UI） | 需多实例或 Rancher 集成 |
| 生态 | 大、社区活跃 | 与 controller-runtime 深度集成 |
| 渐进式交付 | 需配合 Argo Rollouts | Flux + Flagger 内置 |

---

## 7. 渐进式交付（Progressive Delivery）

GitOps 解决「怎么部署」，渐进式交付解决「怎么安全地发布」：
- **Canary**：新版本先接 5% 流量，指标正常再逐步扩大到 100%。
- **Blue-Green**：新旧版本并行，流量一次性切换。
- **工具**：Argo Rollouts（ArgoCD 生态）或 Flagger（Flux 生态），与 Prometheus 联动判断指标。

```yaml
# Argo Rollouts Canary 示例
apiVersion: argoproj.io/v1alpha1
kind: Rollout
spec:
  strategy:
    canary:
      steps:
        - setWeight: 5       # 5% 流量
        - pause: {duration: 5m}
        - setWeight: 20
        - pause: {duration: 5m}
        - setWeight: 100
```

---

## 8. 衔接

- 声明式基础：[[concepts/Kubernetes 声明式模型与控制器]]、[[synthesis/Kubernetes 技术全景综述]]
- 交付物是容器化应用：[[concepts/容器原理与运行时]]、[[synthesis/容器分布式技术全景综述]]
- 与传统 CI 分工：[[concepts/CI_CD与测试策略]]（CI 构建镜像，GitOps 负责部署）
- 安全：[[concepts/Kubernetes 安全模型]]、[[concepts/容器安全]]
- 基础设施层：[[concepts/基础设施即代码 Terraform]]（Terraform 拉集群，GitOps 部署工作负载）

---

## 参考链接

**库内双链**
- [[concepts/Kubernetes 声明式模型与控制器]] — GitOps 的 K8s 内因
- [[concepts/CI_CD与测试策略]] — CI 与 GitOps 的边界
- [[synthesis/Kubernetes 技术全景综述]]、[[synthesis/容器分布式技术全景综述]] — 编排全景
- [[concepts/容器安全]] — 密钥不入 Git

**外部资料**
- ArgoCD 官方文档（argocd.io）
- Flux 文档（fluxcd.io）
- GitOps 原则（Weaveworks / CNCF GitOps WG）
