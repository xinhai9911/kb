---
title: Kubernetes 学习来源
category: reference
tags: [kubernetes, sources, research]
created: 2026-08-12
updated: 2026-08-12
summary: Kubernetes 原理与实战学习所引用的外部来源汇总（官方文档、教程、书籍、社区资源）
base_confidence: 0.85
lifecycle: draft
sources: []
---

# Kubernetes 学习来源

## 官方文档与规范

- [Kubernetes 官方文档](https://kubernetes.io/docs/) — 权威手册：概念、任务、参考（API/CLI/kubectl/组件）
- [Kubernetes 概念（Concepts）](https://kubernetes.io/docs/concepts/) — 架构、工作负载、网络、存储、安全、扩展
- [Kubernetes API 参考](https://kubernetes.io/docs/reference/) — API 对象完整字段与版本
- [kubectl 参考](https://kubernetes.io/docs/reference/kubectl/) — 命令速查与 JSONPath 用法
- [Kubernetes GitHub](https://github.com/kubernetes/kubernetes) — 源码与演进（SIG 结构、KEP 提案）
- [Kubernetes Enhancement Proposals (KEP)](https://github.com/kubernetes/enhancements) — 了解新特性设计动机
- [etcd 文档](https://etcd.io/docs/) — Raft 共识、运维、备份恢复
- [CNCF K8s 认证（CKA/CKAD）](https://training.linuxfoundation.org/certification/) — 官方认证，学习路径与考试范围

## 关键子项目

- [containerd](https://containerd.io/) — 默认容器运行时（CRI）
- [CRI-O](https://cri-o.io/) — 面向 K8s 的轻量运行时
- [Calico](https://docs.tigera.io/calico/latest/) — CNI 与网络策略
- [Cilium](https://docs.cilium.io/) — eBPF 驱动的 CNI / 服务网格 / 可观测（[[entities/Cilium 容器网络]]）
- [CoreDNS](https://coredns.io/) — 集群 DNS
- [Helm](https://helm.sh/docs/) — 包管理与模板（[[entities/Helm 包管理实战]]）
- [kubebuilder](https://book.kubebuilder.io/) — Operator/控制器开发框架（[[concepts/Kubernetes Operator 与 CRD]]）
- [controller-runtime](https://github.com/kubernetes-sigs/controller-runtime) — Reconcile 循环核心库

## 教程与指南

- [Kubernetes 官方教程](https://kubernetes.io/docs/tutorials/) — 交互式入门（Hello Minikube 等）
- [Kube by Example](https://kubebyexample.com/) — 按资源类型组织的实操示例
- [Minikube 文档](https://minikube.sigs.k8s.io/docs/) — 本地开发集群
- [Kind 文档](https://kind.sigs.k8s.io/) — Docker 内多节点集群（CI 友好）
- [kubeadm 安装指南](https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/) — 生产集群自建流程
- [Kubernetes 官方示例](https://github.com/kubernetes/examples) — 各类工作负载样例清单

## 书籍

- 《Kubernetes in Action》— 原理 + 实操，适合系统入门
- 《Kubernetes 权威指南》— 中文经典，覆盖全面
- 《Programming Kubernetes》— 以 client-go / controller 视角理解 API 与控制器
- 《Kubernetes Patterns》— 复用模式（Sidecar、Adapters、Declarative Deployment 等）

## 社区与视频

- [Kubernetes.io Blog](https://kubernetes.io/blog/) — 官方博客（版本发布、设计文档）
- [TheNewStack / KubeWeekly](https://www.cncf.io/newsletter/) — CNCF 每周资讯
- [Kubernetes on YouTube（CNCF 官方频道）](https://www.youtube.com/@CNCF) — 会议（KubeCon）视频
- [Awesome Kubernetes](https://github.com/ramitsurana/awesome-kubernetes) — 精选资源清单

## 相关文档

- [[synthesis/Kubernetes 技术全景综述]]
- [[concepts/Kubernetes 核心架构与组件]]
- [[entities/Kubernetes 部署与工具链实战]]
