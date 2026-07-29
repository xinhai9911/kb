---
title: eBPF 技术全景
category: synthesis
tags: [ebpf, kernel, networking, security, observability]
created: 2026-07-29
updated: 2026-07-29
summary: eBPF 技术综述 — 从内核可编程到云原生生态的全景视图
base_confidence: 0.80
lifecycle: draft
lifecycle_changed: 2026-07-29
sources:
  - sources/eBPF 调研来源
---

# eBPF 技术全景

## 核心技术栈

```
应用层
  ├── 可观测性: Hubble, Pixie, Parca, OpenTelemetry eBPF
  ├── 安全: Falco, Tetragon, Tracee, bpflock
  ├── 网络: Cilium, Calico eBPF, Katran L4 LB, Unimog
  └── 存储: SPDK eBPF, IO_uring eBPF
工具链层
  ├── BCC (学习/原型), libbpf (生产标准), bpftrace (诊断)
  ├── aya (Rust), cilium/ebpf (Go)
  └── bpftool (内核诊断管理)
内核层
  ├── 验证器 + JIT + 运行时
  ├── Hook: XDP / TC / kprobe / tracepoint / fentry / LSM / cgroup
  ├── 30+ 程序类型: xdp/tc/tracing/sk_skb/lsm/cgroup/struct_ops/syscall
  ├── Maps: hash / array / ringbuf / percpu / LRU / bloom / arena / queue-stack
  └── CO-RE: BTF 类型信息 + 字段重定位
```

## 内核实测指标

| 操作 | 延迟 |
|------|------|
| XDP（驱动层） | < 50 ns |
| TC ingress | ~ 200 ns |
| fentry/fexit | ~ 500 ns |
| tracepoint | ~ 1 µs |
| kprobe | ~ 3-5 µs |
| uprobe | ~ 5-10 µs |
| map hash lookup | ~ 50-100 ns |
| map array lookup (JIT inlined) | ~ 10-20 ns |
| ringbuf 事件推送 | ~ 100-200 ns |

## Helper 函数与 kfuncs

截至 Linux 6.19，内核提供约 250+ 个 BPF helper 函数和 kfuncs：

- **网络 helpers**：bpf_skb_load_bytes, bpf_redirect, bpf_fib_lookup, bpf_xdp_adjust_head
- **追踪 helpers**：bpf_probe_read_kernel, bpf_get_current_pid_tgid, bpf_perf_event_output
- **map helpers**：bpf_map_lookup_elem, bpf_map_update_elem — 内核自动内联
- **定时器**：bpf_timer_init/set_callback/cancel（6.6+），实现 BPF 内超时和周期操作
- **kfuncs**：5.13+ 引入，无需维护 BPF helper 白名单，直接在模块/内核中声明。内核需 EXPORT_BPF_KFUNC 导出，依赖 BTF 类型信息，如 bpf_cast_to_kern_ctx, bpf_rcu_read_lock
- **Exceptions (6.19+)**：bpf_throw — 从 BPF 程序抛出异常，verifier 保证所有 throws 被捕获

## Syscall 接口

`bpf()` 系统调用接收 cmd 参数 + union bpf_attr：

| CMD | 功能 | 内核版本 |
|-----|------|---------|
| BPF_PROG_LOAD | 加载 BPF 程序 | 3.18 |
| BPF_MAP_CREATE | 创建 map | 3.18 |
| BPF_MAP_LOOKUP_ELEM | 查询 map 元素 | 3.18 |
| BPF_MAP_UPDATE_ELEM | 更新 map 元素 | 3.18 |
| BPF_PROG_ATTACH | 挂载程序到 hook | 4.10+ |
| BPF_LINK_CREATE | 创建 link（推荐替代 attach） | 5.7+ |
| BPF_TOKEN_CREATE | 创建 BPF token | 6.9+ |
| BPF_PROG_RUN | 同步运行 BPF 程序测试 | 5.10+ |
| BPF_ITER_CREATE | 创建 BPF 迭代器 | 5.8+ |

## eBPF 现代特性时间线

```
2014  Linux 3.18 — eBPF 进入内核主线
2016  Linux 4.8 — XDP 引入，BPF maps 扩展
2019  Linux 5.3 — bounded loops, BPF trampoline (fentry)
2020  Linux 5.8 — CAP_BPF, BPF ringbuf, BPF iterator
2021  Linux 5.13 — kfuncs 机制, CO-RE 里程碑
2021  Linux 5.15 — BPF 可睡眠程序, kernel.mode=only sleepable
2022  Linux 5.19 — BPF 连接跟踪 (bpf_ct)
2023  Linux 6.6 — bpf_loop, bpf_for_each, bpf_timer 完善
2023  Linux 6.8 — 验证器正则等价类 CVE 修复
2024  Linux 6.9 — BPF Token 委派权限
2024  Linux 6.12 — sched_ext (可扩展调度器) 合入主线
2025  Linux 6.18 — struct_ops 扩展, CachyOS 默认启用 sched_ext
2026  Linux 6.19 — BPF exceptions/bpf_throw, arena map, IO_uring eBPF, 
                  恢复保护增强（sched_ext 旁路模式）

IETF 工作组：
2024  成立 eBPF ISA 工作组 (bpfwg)
2026  推进标准化草案，目标 Linux + Windows 统一 ISA
```

## 四大应用领域

### 1. 网络

- **Cilium** 取代 iptables + kube-proxy，2026 年最广泛部署的 K8s CNI
- O(1) 服务查找 vs O(n) 规则链
- 身份安全（Pod Label）替代 IP 的安全策略
- XDP 层 DDoS 防护，纳秒级包处理
- Hubble 提供目前最强的容器网络可观测性
- Katran (Meta)：XDP L4 负载均衡器，处理整个数据中心的入站流量
- Unimog (Cloudflare)：边缘 XDP 负载均衡器
- Cilium Service Mesh：sidecarless L7 策略 + mTLS，CPU < 1% 开销

