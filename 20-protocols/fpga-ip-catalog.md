---
title: FPGA 常用 IP 核速查
tags: [fpga, verilog, ip, xilinx, intel, reference, active]
created: 2026-08-07
summary: >-
    FPGA 厂商常用 IP 核速查手册：Xilinx（MMCM/PLL/FIFO/DMA/Interconnect/MIG/XPM）和 Intel（PLL/DCFIFO/DMA/Interconnect）IP 的用途、配置参数、生成方式与陷阱。
category: reference
updated: 2026-08-07
sources: []
base_confidence: 0.82
lifecycle: draft
---

# FPGA 常用 IP 核速查

> 厂商 IP 核能省几个月的手搓时间，但**配置参数一错就是 bug**。本文按用途速查 Xilinx/Intel 最常用 IP。

## 1. 时钟管理

### MMCM/PLL（Xilinx）

```tcl
# Vivado IP Catalog → Clocking Wizard
create_ip -name clk_wiz -vendor xilinx.com -library ip -module_name clk_wiz_0
set_property -dict [list \
    CONFIG.PRIM_IN_FREQ {100.000} \
    CONFIG.CLKOUT1_REQUESTED_OUT_FREQ {250.000} \
    CONFIG.CLKOUT2_USED {true} \
    CONFIG.CLKOUT2_REQUESTED_OUT_FREQ {125.000} \
    CONFIG.CLKOUT3_USED {true} \
    CONFIG.CLKOUT3_REQUESTED_OUT_FREQ {50.000} \
] [get_ips clk_wiz_0]
```

| 参数 | 说明 |
|------|------|
| `PRIM_IN_FREQ` | 输入时钟频率 (MHz) |
| `CLKOUTn_REQUESTED_OUT_FREQ` | 输出 n 频率 |
| `CLKOUTn_DIVIDE` | 分频比（自动计算） |
| `USE_LOCKED` | 输出 locked 信号（PLL 稳定标志） |
| `USE_RESET` | 输入复位 |

### PLL (Intel/Quartus)

```tcl
# Quartus → IP Catalog → PLL (ALTPLL)
# 输出时钟频率 = INCLK0_FREQ / M * N / C0
# 参数：INCLK0_FREQUENCY, CLK0_DIVIDE_BY, CLK0_MULTIPLY_BY
```

**Xilinx 原语替代**（不走 IP Catalog）：

```verilog
// MMCME2_ADV（7 系列原语，比 Clocking Wizard 更灵活）
MMCME2_ADV #(
    .CLKFBIN_MULT(10),       // 输入 100MHz × 10 = 1000MHz VCO
    .CLKOUT0_DIVIDE(4),      // 1000/4 = 250MHz
    .CLKOUT1_DIVIDE(8),      // 1000/8 = 125MHz
    .CLKOUT2_DIVIDE(20)      // 1000/20 = 50MHz
) u_mmcme2 (
    .CLKIN1(clk_100mhz),
    .CLKFBIN(clkfb),
    .CLKOUT0(clk_250mhz),
    .CLKOUT1(clk_125mhz),
    .CLKOUT2(clk_50mhz),
    .LOCKED(locked),
    .RST(1'b0),
    .CLKFBOUT(clkfb)
);
```

## 2. FIFO

### 同步 FIFO（Xilinx XPM）

```verilog
// XPM 原语（推荐，不走 IP Catalog，代码可移植）
xpm_fifo_sync #(
    .FIFO_WRITE_DEPTH(256),
    .WRITE_DATA_WIDTH(64),
    .READ_DATA_WIDTH(64),
    .FULL_RESET_VALUE(1),
    .READ_DATA_LATENCY(1),
    .FIFO_MEMORY_TYPE("block")  // "block"=BRAM, "distributed"=LUT
) u_fifo (
    .clk(clk),
    .rst(~rst_n),
    .wr_en(wr_en),
    .din(din),
    .rd_en(rd_en),
    .dout(dout),
    .full(full),
    .empty(empty),
    .wr_data_count(wr_count),
    .rd_data_count(rd_count)
);
```

### 异步 FIFO（Xilinx XPM）

```verilog
xpm_fifo_async #(
    .FIFO_WRITE_DEPTH(256),
    .WRITE_DATA_WIDTH(64),
    .READ_DATA_WIDTH(64),
    .CDC_SYNC_STAGES(2),       // CDC 同步级数
    .FIFO_MEMORY_TYPE("block"),
    .WRITE_MODE("no_change")
) u_async_fifo (
    .wr_clk(clk_src),
    .rd_clk(clk_dst),
    .rst(~rst_n),
    .wr_en(wr_en),
    .din(din),
    .rd_en(rd_en),
    .dout(dout),
    .full(full),
    .empty(empty)
);
```

### FIFO (Intel/Quartus)

```tcl
# Quartus → scfifo（同步）/ dcfifo（异步）
# scfifo: Width, Depth, LPM_TYPE = "M-RAM"/"auto"
# dcfifo: 额外参数 ADD_USED_WORDS_MSB_SYNCHRONIZATION_REG
```

## 3. DMA（直接内存访问）

### Xilinx AXI DMA

```tcl
# IP Catalog → AXI DMA
# 两种模式：
#   1. Simple DMA: 单向，单通道（memcpy）
#   2. Scatter-Gather DMA: 多描述符链表，高吞吐

# 关键参数
CONFIG.c_include_sg {0}              # 0=Simple, 1=Scatter-Gather
CONFIG.c_m_axi_mm2s_data_width {64}  # MM2S 数据宽度
CONFIG.c_m_axi_s2mm_data_width {64}  # S2MM 数据宽度
```

