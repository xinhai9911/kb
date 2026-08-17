---
aliases: ["fpga-riscv-softcore"]
title: RISC-V 软核在 FPGA 上部署
tags: [fpga, verilog, riscv, softcore, soc, active]
created: 2026-08-07
summary: >-
    在 FPGA 上部署 RISC-V 软核处理器：VexRiscv/PicoRV32/Rocket LiteX 生态对比、工具链配置、SoC 集成（AXI/UART/BRAM）、调试接口（JTAG/GDB）、资源占用与性能。
category: reference
updated: 2026-08-07
sources:
  - github.com/litex-hub/litex
  - github.com/lucenaught/litex
base_confidence: 0.82
lifecycle: draft
---

# RISC-V 软核在 FPGA 上部署

> RISC-V 开源指令集 + FPGA 可重构硬件 = 零授权费的自定义 CPU。本文对比主流软核、给出 LiteX SoC 集成路径、工具链配置与调试方法。

## 1. 主流 RISC-V 软核对比

| 软核 | 架构 | 流水线 | 性能 | 资源（LUT） | 特点 |
|------|------|--------|------|------------|------|
| **VexRiscv** | RV32IMAC | 2~5 级 | ~1.3 DMIPS/MHz | 1K~5K | SpinalHDL，可配置（MMU/FPU/MPU），LiteX 默认 |
| **PicoRV32** | RV32IMC | 8 周期 | ~0.3 DMIPS/MHz | ~800 | 极小，Verilog 原生，适合控制类 |
| **Rocket Chip** | RV64GC | 5+ 级 | ~1 DMIPS/MHz | 10K~50K | UC Berkeley，含 MMU，可跑 Linux |
| **NEORV32** | RV32I[E][M][C] | 2 级 | ~0.3 DMIPS/MHz | ~1K | 纯 VHDL，零外部依赖，适合教学 |
| **SERV** | RV32I | 位串行 | ~0.01 DMIPS/MHz | ~200 | 世界最小 RISC-V，1 bit ALU |

**选型直觉**：
- 极小控制核 → PicoRV32 / SERV
- 通用 + 能跑 RTOS → VexRiscv (no MMU)
- 能跑 Linux → VexRiscv (MMU) / Rocket
- 学习/教学 → NEORV32

## 2. LiteX SoC Builder

