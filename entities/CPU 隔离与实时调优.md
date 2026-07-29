---
title: CPU 隔离与实时调优
category: entities
tags: [cpu, isolation, isolcpus, cgroups, irq, tuned, dpdk, vpp, active]
created: 2026-07-29
updated: 2026-07-29
summary: >-
    DPDK/VPP 场景的 CPU 隔离与实时化完整方案。核心隔离（isolcpus / cpuset）、
    IRQ 亲和性、NO_HZ 全无滴答、PMU 隔离、tuned-adm realtime 配置、
    中断绑定、网卡队列 RSS 亲和、大页配置、SMT/HT 关闭、
    完整 DPDK 主机配置脚本与验证方法。
base_confidence: 0.85
lifecycle: draft
---

# CPU 隔离与实时调优

> 前置 [[concepts/CPU 核心架构]]（NUMA/SMT），[[concepts/CPU 内存模型与大页]]（huge pages）。
> 本文提供一套完整的 DPDK/VPP 数据面主机 CPU 隔离方案，每段命令均可直接运行。

## 1. 隔离总览

DPDK/VPP 要求 **独占核**，不允许以下干扰：

| 干扰源 | 后果 | 隔离手段 |
|--------|------|---------|
| 进程调度 | worker 被调度走 → 丢包 | isolcpus + cpuset |
| 内核中断 | 打断 PMD 轮询 → 延迟抖动 | IRQ affinity |
| 内核定时器 | tick 打断 → 周期微抖动 | NO_HZ_FULL |
| TLB miss | page walk → 延迟不稳定 | 1GB 大页 |
| SMT 兄弟核 | 共享 L1/L2 资源争抢 | 关 HT |
| 电源管理 C/P-state | 频率变化 → 延迟不稳 | intel_pstate=disable + performance |
| kswapd / khugepaged | 内存回收/碎片整理 | vm.swappiness=0 + THP off |
| watchdogs | NMI 监控 | nmi_watchdog=0 |
| perf sampling | PMI 中断 | perf 定时采样发中断 |

## 2. 内核启动参数

```bash
# /etc/default/grub 完整示例（双路 Xeon，24 核/48 HT）
# 隔离 core 16-23（第 3 个 socket 0 的 8 个核）
# 保留 core 0-15 给系统、控制面、管理面

GRUB_CMDLINE_LINUX_DEFAULT="\
  isolcpus=16-23 \                                    # 从调度器隔离
  nohz_full=16-23 \                                   # 全无滴答模式
  rcu_nocbs=16-23 \                                   # RCU 回调不分配到隔离核
  rcu_nocb_poll \                                     # RCU 轮询模式
  irqaffinity=0-15 \                                  # 所有中断只发到 non-isolated 核
  default_hugepagesz=1G hugepagesz=1G hugepages=8 \   # 1GB 大页
  intel_pstate=disable \                              # 关掉 intel_pstate 电源管理
  processor.max_cstate=1 \                            # 限制最深 C-state
  intel_idle.max_cstate=0 \                           # 关掉 idle 状态（数据面核不休眠）
  mce=ignore \                                        # 关 Machine Check Exception（可选）
  nmi_watchdog=0 \                                    # 关 NMI watchdog
  audit=0 \                                           # 关 audit
  clocksource=tsc \                                   # 强制 TSC 作为时钟源
  skew_tick=1 \                                       # 错开 CPU tick 避免共振
"

# 更新
sudo grub-mkconfig -o /boot/grub/grub.cfg
```

### 参数逐项说明

| 参数 | 含义 | 如果不设的后果 |
|------|------|--------------|
| `isolcpus=16-23` | 隔离核不参与进程调度 | worker 可能被其他进程抢占 |
| `nohz_full=16-23` | 隔离核上没有周期 tick | 每个 tick 打断 PMD 约 1μs |
| `rcu_nocbs=16-23` | RCU 回调不分配到隔离核 | RCU 可能在隔离核上跑回调 |
| `irqaffinity=0-15` | 所有中断亲和到 non-isolated | 中断打断 worker |
| `intel_pstate=disable` | 关掉 intel_pstate 驱动 | 频率变化导致延迟不一致 |
| `processor.max_cstate=1` | 最深 C-state = C1 | C-state 唤醒延迟>100μs |
| `clocksource=tsc` | TSC 最稳定 | jiffies/hpet 不可靠 |
| `skew_tick=1` | 各核 tick 错开 | tick 同频导致共振延迟尖峰 |

