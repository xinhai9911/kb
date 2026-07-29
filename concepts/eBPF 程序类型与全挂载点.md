---
title: eBPF 程序类型与全挂载点
category: concepts
tags: [ebpf, program-types, hooks, kernel]
created: 2026-07-29
updated: 2026-07-29
summary: eBPF 全部程序类型与钩子点的完整目录 — 网络、追踪、cgroup、安全、struct_ops 五大分类
base_confidence: 0.85
lifecycle: draft
lifecycle_changed: 2026-07-29
sources:
  - sources/eBPF 调研来源
---

# eBPF 程序类型与全挂载点

## 分类总览

截至 Linux 6.19，内核定义了约 33 种程序类型，按功能分为五大类。

## 1. 网络程序类型

### XDP (BPF_PROG_TYPE_XDP)
- **位置**：网卡驱动层，分配 skb 之前
- **上下文**：`struct xdp_md`（包含数据起始、结束指针）
- **返回动作**：XDP_PASS / DROP / TX / REDIRECT / ABORTED
- **性能**：纳秒级/包，Cloudflare 用 XDP DDoS 防御 7 Tbps+
- **分载**：SmartNIC 可将 XDP 程序卸载到硬件

### TC (BPF_PROG_TYPE_SCHED_CLS / SCHED_ACT)
- **位置**：内核网络栈 ingress/egress 的 Traffic Control 层
- **上下文**：`struct __sk_buff`（完整 skb 访问）
- **用途**：容器网络策略、流量整形、包变换
- **Cilium**：主数据路径基于 TC hook

### Socket 类型

| 程序类型 | 用途 |
|---------|------|
| BPF_PROG_TYPE_SOCKET_FILTER | 经典 socket 过滤，tcpdump 的工作引擎 |
| BPF_PROG_TYPE_SOCK_OPS | TCP 连接参数动态调整（拥塞控制、缓冲区等） |
| BPF_PROG_TYPE_SK_SKB | 在 sockmap 中转发 socket 包 |
| BPF_PROG_TYPE_SK_MSG | sockmap 中拦截/修改发送的消息 |
| BPF_PROG_TYPE_SK_LOOKUP | 自定义服务查找逻辑（替换标准 accept） |
| BPF_PROG_TYPE_SK_REUSEPORT | reuseport groups 中的选择策略 |
| BPF_PROG_TYPE_FLOW_DISSECTOR | 自定义流分类器 |

### 轻量级隧道 (LWT)

| 程序类型 | 位置 |
|---------|------|
| BPF_PROG_TYPE_LWT_IN | 隧道入口 |
| BPF_PROG_TYPE_LWT_OUT | 隧道出口 |
| BPF_PROG_TYPE_LWT_XMIT | 隧道转发 |
| BPF_PROG_TYPE_LWT_SEG6LOCAL | SRv6 本地处理 |

### Netfilter (BPF_PROG_TYPE_NETFILTER) — 6.3+
- 将 BPF 程序附加到 netfilter hook（iptables/nftables 层）
- 提供传统防火墙策略的 eBPF 替代路径

## 2. 追踪程序类型

| Hook | 可达范围 | 稳定性 | 最佳场景 |
|------|---------|-------|---------|
| kprobe / kretprobe | 任意内核函数入口/返回 | 不稳定，函数随时改名或内联 | 最大自由度，无需预置 tracepoint |
| uprobe / uretprobe | 任意用户空间函数 | 不稳定 | 应用层动态插桩；6.6 起支持 multi-attach |
| tracepoint | 内核预置静态桩点 | 稳定跨版本 | 长期运维工具的首选 |
| raw_tracepoint | 同 tracepoint，裸参数 | 稳定 | 更低开销，不自动转换参数类型 |
| fentry / fexit | 任意内核函数（BTF 类型） | 不稳定 | 5.5+ 替代 kprobe，BTF 类型感知，开销极低 |
| perf_event | PMC 采样、定时器 | — | CPU profiling：每秒 N 次采样栈 |

