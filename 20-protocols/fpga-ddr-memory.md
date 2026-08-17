---
title: DDR 存储器接口与 MIG 控制器
tags: [fpga, verilog, ddr, memory, mig, active]
created: 2026-08-07
summary: >-
    FPGA 上的 DDR SDRAM 接口：DDR3/4/5 原理与差异、Xilinx MIG 控制器 IP、AXI4 用户接口、校准/训练、ECC、时序约束、常见坑。
category: reference
updated: 2026-08-07
sources:
  - amd.com/products/memory-solution
  - jeddarc.org
base_confidence: 0.83
lifecycle: draft
---

# DDR 存储器接口与 MIG 控制器

> FPGA 做数据密集应用（视频缓冲、网络包缓存、大矩阵运算）几乎都需要外挂 DDR。本文讲 FPGA 侧如何接 DDR、用什么 IP、怎么写约束。

## 1. DDR 代际速查

| 特性 | DDR3 | DDR4 | DDR5 |
|------|------|------|------|
| 速率（MT/s） | 800~2133 | 1600~3200 | 3200~6400 |
| 电压 | 1.5V | 1.2V | 1.1V |
| Bank 数 | 8 | 16 | 32 |
| Burst Length | 8（固定） | 8（固定） | 8/16 |
| ECC | 可选（side-band） | 可选 | 片上 ECC（on-die ECC） |
| FPGA 主流支持 | 7 系列 | UltraScale/UltraScale+ | Versal |

**FPGA 选型建议**：
- 7 系列 → DDR3（MIG 7 Series）
- UltraScale/UltraScale+ → DDR4（MIG UltraScale）
- Versal → DDR5（硬核 DDR 控制器）

## 2. FPGA 上的 DDR 系统

```
FPGA 芯片
┌────────────────────────────────────────┐
│                                        │
│  用户逻辑                              │
│     │ AXI4                             │
│     ▼                                  │
│  ┌──────────┐   PHY    ┌──────────┐   │
│  │ MIG IP   │────────►│ DDR PHY  │───►── DDR 芯片
│  │ (控制器)  │         │ (DQ/DM/CS)│      (DIMM/SODIMM/Chip)
│  └──────────┘         └──────────┘   │
│                                        │
└────────────────────────────────────────┘
```

关键组件：
- **MIG（Memory Interface Generator）**：Xilinx 提供的 DDR 控制器 IP
- **DDR PHY**：处理 DQ/DM/CK/CS 等物理信号，含校准逻辑
- **用户接口**：通常为 AXI4，用户逻辑无需关心 DDR 时序

## 3. Xilinx MIG IP 配置要点

### 7 系列 MIG（DDR3）

```
Board Design:
  1. Component → DDR3 SDRAM
  2. FPGA Package → 自动匹配
  3. Memory Parts → 选择具体型号（如 MT41K256M16）
  4. Clock Period → 2500ps (400MHz DDR = 800MT/s)
  5. System Clock → 200MHz 差分输入
  6. Reference Clock → 200MHz（MIG ref_clk）
```

### UltraScale MIG（DDR4）

```
Board Design:
  1. DDR4 SDRAM
  2. Memory Speed → DDR4-2400/2666
  3. Data Width → 64 bit（典型）
  4. ECC → 可选（72-bit 宽度含 ECC）
```

### MIG 输出接口

MIG 生成后的用户端口（简化）：

```verilog
// 用户接口（AXI4）
input  wire [31:0] s_axi_awaddr,
input  wire        s_axi_awvalid,
output wire        s_axi_awready,
input  wire [511:0] s_axi_wdata,   // 宽度可配置
input  wire [63:0]  s_axi_wstrb,
input  wire        s_axi_wlast,
input  wire        s_axi_wvalid,
output wire        s_axi_wready,
output wire [31:0] s_axi_bresp,
output wire        s_axi_bvalid,
input  wire        s_axi_bready,
// ... 读通道同理

// 状态信号
output wire init_calib_complete,   // 校准完成
output wire ui_clk,                // 用户时钟（如 300MHz）
output wire ui_clk_sync_rst        // 同步复位
```

**init_calib_complete** 必须为 1 后才能开始读写。

## 4. DDR 时序基础

### 读写时序（简化）

