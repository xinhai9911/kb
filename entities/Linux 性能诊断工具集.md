---
title: Linux 性能诊断工具集
category: entities
tags: [linux, performance, tools, ftrace, bpftrace, perf, profiling, active]
created: 2026-07-29
updated: 2026-07-29
summary: >-
    Linux 性能诊断全工具链速查。perf（stat/record/top/annotate/c2c）、
    ftrace（function_graph/trace_printk/event tracing）、
    bpftrace（one-liners/脚本）、trace-cmd + kernelshark 图形分析、
    eBPF 工具（BCC/libbpf-tools/bolt）、
    strace/lsof/tcpdump/ss/iotop/slabtop 侧信道工具。
    面向 DPDK/VPP 内核旁路场景和内核网络栈调试。
    "30 秒快速诊断" 和 "深度调优" 两种模式。
base_confidence: 0.85
lifecycle: draft
---

# Linux 性能诊断工具集

> 前置 [[entities/CPU 性能分析实战]]（perf 基础），[[concepts/CPU 微架构内部]]（PMC 微架构级）。
> 本文扩展至内核级 tracing 和整体性能工具栈。

## 1. 30 秒快速诊断

```bash
# 当你不知道问题在哪时——先做这些

# 1. CPU 负载
uptime                              # load average
mpstat -P ALL 1                     # 每核利用率（看是否有核忙死）

# 2. 内存
free -h                             # 内存总量/使用
cat /proc/meminfo | grep -i huge    # 大页分配

# 3. 磁盘
iostat -x 1                         # 磁盘 IOPS/延迟
iotop                               # 实时 IO 进程

# 4. 网络
sar -n DEV 1                        # 网卡吞吐/包率/错误
ss -s                               # socket 连接统计
ethtool -S eth0 | grep -i error     # 网卡硬件错误计数

# 5. 中断
cat /proc/interrupts                # IRQ 分布（重点看隔离核）
cat /proc/softirqs                  # softirq 分布

# 6. 进程
ps aux --sort=-%cpu | head          # CPU 吃最多的进程
ps aux --sort=-%mem | head          # 内存吃最多的进程
top -H -p <pid>                     # 进程内线程占用

# 7. 内核
dmesg -T | tail -20                 # 内核日志（OOM/PCIe error/etc）
vmstat 1                            # swap/context switch/interrupts

# 8. 直接看火焰图（如果已有）
# 见 [[entities/CPU 性能分析实战]] 火焰图章节
```

## 2. Ftrace

### 2.1 function_graph

```bash
# ftrace 追踪内核函数调用图
# 最低开销的跟踪方式（数 ns 级）

# --- 基础用法 ---
mount -t tracefs none /sys/kernel/tracing
cd /sys/kernel/tracing

# 追踪特定函数（如 NAPI poll）
echo napi_poll > set_ftrace_filter
echo function_graph > current_tracer
echo 1 > tracing_on
# ... 等几秒 ...
cat trace | head -50

# --- 追踪特定进程 ---
echo 1234 > set_ftrace_pid   # 只追踪 PID 1234

# --- 跟踪深度控制 ---
echo 10 > max_graph_depth    # 最大 10 级

# --- 关闭并清除 ---
echo 0 > tracing_on
echo > trace
```

### 2.2 trace_printk

```c
// 在驱动中加入（需重编译内核模块）
trace_printk("packet_type=%d, len=%d\n", type, len);
// 输出到 trace 文件
```

### 2.3 Event Tracing

```bash
# 追踪内核事件（比 function 更低开销，因只在事件点采样）
# 常用事件：

# - 调度
echo 1 > events/sched/sched_switch/enable
echo 1 > events/sched/sched_wakeup/enable

# - 内存
echo 1 > events/kmem/mm_page_alloc/enable
echo 1 > events/kmem/mm_page_free/enable

# - IRQ
echo 1 > events/irq/irq_handler_entry/enable
echo 1 > events/irq/irq_handler_exit/enable

# - 软中断
echo 1 > events/softirq/softirq_entry/enable

# - 网络
echo 1 > events/net/netif_receive_skb/enable
echo 1 > events/napi/napi_poll/enable

# 同时追踪多个
echo "sched:*" > set_event

# 看结果
cat trace | head -100 | fold -w $COLUMNS

# 查看事件格式
cat events/napi/napi_poll/format
```

## 3. Bpftrace

```bash
# bpftrace: 基于 eBPF 的动态跟踪（生产环境安全）
# 安装：apt install bpftrace

# --- 常用 One-liners ---

# 新进程创建
bpftrace -e 'tracepoint:syscalls:sys_enter_execve { printf("%s\n", comm); }'

# 谁调用了 kmalloc
bpftrace -e 'kprobe:kmalloc { @[comm, kstack] = count(); }'

# 跟踪块 IO 延迟
bpftrace -e 'tracepoint:block:block_rq_complete { @us = hist(args->now - args->start); }'

# 所有软中断统计
bpftrace -e 'tracepoint:irq:softirq_entry { @[args->vec] = count(); }'

# 跟踪 NAPI poll 每次包处理数
bpftrace -e 'kprobe:napi_poll { @[comm] = count(); }'

# 跟踪 sk_buff 分配
bpftrace -e 'kprobe:__alloc_skb { @cnt++; } interval:s:1 { print(@cnt); clear(@cnt); }'

# --- DPDK 场景 ---
# DPDK 不走内核，bpftrace 只能跟踪控制面和 kernel 交互
# 有用场景：跟踪 VFIO ioctl 调用频率
bpftrace -e 'tracepoint:syscalls:sys_enter_ioctl { @[comm] = count(); }'
```

