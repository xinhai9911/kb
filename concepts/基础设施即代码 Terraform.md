---
title: 基础设施即代码 Terraform
category: concepts
tags: [terraform, iac, hcl, module, state, plan, cloud, active]
created: 2026-08-12
updated: 2026-08-17
summary: >-
    基础设施即代码 Terraform：IaC 理念、HCL 资源/模块/变量、状态文件(state)与远端后端、
    plan/apply 工作流、模块化与可复用（Module 设计模式/标准目录结构）、状态管理最佳实践
    （远端后端+锁+加密）、Workspace 多环境隔离、与声明式哲学（[[concepts/Kubernetes 声明式模型与控制器]]）
    和 GitOps（[[entities/GitOps 与 ArgoCD 实战]]）的关系、在云上拉起 K8s 集群。
    IaC 工具对比（OpenTofu/Pulumi/Ansible）。
    衔接 [[synthesis/容器分布式技术全景综述]]。
base_confidence: 0.85
lifecycle: review
sources: []
---

# 基础设施即代码 Terraform

> 补齐运维/交付域。声明式思想从「应用（K8s）」上推到「基础设施（云资源）」。见 [[entities/GitOps 与 ArgoCD 实战]]。

---

## 1. 什么是 IaC

把服务器/网络/存储等**基础设施写成代码**，用版本管理 + 自动化创建，而非手动点控制台。
好处：可复现、可评审、可回滚、环境一致（dev/staging/prod 同一份描述）。

---

## 2. 核心概念

| 概念 | 含义 |
|---|---|
| **Resource** | 一个云资源（VM/网/VPC/库），`resource "aws_instance" "web" {...}` |
| **Provider** | 对接云厂商/服务的插件（AWS/GCP/Azure/K8s） |
| **Module** | 可复用封装（输入变量→输出），类似函数 |
| **Variable / Output** | 入参 / 出参 |
| **State** | 记录「实际资源 ↔ 代码资源」映射的快照文件 |

```hcl
resource "aws_instance" "web" {
  ami           = var.ami
  instance_type = "t3.medium"
  tags = { Name = "web" }
}
output "web_ip" { value = aws_instance.web.public_ip }
```

---

## 3. 工作流：plan / apply

```
terraform init    # 装 provider、初始化后端
terraform plan    # 预览「要创建/变更/销毁什么」（dry-run）
terraform apply   # 执行，写 state
terraform destroy # 拆除
```

- **plan** 是安全网：先看清变更再 apply，避免误删生产。
- 状态漂移：真实资源被手改，plan 会显示差异 → 以代码为准修正。

---

## 4. 状态管理（关键点）

- **state 文件**是 Terraform 的「事实」，必须安全：放**远端后端**（S3+锁/DynamoDB、或 Terraform Cloud），不要留本地。
- **锁**：多人并发 apply 时防 state 竞争损坏。
- **敏感**：state 可能含明文密码/密钥 → 远端加密 + 最小权限。

> [!warning] 不要手写改 state
> state 与真实资源必须一致；手动改 state 极易导致后续 apply 误判。密钥别进 state（用 `sensitive` 标记 + 外部密钥管理，[[concepts/容器安全]]）。

### 状态管理最佳实践

```
# 推荐远端后端配置（S3 示例）
terraform {
  backend "s3" {
    bucket         = "my-terraform-state"
    key            = "prod/vpc/terraform.tfstate"
    region         = "ap-east-1"
    dynamodb_table = "terraform-locks"    # 状态锁
    encrypt        = true                 # AES-256 加密
  }
}
```

- **分层 state**：每个环境/模块独立 state（`prod/vpc/terraform.tfstate`、`prod/eks/terraform.tfstate`），爆炸半径小。
- **import**：已有资源导入管理：`terraform import aws_instance.web i-0123456789abcdef`。
- **drift 检测**：定期 `terraform plan` 检查真实资源是否偏离代码描述。

