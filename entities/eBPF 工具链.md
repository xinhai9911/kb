---
title: eBPF 工具链
category: entities
tags: [ebpf, bcc, libbpf, bpftrace, toolchain]
created: 2026-07-29
updated: 2026-07-29
summary: eBPF 开发工具链生态 — BCC、libbpf、bpftrace、aya 的对比与演进
base_confidence: 0.80
lifecycle: draft
lifecycle_changed: 2026-07-29
sources:
  - sources/eBPF 调研来源
---

# eBPF 工具链

## 五条开发路径

| 方案 | 语言 | 编译模型 | 启动速度 | 可移植性 | 最佳场景 |
|------|------|---------|---------|---------|---------|
| BCC | Python/Lua + C | 运行时 LLVM 编译 | 慢 | 绑定额内核 | 学习、原型、一次性调试 |
| libbpf | C | 构建时编译 | 快 | CO-RE 全兼容 | 生产工具、守护进程 |
| bpftrace | DSL | 运行时编译 | 中 | 同 BCC | 单行诊断、快速排查 |
| aya | Rust | 构建时编译 | 快 | CO-RE 全兼容 | Rust 生态项目 |
| cilium/ebpf | Go | 构建时编译 | 快 | CO-RE 全兼容 | Go 服务集成 |

## BCC (BPF Compiler Collection)

- **创始人**：Brendan Gregg，最早推动 eBPF 工具化的项目
- **架构**：Python 前端 + 嵌入式 C（字符串）→ 运行时 LLVM 编译 → bpf() syscall 加载
- **优点**：快速原型 — 改代码 → 运行，循环仅数秒
- **缺点**：每台目标机器需安装 LLVM + 内核头文件（~300 MB），无 CO-RE
- **内置工具**：execsnoop、biolatency、tcpconnect、tcplife 等 100+ 工具
- **2026 年位置**：仍是学习和原型开发的最佳环境

## libbpf + CO-RE

- Linux 内核官方维护的 BPF 用户空间库
- **工作原理**：BPF 程序编译时记录字段偏移重定位信息，加载时根据运行内核 BTF 自动调整
- **优点**：编译一次处处运行，启动快，生产级
- **前提**：内核需 CONFIG_DEBUG_INFO_BTF=y（现代发行版默认）
- **推荐路径**：新开发首选 libbpf 而非 BCC

## bpftrace

- 高级单行脚本语言 DSL，类似 awk/dtrace
- 语法：`bpftrace -e 'kprobe:sys_open { printf("%s\n", comm); }'`
- 适用场景：快速诊断、一闪而过的排查、性能热点定位
- 内核要求：与 BCC 类似

## aya (Rust)

- 纯 Rust 的 eBPF 开发框架，无需 libbpf C 依赖
- 支持 CO-RE，编译为 BPF 字节码 + 用户空间 Rust 程序
- 适合 Rust 技术栈项目

## eBPF for Windows

Microsoft 开源项目，目标是让 Linux eBPF 生态在 Windows 上运行：

- **架构**：uBPF 解释器 + bpf2c 原生编译 + PREVAIL 验证器
- **三种加载模式**：Native（bpf2c→C 编译）、JIT（uBPF JIT）、Interpreter（仅 debug）
- **Hook 点**：当前支持 XDP 和 socket bind 等网络钩子
- **API 兼容**：通过 ebpfapi.dll 暴露 libbpf 兼容 API
- **状态**：Work-in-progress，支持 Windows 11 / Windows Server 2022+
- **IETF**：eBPF ISA 工作组正在推进跨平台标准化

## 2026 年最佳实践

- 学习用 BCC → 生产用 libbpf + CO-RE
- 快速排查用 bpftrace 单行脚本
- Rust 项目用 aya，Go 项目用 cilium/ebpf
- Windows 场景关注 ebpf-for-windows

## 程序类型与 ELF Section 映射

libbpf 和内核通过 ELF section 名称自动推断程序类型和附加点：

| ELF Section | 程序类型 | 挂载点 |
|------------|---------|--------|
| `xdp` | XDP | native XDP hook |
| `tc` | SCHED_CLS | TC ingress/egress |
| `kprobe`/`kretprobe` | KPROBE | 内核函数入口/返回 |
| `kprobe.multi` | KPROBE | 6.6+ 批量 kprobe |
| `fentry`/`fexit` | TRACING | BPF trampoline |
| `tracepoint` | TRACEPOINT | 内核静态桩点 |
| `raw_tp`/`raw_tracepoint` | RAW_TRACEPOINT | 裸参数 tracepoint |
| `lsm` | LSM | LSM hook 点 |
| `lsm.s` | LSM (sleepable) | LSM 可睡眠 |
| `cgroup_skb`/`cgroup_sock` | CGROUP_SKB/SOCK | cgroup 网络 |
| `perf_event` | PERF_EVENT | PMC 采样 |
| `struct_ops` | STRUCT_OPS | TCP-CA/sched_ext/HID |
| `sk_skb`/`sk_msg` | SK_SKB/SK_MSG | sockmap 转发 |
| `iter` | TRACING | BPF 迭代器 |

## 开发指引

- [[entities/eBPF 开发实战]] — BCC/libbpf 示例、maps 模式、调试方法与常见陷阱

## 参考来源

- [[sources/eBPF 调研来源]]
- [[concepts/eBPF 核心架构]]
- [[synthesis/eBPF 技术全景]]
- [[concepts/eBPF 程序类型与全挂载点]]
