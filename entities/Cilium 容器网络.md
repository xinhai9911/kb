---
title: Cilium 容器网络
category: entities
tags: [ebpf, cilium, kubernetes, networking, cni]
created: 2026-07-29
updated: 2026-07-29
summary: Cilium — 基于 eBPF 的 Kubernetes CNI，提供高性能网络、可观测性与安全策略
base_confidence: 0.80
lifecycle: draft
lifecycle_changed: 2026-07-29
sources:
  - sources/eBPF 调研来源
---

# Cilium 容器网络

## 概述

Cilium 是基于 eBPF 的 Kubernetes CNI，2026 年已成为 GKE、EKS、AKS 默认 CNI 选项，CNCF 调查显示其生产采用率超过 Flannel 和 Calico，年增长 47%。

核心理念：用 eBPF 程序替换传统的 iptables 数据路径，直接在内核中完成网络、安全和可观测性。

## 核心能力

### 高性能网络

- **替换 kube-proxy**：基于 eBPF maps 的 O(1) svc 查找 vs iptables 的 O(n) 规则链
- **方案**：CiliumEndpoint 身份标识替代 IP，IP 变化不影响身份
- **透明加密**：支持 IPsec（稳定）和 WireGuard（更快），零配置节点间加密
- **Cluster Mesh**：多集群互联，跨集群服务发现

### 网络策略 (CiliumNetworkPolicy)

| 策略类型 | 能力 | 标准 K8s NetworkPolicy |
|---------|------|----------------------|
| L3/L4 | IP + 端口 | 兼容 |
| L7 HTTP | HTTP 方法/路径 | 不支持 |
| L7 gRPC | gRPC 方法 | 不支持 |
| FQDN | 域名级出站策略 | 不支持 |
| 身份认证 | SPIFFE 双向认证 | 不支持 |

### Hubble 可观测性

- 实时网络流可视化（CLI + UI）
- 每连接延迟/RTT/丢包追踪
- Prometheus 指标导出
- 基于身份（Pod Label）而非 IP 的流量关联

### Tetragon 安全

Tetragon 是 Cilium 生态的运行时安全组件，提供：

- 内核级事件追踪（进程执行、系统调用、网络连接、文件访问）
- TracingPolicy CRD 声明式安全策略
- 支持 enforce 模式（signal/kill/error 阻断），不仅是检测告警
- 身份感知：事件绑定到 Pod/Label 而非 PID

## 性能优势

- 服务查找：O(1) 哈希表 vs iptables O(n) → 10K+ svc 场景优势明显
- 无 sidecar 开销：L7 策略在 per-node eBPF 程序中执行，CPU 开销 < 1%
- 无 conntrack 瓶颈：Per-CPU maps 消除全局锁竞争
- 典型延迟降低 40%，吞吐量提升达 10x（iptables 替换场景）

## 生态位置

- **服务网格**：Cilium 提供 sidecarless 服务网格，CPU 开销 < 1%；相比之下 Istio sidecar 每 Pod 100-200MB 内存
- **开源**：Apache 2.0，部分企业版功能需 Cilium Enterprise（Isovalent/Cisco）

## 参考来源

- [[sources/eBPF 调研来源]]
- [[entities/eBPF 安全工具]]
- [[concepts/eBPF 核心架构]]