---

## 5. Module 设计模式

```
modules/
├── vpc/              # 可复用模块：VPC + 子网 + NAT
│   ├── main.tf
│   ├── variables.tf
│   └── outputs.tf
├── eks/              # EKS 集群模块
└── rds/              # RDS 模块

environments/
├── dev/
│   └── main.tf       # 调用 modules/vpc、modules/eks
└── prod/
    └── main.tf       # 同一模块，不同变量
```

| 模式 | 说明 |
|---|---|
| **单一职责** | 每个模块做一件事（VPC/EKS/RDS），不过度封装 |
| **输入输出显式** | `variables.tf` 定义所有输入，`outputs.tf` 暴露关键属性（VPC ID、endpoint） |
| **版本锁定** | `module "vpc" { source = "git::https://...//modules/vpc?ref=v1.2.0" }` |
| **Composition** | 高层模块组合低层模块（env → vpc + eks + rds） |

> [!tip] Terraform Registry
> 官方/社区模块在 [registry.terraform.io](https://registry.terraform.io)，直接引用：`source = "terraform-aws-modules/vpc/aws"`。

---

## 6. Workspace（多环境隔离）

```bash
terraform workspace new dev
terraform workspace new prod
terraform workspace select dev
terraform workspace list

# 代码中根据 workspace 切换变量
locals {
  env = terraform.workspace == "prod" ? "production" : "development"
}
```

> Workspace 适合简单场景；复杂环境推荐**目录隔离**（每个环境独立 backend + variables）。

---

## 7. 与声明式/K8s/GitOps 的关系

- Terraform 负责**底层基础设施**（拉起 K8s 集群、网络、数据库）；K8s 之上的**工作负载**交给 GitOps（[[entities/GitOps 与 ArgoCD 实战]]）用 ArgoCD 同步。
- 同是声明式：Terraform 的「期望状态 + 调和」与 K8s 哲学（[[concepts/Kubernetes 声明式模型与控制器]]）同源。

```
Git(terraform/*.tf) ──apply──▶ 云上 K8s 集群 + 网络 + DB
Git(k8s manifests)   ──ArgoCD─▶ 集群内工作负载（[[synthesis/容器分布式技术全景综述]]）
```

---

## 8. IaC 工具对比

| 工具 | 类型 | 语言 | 状态管理 | 适用场景 |
|---|---|---|---|---|
| **Terraform** | 声明式 | HCL | state 文件 | 多云基础设施编排（主流） |
| **OpenTofu** | 声明式（Terraform fork） | HCL | state 文件 | 需要开源治理/避免 license 风险 |
| **Pulumi** | 声明式 | Python/TS/Go | Pulumi Cloud 或 S3 | 程序员偏好真实语言 |
| **Ansible** | 命令式 | YAML | 无状态 | 配置管理 + 简单编排 |
| **Crossplane** | 声明式（K8s 原生） | YAML (CRD) | K8s etcd | K8s 内统一管理云资源（GitOps 友好） |

> [!note] Terraform vs Crossplane
> Terraform 在 CI 流水线里运行（推式），Crossplane 作为 K8s Operator 运行（拉式/GitOps 友好）。新项目可考虑 Crossplane 统一基础设施和工作负载的声明式管理。

---

## 参考链接

**库内双链**
- [[concepts/Kubernetes 声明式模型与控制器]] — 同源声明式思想
- [[entities/GitOps 与 ArgoCD 实战]] — 上层交付，互补
- [[synthesis/容器分布式技术全景综述]] — 基础设施→编排全链
- [[concepts/容器安全]] — 密钥不入 state/镜像
- [[concepts/关系型数据库内核]] — Terraform 常用于拉起 RDS/Cloud SQL，本文描述其内核原理

**外部资料**
- Terraform 官方文档（registry/learn）、HCL 语法
- 《Terraform: Up & Running》
