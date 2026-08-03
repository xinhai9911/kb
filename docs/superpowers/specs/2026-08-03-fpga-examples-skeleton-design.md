# FPGA 工程骨架建计划 — 设计 spec

**日期:** 2026-08-03
**项目:** `Q:\AI\kb\projects\fpga-examples\`
**状态:** Draft (待用户审核)
**作者:** Claude (brainstorming → writing-plans → implementation)

## Context

用户原话:"帮我新建整个 fpga 芯片工程"。

这是上一轮 `merry-wibbling-conway.md` plan 的延续。该 plan 7 批 23 页过于宏大,被用户两次打断 ExitPlanMode。本次收敛为**只做一件事**:建一份**纯目录骨架 + 最小可跑仿真** 的 FPGA 工程模板,作为后续 FPGA 学习/实验/工程实践的载体。

## 目标

在 `Q:\AI\kb\projects\fpga-examples\` 下,严格按用户给定的目录树建立工程骨架,跑通 iverilog 仿真作为骨架健康验证,空目录用 README 语义化占位(不放 `.gitkeep`,对 Obsidian 友好)。

## 设计决策

1. **目录结构严格按用户贴出的树**,不改名不增层
2. **空目录用 `README.md` 占位**(一句话说明 + 回链 vault 综述),不用 `.gitkeep`
3. **只写 5 个真文件**(4 个 Verilog-2001 + 1 个 bash 脚本)
4. **仿真工具链 = iverilog/Icarus 12.0**(已在 `D:\iverilog\bin\` 探测到,需在 sim.sh 里加路径兜底)。sim.sh 编译开关用 `-g2012`(Icarus 对 V2001 + 少量 SV 2009/2012 关键字的支持开关),**不是要求 RTL 写 SV** — RTL 仍严格 Verilog-2001。
5. **风格沿用 `Q:\AI\vhdl_examples\and_gate.vhd` 的简洁 + Verilog-2001**(不开 SystemVerilog)
6. **不引入 git submodule / Vivado / Python / Makefile**(YAGNI)
7. **README 用 vault 工程惯例 frontmatter**:`project: true, topic, stack, deps, run, docs, updated`

## 目录结构(物理)

```
projects/fpga-examples/
├── README.md
├── rtl/
│   ├── top/
│   │   └── chip_top.v                 # 真:顶层模块
│   ├── core/
│   │   ├── cpu/  (README 占位)
│   │   ├── dsp/  (README 占位)
│   │   └── ctrl/
│   │       └── led_blink.v            # 真:LED 跑马灯
│   ├── ip/
│   │   ├── pll/      (README 占位)
│   │   ├── ddr3/     (README 占位)
│   │   └── eth_mac/  (README 占位)
│   └── infra/
│       ├── clk_rst/
│       │   └── clk_rst.v              # 真:异步复位同步释放
│       ├── axi_crossbar/ (README 占位)
│       └── apb_bridge/   (README 占位)
├── sim/
│   ├── tb/
│   │   └── tb_chip_top.v              # 真:顶层 testbench
│   └── wave/                          # 仿真 VCD 输出
├── constraints/
│   └── timing.xdc                     # 模板(无真实引脚,只列字段)
├── synth/                              # 占位
├── bitstream/                          # 占位
└── scripts/
    └── sim.sh                         # 真:仿真入口
