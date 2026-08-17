---
title: AXI4 总线协议深度
tags: [fpga, verilog, rtl, axi, protocol, active]
created: 2026-08-07
summary: >-
    AMBA AXI4 协议族：Full/Lite/Stream 三变体、5 通道信号定义、burst 传输、outstanding/out-of-order、握手机制、AXI Interconnect 原理。可综合代码示例。
category: reference
updated: 2026-08-07
sources:
  - amd.com/product/silicon-devices/soc/zynq-7000
  - developer.arm.com/documentation/ihi0022
base_confidence: 0.85
lifecycle: draft
---

# AXI4 总线协议深度

> AXI（Advanced eXtensible Interface）是 ARM AMBA 家族中**最高带宽**的总线，也是 Xilinx/Intel FPGA SoC 互联的事实标准。本文覆盖 AXI4 Full、AXI4-Lite、AXI4-Stream 三变体。

## 1. AXI4 协议族

| 变体 | 通道 | 用途 | 典型场景 |
|------|------|------|----------|
| **AXI4 Full** | 5 通道全开 | 高带宽存储映射读写 | DDR、BRAM、DMA |
| **AXI4-Lite** | 5 通道（简化） | 低速寄存器配置 | UART/GPIO/SPI 控制寄存器 |
| **AXI4-Stream** | 无地址，纯数据流 | 流式数据传输 | 网络包处理、DSP 数据流、视频流 |

**选择直觉**：
- 需要 burst + 地址映射 → AXI4 Full
- 只需读写几个寄存器 → AXI4-Lite（省资源）
- 纯流式无地址 → AXI4-Stream（见 [[20-protocols/fpga-design-patterns|设计模式]] §AXI-S）

## 2. 五通道架构

AXI4 Full 由 5 个独立单向通道组成，每个通道有独立的 **Valid/Ready 握手**：

```
                ┌──────────────┐
Write Address ──► AW Channel  │
Write Data    ──► W  Channel  │    写事务
Write Response◄── B  Channel  │
                └──────────────┘
                ┌──────────────┐
Read Address  ──► AR Channel  │
Read Data     ◄── R  Channel  │    读事务
                └──────────────┘
```

### 各通道信号（AXI4 Full）

```verilog
// 写地址通道 (AW)
input  wire [7:0]   s_axi_awid,       // 事务 ID
input  wire [31:0]  s_axi_awaddr,     // 目标地址
input  wire [7:0]   s_axi_awlen,      // burst 长度 (0-255 → 1-256 拍)
input  wire [2:0]   s_axi_awsize,     // 每拍字节数 (2^size)
input  wire [1:0]   s_axi_awburst,    // burst 类型 (FIXED/INCR/WRAP)
input  wire         s_axi_awvalid,
output wire         s_axi_awready,

// 写数据通道 (W)
input  wire [63:0]  s_axi_wdata,      // 写数据
input  wire [7:0]   s_axi_wstrb,      // 字节使能
input  wire         s_axi_wlast,      // 最后一拍
input  wire         s_axi_wvalid,
output wire         s_axi_wready,

// 写响应通道 (B)
input  wire [7:0]   s_axi_bid,        // 匹配 AWID
input  wire [1:0]   s_axi_bresp,      // 响应 (OKAY/EXOKAY/SLVERR/DECERR)
input  wire         s_axi_bvalid,
output wire         s_axi_bready,

// 读地址通道 (AR)
input  wire [7:0]   s_axi_arid,
input  wire [31:0]  s_axi_araddr,
input  wire [7:0]   s_axi_arlen,
input  wire [2:0]   s_axi_arsize,
input  wire [1:0]   s_axi_arburst,
input  wire         s_axi_arvalid,
output wire         s_axi_arready,

// 读数据通道 (R)
input  wire [7:0]   s_axi_rid,
input  wire [63:0]  s_axi_rdata,
input  wire [1:0]   s_axi_rresp,
input  wire         s_axi_rlast,
input  wire         s_axi_rvalid,
output wire         s_axi_rready
```

## 3. 握手机则

所有通道共享同一条规则（与 [[20-protocols/fpga-design-patterns|设计模式]] §握手一致）：

```verilog
// 传输发生在 valid && ready 同一拍
wire transfer = valid && ready;
```

