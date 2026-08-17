---
aliases: ["fpga-usage"]
title: FPGA 使用方法（工具链 / 仿真 / 上板）
tags: [fpga, vhd, vhdl, verilog, hardware, reference, snippet, active]
created: 2026-07-29
summary: >-
    FPGA 日常开发实操：开源仿真（iverilog/Verilator/GTKWave）、商业综合实现（Vivado/Quartus）流程、跨时钟域(CDC)写法、测试平台(testbench)范式、Makefile 一键流程，以及本地 Q:/AI/vhdl_examples 示例。配合 [[20-protocols/FPGA 2|FPGA 知识]]。
category: reference
updated: 2026-07-29
sources: []
base_confidence: 0.8
lifecycle: reviewed
---

# FPGA 使用方法（工具链 / 仿真 / 上板）

> 知识背景见 [[20-protocols/FPGA 2|FPGA 知识]]。本文是"怎么动手"的操作手册。

## 1. 工具链全景

| 类别 | 工具 | 用途 | 许可 |
|---|---|---|---|
| 仿真（开源） | **iverilog** | 编译+运行 Verilog，出 VCD | 开源 |
| 仿真（开源） | **Verilator** | 转 C++ 模型，跑得快，适合大设计/CI | 开源 |
| 波形查看 | **GTKWave** | 看 VCD/FST 波形 | 开源 |
| 仿真（商业） | ModelSim/Questa、VCS、Xcelium | 工业级仿真/调试 | 商业 |
| 综合实现 | **Vivado** (AMD/Xilinx) | 7 系列/Zynq/UltraScale 全流程 | 免费版可用 |
| 综合实现 | **Quartus** (Intel) | Cyclone/Arria/Stratix | 免费版可用 |
| 综合实现 | **Radiant** (Lattice) | ECP5/MachXO | 免费版可用 |
| 综合（开源） | **Yosys** | 开源综合，配 nextpnr 做布局布线 | 开源 |
| 板级编程 | **openFPGALoader** / **vivado prog** / **quartus_pgm** | JTAG/SPI 烧写 | 开源/商业 |

> 没有开发板也能学：用 iverilog/Verilator 做纯仿真即可验证 RTL 行为。

## 2. 开源仿真最小流程（Verilog + iverilog）

### 目录与文件

```
project/
├── src/adder.v          # 设计（RTL）
├── tb/adder_tb.v        # 测试平台 (testbench)
└── Makefile
```

### 设计 `src/adder.v`

```verilog
module adder #(parameter W=8)(
    input  wire [W-1:0] a, b,
    output wire [W-1:0] y
);
    assign y = a + b;     // 组合逻辑，可综合
endmodule
```

### 测试平台 `tb/adder_tb.v`

