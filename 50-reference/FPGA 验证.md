---
aliases: ["fpga-verification"]
title: FPGA 验证方法（Testbench / 断言 / 覆盖率 / CI）
tags: [fpga, verilog, vhdl, verification, reference, active]
created: 2026-07-29
summary: >-
    FPGA RTL 验证方法论：testbench 结构、自检（self-checking）+ VCD 波形、SystemVerilog 断言(SVA)与 PSL、功能覆盖率、约束随机(CRV)、用 Verilator 跑 CI 回归。配合 [[20-protocols/FPGA 设计 模式|RTL 设计模式]] 与 [[50-reference/FPGA 用法|FPGA 使用方法]]。
category: reference
updated: 2026-07-29
sources: []
base_confidence: 0.8
lifecycle: reviewed
---

# FPGA 验证方法（Testbench / 断言 / 覆盖率 / CI）

> RTL 写对只是第一步，**验证**决定流片/上板前能否放心。配合 [[50-reference/FPGA 用法|FPGA 使用方法]]（仿真工具）、[[20-protocols/FPGA 设计 模式|RTL 设计模式]]。

## 1. Testbench 基本结构

一个自检测 testbench（Verilog）三要素：**例化 DUT、生成时钟与激励、检查响应**。

```verilog
`timescale 1ns/1ps
module adder_tb;
    reg clk = 0; always #5 clk = ~clk;   // 100MHz

    reg  [7:0] a, b;
    wire [7:0] y;
    adder dut (.clk(clk), .a(a), .b(b), .y(y));

    reg [7:0] expected;
    int errors = 0;
    task check(input [7:0] av, bv);
        a = av; b = bv;
        @(posedge clk);                  // 等一拍（若组合逻辑可 #1）
        expected = av + bv;
        if (y !== expected) begin
            $error("FAIL a=%0d b=%0d y=%0d exp=%0d", av, bv, y, expected);
            errors++;
        end
    endtask

    initial begin
        $dumpfile("wave.vcd"); $dumpvars(0, adder_tb);
        check(3,4); check(250,10); check(0,0);
        $display("ERRORS=%0d", errors);
        $finish;
    end
endmodule
```

原则：
- **自检查（self-checking）**：testbench 自己比对 expected，输出 `PASS/FAIL`，不靠人眼盯波形。
- **生成 VCD/FST** 供 GTKWave 排查失败用例。
- 退出码：`$fatal`/`$error` 让 CI 能判失败；或用 `errors` 计数后 `$finish`。

## 2. 仿真层次

| 级别 | 内容 | 工具 |
|---|---|---|
| 行为仿真（RTL） | 功能正确，无延时 | iverilog/Verilator/ModelSim |
| 门级仿真（SDF） | 综合后网表 + 延时标注，看时序违例 | VCS/Questa + 反标 SDF |
| 形式验证（Formal） | 用数学证明属性恒成立（无激励） | SymbiYosys/Questa FV |

小项目 RTL 仿真足矣；大项目门级 + 形式验证补强。

## 3. 断言（Assertions）

把"不变量"写进代码，仿真/形式验证自动查：
- **SystemVerilog Assertions (SVA)**：`assert property (...)`
- **PSL**：VHDL 侧（用 `property`/`assert`）

```verilog
// 握手不变量：valid 拉高后，在 ready 拉高前不得撤销
sequence valid_stable;
    $rose(valid) ##1 valid [*0:$] ##1 ready;
endsequence
assert property (@(posedge clk) disable iff(rst)
    $rose(valid) |-> valid until ready);
```

好处：失败直接定位到违反的属性，不必从波形反推。X 态（未初始化）也该用 `assert` 捕获。

## 4. 功能覆盖率（Functional Coverage）

覆盖率是"测了多少"的量化。定义**覆盖组（covergroup）**采样感兴趣的场景：

```verilog
covergroup cg @(posedge clk);
    cp_op:   coverpoint op { bins add = {ADD}; bins sub = {SUB}; }
    cp_cross: cross cp_op, cp_signed;   // 交叉覆盖
endgroup
cg cgi = new();
always @(posedge clk) if (valid) cgi.sample();
```

结合**约束随机（CRV）**自动生成激励，逼出边界：

```verilog
class txn;
    rand bit [7:0] a, b;
    constraint c { a > 0; b < 200; }   // 偏边界
endclass
```

生成 1000 笔随机激励 → 看覆盖率是否达 100% → 未覆盖的 bin 补定向用例。

## 5. 用 Verilator 做 CI 回归

Verilator 把 RTL 转 C++，快且易集成进 CI（GitHub Actions 里 `make ci` 即可）：

```cpp
// adder_tb.cpp（Verilator 风格）
#include "Vadder.h"
int main(int argc, char** argv) {
    VerilatedContext* ctx = new VerilatedContext;
    ctx->commandArgs(argc, argv);
    Vadder* top = new Vadder{ctx};
    for (int i=0; i<100; i++) {
        top->a = rand()&0xff; top->b = rand()&0xff;
        top->eval();
        if (top->y != (top->a + top->b) & 0xff) {
            std::cerr << "FAIL\n"; return 1;   // 非零退出 → CI 失败
        }
    }
    delete top; delete ctx;
    return 0;
}
```

`make ci` 跑全部 testbench，任一非零退出即红灯。可直接并入本库已有的链接校验 CI（`.github/workflows/check-links.yml`）。

## 6. 验证 checklist

- [ ] 每个模块有自检查 testbench，输出 PASS/FAIL
- [ ] 边界值（0、全 1、溢出、最大/最小）覆盖
- [ ] CDC 路径有同步器且经 FIFO/握手（见 [[20-protocols/FPGA 设计 模式|设计模式]] §异步 FIFO）
- [ ] 关键不变量写 SVA/PSL 断言
- [ ] 功能覆盖率达标（通常 >95%）
- [ ] 门级仿真（大设计）无时序违例报告
- [ ] CI 自动跑回归（Verilator/iverilog）

## 延伸

- 设计：[[20-protocols/FPGA 设计 模式|RTL 设计模式]]
- 用法：[[50-reference/FPGA 用法|FPGA 使用方法]]
- 工具链：[[entities/FPGA 厂商|FPGA 厂商与开源工具链]]