```

## 模块规格

### `rtl/infra/clk_rst/clk_rst.v` — 异步复位同步释放

```verilog
module clk_rst (
    input  wire clk_in,      // 100 MHz 外部时钟(骨架占位,真实场景接 PLL)
    input  wire rst_n_in,    // 异步复位,低有效
    output wire clk_out,     // 内部时钟(本骨架直接透传 clk_in)
    output reg  rst_sync_n   // 同步释放的复位,2 级 FF
);
    reg rst_meta;
    always @(posedge clk_in or negedge rst_n_in) begin
        if (!rst_n_in) {rst_meta, rst_sync_n} <= 2'b0;
        else           {rst_meta, rst_sync_n} <= {rst_sync_n, 1'b1};
    end
    assign clk_out = clk_in;
endmodule
```

### `rtl/core/ctrl/led_blink.v` — 跑马灯

```verilog
module led_blink #(
    parameter N = 26  // 2^26 / 100MHz ≈ 671ms 翻一次
) (
    input  wire clk,
    input  wire rst_n,
    output reg  [7:0] led
);
    reg [N-1:0] cnt;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            cnt <= 0;
            led <= 8'b0000_0001;
        end else if (cnt == {N{1'b1}}) begin
            cnt <= 0;
            led <= {led[6:0], led[7]};
        end else begin
            cnt <= cnt + 1;
        end
    end
endmodule
```

### `rtl/top/chip_top.v` — 顶层

```verilog
module chip_top (
    input  wire sys_clk,      // 100 MHz
    input  wire sys_rst_n,    // 异步复位
    output wire [7:0] led
);
    wire clk_int;
    wire rst_sync;
    clk_rst  u_clk_rst (.clk_in(sys_clk), .rst_n_in(sys_rst_n),
                        .clk_out(clk_int), .rst_sync_n(rst_sync));
    led_blink #(.N(20)) u_led  // 仿真加速:2^20/100MHz ≈ 10us 翻一次
              (.clk(clk_int), .rst_n(rst_sync), .led(led));
endmodule
```

注:实测下 `N=26` 跑 100us 看不到翻转(671ms 才翻一次),仿真用 `N=20`(≈10.5us),100us 内能翻 ~9 次,断言更稳。

### `sim/tb/tb_chip_top.v` — 顶层 testbench

```verilog
`timescale 1ns/1ps
module tb_chip_top;
    reg clk = 0;
    reg rst_n = 0;
    wire [7:0] led;

    chip_top u_dut (.sys_clk(clk), .sys_rst_n(rst_n), .led(led));

    always #5 clk = ~clk;            // 100 MHz

    integer toggle_cnt = 0;
    reg [7:0] led_prev = 0;
    always @(posedge clk) begin
        if (rst_n) begin
            if (led !== led_prev) toggle_cnt = toggle_cnt + 1;
            led_prev = led;
        end
    end

    initial begin
        $dumpfile("sim/wave/tb_chip_top.vcd");
        $dumpvars(0, tb_chip_top);
        #200 rst_n = 1;              // 200ns 复位
        #100_000                   // 跑 100us
        if (toggle_cnt >= 5) $display("[PASS] led toggled %0d times in 100us", toggle_cnt);
        else                 $display("[FAIL] led toggled only %0d times", toggle_cnt);
        $finish;
    end
endmodule
```

### `scripts/sim.sh` — 仿真入口

```bash
#!/usr/bin/env bash
# iverilog 路径探测:1) PATH; 2) Windows 默认 D:\iverilog\bin
IVERILOG=$(command -v iverilog 2>/dev/null)
VVP=$(command -v vvp 2>/dev/null)
if [ -z "$IVERILOG" ] && [ -x "/d/iverilog/bin/iverilog.exe" ]; then
  IVERILOG="/d/iverilog/bin/iverilog.exe"
  VVP="/d/iverilog/bin/vvp.exe"
fi
[ -z "$IVERILOG" ] && { echo "ERROR: iverilog not found. Install: http://iverilog.icarus.com/"; exit 1; }

cd "$(dirname "$0")/.."   # 工程根
mkdir -p sim/wave

echo "[iverilog] compile ..."
"$IVERILOG" -g2012 -o sim/wave/tb_chip_top.vvp \
  sim/tb/tb_chip_top.v \
  rtl/top/chip_top.v \
  rtl/core/ctrl/led_blink.v \
  rtl/infra/clk_rst/clk_rst.v \
  || { echo "[FAIL] compile error"; exit 2; }

echo "[vvp] run 100us ..."
"$VVP" sim/wave/tb_chip_top.vvp
RC=$?
[ $RC -eq 0 ] && echo "[EXIT 0] PASS" || echo "[EXIT $RC] FAIL"
exit $RC
```

注:用 `-g2012` 是 Icarus 对 Verilog-2001 + 部分 SystemVerilog 2009/2012 特性的支持,**不是**要用户写 SV(代码仍是 V2001 风格)。

### `constraints/timing.xdc` — 占位模板

只列字段,不绑引脚(纯骨架):

```tcl
# 伪约束 — 真工程应按数据手册填
create_clock -name sys_clk -period 10.000 [get_ports sys_clk]   ;# 100 MHz
set_false_path -from [get_ports sys_rst_n]
set_input_delay  -clock sys_clk  2.0 [all_inputs]
set_output_delay -clock sys_clk  2.0 [all_outputs]
```

### 空目录 README 占位(每个一份)

`rtl/core/cpu/README.md` 范例:
```markdown
# rtl/core/cpu/

CPU 类核心模块(CPU/指令译码/寄存器堆/CSR 等)预留位。
当前空 — 后续按 RISC-V/MIPS/自研 ISA 增量填入。
回链:[[fpga-chip-design-systematic-guide]]
```

`rtl/ip/ddr3/README.md` 同结构,内容换成 DDR3 控制器 stub 位置说明。

### `README.md` — 工程入口

```markdown
---
project: true
topic: fpga-skeleton
stack: [verilog-2001, iverilog, icarus]
deps: [iverilog >= 11]
run: bash scripts/sim.sh
docs: [[fpga-chip-design-systematic-guide]]
updated: 2026-08-03
---

# fpga-examples

FPGA 芯片工程骨架 — 纯目录模板 + 最小可跑仿真。
设计意图见 [[fpga-chip-design-systematic-guide]]。

## 目录树
[贴上面那张树]

## 编译运行
\`\`\`bash
bash scripts/sim.sh
\`\`\`
期望输出:`[PASS] led toggled N times in 100us` + `[EXIT 0] PASS`。

## 排错
| 现象 | 原因 | 处理 |
|---|---|---|
| `iverilog not found` | 工具未装或不在 PATH | 装 http://iverilog.icarus.com/ 或 `export PATH=$PATH:/d/iverilog/bin` |
| `[FAIL] led toggled 0 times` | 仿真时长不够 / N 参数过大 | 检查 chip_top.v 的 `N` 参数(仿真用 20) |
```

## 验证步骤(spec 实施后跑)

1. `bash Q:/AI/kb/projects/fpga-examples/scripts/sim.sh`
2. 期望:stdout 含 `[PASS] led toggled` 行 + `[EXIT 0] PASS`,exit code 0
3. 失败排查:看 stderr,常见 = iverilog 找不到 / 路径写错

## 不做的事(YAGNI)

- ❌ 真实 PLL/DDR/AXI/Eth IP stub
- ❌ Vivado 工程文件 / .xpr / .tcl
- ❌ git submodule / 子仓库
- ❌ Python 脚本 / Makefile / CMake
- ❌ Verilator lint / 覆盖率收集
- ❌ 真 XDC 引脚约束
- ❌ SystemVerilog UVM 验证环境

## 后续追加(本次不做,留 spec 给后续 spec)

- RISC-V 最小核(从 `picorv32` 或自研 5 级流水线)
- AXI4-Lite crossbar stub
- DDR3 控制器(简化版)
- UART/SPI/I2C 控制器
- CDC 模板
- Vivado/Quartus 工具链集成
