---
title: CPU 功耗与 RAPL
category: concepts
tags: [cpu, power, rapl, cstate, pstate, turbostat, tuning, active]
created: 2026-07-29
updated: 2026-07-29
summary: >-
    CPU 功耗管理与能效调优。P-state（频率电压缩放）、
    C-state（休眠深度）、Intel RAPL（Running Average Power Limit）功耗封顶、
    RAPL 域（Package/DRAM/PP0/PP1）、功耗监测与 power capping、
    TDP 解读、intel_pstate vs acpi_cpufreq governor 选择、
    数据面场景的功耗权衡（性能损失 vs 节能收益）。
base_confidence: 0.85
lifecycle: draft
---

# CPU 功耗与 RAPL

> 前置 [[concepts/CPU 核心架构]]（C-state/P-state 基础），[[entities/CPU 隔离与实时调优]]（intel_pstate=disable）。
> 本文深入功耗管理机制与调优。

## 1. P-state（Performance State）

### 1.1 状态模型

```
P0 = 最高频率/电压（base 或 turbo）
P1 = 次高频率
...
Pn = 最低频率

Intel:
  Base Frequency  = 保证的 P0
  Turbo Frequency = 单核/多核睿频（依赖散热和功率预算）
  Efficient Frequency = 性能和功耗平衡点

AMD:
  CPPC (Collaborative Power Performance Control)
  OS 通过 CPPC 接口建议 perf level，硬件自行决定实际频率
```

### 1.2 intel_pstate vs acpi_cpufreq

| 驱动 | 模式 | 特点 | 推荐场景 |
|------|------|------|---------|
| `intel_pstate` | passive | 硬件 P-state 控制，响应快 | 普通负载 |
| `intel_pstate` | active | OS 参与频率选择 | 普通负载 |
| `acpi_cpufreq` | — | 传统 ACPI，P-state 表 | 需 fine-grained 控制时 |
| 禁用 (`intel_pstate=disable`) | — | 关掉频率缩放 | 数据面推荐 |

**数据面推荐**：`intel_pstate=disable` + `performance governor`

```bash
# 禁用后 CPU 恒定运行在 base/turbo 频率
# 无频率切换延迟，无 transient power 带来的微延迟

# 查看当前 CPU 频率
cat /sys/devices/system/cpu/cpu16/cpufreq/scaling_cur_freq

# 即使 governor=performance
# intel_pstate 仍可在空闲时降频（取决于硬件）
# 彻底固定频率仍需 intel_pstate=disable
```

## 2. C-state（Idle State）

### 2.1 状态层次

```
C0    = 运行（执行指令）
C1    = HLT（暂停，最快唤醒 ~1μs）
C1E   = C1 + 最低电压
C2    = 时钟门控
C3    = L2 缓存 flush（Skylake 后不再需要）
C6    = 核心电源门控（保存上下文，唤醒 ~50-100μs）
C7    = 核心电源门控 + LLC L3 压缩/清空
C8-C10 = 更深度合并（C8 ~300μs 唤醒）
```

**延迟成本**：

```bash
# 实测各状态的退出延迟（turbostat）
sudo turbostat --show Core,CPU,Avg_MHz,Busy%,Bzy_MHz,TSC_MHz,CPU%c1,CPU%c6,CPU%c7 --interval 1

# C6 → C0 退出延迟: ~50-100μs
# 这个延迟在数据面场景 = 丢数百个 64B 包！
# 因此数据面核必须限制 C-state 深度
```

**数据面配置**：

```bash
# BIOS 限制（最可靠）
# Processor C6 = Disabled
# Package C State = C1 or C0

# 内核参数
processor.max_cstate=0    # 硬件 C-state 限制到 C1
intel_idle.max_cstate=0   # 使用 acpi_idle（浅 C-state）

# 运行时（部分平台支持）
for cpu in /sys/devices/system/cpu/cpu[16-23]/cpuidle; do
    # state0 = C1, state1 = C6 ...
    echo 1 | sudo tee $cpu/state*/disable  # 禁用深 C-state
done
```

## 3. RAPL（Running Average Power Limit）

### 3.1 RAPL 域

```
┌─────────────────────────────────────┐
│  PKG (Package)  ← 整颗 CPU 的功耗   │
│  ┌──────────┐  ┌──────────┐         │
│  │ PP0/Core │  │ PP1/GFX  │         │  ← 子域
│  └──────────┘  └──────────┘         │
│  ┌──────────────────┐               │
│  │ DRAM              │               │  ← 内存域
│  └──────────────────┘               │
│  ┌──────────────────┐               │
│  │ PSys (Platform)  │               │  ← Skylake+ SoC 总功耗
│  └──────────────────┘               │
└─────────────────────────────────────┘
```

### 3.2 读取 RAPL 数据

