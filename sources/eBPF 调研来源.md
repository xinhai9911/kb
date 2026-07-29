---
title: eBPF 调研来源
category: reference
tags: [ebpf, sources, research]
created: 2026-07-29
updated: 2026-07-29
summary: eBPF (extended Berkeley Packet Filter) 技术调研所引用的外部来源汇总
base_confidence: 0.85
lifecycle: draft
lifecycle_changed: 2026-07-29
sources: []
---

# eBPF 调研来源

## 官方文档

- [kernel.org BPF 文档](https://docs.kernel.org/bpf/) — Linux 内核 BPF 子系统官方文档，涵盖架构、maps、helpers、syscall 等
- [eBPF.io 文档](https://docs.ebpf.io/) — eBPF 基金会官方文档站点，含各 map type 详解、工具链指南
- [libbpf 文档](https://libbpf.readthedocs.io/) — libbpf 库官方文档，CO-RE 实现的核心用户空间库
- [Cilium 官方文档](https://docs.cilium.io/) — Cilium CNI 项目文档，含 eBPF 数据路径详解

## 教程与指南

- [Cilium and eBPF: High-Performance Kubernetes Networking (2026)](https://codingprotocols.com/blog/cilium-ebpf-kubernetes-networking) — Cilium 架构与生产部署教程
- [eBPF and Cilium Tutorial 2026](https://tutorials.technology/tutorials/ebpf-cilium-tutorial-2026.html) — 零基础到生产级 Cilium 安装与策略配置
- [eBPF Overview: Kernel Programmability](https://hed0rah.github.io/linux/ebpf-overview.html) — 2026 年 eBPF 入门教程，含 BCC 逐步示例
- [Types of eBPF Maps](https://prototype-kernel.readthedocs.io/en/latest/bpf/ebpf_maps_types.html) — eBPF maps 类型详解与选择指南

## 安全工具对比

- [eBPF Runtime Security in 2026: Falco vs Tetragon vs Tracee](https://1337skills.com/blog/2026-06-24-ebpf-runtime-security-2026-falco-tetragon-tracee) — 三款 eBPF 运行时安全工具深度对比
- [eBPF Runtime Security Tools: Falco vs. Tetragon vs. Tracee Compared](https://www.decryptiondigest.com/blog/ebpf-runtime-security-tools-falco-tetragon) — 买家指南角度对比
- [Container Runtime Security 2026](https://kubernetes.ae/container-runtime-security-2026) — 六款 K8s 安全工具横评（含对比矩阵）

## 深度技术参考（新增）

- [ebpf.io Linux Program Types](https://ebpf.io/linux/program-type/) — 33+ 程序类型与挂载点的官方编目，含内核版本、helper 兼容表
- [sched_ext Kernel Documentation](https://www.kernel.org/doc/html/latest/scheduler/sched-ext.html) — Linux 内核官方 sched_ext 文档，架构与 ops 接口详解
- [eBPF Verifier Overview (hed0rah)](https://hed0rah.github.io/linux/ebpf-overview.html) — 2026 年 eBPF 入门教程，含 verifier 状态追踪、BCC 逐步示例
- [eBPF Production Report 2026 (eBPF Foundation)](https://ebpf.io/ebpf-in-production-2026/) — eBPF Foundation 年度生产部署报告，含 Netflix/Cloudflare/Meta 案例
- [sched_ext: A BPF Extensible Scheduler Class (emergent.tech)](https://emergent.tech/sched-ext-a-bpf-extensible-scheduler-class/) — sched_ext 设计与案例详解

## 跨平台

- [Microsoft eBPF for Windows](https://github.com/microsoft/ebpf-for-windows) — eBPF 在 Windows 上的实现，含架构图与设计文档
- [Making eBPF Work on Windows](https://opensource.microsoft.com/blog/2021/05/10/making-ebpf-work-on-windows/) — Microsoft 开源博客介绍 eBPF for Windows 架构
- [eBPF Is Coming for Windows (The New Stack)](https://thenewstack.io/ebpf-is-coming-for-windows/) — IETF eBPF 工作组推动跨平台 ISA 标准化

## DPDK (Data Plane Development Kit)

- [DPDK.org 官方文档](https://doc.dpdk.org/) — DPDK 核心库与驱动文档
- [DPDK Programmer's Guide](https://doc.dpdk.org/guides/prog_guide/) — 环境抽象层 (EAL)、轮询模式驱动 (PMD)、内存管理、无锁队列
- [DPDK What is DPDK?](https://doc.dpdk.org/guides/linux_gsg/sys_reqs.html) — 架构概述与系统需求
- [XDP vs DPDK: Performance Analysis](https://inbox.source-yard.com/xdp-vs-dpdk-performance-and-architecture/) — XDP 与 DPDK 性能与架构对比
- [DPDK 原理与架构分析](https://zhuanlan.zhihu.com/p/141218646) — 知乎 DPDK 架构中文详解
- [SKYLB (京东 DPDK L4 负载均衡器)](https://gitee.com/baidu/X-Fund/tree/master/skylb) — 基于 DPDK 的 L4 负载均衡器生产案例
- [FD.io/VPP 文档](https://fd.io/) — 基于 DPDK 的向量包处理框架

## 相关概念

- [[synthesis/eBPF 技术全景]]
- [[concepts/eBPF 核心架构]]
- [[concepts/eBPF Maps 存储模型]]
- [[entities/Cilium 容器网络]]
- [[entities/eBPF 安全工具]]
- [[entities/eBPF 工具链]]