## 3. 运行时隔离

### 3.1 验证隔离

```bash
# 确认隔离核未调度普通进程
cat /proc/16-23/sched | grep nr_switches

# 或看隔离核的上下文切换
cat /proc/interrupts | grep 16-23

# 隔离核上运行的进程
ps -eo pid,tid,class,rtprio,pri,psr,comm | awk '$6 ~ /^1[6-9]|^2[0-3]$/'
```

### 3.2 cpuset 二次加固

即使 `isolcpus` 设置了，root 进程仍可运行在隔离核。cpuset 彻底禁止：

```bash
# 创建 cpuset，把隔离核从系统 cpuset 中剔除
# 推荐用 cgroup v2

sudo mkdir -p /sys/fs/cgroup/cpuset/dpdk

# 可分配给 DPDK 的核
echo "16-23" | sudo tee /sys/fs/cgroup/cpuset/dpdk/cpuset.cpus
echo "0" | sudo tee /sys/fs/cgroup/cpuset/dpdk/cpuset.mems

# 系统 cpuset 剔除隔离核
CURRENT=$(cat /sys/fs/cgroup/cpuset/cpuset.cpus)
echo "0-15" | sudo tee /sys/fs/cgroup/cpuset/cpuset.cpus

# DPDK 进程加入 cpuset
echo $DPDK_PID | sudo tee /sys/fs/cgroup/cpuset/dpdk/cgroup.procs
```

### 3.3 IRQ 亲和绑定

```bash
#!/bin/bash
# 把所有网卡中断绑到 non-isolated 核
# 隔离核 = 16-23，系统核 = 0-15

# 遍历所有网卡 IRQ
for irq in $(ls /proc/irq/); do
    # 跳过非数字目录
    [[ ! "$irq" =~ ^[0-9]+$ ]] && continue
    # 检查关联设备
    dev=$(cat /proc/irq/$irq/affinity_hint 2>/dev/null || echo "")
    [[ -z "$dev" ]] && continue
    # 只绑非 DPDK 设备的 IRQ（VPP / DPDK 接管的不绑）
    echo 0-15 > /proc/irq/$irq/smp_affinity_list 2>/dev/null
done

# 确认
cat /proc/interrupts | head -20
```

### 3.4 设置 Governor

```bash
# 所有核设置 performance governor
for cpu in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
    echo performance | sudo tee "$cpu"
done

# 隔离核关掉 smt（if applicable）
echo off | sudo tee /sys/devices/system/cpu/smt/control
```

## 4. 大页配置

```bash
# ===== 1GB 大页（需要启动参数预留）=====
grep HugePages /proc/meminfo
# => HugePages_Total: 8（8 × 1GB = 8GB 给 DPDK）

# ===== 2MB 大页（运行时分配）=====
echo 4096 | sudo tee /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages

# ===== 挂载 hugetlbfs =====
sudo mkdir -p /mnt/huge
sudo mount -t hugetlbfs nodev /mnt/huge

# ===== /etc/fstab 持久化 =====
echo "nodev /mnt/huge hugetlbfs defaults 0 0" | sudo tee -a /etc/fstab

# ===== NUMA 均衡分配 =====
# 两个 NUMA node 各 4GB 1G 大页
echo 4 | sudo tee /sys/devices/system/node/node0/hugepages/hugepages-1048576kB/nr_hugepages
echo 4 | sudo tee /sys/devices/system/node/node1/hugepages/hugepages-1048576kB/nr_hugepages
```

## 5. tuned-adm 配置