**关键约束**：
- `valid` 一旦拉高，**必须在 `ready` 拉高前保持稳定**（不能撤回）
- `ready` 可以在 `valid` 之前拉高（提前就绪）
- **禁止依赖 `ready` 来生成 `valid`**（否则死锁）

```
valid ──┐    ┌───────────────┐    ┌──
        └────┘               └────┘
ready ──────┐        ┌──┐           ┌──
            └────────┘  └───────────┘
                    ↑ 这一拍 transfer=1
```

## 4. Burst 传输

AXI4 支持一次地址发送多拍数据，减少地址开销：

| Burst 类型 | 编码 | 地址行为 | 用途 |
|-----------|------|---------|------|
| **FIXED** | 2'b00 | 地址不变 | FIFO 读写 |
| **INCR** | 2'b01 | 地址递增 | 顺序存储访问（最常用） |
| **WRAP** | 2'b10 | 地址环绕（对齐边界） | Cache line fill |

**关键参数**：
- `awlen`[7:0]：burst 长度 = awlen + 1（1~256 拍）
- `awsize`[2:0]：每拍字节数 = 2^awsize（最大 128B/拍）
- `awburst`[1:0]：类型
- 最大 burst 大小 = (awlen+1) × 2^awsize ≤ 4KB（AXI4 规范限制）

**地址计算**（INCR）：
```
beat_n_addr = start_addr + n × 2^awsize
```

## 5. Outstanding 与 Out-of-Order

### Outstanding（未完成事务）

AXI 允许主机**不等响应就发出下一个事务**，提高总线利用率：

```
AW #1 ──►    ┌─ AW #2 ──►  ┌─ AW #3 ──►
             │              │
B   ◄── #1 ──┘  B ◄── #2 ──┘  B ◄── #3 ──┘
```

- Outstanding 深度 = 同时在飞的事务数（典型 4~16）
- 用 **ID 标签**区分不同事务（AWID/ARID）
- AXI4 要求**同一 ID 的事务必须按序**，不同 ID 可乱序

### Out-of-Order（乱序完成）

- 从机可对不同 ID 的事务**乱序响应**（如快的先回、慢的后回）
- 主机用 ID 匹配响应，重组装数据

## 6. AXI4-Lite（寄存器访问）

AXI4-Lite 是 AXI4 Full 的**极简子集**，用于低速寄存器配置：

| 特性 | AXI4 Full | AXI4-Lite |
|------|-----------|-----------|
| burst | 支持 1~256 拍 | 仅单拍 |
| 数据宽度 | 8~1024 bit | 32 或 64 bit |
| ID 信号 | 有 | 无 |
| 面积 | 大 | 小 |

```verilog
// AXI4-Lite Slave 最小实现
reg [31:0] reg_file [0:15];

// 写：AW + W 同时到（简化：不分两拍）
always_ff @(posedge clk) begin
    if (s_axil_awvalid && s_axil_wvalid) begin
        reg_file[s_axil_awaddr[5:2]] <= s_axil_wdata;
    end
end

// 读：AR → R
always_ff @(posedge clk) begin
    if (s_axil_arvalid) begin
        s_axil_rdata <= reg_file[s_axil_araddr[5:2]];
    end
end
```

## 7. AXI Interconnect

多主多从互联矩阵，典型实现：

```
Master 0 ──┐
Master 1 ──┤    ┌─────────────┐    ┌── Slave 0 (DDR)
Master 2 ──┼────┤  AXI        ├────┼── Slave 1 (BRAM)
Master 3 ──┘    │  Interconnect│    └── Slave 2 (UART)
                └─────────────┘
```

**Xilinx IP**：
- `axi_interconnect`（非互联矩阵，适合简单场景）
- `smartconnect`（真正的 crossbar，高性能）
- `axi_dwidth_converter`（数据宽度转换）
- `axi_clock_converter`（跨时钟域）

## 8. 可综合 Slave 骨架

