---
title: eBPF 运行时安全工具
category: entities
tags: [ebpf, security, falco, tetragon, tracee, runtime-security]
created: 2026-07-29
updated: 2026-07-29
summary: 基于 eBPF 的三大运行时安全工具对比 — Falco、Tetragon、Tracee
base_confidence: 0.80
lifecycle: draft
lifecycle_changed: 2026-07-29
sources:
  - sources/eBPF 调研来源
---

# eBPF 运行时安全工具

## 概述

2026 年运行时安全已全面转向 eBPF。传统内核模块方案有以下痛点：CPU 和内存开销大、内核版本兼容困难、有 crash 内核风险。eBPF 方案以 1-5% CPU 开销、沙箱安全、跨版本兼容的优势取代了旧的 agent 模型。

三大开源工具共享 eBPF 基础，但设计哲学不同。

## 工具对比

| 维度 | Falco | Tetragon | Tracee |
|------|-------|----------|--------|
| 核心定位 | 检测告警 | 可观测 + 内核阻断 | 检测 + 取证 |
| CNCF 状态 | 毕业项目 | 孵化中 | OSS |
| 规则语言 | YAML 条件语法 | TracingPolicy CRD (YAML) | Rego / Go 签名 |
| 内核阻断 | 否（集成外部工具实现） | 原生（signal/kill/error） | 有限 |
| 默认规则库 | 100+ 规则 | 中等（快速增长） | 中等 |
| K8s 集成 | 强 | 强（Cilium 原生） | 强 |
| 内核要求 | 4.14+（有模块 fallback） | 5.3+ (需 BTF) | 5.8+ (需 BTF) |
| 开发方 | Sysdig → CNCF | Isovalent/Cisco | Aqua Security |

### Falco — 检测标准

- 最成熟的 eBPF 安全工具，2018 年捐赠给 CNCF，2024 年毕业
- 规则驱动：YAML 规则匹配 syscall 事件流
- 典型规则："容器内 spawn shell"、"写入敏感路径"、"异常出站连接"
- 生态最大：社区规则包编排 MITRE ATT&CK、PCI DSS、HIPAA、NIST 800-190
- 性能：1-3% CPU 开销（Falco 0.40+ 默认使用 eBPF driver）

### Tetragon — 内核阻断

- Cilium 生态的安全组件，2024 年达到 v1.0
- 核心特性：TracingPolicy CRD 声明式规则 + 内核级阻断（kill/signal/error 返回）
- 身份感知：事件绑定到 Pod 和 Label，而非 PID
- 取舍：enforce 模式强大但有误杀风险，需充分测试后上线

### Tracee — 取证优先

- 事件签名匹配 + 二进制/内存/网络流量捕获到磁盘
- 当攻击发生时不止告警，还保留证据（恶意二进制、进程内存、网络包）
- 适合 incident response 重的工作流
- 签名系统可扩展（Go + Rego），事件过滤粒度精细

## 选型建议

- **检测告警** → Falco：最低学习曲线，最大生态，2026 年运行时安全默认选择
- **内核阻断** → Tetragon：Cilium 用户首选，预防而非检测
- **取证分析** → Tracee：需要事后分析和重建攻击路径的场景

## 参考来源

- [[sources/eBPF 调研来源]]
- [[entities/Cilium 容器网络]]
- [[concepts/eBPF 核心架构]]
