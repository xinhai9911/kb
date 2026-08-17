---
aliases: ["fpga", "FPGA 2"]
title: FPGA 知识（现场可编程门阵列）
tags: [protocol, fpga, vhd, vhdl, verilog, hardware, active]
created: 2026-07-29
summary: >-
    FPGA（现场可编程门阵列）是可重构的硬件逻辑器件：基于 SRAM 配置 LUT+FF+互连实现任意数字电路。本文梳理其架构（LUT/触发器/Block RAM/DSP/时钟资源）、开发全流程（RTL→仿真→综合→实现→比特流）、HDL 语言对比（VHDL/Verilog/SystemVerilog）、时序与跨时钟域、以及它与 ASIC/CPU/GPU 的取舍。
category: reference
updated: 2026-07-29
sources: []
base_confidence: 0.85
lifecycle: reviewed
---

# FPGA 知识（现场可编程门阵列）

## 概述

FPGA（Field-Programmable Gate Array，现场可编程门阵列）是一种**出厂后可由用户反复配置**的集成电路。与固定功能的 CPU/ASIC 不同，FPGA 内部是海量可配置逻辑单元 + 可编程互连，上电时由比特流（bitstream）把这片"空白逻辑"烧成你想要的任意数字电路（软核 CPU、网络处理、信号处理、协议卸载等）。

> 用法/工具链见 [[50-reference/FPGA 用法|FPGA 使用方法]]。本文讲"是什么 / 为什么"。

## 核心架构

### 1. 可配置逻辑块（CLB / ALM）

- **LUT（Look-Up Table，查找表）**：本质是一个小 SRAM（通常 6 输入），用真值表实现任意 n 输入组合逻辑。比如 6-LUT 能实现任意 6 输入布尔函数。
- **FF（Flip-Flop，触发器）**：每个 LUT 后通常跟一个寄存器，实现时序逻辑（打拍、状态机）。
- **Carry Chain**：专用进位链，高效实现加法器/计数器，避免占用普通互连。
- Xilinx 称为 **CLB**（含 SLICEL/SLICEM），Intel 称为 **ALM**（Adaptive Logic Module）。

### 2. 互连资源（Interconnect / Routing）

- 可编程开关矩阵把 LUT/FF/IO 连成电路。**布线（routing）**是 FPGA 实现阶段最耗时的一步。
- 长线 / 短线 / 全局时钟线分级，长线用于跨芯片信号，全局时钟线低偏斜（low skew）。

### 3. 嵌入式块资源

| 资源 | 用途 |
|---|---|
| **Block RAM (BRAM)** | 片上大容量 RAM（Xilinx 典型 36Kb/块），做 FIFO、缓存、ROM 初始化 |
| **DSP Slice** | 硬核乘法器/乘加（MAC），高效做 FIR、矩阵运算 |
| **时钟资源（MMCM/PLL/DCM）** | 时钟倍频/分频/相移/去抖，产生多路低抖动时钟 |
| **高速收发器（SerDes / GTY/GTH）** | 实现 10G/25G/100G 收发，PCIe、以太网、JESD204 |
| **硬核 IP** | 部分 FPGA 含硬核 CPU（Zynq 的 ARM）、PCIe 控制器、以太网 MAC |

### 4. 配置方式

- **SRAM 型**（Xilinx/Intel 主流）：易重配置，但掉电丢失，需外挂 Flash/处理器每次上电加载比特流。
- **Flash/反熔丝型**（Microchip/Actel、Lattice 部分）：掉电不丢，抗辐照，适合航天/工业。

## 开发全流程

```
RTL 设计 (VHDL/Verilog/SystemVerilog/HLS)
   │
   ▼ 仿真 (功能验证)
   ├─ 行为仿真 (RTL 级，无延时) —— iverilog / Verilator / ModelSim
   ▼ 综合 (Synthesis)
   │  RTL → 门级网表（映射 LUT/FF/DSP/BRAM）
   ▼ 实现 (Implementation)
   │  布局 (Place) + 布线 (Route) + 时序分析 (STA)
   ▼ 生成比特流 (Bitstream)
   │  .bit / .sof / .rbf
   ▼ 上板 (Program)
       JTAG / Quad-SPI Flash / 处理器加载
```

详细说明与命令见 [[50-reference/FPGA 用法|FPGA 使用方法]]。

## HDL 语言对比

| 维度 | VHDL | Verilog | SystemVerilog |
|---|---|---|---|
| 类型系统 | 强类型、严谨 | 弱类型、松散 | 兼具，强类型子集 |
| 学习曲线 | 陡，适合大型工程 | 平缓，类 C | 中 |
| 主流用途 | 欧洲/航天/防务 | 北美/ASIC 移植 | 现代验证+设计主流 |
| 本文库样例 | `Q:/AI/vhdl_examples/and_gate.vhd` | — | — |

- **RTL（Register-Transfer Level）**：描述"每个时钟沿，寄存器间的数据如何传输与变换"，是综合工具能映射到硬件的写法。
- 综合**不支持**所有语言特性（如 `wait for 10 ns`、文件 I/O、动态内存）——这些只用于仿真，称"不可综合（non-synthesizable）"。

## 时序与时钟

