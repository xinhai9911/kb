---
title: eBPF 核心架构
category: concepts
tags: [ebpf, kernel, architecture, verifier]
created: 2026-07-29
updated: 2026-07-29
summary: eBPF (extended Berkeley Packet Filter) 的核心架构 — 内核虚拟机、验证器、JIT、Hook 与程序生命周期
base_confidence: 0.85
lifecycle: draft
lifecycle_changed: 2026-07-29
sources:
  - sources/eBPF 调研来源
---

# eBPF 核心架构

## 概述

eBPF 是一种在内核中安全运行沙箱化程序的技术，允许用户在不修改内核源码或加载内核模块的情况下，动态扩展内核行为。起源于 1992 年的经典 BPF（用于网络包过滤），自 Linux 3.18 起演化为通用内核可编程框架。

## 核心组件

### BPF 虚拟机

- 提供 11 个 64 位寄存器 (R0-R10) + 程序计数器 (PC)
- R0: 返回值
- R1-R5: 函数调用参数
- R6-R10: 被调用者保存的寄存器
- 支持 ALU、内存访问、条件/无条件跳转等指令
- 已由 IETF 工作组推进标准化

### 验证器 (Verifier)

验证器在程序加载时静态检查所有代码路径，确保：

- **程序终止**：通过有界循环检测（5.3+ 引入 bounded loops，verifier 证明终止）
- **内存安全**：禁止越界指针解引用
- **内核保护**：禁止写入非授权内核内存
- **API 合规**：helper 调用限于 BPF API 集合

失败的程序被拒绝加载，无法崩溃内核。6.8/6.12 内核修复了最后几类重大绕过 CVE，验证器目前是内核中模糊测试最密集的组件。

### JIT 编译器

- 将 BPF 字节码编译为本地机器码
- 支持 x86_64, ARM64, RISC-V, s390 等架构
- 相比解释器模式，JIT 可提供 3-5 倍性能提升
- 部分 map 操作（如 array lookup）可被 JIT 内联

### Hook 点（挂载点）

| Hook 类型 | 触发时机 | 典型用途 |
|----------|---------|---------|
| XDP | 网卡驱动层，最早包处理点 | DDoS 防护、负载均衡 |
| TC (Traffic Control) | 内核网络栈 ingress/egress | 容器网络策略 |
| Tracepoint | 内核静态跟踪点 | 系统调用跟踪 |
| kprobe/kretprobe | 内核函数入口/返回 | 动态插桩 |
| uprobe | 用户空间函数 | 应用层监控 |
| LSM (Landlock) | 内核安全模块接口 | 强制访问控制 |
| cgroup hook | cgroup 层级事件 | 容器资源控制 |
| socket filter | Socket 操作 | 自定义 sock 逻辑 |

## 程序生命周期

```
编写 (C/Rust) → 编译 (clang -target bpf) → 加载 (bpf() syscall) → 验证 → JIT → 挂载 → 运行
```

1. **编写**：用 C（主流）、Rust（aya 框架）或 Python（BCC）编写 BPF 程序
2. **编译**：LLVM BPF 后端（clang -target bpf）编译为 ELF 格式字节码
3. **加载**：通过 bpf() 系统调用将字节码、map 定义和 BTF 类型信息传入内核
4. **验证**：verifier 检查程序安全性，拒绝危险程序；需 CAP_BPF（6.9+ 可委派 BPF token）
5. **JIT 编译**：字节码转为本地指令
6. **挂载**：附加到指定 hook 点开始处理事件
7. **运行**：每次事件触发时执行，通过 maps 与用户空间通信

## CO-RE (Compile Once, Run Everywhere)

- **BTF (BPF Type Format)**：压缩的内核类型信息，存储在 /sys/kernel/btf/vmlinux
- **BPF CO-RE**：在字节码中记录内核结构体字段的偏移量重定位信息
- 加载器（libbpf）在加载时根据运行内核的 BTF 信息自动调整偏移量
- 消除了 BCC 时代"每台机器都要安装 LLVM + 内核头文件"的痛点
- 前提：内核需打开 CONFIG_DEBUG_INFO_BTF=y（现代发行版默认开启）

## 性能特征

- 典型 CPU 开销：1-5%（视 hook 点和事件量）
- XDP 模式可达每包纳秒级处理
- 相比内核模块更安全（验证器保护），相比 iptables 更快（O(1) map 查找）
- Per-CPU maps 消除了全局锁竞争，随核数线性扩展

## 关联页面

- [[concepts/eBPF 验证器与安全模型]] — 验证器状态追踪、CAP_BPF、BPF Token
- [[concepts/eBPF 程序类型与全挂载点]] — 33+ 程序类型目录与挂载点
- [[concepts/XDP 高速数据路径]] — XDP 架构与生产案例
- [[entities/sched_ext 可扩展CPU调度器]] — eBPF 可扩展调度器 (6.12+)

## 参考来源

- [[sources/eBPF 调研来源]]
- [[concepts/eBPF Maps 存储模型]]
- [[synthesis/eBPF 技术全景]]
