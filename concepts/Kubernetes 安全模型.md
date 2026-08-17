---
title: Kubernetes 安全模型
category: concepts
tags: [kubernetes, security, rbac, serviceaccount, networkpolicy, secret, admission, active]
created: 2026-08-12
updated: 2026-08-12
summary: >-
    Kubernetes 安全纵深：认证（客户端证书/Token）、授权（RBAC 的
    Role/ClusterRole/Binding）、ServiceAccount 与自动挂载、
    Pod 安全上下文与 Pod Security Standards（PSS）、Secret 存储
    与加密（KMS）、NetworkPolicy 微隔离、准入控制（Webhook）、
    镜像与供应链安全、运行时安全（Seccomp/AppArmor/SELinux）。
base_confidence: 0.87
lifecycle: draft
---

# Kubernetes 安全模型

> K8s 安全是**纵深防御**：认证（你是谁）→ 授权（你能做什么）→ 准入（策略是否允许）→ 容器运行时加固。
> 安全边界不只是在「API 层」，还有网络微隔离与节点内核隔离。
> 「容器运行时加固」的内核机制（Capabilities/seccomp/AppArmor/Rootless/镜像供应链）见 [[concepts/容器安全]]。

## 1. 认证（Authentication）

| 方式 | 说明 |
|------|------|
| 客户端证书（X.509） | kubeconfig 里的 client-cert，kubelet 与管理员常用 |
| 静态 Token / ServiceAccount Token | 程序化访问 |
| OIDC / Webhook | 对接企业 SSO / 自定义认证 |
| 匿名访问（仅集群内有限情况） | 通常关闭 |

- 认证只回答「你是谁」，**不决定权限**；权限由 RBAC 决定。

## 2. 授权：RBAC（最核心）

### 2.1 四个对象

| 对象 | 作用域 | 含义 |
|------|--------|------|
| **Role** | Namespace | 某个命名空间内的权限集合 |
| **ClusterRole** | 全集群 | 集群级权限（可跨命名空间复用） |
| **RoleBinding** | Namespace | 把 Role/ClusterRole 绑给用户/SA/组 |
| **ClusterRoleBinding** | 全集群 | 集群级绑定 |

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata: {namespace: prod, name: pod-reader}
rules:
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list", "watch"]
---
kind: RoleBinding
metadata: {namespace: prod, name: read-pods}
subjects:
- kind: User
  name: alice
  apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: Role
  name: pod-reader
  apiGroup: rbac.authorization.k8s.io