[LiteX](https://github.com/litex-hub/litex) 是 RISC-V FPGA SoC 的**事实标准构建框架**：

```python
# my_soc.py — LiteX 生成完整 SoC
from migen import *
from litex_boards.platforms import arty  # Arty A7 开发板
from litex.soc.cores.clock import *
from litex.soc.integration.soc_core import *
from litex.soc.cores.uart import UARTWishboneBridge
from litex.soc.interconnect import axi
from litex.soc.cores import gpio
from litex.build.generic_toolchain import GenericToolchain

class MySoC(SoCCore):
    def __init__(self):
        platform = arty.Platform()

        # 时钟
        self.submodules.crg = _CRG(platform, 100e6)

        # CPU
        SoCCore.__init__(self, platform, clk_freq=100e6,
                         cpu_type="vexriscv",  # 或 "picorv32"
                         with_uart=True,
                         with_timer=True)

        # DDR (如果有)
        self.add_ram("sram", 0x40000000, 256 * 1024)  # 256KB BRAM

        # GPIO
        self.submodules.leds = gpio.GPIOOut(
            Pins="D4 D3 F3 E3 H5 T5 T4 P3")

# 生成
if __name__ == "__main__":
    from litex.build.parser import LiteXArgumentParser
    parser = LiteXArgumentParser(platform=arty.Platform,
        description="My RISC-V SoC on Arty A7")
    soc = MySoC()
    builder = Builder(soc, output_dir="build")
    builder.build()
```

### LiteX 一键生成

```bash
# 安装
pip install litex litex-boards pythondata-software-picolibc

# 生成比特流
python my_soc.py --platform arty --cpu-type vexriscv --build

# 输出
# build/gateware/top.bit      (FPGA 比特流)
# build/software/firmware.bin  (固件)
```

## 3. SoC 集成架构

```
┌─────────────────────────────────────────────┐
│                LiteX SoC                    │
│                                             │
│  ┌──────────┐     ┌───────────────────┐     │
│  │ VexRiscv │◄───►│  Wishbone/AXI     │     │
│  │  CPU     │     │  Interconnect     │     │
│  └──────────┘     └────┬──┬──┬──┬────┘     │
│                        │  │  │  │           │
│  ┌──────┐  ┌──────┐   │  │  │  │           │
│  │ UART │  │ Timer│   │  │  │  │           │
│  └──────┘  └──────┘   │  │  │  │           │
│  ┌──────┐  ┌──────┐   │  │  │  │           │
│  │ GPIO │  │ SPI  │   │  │  │  │           │
│  └──────┘  └──────┘   │  │  │  │           │
│  ┌──────┐  ┌──────┐   │  │  │  │           │
│  │ BRAM │  │ DDR  │◄──┘  │  │  │           │
│  │      │  │ MIG  │      │  │  │           │
│  └──────┘  └──────┘      │  │  │           │
│                           │  │  │           │
│  ┌──────────────────┐    │  │  │           │
│  │ JTAG Debug Bridge│◄───┘  │  │           │
│  └──────────────────┘       │  │           │
│                             │  │           │
└─────────────────────────────┴──┴───────────┘
```

## 4. 工具链配置

### GCC 工具链

```bash
# 安装 RISC-V GCC（Linux）
wget https://github.com/xpack-dev-tools/riscv-none-elf-gcc-xpack/releases/download/v14.2.0-3/xpack-riscv-none-elf-gcc-14.2.0-3-linux-x64.tar.gz
tar xzf xpack-riscv-none-elf-gcc-*.tar.gz
export PATH=$PWD/xpack-riscv-none-elf-gcc-*/bin:$PATH

# 编译固件
riscv-none-elf-gcc -march=rv32imac -mabi=ilp32 -O2 \
    -T link.ld -o firmware.elf firmware.S firmware.c

# 生成 bin（LiteX 用）
riscv-none-elf-objcopy -O binary firmware.elf firmware.bin
```

### 调试

```bash
# OpenOCD + JTAG
openocd -f ft2232h.cfg -f riscv-vexriscv.cfg
# 另一终端
riscv-none-elf-gdb firmware.elf
(gdb) target remote :3333
(gdb) monitor reset halt
(gdb) load
(gdb) break main
(gdb) continue
```

### GDB 支持

VexRiscv Debug 模块提供：
- `ebreak` 指令触发调试中断
- 单步执行（step）
- 断点（hardware breakpoint）
- 寄存器读写
- 内存读写

## 5. 资源占用参考

| 配置 | LUT | FF | BRAM | Fmax (7 系列) |
|------|-----|----|------|--------------|
| VexRiscv 最小 | ~1K | ~500 | 0 | 200+ MHz |
| VexRiscv + MMU | ~3K | ~2K | 1 | 150 MHz |
| PicoRV32 | ~800 | ~400 | 0 | 250+ MHz |
| Rocket RV64GC | ~30K | ~20K | 8+ | 100 MHz |
| SERV | ~200 | ~150 | 0 | 300+ MHz |

> 在 Artix-7 (50K LUT) 上跑 VexRiscv + UART + GPIO + 64KB BRAM 仅占 ~15% 资源。

## 6. SoC 外设集成示例

### UART（调试串口）

LiteX 自动生成 UART Wishbone Bridge，PC 端：

```bash
litex_term /dev/ttyUSB0
```

### 自定义 IP（Wishbone 总线）

```python
# LiteX 中添加自定义 Wishbone 从设备
from litex.soc.interconnect import wishbone

class MyAccelerator(Module, AutoCSR):
    def __init__(self, platform):
        self.bus = wishbone.Slave()  # Wishbone 从端口
        self.start = CSRStorage()
        self.done  = CSRStatus()

        # 自定义逻辑
        self.comb += self.bus.dat_r.eq(self.reg_file[self.bus.adr[2:]])
```

## 7. FPGA 板卡推荐

| 板卡 | FPGA | 价格 | RISC-V 适配 |
|------|------|------|------------|
| **Arty A7** | XC7A35T | ~$130 | LiteX 完美支持 |
| **Tang Nano 9K** | GW1NR-9 | ~$15 | LiteX + Gowin 工具链 |
| **ULX3S** | ECP5-85F | ~$100 | LiteX + Yosys/nextpnr |
| **OrangeCrab** | ECP5-25F | ~$50 | 极小 + USB-C |
| **DE10-Lite** | 10M50DA | ~$85 | Intel Quartus + Nios II（非 RISC-V） |

## 8. 常见坑

| 现象 | 原因 | 解决 |
|------|------|------|
| CPU 不启动 | 固件未加载到正确地址 | 检查 linker script 地址映射 |
| UART 无输出 | 波特率不匹配 | LiteX 默认 115200，检查终端 |
| JTAG 无法连接 | OpenOCD 配置错 | 确认 FT2232H 引脚配置 |
| 仿真通、上板挂 | 时钟/复位不对 | 检查 CRG 生成的时钟频率 |
| 指令异常 | ISA 扩展不匹配 | `march` 参数与软核配置一致 |

## 延伸

- Zynq SoC：[[20-protocols/FPGA Zynq SoC|Zynq SoC 开发]]（硬核 ARM + FPGA）
- AXI 总线：[[20-protocols/FPGA AXI 4 总线|AXI4 总线协议深度]]
- IP 核：[[20-protocols/FPGA IP 目录|FPGA 常用 IP 核速查]]
- 知识：[[20-protocols/FPGA 2|FPGA 知识]]
