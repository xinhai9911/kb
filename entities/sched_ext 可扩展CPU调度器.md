---
title: sched_ext 可扩展 CPU 调度器
category: entities
tags: [ebpf, sched-ext, scheduler, kernel, cpu]
created: 2026-07-29
updated: 2026-07-29
summary: sched_ext — 用 eBPF 程序实现自定义 CPU 调度策略的 Linux 内核调度类 (6.12+)
base_confidence: 0.80
lifecycle: draft
lifecycle_changed: 2026-07-29
sources:
  - sources/eBPF 调研来源
---

# sched_ext 可扩展 CPU 调度器

sched_ext (SCHED_EXT) 是 Linux 6.12（2024 年末）合入的新调度类——允许通过 eBPF 程序实现完整的主机级 CPU 调度策略，动态加载/卸载，无需编译内核模块或重启。

开发者：Tejun Heo。基于 BPF_PROG_TYPE_STRUCT_OPS 机制将内核 `struct sched_ext_ops` 的函数指针替换为 BPF 程序实现。

## 架构

```
用户空间
  └─ scx 调度器二进制（scx_simple, scx_bpfland 等）
       │
       ├─ BPF 程序（调度策略）→ 内核 ext_sched_class
       └─ 用户空间监控组件
            ↓
内核
  ext_sched_class（新增调度类）
  └─ 优先级：低于 RT (SCHED_FIFO/RR) 和 Deadline，高于 Fair (CFS)
  └─ 默认回退：BPF 调度器出错时自动恢复到 CFS
```

## 核心概念

### Dispatch Queue (DSQ)
sched_ext 不使用每 CPU runqueue，而是使用调度队列 (DSQ)：

- **Local DSQ**：每 CPU 的本地队列，最快访问
- **Global DSQ**：单个全局队列
- **User DSQ**：BPF 程序创建的命名队列，存在 rhashtable 中

任务携带 `dsq_id`（64 位编码：bit 63 表示内置/用户，bit 62 表示 local-only，低位为 CPU 号/queue 标识符）。

### Callback 接口

`struct sched_ext_ops` 暴露的关键操作：

| 回调 | 含义 |
|------|------|
| `select_cpu` | 选择任务首次运行的 CPU |
| `enqueue` | 将任务放入 DSQ |
| `dequeue` | 从 DSQ 取出任务 |
| `dispatch` | 从 DSQ 分发任务到 CPU |
| `init` / `exit` | 调度器加载/卸载 |
| `tick` | 定时器滴答更新 |
| `check_preempt` | 抢占检查（目标 CPU 被唤醒抢占） |

## 安全设计

- **静默回退**：任何失败（超时、崩溃、SysRq+S）自动恢复 CFS
- **任务停滞检测**：可运行任务长时间得不到 CPU 时触发回退
- **SysRq+D**：触发调度器 debug dump
- **scx_cpu0 示例**：展示错误的 BPF 调度器会怎样被内核安全地恢复
- **6.19 改进**：misbehaving BPF 调度器的旁路模式（per-CPU DSQ + 负载均衡器）和 hardlockup 检测器集成

## 已有调度器

| 调度器 | 策略 | 实现语言 | 特点 |
|-------|------|---------|------|
| scx_simple | 全局 FIFO | C | 最小参考实现 |
| scx_central | 专用中央调度 CPU | C | 实验性设计 |
| scx_bpfland | 拓扑感知公平调度 | Rust | 类似 CFS |
| scx_rustland | 用户空间辅助决策 | Rust | 复杂策略回退到用户空间 |
| scx_layered | 分层调度策略 | C | 多级策略组合 |
| scx_horoscope | 占星调度 | C | 教育娱乐用 |
| scx_goland_core | Go 实现 | Go | 实验性 Go 替换 |

## 内核版本演进

| 内核版本 | 新特性 |
|---------|--------|
| 6.12 | sched_ext 合入主线 |
| 6.13 | LLC/NUMA 感知，WAKE_SYNC 改进，修复多 socket Intel Xeon 死锁 |
| 6.18 | CachyOS 等发行版默认启用 |
| 6.19 | 恢复保护增强：per-CPU DSQ + hardlockup 检测 + 误行为 BPF 调度器自动旁路 |

## 生产化进展

- CachyOS (Arch Linux 衍生版) 将 sched_ext 作为默认调度基础
- Ubuntu 24.10+ 提供可选包支持
- 大模型训练/推理工作负载开始尝试 scx_bpfland 改善尾部延迟
- 实时 GPU 调度和网络包处理场景是两大探索方向

## 局限

- 调度器开发门槛高（需了解 BPF verifier 约束 + 调度算法）
- EEVDF（CFS 的后继）仍然是社区首选默认调度器
- 多级 NUMA 大系统中的公平性和复杂拓扑仍需更多验证
- sched_ext 优先级低于 RT 和 Deadline，不适用于硬实时场景

## 参考来源

- [[sources/eBPF 调研来源]]
- [[concepts/eBPF 核心架构]]
- [[concepts/eBPF 程序类型与全挂载点]]