### BPF_PROG_TYPE_TRACING
- 通用追踪类型，支持 fentry/fexit/fmod_ret 三种挂载模式
- **fmod_ret**：拦截函数返回值，覆盖或增强内核行为

### BPF_PROG_TYPE_PERF_EVENT
- 附加到性能监控计数器（PMC）事件
- 采样栈回溯、分支记录、缓存缺失分析

### BPF_PROG_TYPE_KPROBE / TRACEPOINT / RAW_TRACEPOINT / RAW_TRACEPOINT_WRITABLE
- 分别对应传统内核追踪机制
- RAW_TRACEPOINT_WRITABLE：修改 tracepoint 上下文

## 3. cgroup 程序类型

| 程序类型 | 作用 |
|---------|------|
| BPF_PROG_TYPE_CGROUP_SKB | cgroup 级别 ingress/egress 包过滤 |
| BPF_PROG_TYPE_CGROUP_SOCK | cgroup 级别 socket 创建/连接事件 |
| BPF_PROG_TYPE_CGROUP_SOCK_ADDR | bind/connect 时修改地址参数 |
| BPF_PROG_TYPE_CGROUP_SOCKOPT | 拦截并允许/拒绝 setsockopt/getsockopt |
| BPF_PROG_TYPE_CGROUP_SYSCTL | 拦截 sysctl 读写 |
| BPF_PROG_TYPE_CGROUP_DEVICE | cgroup 设备白名单（替代 device cgroup） |

核心场景：Kubernetes 中每 Pod 的网络策略、设备权限控制。

## 4. 操作系统/安全程序类型

### BPF_PROG_TYPE_LSM (Linux Security Module)
- 附加到内核的 LSM hook 点（与 SELinux/AppArmor 相同位置）
- 200+ hook 点：文件打开、任务执行、网络连接、inode 操作
- 可 sleep（5.10+），处理涉及 page fault 的操作
- **案例**：Cloudflare 用 bpf-lsm 在运行时缓解"Copy Fail"漏洞

### BPF_PROG_TYPE_LIRC_MODE2
- 红外遥控设备解码

### BPF_PROG_TYPE_EXT (Extension)
- 扩展已加载的 BPF 程序，无需替换整个程序
- 类似内核的 livepatch 但用于 BPF

## 5. struct_ops 程序类型

BPF_PROG_TYPE_STRUCT_OPS（5.6+）允许用 BPF 程序替换内核子系统中的函数指针表：

| 服务 | 用途 |
|------|------|
| tcp_congestion_ops | 自定义 TCP 拥塞控制算法（BBR 已在 BPF 中实现） |
| sched_ext_ops | CPU 调度器策略（6.12+ 核心特性） |
| hid_bpf_ops | HID (人机交互设备) 处理 |
| Qdisc_ops | 自定义排队规则 |
| io_uring_bpf_ops | io_uring 操作扩展 |
| smc_hs_ctrl_ops | SMC (共享内存通信) 握手控制 |

意义：过去需要编译内核模块才能替换的内核行为，现在通过加载 BPF 程序即可热替换。

## BPF_PROG_TYPE_SYSCALL
- 运行 BPF 程序作为 bpf() syscall 的直接调用，不附加到任何 hook
- 用于复杂初始化逻辑、测试和 BPF 迭代器

## 挂载点性能对比

```
延迟（近似值）          Hook
< 10 ns                 XDP（硬件分载）
~ 50 ns                 XDP（驱动层）
~ 200 ns                TC ingress
~ 500 ns                fentry/fexit
~ 1 µs                  tracepoint
~ 3-5 µs                kprobe
~ 5-10 µs               uprobe
```

XDP 位于驱动层，是最快路径。fentry（BPF trampoline）是当前最快的动态追踪路径，优于 kprobe。

## 参考来源

- [[sources/eBPF 调研来源]]
- [[concepts/eBPF 核心架构]]
- [[concepts/XDP 高速数据路径]]