- **建立时间 (Setup) / 保持时间 (Hold)**：数据在时钟沿前后必须稳定的窗口。STA（静态时序分析）保证所有路径满足。
- **最大频率 Fmax**：由最长组合逻辑路径（关键路径）决定。优化手段：流水线（pipeline）、寄存器重定时、减少扇出。
- **跨时钟域 (CDC, Clock Domain Crossing)**：不同时钟域间传信号必须用**两级同步器（2-FF synchronizer）**、握手或异步 FIFO（见 [[50-reference/FPGA 用法|FPGA 使用方法]] §CDC）。
- **时钟使能 (CE)**：用同一时钟 + 使能信号比用多个分频时钟更省资源、更易满足时序。

## FPGA vs ASIC vs CPU vs GPU

| 维度 | FPGA | ASIC | CPU | GPU |
|---|---|---|---|---|
| 灵活性 | 可重配置 | 固定 | 可编程（软件） | 可编程（核多） |
| 单位性能/功耗 | 中 | 最优 | 低 | 高（并行） |
| 开发成本 | 低（无流片） | 极高（流片百万级） | 低 | 中 |
| 延迟 | 极低确定性 | 极低 | 高（OS/缓存） | 中（批处理） |
| 典型场景 | 原型验证、协议卸载、低延迟、小批量 | 大批量、低功耗 | 通用计算 | 大吞吐并行 |

## 典型应用（与本项目关联）

- **网络数据面**：FPGA 可做线速包处理、协议识别、加解密卸载（与 [[20-protocols/VPP 2|VPP]] 用户态方案互补：FPGA 在硬件层、VPP 在软件层）。
- **交换芯片**：盛科/博通交换 ASIC 的前端常配 FPGA 做灵活匹配（参见 [[50-reference/sources/chips/Centec CTC 7132|CTC7132]]）。
- **信号处理**：雷达、通信基带、DSP Slice 做 FIR/FFT。
- **原型验证**：ASIC 流片前的 FPGA 原型（emulation）。
- **加速卡**：SmartNIC、NVMe 卸载、TLS 加速。

## 深入主题

下面这些子领域已有独立笔记，按需深入：

- **可复用 RTL 范式**：FSM、流水线、同步/异步 FIFO、握手、AXI-Stream、仲裁器 → [[20-protocols/FPGA 设计 模式|FPGA 常用设计模式]]
- **验证方法论**：自检查 testbench、SVA/PSL 断言、功能覆盖率、约束随机、Verilator CI → [[50-reference/FPGA 验证|FPGA 验证方法]]
- **工具链实操**：仿真（iverilog/Verilator/GHDL）、综合实现（Vivado/Quartus）、CDC 写法、上板 → [[50-reference/FPGA 用法|FPGA 使用方法]]
- **厂商与开源生态**：AMD/Intel/Lattice/Microchip 选型、Yosys/nextpnr/openFPGALoader → [[entities/FPGA 厂商|FPGA 厂商与开源工具链]]

### 时序收敛（Timing Closure）要点

- **关键路径（critical path）**决定 Fmax。STA 报 WNS（最差负 slack）/ TNS（总负 slack），必须 ≥ 0。
- 优化手段：**流水线**切短组合路径、**寄存器重定时（retiming）**、**复制高扇出网络（fanout replication）**、**BLOCK RAM 替代分布式 RAM**、约束**多周期路径（multicycle）**放宽非关键路径。
- **跨时钟域**是 STA 难点：用 `set_clock_groups -asynchronous` 告诉工具两条时钟无关，避免误报；物理同步用 [[20-protocols/FPGA 设计 模式|设计模式]] §异步 FIFO。

### SoC / 软核

- **硬核 SoC**：Zynq（ARM Cortex-A + FPGA PL）、Intel SoC FPGA —— 软件跑 Linux，逻辑做加速，AMBA/AXI 互联。
- **软核（soft-core）**：在 LUT 里实现的 CPU，如 **MicroBlaze**（Xilinx）、**Nios II**（Intel）、开源 **RISC-V（VexRiscv / PicoRV32 / Rocket）**。小到控制状态机，大到跑 RTOS。

### 部分重配置（Partial Reconfiguration）

- 运行中只替换部分逻辑（其余继续工作），适合多协议时分复用、功能切换、热补丁。
- 商业工具支持（Vivado PR / Quartus PR）；开源侧尚不成熟。

### 资源、功耗、面积权衡

- **面积**：LUT/FF/BRAM/DSP 占用率；过高布线拥挤、Fmax 下降。
- **功耗**：静态（漏电流，工艺/温度） + 动态（翻转率 × 电容 × V² × f）。降功耗：降频降压、门控时钟（clock gating）、减少高翻转信号、用硬核替代软逻辑。
- **散热**：高密度设计注意结温，影响可靠性与 Fmax。

## 本地资源

- VHDL 样例：`Q:/AI/vhdl_examples/and_gate.vhd`（可用 GHDL 仿真）
- 设计模式、验证、用法、厂商笔记见上方「深入主题」与「延伸」。

## 延伸

- [[50-reference/FPGA 用法|FPGA 使用方法]]（Vivado/Quartus/Verilator/Icarus 实操、仿真、CDC、上板）
- [[20-protocols/FPGA 设计 模式|FPGA 常用设计模式]]（FSM/流水线/FIFO/握手/AXI-S/仲裁器）
- [[50-reference/FPGA 验证|FPGA 验证方法]]（testbench/断言/覆盖率/CI）
- [[entities/FPGA 厂商|FPGA 厂商与开源工具链]]（选型 + Yosys/nextpnr 生态）
- 厂商文档：Xilinx/AMD Vivado、Intel Quartus、Lattice Radiant、Verilator/iverilog 开源工具链
