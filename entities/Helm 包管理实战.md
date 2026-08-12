---
title: Helm 包管理实战
category: entities
tags: [kubernetes, helm, chart, templating, release, package-management, active]
created: 2026-08-12
updated: 2026-08-12
summary: >-
    Helm 包管理实战：Chart / Release / Repository 三大概念、Chart
    目录结构与模板机制（values/内置对象/控制结构/functions/子模板）、
    helm 命令速查（install/upgrade/rollback/uninstall）、Hooks 与
    生命周期管理、Chart 打包发布与仓库、与 GitOps（ArgoCD）的关系、
    常见误区。
base_confidence: 0.85
lifecycle: draft
---

# Helm 包管理实战

> **Helm = K8s 的「应用商店 + 包管理器」**。把一组 K8s 清单（YAML）打包成可参数化、可版本化的 Chart，一条命令部署/升级/回滚。

## 1. 三大概念

| 概念 | 含义 | 类比 |
|------|------|------|
| **Chart** | 打包好的应用模板（含默认值） | 「安装包/源码」 |
| **Release** | Chart 的一次**部署实例** | 「已安装的软件」 |
| **Repository** | Chart 的存储仓库 | 「软件源/商店」 |

```
helm install my-app bitnami/nginx   # Chart: bitnami/nginx, Release: my-app
helm upgrade my-app bitnami/nginx   # 升级这个 Release
helm rollback my-app 1              # 回滚到 revision 1
```

- 一个 Chart 可以部署成多个 Release（不同环境、不同 namespace）。
- 每 次 upgrade 产生新 **revision**（可回滚）。

## 2. Chart 目录结构

```
my-chart/
├─ Chart.yaml          # 元信息（name/version/appVersion/dependencies）
├─ values.yaml         # 默认配置值（用户可覆盖）
├─ values.schema.json  # values 的 JSON Schema 校验（可选，推荐）
├─ charts/             # 子依赖（subchart）
├─ crds/               # CRD 定义（安装时自动创建）
├─ templates/          # Go 模板，渲染成 YAML
│   ├─ deployment.yaml
│   ├─ service.yaml
│   ├─ _helpers.tpl    # 公共模板（命名模板，以下划线开头）
│   ├─ NOTES.txt       # 安装后提示信息
│   └─ tests/          # 安装后 smoke test（test-connection Pod）
└─ .helmignore         # 打包忽略
```

## 3. 模板机制（核心）

### 3.1 values 与内置对象

```yaml
# values.yaml
replicaCount: 3
image:
  repository: nginx
  tag: "1.27"
service:
  type: ClusterIP
  port: 80
```

```yaml
# templates/deployment.yaml（片段）
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "my-chart.fullname" . }}
  labels:
    app.kubernetes.io/name: {{ .Chart.Name }}
    helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
spec:
  replicas: {{ .Values.replicaCount }}
  template:
    spec:
      containers:
      - name: {{ .Chart.Name }}
        image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
        ports:
        - containerPort: {{ .Values.service.port }}
```

- 内置对象：`.Values`（用户值）、`.Chart`（Chart.yaml）、`.Release`（名称/命名空间/revision）、`.Template`（模板信息）、`.Capabilities`（K8s 版本能力）。
- 命名模板：`{{ define "my-chart.fullname" }}` + `{{ include "..." . }}`——公共逻辑抽到 `_helpers.tpl`。

### 3.2 控制结构

```yaml
# 条件（if/else）
{{- if .Values.tls.enabled }}
tls:
  secretName: {{ .Values.tls.secretName }}
{{- end }}

# 遍历（range）—— 生成多个端口/挂载
{{- range .Values.extraPorts }}
- containerPort: {{ . }}
{{- end }}

# 默认值 / 必填
{{ .Values.image.tag | default "latest" }}
{{ required "mysql.password is required" .Values.mysql.password }}

# 管道与函数：quote / upper / b64enc / toYaml / include
{{ .Values.region | quote }}
{{ toYaml .Values.nodeSelector | nindent 8 }}   # 整段 YAML 缩进渲染
```