## 4. Perf（补充）

```bash
# 之前 [[entities/CPU 性能分析实战]] 已覆盖 perf stat/record
# 这里补充深层用法:

# === per-core PMC ===
perf stat -e cycles,instructions -C 16-23 -- sleep 5

# === 跟踪 tracepoint 频率 ===
perf stat -e sched:sched_switch,irq:irq_handler_entry -p $DPDK_PID -- sleep 5

# === 时间线采样 ===
perf record -e cycles -T -p $DPDK_PID -- sleep 10
perf script --ns         # 纳秒精度时间线

# === 函数级热点 + 源码行 ===
perf record -e cycles -g -a -- sleep 10
perf report --stdio --sort symbol

# === 对比两次 profile ===
perf record -e cycles -p $PID_OLD -o perf_before.data -- sleep 10
perf record -e cycles -p $PID_NEW -o perf_after.data -- sleep 10
perf diff perf_before.data perf_after.data
```

## 5. Trace-cmd + Kernelshark

```bash
# trace-cmd: ftrace 的前端封装（记录+回放）
# kernelshark: trace-cmd 的图形查看器

# 记录调度+IRQ 事件 10 秒
sudo trace-cmd record -e sched_switch -e irq_handler_entry -e napi_poll sleep 10

# 回放
sudo trace-cmd report

# 图形界面（需图形环境）
kernelshark trace.dat &

# 适用场景：
# - 找延迟抖动根因（时间线可视化）
# - 看中断与进程调度的因果关系
# - 看 DPDK worker 是否被抢占
```

## 6. /proc 快速诊断

```bash
# 以下文件不需要 root，直接 cat

# CPU 状态
/proc/cpuinfo        # CPU 详细信息
/proc/stat           # CPU 总统计
/proc/loadavg        # 负载
/proc/softirqs       # 软中断统计

# 内存
/proc/meminfo        # 内存使用
/proc/buddyinfo      # 伙伴系统碎片
/proc/pagetypeinfo   # 页迁移类型分布
/proc/zoneinfo       # zone 状态
/proc/slabinfo       # slab 分配
/proc/vmallocinfo    # 虚拟内存分配

# 进程
/proc/<pid>/maps     # 内存映射
/proc/<pid>/numa_maps # NUMA 分布
/proc/<pid>/smaps    # 逐段内存详情
/proc/<pid>/wchan    # 进程当前在内核什么函数
/proc/<pid>/stack    # 内核调用栈
/proc/<pid>/sched    # 调度统计

# 网络
/proc/net/dev        # 网卡统计
/proc/net/tcp        # TCP 连接
/proc/net/nf_conntrack # 连接跟踪表
```

## 7. 特定场景诊断组合

### 7.1 "DPDK worker 延迟抖动"

```bash
# 检查：
cat /proc/interrupts | grep <worker_core>     # 中断打到了 worker？
cat /proc/<worker_pid>/sched | grep nr_switches  # 上下文切换？
sudo trace-cmd record -e irq_handler_entry -e sched_switch -C 16 sleep 10
sudo trace-cmd report | grep "core 16"         # 16 号核上发生什么？

# 修正：
# - IRQ 亲和重新配置到 non-isolated 核
# - cpuset 加固（见 [[entities/CPU 隔离与实时调优]]）
```

### 7.2 "网络吞吐突然下降"

```bash
# 检查链路
ethtool -S eth0 | grep -iE "error|drop|miss"
ethtool -k eth0            # 卸载设置
ethtool -c eth0            # 中断合并

# 检查内存压力
vmstat 1
cat /proc/zoneinfo | grep -E "high|low|min"

# 检查 CPU 调度
mpstat -P ALL 1
```

### 7.3 "用户态程序为何慢"

```bash
# 1. 是 CPU 还是 IO 密集？
perf stat ./myapp

# 2. 如果是 syscall 密集
perf stat -e raw_syscalls:sys_enter ./myapp

# 3. 如果是 page fault 密集
perf stat -e page-faults ./myapp

# 4. 如果是 context switch 密集
perf stat -e context-switches ./myapp

# 5. 看 wait time
time ./myapp               # real vs user vs sys
strace -c ./myapp          # syscall 统计
```

## 8. 工具选择决策树

```
问题现象
  │
  ├─ 性能数字不对（吞吐/延迟）
  │   ├─ 硬件错误？→ dmesg | ethtool -S | mcelog
  │   └─ 软件瓶颈？→ perf top → perf stat → perf record
  │
  ├─ 特定函数慢？
  │   ├─ 内核 → ftrace function_graph → event tracing
  │   └─ 用户态 → perf annotate → gdb
  │
  ├─ 延迟不稳定？
  │   ├─ 中断 → cat /proc/interrupts → trace-cmd + kernelshark
  │   └─ 调度 → cat /proc/schedstat → bpftrace sched_switch
  │
  ├─ 内存不足？
  │   ├─ OOM → dmesg | free | slabtop
  │   └─ 碎片 → /proc/buddyinfo | compaction stats
  │
  └─ 网络问题？
      ├─ 丢包 → netstat -s | ethtool -S | dropwatch
      └─ 延迟 → ping | mtr | tcpdump
```

## 参考来源

- [[entities/CPU 性能分析实战]]
- [[concepts/CPU 微架构内部]]
- Brendan Gregg: Linux Performance Tools (2014, updated 2024)
- Linux kernel: Documentation/trace/ftrace.rst
- bpftrace: one-liners tutorial (github.com/iovisor/bpftrace)
- perf-tools: github.com/brendangregg/perf-tools
- Julia Evans: linux-debugging tools zine