### 2. 安全

- 运行时安全从内核模块转向 eBPF 是确定趋势
- Falco（检测告警）vs Tetragon（内核阻断）vs Tracee（取证）三足鼎立
- eBPF verifier 本身也是安全基座 — 被拒绝加载是系统在正常工作
- 内核 6.8/6.12 修复了最后几类重大验证器绕过 CVE
- BPF LSM 动态安全策略，BPF token 最小权限委派（6.9+）
- bpflock：eBPF 驱动的 Linux 安全加固

### 3. 可观测性

- Hubble：连接级 L3-L7 追踪，无 sidecar
- Pixie：K8s 应用内自动仪表化（eBPF uprobe）
- Parca：持续性能分析（eBPF 采样）
- OpenTelemetry eBPF：正在标准化的内核级遥测路径
- eBPF flow logs：Netflix 数万 EC2 实例网络可见性
- eBPF off-CPU profiling：锁定竞争、IO 等待延迟诊断

### 4. 调度器 (sched_ext)

- sched_ext (SCHED_EXT)：Linux 6.12 合入的新调度类
- 通过 BPF struct_ops 实现自定义 CPU 调度器
- 静默回退到 CFS：BPF 调度器崩溃不影响系统稳定性
- 已有 7+ 实验调度器：scx_bpfland（拓扑感知）、scx_rustland（用户辅助决策）、scx_layered（分层策略）
- CachyOS 已默认启用，大模型推理场景探索尾部延迟改善

## 跨平台进展

- Microsoft eBPF for Windows 基于 uBPF + PREVAIL 验证器 + bpf2c
- 当前支持 XDP、socket bind 等网络 hook，支持 Windows 11/Server 2022+
- IETF BPF 工作组正在标准化 eBPF ISA，推进 Linux/Windows 交叉兼容
- 跨平台 eBPF 应用仍受限于平台特定 hook 和 helper 的差异

## 核心生产案例一览

| 企业 | 场景 | 成效 |
|------|------|------|
| Cloudflare | XDP DDoS 防御 | 7 Tbps+ 缓解，基础架构成本降低 30% |
| Meta | Katran L4 负载均衡 | 2017 年起处理每个入站包，~200 Gbps/单机 |
| Netflix | eBPF 网络可观测性 | 数万 EC2 实例，支持 3.25 亿+ 用户 |
| LinkedIn | XDP + 内核诊断 | 125K iptables 规则→144 条 XDP，日志减少 70% |
| ByteDance | eBPF 网络加速 | 约 100 万服务器，吞吐量提升 10% |
| Datadog | eBPF 连接跟踪 | CPU 使用率降低 35% |
| DoorDash | eBPF 监控迁移 | 内存减少 40%，重启减少 98% |
| Polar Signals | eBPF 可观测性 | 跨区域流量成本降低 50% |
| SentinelOne | eBPF 安全防御 | 勒索软件 < 1 秒检测阻断 |

## 趋势判断

1. **CO-RE 成为标配**：BCC 的运行时编译模式正被 libbpf CO-RE 取代
2. **eBPF 左移安全**：LSM + eBPF 实现内核级强制访问控制
3. **eBPF + 服务网格**：Cilium 已实现 sidecarless 网格，CPU 开销 < 1%
4. **AI 工作负载**：eBPF 被用于 GPU/NIC 可观测性和调度（Cilium 在 AI 集群中扩展）
5. **Windows 兼容**：IETF 标准化 + 微软投入使 eBPF 走向跨 OS
6. **sched_ext**：CPU 调度器从内核模块转向 eBPF，大模型推理工作负载受益
7. **BPF exceptions/arenas**：6.19 异常处理 + 共享内存消除 verifier 带来的编程摩擦

## 局限性

- 需要较新内核（CO-RE + ringbuf 等功能需要 5.8+）
- eBPF 程序有复杂度上限（验证器 1M 指令预算、栈 512 字节等）
- Windows 版本仍不成熟，跨平台应用场景有限
- 学习曲线陡峭（内核编程知识 + verifier 约束 + BPF 软件栈概念）
- sched_ext 调度器开发门槛高（同时理解调度算法 + BPF 约束）
- 极端性能场景（100GbE 线速、用户空间协议栈）不如 DPDK 成熟

## 关系概览

eBPF/XDP 与 DPDK 代表两种不同思路：**内核内加速** (in-kernel) vs **内核旁路** (kernel bypass)。二者并非替代关系，而是面向不同场景：

| | eBPF/XDP | DPDK |
|---|----------|------|
| 核心优势 | 云原生集成、安全、可观测 | 极致性能、用户空间控制、NFV 生态 |
| 最佳场景 | K8s 网络、安全监控、追踪 | 运营商 NFV、100GbE、裸金属 |
| 融合点 | AF_XDP PMD + XDP 路径 | |
| 选型参考 | [[synthesis/DPDK 与 eBPF XDP 技术对比]] | |

## 参考来源

- [[sources/eBPF 调研来源]]
- [[concepts/eBPF 核心架构]]
- [[concepts/eBPF Maps 存储模型]]
- [[entities/Cilium 容器网络]]
- [[entities/eBPF 安全工具]]
- [[entities/eBPF 工具链]]
- [[concepts/eBPF 程序类型与全挂载点]]
- [[concepts/eBPF 验证器与安全模型]]
- [[concepts/XDP 高速数据路径]]
- [[entities/sched_ext 可扩展CPU调度器]]
- [[entities/eBPF 生产案例与生态系统]]