```bash
# 通过 MSR 接口（原始）
for pkg in /sys/class/powercap/intel-rapl/intel-rapl:*; do
    echo "$(basename $pkg): $(cat $pkg/name) = $(cat $pkg/energy_uj) μJ"
done

# 更直观：turbostat 的 Watts 列
sudo turbostat --show PkgWatt,RAMWatt,GFXWatt,PKG_% --interval 1

# 编程读取（C / Python）
# uevent 文件包含域信息，energy_uj 是累计能耗计数器
# 两次读差 / 时间差 = 平均功率

# DPDK 应用：通过 rte_power 库读取/限制功耗
rte_power_get_cap(cpu_id);      # 当前 power cap
rte_power_set_cap(cpu_id, watts);  # 设置功率上限

# 持续监测
watch -n1 'echo "Pkg: $(cat /sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj) μJ"'
```

### 3.3 Power Capping

```bash
# 设置 Package 功率上限（单位 μW）
echo 100000000 | sudo tee /sys/class/powercap/intel-rapl/intel-rapl:0/constraint_0_power_limit_uw

# 设置时间窗口
echo 1000000 | sudo tee /sys/class/powercap/intel-rapl/intel-rapl:0/constraint_0_time_window_us

# 限制效果：
# 200W → 100W: 频率自动降低，吞吐下降约 30-40%（取决于 workload）
# 适用：数据中心 power capping、散热受限环境

# 检查是否生效
cat /sys/class/powercap/intel-rapl/intel-rapl:0/constraint_0_power_limit_uw

# 数据面场景的权衡：
# 关 capping（最高性能） vs 开 capping（可预测功耗，适合机架密度场景）
```

### 3.4 功耗与性能实测

```bash
# 测试方案：不同功率上限下的 DPDK 吞吐
for pwr in 225 200 150 120 100; do
    echo $(($pwr * 1000000)) | \
        sudo tee /sys/class/powercap/intel-rapl/intel-rapl:0/constraint_0_power_limit_uw
    sleep 2  # 等待频率稳定
    # 跑 DPDK l2fwd 测 pps
    dpdk-l2fwd -l 16-23 -- -P -p 0x1 --no-mac-updating > /tmp/l2fwd.log
    # 记录结果
    pps=$(grep "tx" /tmp/l2fwd.log | awk '{print $2}')
    watts=$(sudo turbostat --interval 1 --quiet | tail -1 | awk '{print $NF}')
    echo "Limit=${pwr}W, Actual=${watts}W, PPS=${pps}"
done
```

## 4. TDP 解读

| 概念 | 含义 | 对用户的意义 |
|------|------|-----------|
| TDP (Thermal Design Power) | 散热器必须散掉的最大热量 (W) | 选散热、选电源的基准 |
| PL1 (Power Limit 1) | 长期平均功耗上限 = TDP | 默认限制 |
| PL2 (Power Limit 2) | 短时爆发功耗上限 (~TDP × 1.25) | 决定 Turbo 持续时长 |
| Tau | PL2 持续时间 (秒) | 长 Tau = 长时间高性能 |
| ICC_MAX | 最大电流 | 影响超频 / VF 降频 |

```bash
# 查看 PL1/PL2/Tau 配置
# 通过 MSR 0x610 (PKG_POWER_LIMIT)
sudo rdmsr -a 0x610 -f 64

# 或通过 intel-rapl sysfs（见上）
# 修改 PL2 提高爆发性能（注意散热！）
# 或降低 PL2 来限制运行功耗
```

## 5. 数据面推荐配置

```bash
# ===== 网络数据面的标准配置 =====

# 1. intel_pstate=disable + performance governor
# 频率恒定，无瞬态

# 2. processor.max_cstate=0 / intel_idle.max_cstate=0
# 只允许 C1 空闲，无 C6/C7

# 3. RAPL 不设 cap（除非机架功率受限）
# 全性能运行

# 4. 用 turbostat 验证稳态
sudo turbostat --show Core,CPU,Avg_MHz,Busy%,Bzy_MHz,PkgWatt,RAMWatt,POLL,CPU%c1,CPU%c6,CPU%c7 \
    -c 16-23 --interval 5

# 期望输出（数据面 worker 核）：
# Core  CPU  Avg_MHz  Busy%  Bzy_MHz  PkgWatt  CPU%c1  CPU%c6
# 16    16   2800     100    2800     180      0       0
# 17    17   2800     100    2800     180      0       0
# → Busy%=100, CPU%c6=0, 频率稳定
```

## 6. 常见误区

| 误区 | 正确理解 |
|------|---------|
| "performance governor 就够了" | intel_pstate 仍可在空闲时主动降频，数据面需 `intel_pstate=disable` |
| "关 C-state 会堆高功耗" | 数据面核 100% busy 本来就进不了 C-state；控制面核可保留 |
| "RAPL 限制不影响延迟" | 限制功率 → 降频 → 延迟增加 10-50% |
| "TDP = 实际功耗" | TDP 是散热设计值，实际可在 PL2 下短期超出 25% |
| "turbostat 显示频率稳定就够了" | 还要看 Busy%、CPU%c6、PkgWatt 三者配合同步检查 |

## 参考来源

- [[concepts/CPU 核心架构]]
- [[entities/CPU 隔离与实时调优]]
- Intel 64 and IA-32 Arch. Developer's Manual Vol.3B (Ch.14: Power Management)
- Intel RAPL Specification (Doc 323272)
- `turbostat` man page (Linux kernel tools/power/x86/turbostat)
- DPDK Power Management Library docs