```

- **verbs**：get/list/watch/create/update/patch/delete/deletecollection…
- **resources** 支持子资源：`pods/exec`、`pods/log`、`deployments/scale`。
- 授权失败返回 **403 Forbidden**；`kubectl auth can-i` 可自测。

### 2.2 最小权限原则

- 给应用只分配所需资源的只读/最小 verbs。
- 常见建议：**不直接给用户 cluster-admin**；用 `kubectl create token` 创建短期令牌给 CI。

## 3. ServiceAccount（应用身份）

- Pod 内进程用 **ServiceAccount** 作为身份访问 API Server（不是普通用户）。
- 每个 Namespace 默认有 `default` SA；**令牌默认自动挂载**到 `/var/run/secrets/kubernetes.io/serviceaccount`。
- 生产建议：为每个应用建独立 SA + 最小权限 RBAC；1.24+ 默认绑定**短期 Token**（1h），过期自动刷新。
- 自动挂载（`automountServiceAccountToken: false`）可关，减少暴露面。

## 4. Secret 与配置安全

### 4.1 Secret 类型

- `Opaque`（通用键值）、`kubernetes.io/dockerconfigjson`（镜像拉取凭证）、`kubernetes.io/tls`（证书）、`kubernetes.io/basic-auth` 等。
- Secret 体积上限 **1MB**；不适合存大文件。

### 4.2 Secret 的真相与常见误解

- ⚠️ Secret **只是 base64 编码，不是加密**！`kubectl get secret -o yaml` 就能看到明文。
- etcd 默认明文存储 → 生产必须 **KMS 加密**（`EncryptionConfiguration` + 云 KMS）。
- 最小暴露：不直接挂整卷，用 `secretKeyRef` 引用单个键；配合 RBAC 限制 secret 读取。
- 轮换：改 Secret → 重建 Pod 生效（挂载文件有 ~1min 延迟刷新）。

## 5. 容器与 Pod 安全上下文（securityContext）

| 字段 | 作用 |
|------|------|
| `runAsNonRoot` | 拒绝以 root 运行（强烈建议 true） |
| `runAsUser/Group` | 指定 UID/GID |
| `readOnlyRootFilesystem` | 根文件系统只读（写临时用 emptyDir） |
| `capabilities.drop: [ALL]` | 丢弃所有 Linux 权限（再按需 add） |
| `allowPrivilegeEscalation: false` | 禁止提权 |
| `privileged: false` | 禁止特权容器 |

- **基础镜像里应建非 root 用户**，配合 `runAsNonRoot` 形成双保险。

## 6. Pod Security Standards（PSS）

官方三级策略（准入层面执行）：

| 级别 | 含义 |
|------|------|
| **Privileged** | 不受限制（系统组件级别） |
| **Baseline** | 默认安全基线（禁用特权、hostPath、hostNetwork、root 提权等） |
| **Restricted** | 最严格（非 root、只读根文件系统、丢弃 ALL capabilities 等） |

- 落地：`PodSecurityAdmission`（内置，用 namespace label `pod-security.kubernetes.io/enforce: restricted` 标注）。
- 替代/增强：准入 Webhook 工具（Kyverno / OPA Gatekeeper）。

## 7. 准入控制（Admission Control）

```
认证 → 授权 → ──准入──→ etcd
            MutatingAdmission   （改请求：默认值、注入 sidecar）
            ValidatingAdmission （拦请求：校验、策略）
            （Webhook 可自定义）
```

- 内置插件：`NamespaceLifecycle`、`LimitRanger`、`ResourceQuota`、`PodSecurity`…
- 自定义：**MutatingWebhookConfiguration / ValidatingWebhookConfiguration**——策略引擎（Kyverno/Gatekeeper）都建在此之上。

## 8. 网络隔离（NetworkPolicy）

- 详见 [[concepts/Kubernetes 网络模型]]。生产建议：**默认拒绝 + 按需放行**。
- 需要 CNI 支持（Calico/Cilium）；Flannel 不支持。

## 9. 供应链与镜像安全

- **镜像来源**：只从可信 Registry 拉取；`imagePullSecrets` 控制私有镜像。
- **签名验证**：Sigstore / cosign 验签；`ImagePolicyWebhook` 强制策略。
- **扫描**：Trivy / Grype 扫描镜像漏洞（CI 阶段做）。
- **运行时安全**：Seccomp / AppArmor / SELinux Profile 限制系统调用；Falco（eBPF 运行时告警，[[entities/eBPF 安全工具]]）。

## 10. 最小加固清单（生产必做）

1. 关闭匿名访问，启用严格认证。
2. RBAC 最小权限 + 独立 SA + 短期 Token。
3. Secret 用 KMS 加密，etcd 不存明文。
4. Pod 用 **restricted** 或 baseline 策略（非 root、只读根、丢 capability）。
5. 默认拒绝的 NetworkPolicy。
6. 镜像签名 + 漏洞扫描 + 只拉可信源。
7. 启用审计日志（Audit Logging），记录敏感操作。
8. 升级补丁：控制面与节点及时升级。

## 11. 常见误区

- ❌ 「Secret 是加密的」—— 只是 base64，必须 KMS 加密才安全。
- ❌ 「RBAC 配了 Role 就能用」—— 还要 RoleBinding 绑定才生效。
- ❌ 「NetworkPolicy 写了就隔离」—— 需要支持它的 CNI。
- ❌ 「容器 root 没问题」—— 多数容器漏洞都靠 root 提权放大，默认应非 root。

## 来源

- [[sources/Kubernetes 学习来源]]

## 相关文档

- [[concepts/Kubernetes 网络模型]]
- [[concepts/Kubernetes 核心架构与组件]]
- [[concepts/认证授权 OAuth2 OIDC JWT]] — OIDC/RBAC 认证授权原理
- [[entities/eBPF 安全工具]]
- [[entities/Cilium 容器网络]]
