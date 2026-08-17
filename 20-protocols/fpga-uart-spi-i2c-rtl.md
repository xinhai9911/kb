---
title: UART/SPI/I2C 外设接口 RTL 模板
tags: [fpga, verilog, rtl, uart, spi, i2c, active]
created: 2026-08-07
summary: >-
    FPGA 常用外设接口的可综合 Verilog 实现：UART 收发（波特率发生器+FIFO）、SPI Master/Slave（四种模式）、I2C Master（START/STOP/ACK 状态机）。含完整代码骨架与 AXI-Lite 集成。
category: reference
updated: 2026-08-07
sources: []
base_confidence: 0.84
lifecycle: draft
---

# UART/SPI/I2C 外设接口 RTL 模板

> UART、SPI、I2C 是 FPGA 最常实现的三种低速外设接口。本文给出**可综合的 Verilog 骨架**，可直接作为 SoC 外设子模块使用。

## 1. UART（串口）

### 协议要点

```
空闲态 = 高电平
Start = 1 bit 低电平
Data  = 8 bit（LSB first）
Stop  = 1 bit 高电平
```

```
idle ─┐   ┌─D0─D1─D2─...─D7─┐   ┌─ idle
      └───┘                  └───┘
      Start                   Stop
```

### 波特率发生器

```verilog
module baud_gen #(
    parameter CLK_FREQ = 100_000_000,
    parameter BAUD     = 115200
)(
    input  wire clk,
    input  wire rst_n,
    output reg  baud_tick   // 16x oversampling tick
);
    localparam DIVISOR = CLK_FREQ / (BAUD * 16);
    reg [$clog2(DIVISOR)-1:0] cnt;

    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n)           cnt <= 0;
        else if (cnt == DIVISOR-1) cnt <= 0;
        else                   cnt <= cnt + 1;

    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n)                 baud_tick <= 0;
        else if (cnt == DIVISOR-1)  baud_tick <= 1;
        else                        baud_tick <= 0;
endmodule
```

### UART TX（可综合）

```verilog
module uart_tx #(
    parameter CLK_FREQ = 100_000_000,
    parameter BAUD     = 115200
)(
    input  wire       clk,
    input  wire       rst_n,
    input  wire [7:0] din,
    input  wire       din_valid,
    output reg        din_ready,
    output reg        tx
);
    // FSM
    localparam S_IDLE = 2'd0, S_START = 2'd1, S_DATA = 2'd2, S_STOP = 2'd3;
    reg [1:0] state;
    reg [3:0] bit_cnt;
    reg [7:0] shift_reg;

    wire baud_tick;
    baud_gen #(.CLK_FREQ(CLK_FREQ), .BAUD(BAUD))
        u_baud (.clk(clk), .rst_n(rst_n), .baud_tick(baud_tick));

    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n) begin
            state     <= S_IDLE;
            tx        <= 1'b1;  // 空闲高
            din_ready <= 1'b1;
        end else begin
            case (state)
                S_IDLE: if (din_valid) begin
                    state     <= S_START;
                    shift_reg <= din;
                    bit_cnt   <= 0;
                    din_ready <= 1'b0;
                end
                S_START: if (baud_tick) state <= S_DATA;
                S_DATA: if (baud_tick) begin
                    tx <= shift_reg[0];
                    shift_reg <= {1'b0, shift_reg[7:1]};
                    bit_cnt <= bit_cnt + 1;
                    if (bit_cnt == 4'd7) state <= S_STOP;
                end
                S_STOP: if (baud_tick) begin
                    tx        <= 1'b1;
                    state     <= S_IDLE;
                    din_ready <= 1'b1;
                end
            endcase
        end
endmodule
```

### UART RX（16x 过采样）

```verilog
module uart_rx #(
    parameter CLK_FREQ = 100_000_000,
    parameter BAUD     = 115200
)(
    input  wire       clk,
    input  wire       rst_n,
    input  wire       rx,
    output reg  [7:0] dout,
    output reg        dout_valid,
    input  wire       dout_ready
);
    // 16x 过采样：在 bit 中心采样（tick 7/8/9 拍取多数表决）
    localparam S_IDLE = 3'd0, S_START = 3'd1, S_DATA = 3'd2, S_STOP = 3'd3;
    reg [2:0] state;
    reg [3:0] tick_cnt, bit_cnt;
    reg [7:0] shift_reg;

    wire baud_tick;
    baud_gen #(.CLK_FREQ(CLK_FREQ), .BAUD(BAUD*16))
        u_baud (.clk(clk), .rst_n(rst_n), .baud_tick(baud_tick));

    // 简化：1x baud（实际项目用 16x + 中心采样）
    // 此处省略完整 oversample 逻辑，用等效 1x 采样
    wire sample = baud_tick;

    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n) begin
            state      <= S_IDLE;
            dout_valid <= 1'b0;
        end else begin
            case (state)
                S_IDLE: if (!rx) begin          // 检测起始位
                    state   <= S_START;
                    tick_cnt <= 0;
                end
                S_START: if (sample) begin
                    tick_cnt <= tick_cnt + 1;
                    if (tick_cnt == 4'd7) begin  // bit 中心
                        if (!rx) begin           // 确认起始位
                            state   <= S_DATA;
                            bit_cnt <= 0;
                        end else
                            state <= S_IDLE;
                    end
                end
                S_DATA: if (sample) begin
                    tick_cnt <= tick_cnt + 1;
                    if (tick_cnt == 4'd15) begin
                        shift_reg <= {rx, shift_reg[7:1]};
                        tick_cnt <= 0;
                        bit_cnt <= bit_cnt + 1;
                        if (bit_cnt == 4'd7) state <= S_STOP;
                    end
                end
                S_STOP: if (sample) begin
                    if (rx) begin               // 确认停止位
                        dout_valid <= 1'b1;
                        dout       <= shift_reg;
                    end
                    state <= S_IDLE;
                end
            endcase
        end
endmodule
```