```bash
# 安装
sudo apt install tuned
sudo systemctl start tuned

# 使用现成的 realtime 模板
sudo tuned-adm profile realtime

# 查看当前 profile
tuned-adm active

# 自定义 DPDK profile（/etc/tuned/dpdk/tuned.conf）
# [main]
# include=realtime
# [cpu]
# force_latency=1
# governor=performance
# energy_perf_bias=performance
# [vm]
# transparent_hugepages=never
# [sysctl]
# kernel.nmi_watchdog=0
```

## 6. 完整 DPDK 主机环境验证脚本

```bash
#!/bin/bash
# dpdk-host-check.sh — 验证主机是否满足 DPDK 隔离要求

echo "=== CPU 隔离 ==="
cat /sys/devices/system/cpu/isolated | xargs echo "isolcpus:"

echo "=== NO_HZ_FULL ==="
cat /sys/devices/system/cpu/nohz_full | xargs echo "nohz_full:"

echo "=== SMT ==="
cat /sys/devices/system/cpu/smt/control

echo "=== Governor ==="
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor

echo "=== Interrupts on isolated cores ==="
for core in $(cat /sys/devices/system/cpu/isolated | tr ',' ' '); do
    total=$(awk -v c=$core '{print $(c+2)}' /proc/interrupts | paste -sd+ | bc)
    echo "Core $core: $total interrupts"
done

echo "=== C-state ==="
cat /sys/module/intel_idle/parameters/max_cstate

echo "=== Huge Pages ==="
grep -i huge /proc/meminfo

echo "=== VM NUMA ==="
numactl --hardware | grep available

echo "=== RCU nocb ==="
gawk '/^rcu_nocbs/' /proc/cmdline

echo "=== Page Table ==="
grep PageTables /proc/meminfo
```

## 7. 常见问题排查

| 现象 | 原因 | 检查 | 解决 |
|------|------|------|------|
| pps 周期性跳水 | tick 打断 | `turbostat --debug` 看 C1 进入 | `nohz_full` + `intel_idle.max_cstate=0` |
| 延迟偶尔 100μs+ | IRQ 打断 | `cat /proc/interrupts` 看隔离核中断数 | IRQ affinity 设到 non-isolated |
| worker 进程跑错核 | cpuset 没配 | `ps -o psr,comm` | cpuset 限制 |
| 内存不足 | 大页不够 | `cat /proc/meminfo \| grep HugePages_Free` | 调大 `hugepages=` |
| 跨 NUMA 高延迟 | 网卡绑错 NUMA | `lspci -vv \| grep NUMA` | 绑同 NUMA worker |
| 频率不稳定 | P-state 动态 | `turbostat` 看实际 MHz | `intel_pstate=disable` + `performance` governor |
| EAL 初始化失败 | 大页没挂载 | DPDK EAL 日志 | `mount -t hugetlbfs` |
| 上下文切换高 | 后台进程抢核 | `cat /proc/16-23/sched` | `ps -o psr` 定位并迁移 |

## 8. turbostat —— 隔离后验证

```bash
# 确认隔离核无中断、无 C-state 切换
sudo turbostat --show Core,CPU,Avg_MHz,Busy%,Bzy_MHz,TSC_MHz,CPU%c1,CPU%c6,CoreTmp,PkgTmp \
  --interval 5

# 输出中：
# Busy% ≈ 100%   → worker 核一直在跑
# CPU%c1 ≈ 0     → 没有进入 idle
# Avg_MHz ≈ base → 频率稳定
# 中断计数 = 0   → 没有 IRQ 打扰

# 单独看隔离核
sudo turbostat -c 16-23 --interval 5

# 确认没有 RCU 回调跑在隔离核
grep "^rcu" /proc/16-23/sched | grep -v "0 "
```

## 参考来源

- [[concepts/CPU 核心架构]]
- [[concepts/CPU 内存模型与大页]]
- [[entities/CPU 性能分析实战]]
- Linux kernel Documentation: `kernel-parameters.txt` (isolcpus, nohz_full)
- DPDK Env Abstration Layer (EAL) docs
- Red Hat Performance Tuning Guide
- `tuned-adm` / `turbostat` man pages