DMA 接口：
```
AXI4-MM 读端口 → 从 DDR 读数据 → AXI-Stream MM2S → 用户 IP
用户 IP → AXI-Stream S2MM → 从 DDR 写数据 → AXI4-MM 写端口
```

### Intel DMA (Intel Avalon)

```tcl
# Quartus → DMA Controller (Qsys)
# 接口：Avalon-MM Master + Avalon-ST Sink/Source
```

## 4. AXI 互联

### Xilinx SmartConnect（推荐）

```tcl
# IP Catalog → SmartConnect
# 参数：NUM_SI (slave 端口数), NUM_MI (master 端口数)
# 比旧版 axi_interconnect 更高效（真 crossbar，非 time-multiplexed）
```

### Xilinx AXI Interconnect（简单场景）

```tcl
# 参数同上，但内部是共享总线（time-multiplexed），带宽较低
```

### AXI 数据宽度转换

```tcl
# AXI4 Data Width Converter
# 用途：64-bit AXI ↔ 512-bit AXI（如 CPU 64-bit → DDR 512-bit）
# 参数：S_AXI_DATA_WIDTH, M_AXI_DATA_WIDTH
```

### AXI 时钟转换

```tcl
# AXI4 Clock Converter
# 用途：跨时钟域 AXI 互联（如 100MHz CPU → 250MHz 加速器）
# 参数：S_AXI_ACLK_FREQ, M_AXI_ACLK_FREQ
```

## 5. 存储器接口

### MIG 7 系列（DDR3）

```tcl
# IP Catalog → Memory Interface Generator (7 Series)
# 1. Component → DDR3 SDRAM
# 2. Memory Part → MT41K256M16 (例)
# 3. Data Width → 16/32/64
# 4. System Clock → 200MHz 差分
# 输出：AXI4 用户接口 + init_calib_complete
```

### MIG UltraScale（DDR4）

```tcl
# 同上，选择 DDR4 SDRAM 组件
# 额外参数：ECC（可选）、Bank Group
```

## 6. XPM 原语速查（Xilinx Parameterized Macros）

XPM 是**代码内嵌**的参数化宏，无需生成 IP 文件：

| XPM 名称 | 用途 |
|----------|------|
| `xpm_fifo_sync` | 同步 FIFO |
| `xpm_fifo_async` | 异步 FIFO |
| `xpm_memory_dpram` | 双端口 RAM |
| `xpm_memory_sprom` | 单端口 ROM |
| `xpm_memory_sdpram` | 简单双端口 RAM |
| `xpm_cdc_gray` | 格雷码 CDC |
| `xpm_cdc_single` | 单比特 CDC |
| `xpm_cdc_array_single` | 多比特 CDC |
| `xpm_counter_binary` | 二进制计数器 |
| `xpm_counter_gray` | 格雷码计数器 |

```verilog
// 示例：用 XPM 做双端口 BRAM（替代手写）
xpm_memory_dpram #(
    .MEMORY_SIZE(8192),
    .MEMORY_PRIMITIVE("block"),
    .WRITE_DATA_WIDTH_A(64),
    .READ_DATA_WIDTH_A(64),
    .ADDR_WIDTH_A(7)
) u_bram (
    .clka(clk_a),
    .wea(we_a),
    .addra(addr_a),
    .dina(din_a),
    .douta(dout_a),
    .clkb(clk_b),
    .web(we_b),
    .addrb(addr_b),
    .dinb(din_b),
    .doutb(dout_b)
);
```

## 7. IP 选型决策树

```
需要什么？
├─ 时钟生成 → MMCM/PLL (Clocking Wizard)
├─ 缓冲/弹性 → FIFO (xpm_fifo_sync / xpm_fifo_async / scfifo / dcfifo)
├─ 数据搬运 → DMA (AXI DMA / Qsys DMA)
├─ 多主互联 → SmartConnect / AXI Interconnect
├─ 宽度/时钟转换 → AXI Data Width Converter / Clock Converter
├─ 外部存储 → MIG (DDR3/4) / QSPI Flash Controller
├─ 高速收发 → GTH/GTY Transceiver (10G/25G/100G)
└─ 通用计数 → xpm_counter_binary / xpm_counter_gray
```

## 8. IP 核使用陷阱

| 陷阱 | 说明 |
|------|------|
| **IP 版本不一致** | 升级 Vivado 后旧 IP 可能不可用，需 regenerate |
| **AXI ID 宽度不匹配** | Master/Slave 的 ID 宽度必须一致 |
| **FIFO 深度必须是 2 的幂** | Xilinx FIFO IP 不支持非 2 深度 |
| **异步 FIFO 空满有延迟** | 空/满标志有 2~3 拍延迟，不能做背靠背写 |
| **MIG 校准时间** | init_calib_complete 需要 ~100ms，复位后不要立即访问 |
| **DMA 描述符对齐** | Scatter-Gather 描述符需 32/64 字节对齐 |
| **License** | 部分 IP 需要 Vivado Enterprise License |

## 延伸

- 设计模式：[[20-protocols/fpga-design-patterns|FPGA 常用设计模式]]
- AXI 总线：[[20-protocols/fpga-axi4-bus|AXI4 总线协议深度]]
- DDR 存储：[[20-protocols/fpga-ddr-memory|DDR 存储器接口与 MIG 控制器]]
- 工具链：[[50-reference/fpga-usage|FPGA 使用方法]]
- 知识：[[20-protocols/fpga|FPGA 知识]]