- `-` 破折号（`{{-` / `-}}`）去掉模板语法产生的多余空白/换行，保证渲染后 YAML 合法。

### 3.3 校验与调试

```bash
helm lint my-chart                    # 语法/结构检查
helm template my-chart --debug        # 本地渲染出最终 YAML（不部署）
helm install my-app my-chart --dry-run --debug   # 试跑 + 渲染
```

- `helm template` 是排模板 bug 的第一工具：先看渲染结果，再决定改模板还是改 values。

## 4. 命令速查

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update
helm search repo bitnami/nginx

helm install my-app bitnami/nginx -n prod --create-namespace \
  --set replicaCount=5 -f extra-values.yaml

helm upgrade my-app bitnami/nginx --set image.tag=1.28
helm history my-app                  # 查看 revision
helm rollback my-app 1               # 回滚
helm uninstall my-app                # 卸载（可 --keep-history 保留 revision）

helm list -n prod                    # 列出 Releases
helm get values my-app               # 查看最终生效 values
```

- `--set` 是命令行覆盖；`-f` 合并文件；优先级：`--set > -f > values.yaml`（后设覆盖先设）。

## 5. Hooks 与生命周期

- **Hooks**：在特定时机执行 Job（`pre-install`、`post-install`、`pre-upgrade`、`post-upgrade`、`pre-delete`…）。

```yaml
# templates/pre-install-migrate.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: "{{ include "my-chart.fullname" . }}-migrate"
  annotations:
    "helm.sh/hook": pre-install,pre-upgrade   # 时机
    "helm.sh/hook-delete-policy": before-hook-creation,hook-succeeded
```

- 典型用途：数据库迁移（pre-upgrade）、初始化数据（post-install）、资源清理（pre-delete）。
- ⚠️ Hook 资源**不参与**模板中常规资源的统一管理，失败会影响 install/upgrade 结果。

## 6. Chart 打包与发布

```bash
helm package my-chart                    # 生成 my-chart-0.1.0.tgz
helm repo index . --url https://my-repo/  # 生成 index.yaml（仓库索引）
helm install x my-chart-0.1.0.tgz        # 本地安装
```

- 私有仓库：ChartMuseum / Harbor（企业常用）+ OCI Registry（`helm push` 到 OCI）。
- **依赖**（dependencies in Chart.yaml）：一个 Chart 依赖另一个 Chart（如依赖 mysql 子 chart），`helm dependency update` 拉取打包。

## 7. Helm 与 GitOps（ArgoCD）

- Helm 是「打包与模板」，GitOps（ArgoCD）是「声明式持续同步」。
- 二者配合：Git 仓库存 Helm values → ArgoCD 以 Helm 作为渲染源持续同步到集群（不是 `helm install` 一次性动作）。
- 区别：
  - `helm install/upgrade`：命令驱动，状态在集群。
  - GitOps：Git 是唯一真相，集群不断向 Git 对齐（SSA / server-side diff）。

## 8. 常见误区

- ❌ 「`--set` 随手加就行」—— 复杂覆盖建议用 `-f values.yaml`，`.--set` 改多易乱且难审计。
- ❌ 「改了 Chart 模板就生效」—— 只有 **release（upgrade）** 才渲染，改 Chart 源码不影响已装 release。
- ❌ 「Helm 是部署工具」—— 它是**打包+参数化**工具；部署编排由 GitOps/CI 负责。
- ❌ 「Hook 出问题不重试」—— hook Job 失败默认中断 install，需清理或 `--atomic` 自动回滚。

## 相关文档

- [[concepts/Kubernetes 声明式模型与控制器]]
- [[concepts/Kubernetes Operator 与 CRD]]
- [[entities/kubectl 与日常运维实战]]
- [[entities/CI_CD 流水线实战]]
- [[sources/Kubernetes 学习来源]]