```verilog
module axi4lite_slave #(
    parameter ADDR_W = 8
)(
    input  wire        aclk,
    input  wire        aresetn,
    // AXI4-Lite Write Address
    input  wire [ADDR_W-1:0] s_axil_awaddr,
    input  wire        s_axil_awvalid,
    output reg         s_axil_awready,
    // AXI4-Lite Write Data
    input  wire [31:0] s_axil_wdata,
    input  wire [3:0]  s_axil_wstrb,
    input  wire        s_axil_wvalid,
    output reg         s_axil_wready,
    // AXI4-Lite Write Response
    output reg  [1:0]  s_axil_bresp,
    output reg         s_axil_bvalid,
    input  wire        s_axil_bready,
    // AXI4-Lite Read Address
    input  wire [ADDR_W-1:0] s_axil_araddr,
    input  wire        s_axil_arvalid,
    output reg         s_axil_arready,
    // AXI4-Lite Read Data
    output reg  [31:0] s_axil_rdata,
    output reg  [1:0]  s_axil_rresp,
    output reg         s_axil_rvalid,
    input  wire        s_axil_rready
);

    // 寄存器文件
    reg [31:0] regs [0:(1<<(ADDR_W-2))-1];

    // 写通道：简化为单拍（AW 和 W 同时到达）
    wire wr_ready = s_axil_awready && s_axil_wready;
    always_ff @(posedge aclk or negedge aresetn)
        if (!aresetn) begin
            s_axil_awready <= 1'b0;
            s_axil_wready  <= 1'b0;
            s_axil_bvalid  <= 1'b0;
        end else begin
            if (!s_axil_awready && s_axil_awvalid && s_axil_wvalid)
                s_axil_awready <= 1'b1;
            else
                s_axil_awready <= 1'b0;
            s_axil_wready <= s_axil_awready;
            // 写入寄存器
            if (s_axil_awvalid && s_axil_awready && s_axil_wvalid) begin
                if (s_axil_wstrb[0]) regs[s_axil_awaddr[ADDR_W-1:2]][7:0]   <= s_axil_wdata[7:0];
                if (s_axil_wstrb[1]) regs[s_axil_awaddr[ADDR_W-1:2]][15:8]  <= s_axil_wdata[15:8];
                if (s_axil_wstrb[2]) regs[s_axil_awaddr[ADDR_W-1:2]][23:16] <= s_axil_wdata[23:16];
                if (s_axil_wstrb[3]) regs[s_axil_awaddr[ADDR_W-1:2]][31:24] <= s_axil_wdata[31:24];
                s_axil_bvalid <= 1'b1;
            end
            if (s_axil_bvalid && s_axil_bready)
                s_axil_bvalid <= 1'b0;
        end

    always_comb s_axil_bresp = 2'b00; // OKAY

    // 读通道
    always_ff @(posedge aclk or negedge aresetn)
        if (!aresetn) begin
            s_axil_arready <= 1'b0;
            s_axil_rvalid  <= 1'b0;
        end else begin
            if (!s_axil_arready && s_axil_arvalid)
                s_axil_arready <= 1'b1;
            else
                s_axil_arready <= 1'b0;
            if (s_axil_arvalid && s_axil_arready) begin
                s_axil_rdata  <= regs[s_axil_araddr[ADDR_W-1:2]];
                s_axil_rvalid <= 1'b1;
            end
            if (s_axil_rvalid && s_axil_rready)
                s_axil_rvalid <= 1'b0;
        end

    always_comb s_axil_rresp = 2'b00; // OKAY

endmodule
```

## 9. 常见坑

| 现象 | 原因 | 解决 |
|------|------|------|
| 写数据丢失 | `wready` 未正确响应 | 确保 AW/W/B 三通道握手完整 |
| 读数据错误 | 地址未对齐 | AXI4 要求地址按 `awsize` 对齐 |
| 总线挂死 | 循环等待（互相等 `ready`） | 避免依赖 `ready` 生成 `valid` |
| 性能低 | Outstanding 太小 | 增加 ID 数量，允许更深 pipeline |
| 仿真通、上板挂 | AXI 互联未正确配置 ID 宽度 | 检查 master/slave ID 宽度匹配 |

## 延伸

- 设计模式：[[20-protocols/fpga-design-patterns|FPGA 常用设计模式]]（握手/AXI-S/仲裁器）
- Zynq：[[20-protocols/fpga-zynq-soc|Zynq SoC 开发]]（PS/PL AXI 互联）
- IP 核：[[20-protocols/fpga-ip-catalog|FPGA 常用 IP 核速查]]
- 知识：[[20-protocols/fpga|FPGA 知识]]
