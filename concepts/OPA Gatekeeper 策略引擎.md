---
title: OPA Gatekeeper 策略引擎
category: concepts
tags: [opa, gatekeeper, policy, admission, rego, kubernetes, active]
created: 2026-08-17
updated: 2026-08-17
summary: >-
    OPA Gatekeeper 策略引擎：OPA 通用策略引擎（Rego 语言）、Gatekeeper 作为 K8s Admission
    Webhook（ConstraintTemplate/Constraint）、常见策略（镜像来源限制/资源限制/标签强制/
    命名规范）、审计模式与强制模式、与 Kyverno 对比。
    衔接 [[concepts/Kubernetes 安全模型]]、[[concepts/Kubernetes Operator 与 CRD]]、[[concepts/容器安全]]。
base_confidence: 0.85
lifecycle: draft
sources: []
---

# OPA Gatekeeper 策略引擎

> K8s 的 RBAC 管「谁能做什么」，但不管「做的对不对」——比如「只能用内部镜像仓库」
> 「必须设 resource limits」这类策略，需要 Admission Webhook 拦截。OPA/Gatekeeper 是标准方案。
> 见 [[concepts/Kubernetes 安全模型]]。

---

## 1. OPA（Open Policy Agent）

OPA 是通用的**策略引擎**，不只用于 K8s：
- **Rego 语言**：声明式策略语言（类似 Prolog/Datalog）。
- **输入**：JSON 请求（K8s AdmissionReview / HTTP 请求 / API 调用）。
- **输出**：`allow: true/false` + 即时数据。

```rego
# 示例：禁止使用 latest 标签
package k8s.admission

deny[msg] {
    input.request.kind.kind == "Pod"
    container := input.request.object.spec.containers[_]
    endswith(container.image, ":latest")
    msg := sprintf("禁止使用 latest 标签: %v", [container.image])
}
```

---

## 2. Gatekeeper（K8s 适配层）

Gatekeeper = OPA + K8s Admission Webhook + CRD 管理：

```
kubectl apply → kube-apiserver → AdmissionReview → Gatekeeper Webhook
                                    │
                              执行 Rego 策略
                                    │
                              ✅ 允许 / ❌ 拒绝
```

### 两个核心 CRD

| CRD | 作用 |
|-----|------|
| **ConstraintTemplate** | 定义策略模板（Rego 逻辑 + 参数化） |
| **Constraint** | 用模板创建具体约束（填参数） |

```yaml
# ConstraintTemplate（定义模板）
apiVersion: templates.gatekeeper.sh/v1
kind: ConstraintTemplate
metadata:
  name: k8srequiredlabels
spec:
  crd:
    spec:
      names:
        kind: K8sRequiredLabels
      validation:
        openAPIV3Schema:
          type: object
          properties:
            labels:
              type: array
              items:
                type: string
  targets:
    - target: admission.k8s.gatekeeper.sh
      rego: |
        package k8srequiredlabels
        violation[{"msg": msg}] {
          required := input.parameters.labels[_]
          not input.review.object.metadata.labels[required]
          msg := sprintf("缺少必填标签: %v", [required])
        }

---
# Constraint（创建约束）
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: K8sRequiredLabels
metadata:
  name: require-team-label
spec:
  match:
    kinds:
      - apiGroups: [""]
        kinds: ["Pod"]
  parameters:
    labels: ["team", "environment"]
```

---

## 3. 常见策略

| 策略 | 用途 |
|------|------|
| **镜像来源限制** | 只允许从指定 registry 拉取镜像 |
| **资源限制必填** | 所有容器必须设 `resources.limits` |
| **标签强制** | 必须有 `team`/`cost-center` 标签（对接 FinOps） |
| **命名规范** | Namespace 名必须匹配 `^[a-z0-9-]+$` |
| **禁止特权容器** | `securityContext.privileged: true` 被拒绝 |
| **PVC 大小限制** | 存储请求不超过指定上限 |
| **Host 网络禁止** | `hostNetwork: true` 被拒绝 |

---

## 4. 审计模式与强制模式

```
1. Install Template + Constraint（默认 Audit 模式）
   → 扫描现有资源，报告违规（不拦截）

2. 切换到 Enforce 模式
   → 新请求被拦截，已有资源继续报告

3. 逐步收紧策略（先宽松后严格）
```

> [!tip] 渐进式落地
> 先 Audit 模式评估影响，再切 Enforce。避免「上线即拦截」导致业务中断。

---

## 5. OPA vs Kyverno

| 维度 | OPA/Gatekeeper | Kyverno |
|------|----------------|---------|
| **语言** | Rego（专用策略语言）| YAML（K8s 原生风格）|
| **学习曲线** | 高（需学 Rego）| 低（YAML 即策略）|
| **通用性** | ✅ 通用（可走出 K8s）| ❌ 仅 K8s |
| **生态** | 成长中 | 与 K8s 深度集成 |
| **验证/变更** | 验证为主 | 验证 + 变更 + 生成 |
| **社区** | CNCF 毕业 | CNCF 沙箱→毕业 |

> 选型：已有 OPA 生态 / 需要走出 K8s → OPA/Gatekeeper；纯 K8s / 快速上手 → Kyverno。

---

## 6. 衔接

- K8s 安全：[[concepts/Kubernetes 安全模型]]
- Operator/CRD：[[concepts/Kubernetes Operator 与 CRD]]
- 容器安全：[[concepts/容器安全]]
- 准入控制：[[concepts/Kubernetes 安全模型]] §7
- GitOps：[[entities/GitOps 与 ArgoCD 实战]]（策略即代码，Git 管理）

---

## 参考链接

**库内双链**
- [[concepts/Kubernetes 安全模型]] — RBAC/Admission 安全模型
- [[concepts/Kubernetes Operator 与 CRD]] — CRD 扩展机制
- [[concepts/容器安全]] — 容器级加固
- [[entities/GitOps 与 ArgoCD 实战]] — 策略即代码管理
- [[synthesis/容器分布式技术全景综述]] — 全景地图

**外部资料**
- OPA 官方文档（openpolicyagent.org）
- Gatekeeper 文档（open-policy-agent.github.io/gatekeeper）
- Kyverno 文档（kyverno.io）
- 《Policy-Based Control for Kubernetes》
