---
title: FPGA 综合约束 XDC/SDC 写法
tags: [fpga, verilog, constraints, xdc, sdc, timing, active]
created: 2026-08-07
summary: >-
    FPGA 约束文件参考：Xilinx XDC / Intel SDC 语法速查、时钟约束（create_clock/Generated Clock）、I/O 约束（管脚/电容/驱动力）、伪路径/多周期路径、物理约束（Pblock/Location）、约束验证。
category: reference
updated: 2026-08-07
sources:
  - amd.com/support/documentation/user_guides
  - intel.com/content/www/us/en/docs/programmable/683091
base_confidence: 0.83
lifecycle: draft
---

# FPGA 综合约束 XDC/SDC 写法

> 约束写错 → 时序误报、功耗误判、管脚冲突。本文是 Xilinx XDC 和 Intel SDC 的**日常速查手册**。

## 1. 约束文件类型

| 文件 | 用途 | Xilinx | Intel |
|------|------|--------|-------|
| **时序约束** | 定义时钟、路径例外 | XDC | SDC |
| **I/O 约束** | 管脚绑定、电平标准 | XDC | QSF |
| **物理约束** | Pblock、位置锁定 | XDC | QSF |

Xilinx 用 **XDC**（Tcl 语法），Intel 用 **SDC**（标准 Tcl）+ **QSF**（Quartus Settings File）。

## 2. 时钟约束

### 基础时钟

```tcl
# XDC (Xilinx)
create_clock -name clk_100 -period 10.000 [get_ports clk_p]  ;# 100MHz
create_clock -name clk_200 -period 5.000  [get_ports clk_200] ;# 200MHz
```

```tcl
# SDC (Intel)
create_clock -name clk_100 -period 10.000 [get_ports clk]
```

### 生成时钟（PLL/MMCM 输出）

```tcl
# XDC — PLL 生成的时钟
create_generated_clock -name clk_250m \
    -source [get_ports clk_p] \
    -master_clock clk_100 \
    -multiply_by 5 -divide_by 2 \
    [get_pins u_pll/clk_out1]
```

```tcl
# SDC (Intel)
create_generated_clock -name clk_250m \
    -source [get_ports clk] \
    -multiply_by 5 -divide_by 2 \
    [get_pins u_pll|outclk0]
```

### 虚拟时钟（无输入端口的时钟）

```tcl
# XDC — 当 PLL 输入未连到顶层端口（内部 PLL 自振）
create_clock -name virtual_clk -period 8.0  ;# 无源端口
```

## 3. I/O 约束

### 管脚绑定

```tcl
# XDC
set_property PACKAGE_PIN E3 [get_ports clk_p]
set_property IOSTANDARD LVCMOS33 [get_ports clk_p]
set_property DRIVE 8 [get_ports led[0]]          ;# 驱动电流 8mA
set_property SLEW SLOW [get_ports led[0]]        ;# 压摆率
```

```tcl
# QSF (Intel)
set_location_assignment PIN_E3 -to clk
set_instance_assignment -name IO_STANDARD "3.3-V LVCMOS" -to clk
set_instance_assignment -name CURRENT_STRENGTH_NEW 8MA -to led[0]
```

### 输入/输出延迟

```tcl
# XDC — 外部器件延迟约束
set_input_delay -clock clk_100 -max 5.0 [get_ports data_in]   ;# 输入最大延迟
set_input_delay -clock clk_100 -min 2.0 [get_ports data_in]   ;# 输入最小延迟
set_output_delay -clock clk_100 -max 4.0 [get_ports data_out] ;# 输出最大延迟
set_output_delay -clock clk_100 -min 1.0 [get_ports data_out] ;# 输出最小延迟
```

## 4. 路径例外

### 伪路径（False Path）