```
写事务：
  AW ──► [tRP] Precharge ──► [tRCD] Activate ──► [CAS] Write Burst
  W  ────────────────────────────────────────────► Write Data (BL8)

读事务：
  AR ──► [tRP] Precharge ──► [tRCD] Activate ──► [CAS] Read Burst
  R  ◄─────────────────────────────────────────────── Read Data (BL8)
```

关键时序参数：
- **tRCD**：Row-to-Column Delay（行激活到读/写）
- **CAS Latency (CL)**：列地址到数据输出的延迟
- **tRP**：Row Precharge Time
- **tRC**：Row Cycle Time = tRCD + tRP
- **tREFI**：刷新周期（64ms 内全部行刷新）

> **用户无需手动管理这些时序**——MIG 控制器自动处理，AXI4 接口已屏蔽底层。

## 5. DDR 带宽计算

```
理论带宽 = 数据速率 × 数据宽度 / 8

例：DDR3-1600 × 64-bit
  = 1600 MT/s × 64 bit / 8
  = 12.8 GB/s

实际带宽 ≈ 理论 × 70~85%（命令开销 + 刷新 + bank 切换）
```

## 6. ECC 与可靠性

| 方案 | 实现 | 特点 |
|------|------|------|
| **Side-band ECC** | MIG 控制器额外加 ECC 校验码 | DDR3/4 常用，需额外 8 bit |
| **On-die ECC** | DDR5 芯片内部自纠错 | 对 FPGA 透明 |
| **Chipkill** | 多芯片冗余 | 服务器级，FPGA 少用 |

ECC 启用后数据宽度从 64 bit 变为 72 bit（64 data + 8 ECC）。

## 7. 时序约束（XDC）

```tcl
# 系统参考时钟（给 MIG）
create_clock -name sys_clk -period 5.000 [get_ports sys_clk_p]  ;# 200MHz

# MIG 生成的用户时钟（由 MIG 自动约束）
# 通常不需要手动约束 ui_clk，但需确保：
set_false_path -from [get_pins -hierarchical -filter {NAME =~ *init_calib_complete*}]

# DDR 接口管脚约束（MIG 自动输出到 .xdc）
# 手动检查项：
#   1. DQ/DQS 组是否在同一 Bank
#   2. 差分时钟 CK/CK# 是否正确绑定
#   3. VCCO = 1.5V（DDR3）或 1.2V（DDR4）

# 异步复位
set_false_path -from [get_ports sys_rst_n]

# MIG init_calib_complete 到用户逻辑
set_false_path -from [get_pins -hierarchical -filter {NAME =~ *u_mig_7series_0/*calib_complete*}]
```

## 8. DDR vs BRAM 选型

| 维度 | BRAM (片上) | DDR (片外) |
|------|------------|------------|
| 容量 | 1~10 MB | 512 MB~16 GB |
| 延迟 | 1~3 拍（极低） | ~100 拍（含行激活） |
| 带宽 | 10~100 GB/s（多端口） | 10~25 GB/s（单通道） |
| 适用 | FIFO、小缓冲、LUT RAM | 大帧缓冲、数据库、大矩阵 |

**常见模式**：BRAM 做 FIFO/小缓冲 ↔ DDR 做大容量存储，中间用 DMA 搬运。

## 9. 常见坑

| 现象 | 原因 | 解决 |
|------|------|------|
| init_calib_complete 不拉高 | 时钟/管脚/电压不对 | 检查 sys_clk、VCCO、DQ 线序 |
| 读写数据不一致 | AXI burst 长度超限 | AXI burst ≤ DDR page size |
| 间歇性数据错误 | DQ 时序偏移 | 检查 DQS center-align，跑 MIG 校准 |
| 带宽不达标 | bank 切换频繁 | 优化访问模式，row-hit 优先 |
| 功耗过高 | 频繁刷新 + 高翻转率 | 降频、关闭未用 bank |

## 延伸

- AXI 总线：[[20-protocols/fpga-axi4-bus|AXI4 总线协议深度]]
- IP 速查：[[20-protocols/fpga-ip-catalog|FPGA 常用 IP 核速查]]
- Zynq SoC：[[20-protocols/fpga-zynq-soc|Zynq SoC 开发]]（PS 侧 DDR 控制器）
- 知识：[[20-protocols/fpga|FPGA 知识]]