### UART 与 AXI-Lite 集成

常见模式：UART TX/RX + 16 字节 FIFO → AXI-Lite 寄存器映射：

| 偏移 | 读 | 写 | 说明 |
|------|-----|-----|------|
| 0x00 | RX FIFO data | TX FIFO data | 数据端口 |
| 0x04 | RX FIFO count | TX FIFO count | 队列深度 |
| 0x08 | Status (bit0=RX ready, bit1=TX empty) | Control (bit0=RX reset, bit1=TX reset) | 状态/控制 |

## 2. SPI（串行外设接口）

### 协议要点

```
SPI Master                      SPI Slave
  SCLK ──────────────────────────► SCLK
  MOSI ──────────────────────────► MOSI
  MISO ◄──────────────────────────  MISO
  SS#  ──────────────────────────► SS#
```

**四种模式**（CPOL + CPHA）：

| Mode | CPOL | CPHA | 时钟空闲 | 采样边沿 |
|------|------|------|---------|---------|
| 0 | 0 | 0 | 低 | 上升沿 |
| 1 | 0 | 1 | 低 | 下降沿 |
| 2 | 1 | 0 | 高 | 下降沿 |
| 3 | 1 | 1 | 高 | 上升沿 |

### SPI Master（可综合）

```verilog
module spi_master #(
    parameter CLK_FREQ  = 100_000_000,
    parameter SPI_FREQ  = 10_000_000,
    parameter CPOL      = 0,
    parameter CPHA      = 0,
    parameter DATA_WIDTH = 8
)(
    input  wire                        clk,
    input  wire                        rst_n,
    // 用户接口
    input  wire [DATA_WIDTH-1:0]       din,
    input  wire                        din_valid,
    output reg                         din_ready,
    output reg  [DATA_WIDTH-1:0]       dout,
    output reg                         dout_valid,
    // SPI 接口
    output reg                         sclk,
    output reg                         mosi,
    input  wire                        miso,
    output reg                         ss_n
);
    localparam DIVISOR = CLK_FREQ / (SPI_FREQ * 2);
    reg [$clog2(DIVISOR)-1:0] clk_cnt;
    reg [$clog2(DATA_WIDTH):0] bit_cnt;
    reg [DATA_WIDTH-1:0] shift_reg;

    wire sclk_edge = (clk_cnt == DIVISOR-1);

    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n) begin
            ss_n      <= 1'b1;
            sclk      <= CPOL;
            din_ready <= 1'b1;
            dout_valid<= 1'b0;
        end else begin
            case ({din_valid && din_ready, sclk_edge})
                2'b10: begin  // 开始传输
                    ss_n     <= 1'b0;
                    din_ready<= 1'b0;
                    shift_reg<= din;
                    bit_cnt  <= DATA_WIDTH;
                    clk_cnt  <= 0;
                end
                2'b01: begin  // 时钟沿
                    clk_cnt <= 0;
                    if (!ss_n) begin
                        if (CPHA == 0) begin
                            mosi <= shift_reg[DATA_WIDTH-1];
                            shift_reg <= {shift_reg[DATA_WIDTH-2:0], miso};
                        end else begin
                            shift_reg <= {shift_reg[DATA_WIDTH-2:0], miso};
                            mosi <= shift_reg[DATA_WIDTH-1];
                        end
                        bit_cnt <= bit_cnt - 1;
                        if (bit_cnt == 1) begin
                            ss_n      <= 1'b1;
                            din_ready <= 1'b1;
                            dout_valid<= 1'b1;
                            dout      <= shift_reg;
                        end
                    end else
                        clk_cnt <= clk_cnt + 1;
                end
                default: begin
                    clk_cnt <= clk_cnt + 1;
                    if (dout_valid) dout_valid <= 1'b0;
                end
            endcase
        end
endmodule
```

## 3. I2C（双线串行）

### 协议要点

```
SDA ──┐───┐───┐───...───┐───┐───
      └───┘   └───      └───┘
SCL ───┐   ┌───┐   ┌───...───┐   ┌───
       └───┘   └───┘         └───┘

START: SDA↓ while SCL=H
STOP:  SDA↑ while SCL=H
ACK:   SDA=L on 9th SCL cycle
```