```tcl
# XDC
# 异步复位（跨时钟域）
set_false_path -from [get_ports rst_n]

# 异步时钟组
set_clock_groups -asynchronous \
    -group [get_clocks clk_100] \
    -group [get_clocks clk_200]

# 跨 CDC 同步器（已知安全）
set_false_path -from [get_pins u_cdc/sync_reg1_reg/C] \
               -to   [get_pins u_cdc/sync_reg2_reg/D]
```

```tcl
# SDC (Intel)
set_false_path -from [get_ports rst_n]
set_false_path -from [get_clocks clk_100] -to [get_clocks clk_200]
```

### 多周期路径（Multicycle Path）

```tcl
# XDC — 非关键路径放宽 2 个周期
set_multicycle_path -setup 2 -from [get_pins u_reg1/C] -to [get_pins u_reg2/D]
set_multicycle_path -hold  1 -from [get_pins u_reg1/C] -to [get_pins u_reg2/D]

# 跨时钟域（同频异相）用 max/min delay 替代
set_max_delay -datapath_only 5.0 \
    -from [get_clocks clk_a] -to [get_clocks clk_b]
set_min_delay 1.0 \
    -from [get_clocks clk_a] -to [get_clocks clk_b]
```

## 5. 物理约束

### Pblock（区域约束）

```tcl
# XDC — 将某模块锁定到特定区域
create_pblock pblock_dma
resize_pblock pblock_dma -add {SLICE_X0Y0:SLICE_X31Y49}
add_cells_to_pblock pblock_dma [get_cells u_dma/*]
```

### IOB（寄存器打包到 IOB）

```tcl
# XDC — 强制输入寄存器打包到 IOB（改善 I/O 时序）
set_property IOB TRUE [get_ports data_in[*]]
```

### 位置锁定

```tcl
# XDC
set_property LOC SLICE_X10Y20 [get_cells u_shift_reg/shift_reg_reg[0]]
```

## 6. 约束验证

### Xilinx Vivado

```bash
# 检查约束语法
report_timing_summary -max_paths 10   # 看 WNS/TNS
report_clock_networks                  # 时钟网络报告
report_clocks -attribute               # 所有约束的时钟
check_timing -override_defaults no_clock  # 检查无时钟驱动的寄存器
```

### Intel Quartus

```bash
# TimeQuest 分析
TimeQuest> report_clocks
TimeQuest> report_timing -npaths 10
TimeQuest> report_unconstrained
```

## 7. 约束 Checklist

- [ ] 所有输入时钟都有 `create_clock`
- [ ] PLL/MMCM 输出有 `create_generated_clock`
- [ ] 异步时钟域有 `set_clock_groups -asynchronous` 或 `set_false_path`
- [ ] 异步复位有 `set_false_path -from [get_ports rst_n]`
- [ ] CDC 同步器有 `set_false_path`（或确认在同步器寄存器间）
- [ ] 输入/输出延迟有 `set_input_delay` / `set_output_delay`
- [ ] 非关键路径有多周期约束
- [ ] 无时钟寄存器已处理（`set_false_path` 或 `create_clock`）
- [ ] `report_timing_summary` 无负 slack

## 8. 常见坑

| 现象 | 原因 | 解决 |
|------|------|------|
| WNS 全负 | 缺少 `create_clock` | 补时钟约束 |
| 误报跨时钟域违规 | 未加 `set_clock_groups` | 加异步时钟组声明 |
| 时序收敛极慢 | 虚拟时钟路径过多 | 用 `set_max_delay -datapath_only` |
| I/O 时序差 | 缺少 `set_input_delay` | 加外部器件延迟约束 |
| 功耗估算偏差 | 翻转率未约束 | 加 `set_switching_activity` |

## 延伸

- AXI 总线：[[20-protocols/fpga-axi4-bus|AXI4 总线协议深度]]
- IP 核：[[20-protocols/fpga-ip-catalog|FPGA 常用 IP 核速查]]
- 工具链：[[50-reference/fpga-usage|FPGA 使用方法]]
- 知识：[[20-protocols/fpga|FPGA 知识]]