```verilog
`timescale 1ns/1ps
module adder_tb;
    reg  [7:0] a, b;
    wire [7:0] y;

    adder #(.W(8)) dut (.a(a), .b(b), .y(y));

    initial begin
        $dumpfile("wave.vcd");      // 生成波形
        $dumpvars(0, adder_tb);
        a = 8'd3;  b = 8'd4;  #10;
        if (y !== 8'd7) $error("FAIL: 3+4=%0d", y); else $display("OK 3+4=%0d", y);
        a = 8'd250; b = 8'd10; #10;   // 测试溢出
        $display("overflow case y=%0d", y);
        $finish;
    end
endmodule
```

### 编译运行（iverilog）

```bash
iverilog -g2012 -o sim.vvp src/adder.v tb/adder_tb.v
vvp sim.vvp                 # 运行，输出 OK/FAIL，生成 wave.vcd
gtkwave wave.vcd &          # 看波形
```

### Verilator（更快，C++ 模型）

```bash
verilator --cc --exe --build -j 0 --trace \
    src/adder.v tb/adder_tb.cpp -o sim
./obj_dir/Vadder_tb         # 跑仿真
```

Verilator 要求 testbench 用 C++ 写（`main` 里 `while (!contextp->gotFinish())` 推进时钟），适合做 CI 回归。

## 3. VHDL 本地示例

本库 `Q:/AI/vhdl_examples/and_gate.vhd` 是最小 VHDL 样例（与门）。VHDL 仿真可用 **GHDL**（开源）：

```bash
ghdl -a and_gate.vhd                 # 分析
ghdl -a and_gate_tb.vhd              # 测试平台
ghdl -e and_gate_tb                  # 精细
ghdl -r and_gate_tb --wave=wave.ghw  # 运行，出 GHW 波形
gtkwave wave.ghw &
```

## 4. 跨时钟域（CDC）写法 ⚠️

不同时钟域直接传单比特信号会**亚稳态（metastability）**。标准做法：

### 两级同步器（单比特）

```verilog
reg sync1, sync2;
always @(posedge clk_dst or posedge rst) begin
    if (rst) {sync2, sync1} <= 2'b00;
    else     {sync2, sync1} <= {sync1, sig_src};  // 打两拍
end
wire sig_dst_safe = sync2;   // 已同步，可安全使用
```

### 多比特 / 脉冲：用异步 FIFO 或握手

- 多比特总线跨域：**异步 FIFO**（写侧用 `clk_src`、读侧用 `clk_dst`，双端口 RAM + 格雷码指针判空满）。
- Xilinx 提供 `xpm_cdc_*` 原语、Intel 提供 `dcfifo` IP，直接用成熟 IP 比手搓稳。

## 5. 商业综合实现流程（Vivado 示例）

```tcl
# 1) 建工程后，在 Tcl 控制台或 build.tcl 里：
read_verilog [glob src/*.v]
read_xdc constraints.xdc          # 管脚/时钟约束
synth_design -top top -part xc7z020clg400-1
opt_design; place_design; route_design
report_timing_summary -file timing.rpt   # 看是否满足时序(Fmax)
write_bitstream -force top.bit           # 生成比特流
```

批处理（无 GUI）：

```bash
vivado -mode batch -source build.tcl
```

约束文件 `constraints.xdc` 关键项：

```
set_property PACKAGE_PIN W19 [get_ports clk]      ; # 管脚绑定
set_property IOSTANDARD LVCMOS33 [get_ports clk]
create_clock -period 10.000 [get_ports clk]       ; # 100MHz 时钟约束
```

### Quartus 等价

```tcl
# Quartus: 用 qsys/Platform Designer 或直接 qsf 约束 + 命令行
quartus_sh --flow compile top.qpf
quartus_pgm -c USB-Blaster -m JTAG -o "P;top.sof"
```

## 6. 上板编程（Bitstream 加载）

| 方式 | 说明 | 适用 |
|---|---|---|
| **JTAG** | 通过下载器（USB-Blaster/Digilent）直接烧，掉电丢失 | 调试 |
| **Quad-SPI Flash** | 比特流存 Flash，上电自动加载（需生成 `.mcs`/`.rbf`） | 部署 |
| **处理器加载** | Zynq 的 ARM 从 FSBL 把 bitstream 喂 PL | 异构 SoC |

```bash
# openFPGALoader（开源，支持多厂商）
openFPGALoader -b tinyfpga top.bit

# Vivado 命令行
vivado -mode batch -source prog.tcl   # 内含 program_hw_devices
```

## 7. Makefile 一键流程（开源仿真）

```make
SIM ?= sim.vvp
SRC := $(wildcard src/*.v)
TB  := $(wildcard tb/*.v)

sim: $(SRC) $(TB)
	iverilog -g2012 -o $(SIM) $(SRC) $(TB)

run: sim
	vvp $(SIM)
	gtkwave wave.vcd &

clean:
	rm -f $(SIM) wave.vcd

.PHONY: sim run clean
```

用法：`make run`。

## 8. 常见坑

| 现象 | 原因 | 解决 |
|---|---|---|
| 仿真正常、上板乱 | 跨时钟域未同步 | 加 2-FF 同步器 / 异步 FIFO |
| 时序不满足 (WNS<0) | 关键路径太长 | 插入流水线寄存器、降低 Fmax 目标 |
| 综合后功能错 | 写了不可综合结构（如 `wait`、`initial` 用于寄存器初值某些工具不支持） | 遵循可综合子集 |
| 亚稳态/偶发错 | 复位释放与时钟不同步 | 用异步复位同步释放（复位桥） |
| 资源爆了 | BRAM/DSP 用超 | 资源共享、改用分布式 RAM |
| 上电不跑 | Flash 比特流未烧 / 启动模式跳线错 | 确认 `.mcs` 烧写与 BOOT 模式 |

## 9. 本地实战建议

- 从 `Q:/AI/vhdl_examples/and_gate.vhd` 起步，用 GHDL 跑通仿真。
- 用 iverilog/Verilator 做**纯软件仿真验证**，无需开发板即可掌握 RTL 与 testbench。
- 把常用 fish/Makefile 流程沉淀到 [[30-snippets/]] 便于复用。

## 延伸

- 知识：[[20-protocols/FPGA 2|FPGA 知识]]
- 芯片资料：[[50-reference/sources/chips/Centec CTC 7132|CTC7132]]（FPGA 常与之配合做灵活前端）
- 开源工具：iverilog / Verilator / Yosys+nextpnr / openFPGALoader 文档