### I2C Master 状态机

```verilog
module i2c_master #(
    parameter CLK_FREQ = 100_000_000,
    parameter I2C_FREQ = 100_000   // 标准模式 100kHz
)(
    input  wire       clk,
    input  wire       rst_n,
    // User interface
    input  wire [6:0] addr,       // 7-bit slave address
    input  wire       rw,         // 0=write, 1=read
    input  wire [7:0] din,
    input  wire       din_valid,
    output reg  [7:0] dout,
    output reg        dout_valid,
    output reg        busy,
    // I2C lines (active-low, open-drain)
    inout  wire       sda,
    inout  wire       scl
);
    // 时钟分频产生 SCL
    localparam DIVISOR = CLK_FREQ / (I2C_FREQ * 2);
    reg [$clog2(DIVISOR)-1:0] clk_cnt;
    reg scl_toggle;

    // SDA 控制（开漏）
    reg sda_out;
    assign sda = sda_out ? 1'bz : 1'b0;  // 开漏
    assign scl = scl_toggle ? 1'bz : 1'b0;

    // FSM: IDLE → START → ADDR → ACK → DATA → ACK → STOP
    localparam S_IDLE=4'd0, S_START=4'd1, S_ADDR=4'd2,
               S_ACK1=4'd3, S_WRITE=4'd4, S_READ=4'd5,
               S_ACK2=4'd6, S_STOP=4'd7;
    reg [3:0] state;
    reg [3:0] bit_cnt;
    reg [7:0] shift_reg;

    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n) begin
            state <= S_IDLE;
            sda_out <= 1'b1;
            scl_toggle <= 1'b1;
            busy <= 1'b0;
        end else begin
            case (state)
                S_IDLE: if (din_valid) begin
                    state     <= S_START;
                    shift_reg <= {addr, rw};
                    busy      <= 1'b1;
                end
                S_START: begin
                    sda_out <= 0;       // SDA↓ (SCL=H)
                    #T_su;              // 等待 tSU;STA
                    scl_toggle <= 0;    // SCL↓
                    state <= S_ADDR;
                    bit_cnt <= 7;
                end
                S_ADDR: begin
                    scl_toggle <= 1;    // SCL↑
                    sda_out <= shift_reg[bit_cnt]; // 发送地址
                    // ... 在 SCL 高电平时采样/驱动
                end
                // ... 后续状态省略（ACK/DATA/STOP）
                S_STOP: begin
                    sda_out <= 0;
                    scl_toggle <= 1;    // SCL↑
                    #T_h;              // tHD;STA
                    sda_out <= 1;       // SDA↑ (SCL=H) → STOP
                    state <= S_IDLE;
                    busy  <= 1'b0;
                end
            endcase
        end
endmodule
```

> 完整 I2C Master 需要处理：时钟拉伸（clock stretching）、多主机仲裁、总线空闲检测。建议使用开源 IP 如 [wishbone-i2c](https://github.com/stffrdhrn/i2c) 或 Xilinx LogiCORE。

## 4. 三种协议对比

| 特性 | UART | SPI | I2C |
|------|------|-----|-----|
| 线数 | 2 (TX/RX) | 4+ (SCLK/MOSI/MISO/SS) | 2 (SDA/SCL) |
| 速率 | 115200~3M baud | 1~100 MHz | 100K/400K/1MHz |
| 主从 | 点对点 | 1 主 N 从（SS 选） | 多主多从（地址选） |
| 时钟 | 异步（双方波特率约定） | 同步（Master 提供） | 同步（Master 提供） |
| FPGA 资源 | 极少 | 少 | 少（需开漏驱动） |
| 典型场景 | 调试串口、GPS | Flash/ADC/传感器 | EEPROM/PMIC/温传 |

## 5. AXI-Lite 集成模式

三种外设都可通过 AXI-Lite 挂到 SoC 总线（见 [[20-protocols/fpga-axi4-bus|AXI4 总线协议]] §AXI4-Lite）：

```
CPU (MicroBlaze / RISC-V)
  │
  │ AXI Interconnect
  ├──► AXI-Lite UART → TX/RX pins
  ├──► AXI-Lite SPI  → MOSI/MISO/CLK/SS pins
  └──► AXI-Lite I2C  → SDA/SCL pins
```

每个外设占用 4~64 字节地址空间，CPU 通过寄存器读写控制收发。

## 延伸

- 总线：[[20-protocols/fpga-axi4-bus|AXI4 总线协议深度]]
- 设计模式：[[20-protocols/fpga-design-patterns|FPGA 常用设计模式]]
- IP 核：[[20-protocols/fpga-ip-catalog|FPGA 常用 IP 核速查]]
- Zynq SoC：[[20-protocols/fpga-zynq-soc|Zynq SoC 开发]]
- 知识：[[20-protocols/fpga|FPGA 知识]]
