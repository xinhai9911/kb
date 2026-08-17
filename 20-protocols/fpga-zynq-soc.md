---
title: Zynq SoC 开发
tags: [fpga, verilog, zynq, soc, arm, active]
created: 2026-08-07
summary: >-
    Xilinx Zynq-7000/MPSoc SoC 开发：PS/PL 架构、AXI 互联（HP/ACP/GP）、中断体系、PS-PL 协同、Linux on PS、Vitis HLS 加速、裸机 RTOS、典型工程结构。
category: reference
updated: 2026-08-07
sources:
  - amd.com/products/silicon-devices/soc/zynq-7000
  - ug1137_zynq_ultrascale_plus
base_confidence: 0.83
lifecycle: draft
---

# Zynq SoC 开发

> Zynq 是 Xilinx/AMD 的**硬核 SoC**，把 ARM Cortex-A 处理器系统（PS）和 FPGA 可编程逻辑（PL）封装在一颗芯片上。软件跑 Linux/RTOS，硬件做加速，通过 AXI 互联。

## 1. Zynq 架构全景

```
┌─────────────────────────────────────────────────────────┐
│                     Zynq-7000 SoC                       │
│                                                         │
│  ┌──────────────────────┐    ┌──────────────────────┐   │
│  │  PS (Processing Sys) │    │  PL (Programmable    │   │
│  │                      │◄──►│       Logic)         │   │
│  │  ARM Cortex-A9       │    │  Artix-7 / Kintex-7 │   │
│  │  DDR 控制器           │    │  LUT/FF/BRAM/DSP    │   │
│  │  外设 (UART/SPI/I2C) │    │  用户 RTL            │   │
│  │  GEM Ethernet        │    │  HLS IP              │   │
│  │  USB / SD / TTC      │    │  DMA                 │   │
│  └──────────────────────┘    └──────────────────────┘   │
│              │                         │                 │
│              └───── AXI互联 ──────────┘                 │
└─────────────────────────────────────────────────────────┘
```

### Zynq 家族

| 系列 | PS 核心 | PL 逻辑 | 典型应用 |
|------|--------|---------|---------|
| **Zynq-7000** | Cortex-A9 (双核) | Artix/Kintex 7 系列 | 工业控制、视频处理 |
| **Zynq UltraScale+ (MPSoC)** | A53 + R5F | UltraScale+ 逻辑 | 自动驾驶、5G、军工 |
| **Zynq UltraScale+ RFSoC** | A53 + R5F | RF ADC/DAC + FPGA | 雷达、射频 |

## 2. PS-PL AXI 互联

PS 和 PL 之间通过多条 AXI 通道互联：

| AXI 通道 | 方向 | 用途 | 带宽 |
|----------|------|------|------|
| **AXI GP0/GP1** | PS↔PL | 通用控制（配置 PL 寄存器） | 低（~几十 MB/s） |
| **AXI HP0~HP3** | PL→PS | PL 高性能访问 DDR/OCM | 高（~4 GB/s） |
| **AXI ACP** | PL→PS | 缓存一致性（PL 可读 PS cache） | 高 |
| **AXI HPC0/HPC1** | PL→PS | 高性能缓存端口（双核） | 最高 |

**选择直觉**：
- 配置寄存器 → GP（低速够用）
- DMA 搬数据到 DDR → HP
- PL 需要读 CPU cache 中的数据 → ACP

## 3. 中断体系

```
PL → PS 中断:
  IRQ_F2P[15:0]  → 64 个 PL 中断（通过 PS ICDIC 寄存器配置）

PS → PL 中断:
  不直接支持（用轮询或共享内存通知）
```

**连接方式**（Vivado Block Design）：
- PL 中断线 → Zynq PS 的 `IRQ_F2P` 端口
- 在 PS 的中断控制器（GIC）中配置优先级

## 4. 工程结构（Vivado + Vitis）

```
zynq_project/
├── vivado/                  # Vivado 工程
│   ├── zynq_project.xpr     # 工程文件
│   ├── block_design/        # Block Design (BD)
│   │   └── system.bd        # 包含 Zynq PS + PL IP
│   ├── constraints/         # XDC 约束
│   └── ip/                  # 自定义 IP
├── vitis/                   # Vitis（软件）工程
│   ├── zynq_sw/             # 软件工程
│   │   ├── src/
│   │   │   ├── main.c       # 裸机 / FreeRTOS
│   │   │   └── xparameters.h # 自动生成的硬件参数
│   │   └── lscript.ld       # 链接脚本
│   └── hls/                 # HLS 工程（可选）
└── petalinux/               # PetaLinux（Linux on Zynq）
    ├── project-spec/        # 设备树 / 内核配置
    └── images/linux/        # boot.bin + image.dtb + rootfs
```

## 5. Block Design（Vivado）

关键 IP 连接：

```tcl
# 1. 添加 Zynq PS
create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7:5.5 ps7

# 2. 配置 PS（DDR type, UART, MIO, AXI 时钟）
set_property -dict [list \
    CONFIG.PCW_UART0_PERIPHERAL_ENABLE {1} \
    CONFIG.PCW_DDR_RAM_BASEADDR {0x00100000} \
    CONFIG.PCW_USE_S_AXI_HP0 {1} \
] [get_bd_cells ps7]

# 3. 添加 AXI Interconnect（PL IP ↔ PS）
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:2.1 axi_ic
connect_bd_intf_net [get_bd_intf_pins ps7/S_AXI_HP0] \
    [get_bd_intf_pins axi_ic/M00_AXI]
connect_bd_intf_net [get_bd_intf_pins axi_ic/S00_AXI] \
    [get_bd_intf_pins my_pl_ip/S_AXI]

# 4. 自动连线 + 分配地址
apply_bd_automation -rule xilinx.com:bd_rule:processing_system7 \
    -config {make_external "FIXED_IO, DDR"}  [get_bd_cells ps7]
assign_bd_address
```

## 6. 软件开发模式

### 裸机（Bare-Metal）

```c
#include "xparameters.h"
#include "xil_io.h"

// 直接读写 PL 寄存器（GP 端口映射的地址）
#define PL_BASEADDR XPAR_MY_PL_IP_0_S_AXI_BASEADDR

int main() {
    // 写寄存器
    Xil_Out32(PL_BASEADDR + 0x00, 0x12345678);
    // 读寄存器
    uint32_t val = Xil_In32(PL_BASEADDR + 0x04);
    return 0;
}
```

### FreeRTOS

```c
// 任务中访问 PL IP
void vTaskPL(void *pv) {
    while (1) {
        uint32_t status = Xil_In32(PL_BASEADDR + 0x08);
        if (status & 0x1) {
            // 处理 PL 完成的事件
        }
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}
```

### Linux on Zynq（PetaLinux）

```bash
# 1. 生成设备树（自动包含 PL IP）
petalinux-config --get-hw-description=hardware/

# 2. 编译
petalinux-build

# 3. 生成启动镜像
petalinux-package --boot --fsbl images/linux/zynq_fsbl.elf \
    --fpga images/linux/system.bit --u-boot

# 4. PL IP 在 Linux 中自动映射为设备文件
# /sys/class/uio/uio0  (UIO 驱动)
# 或自定义驱动通过 /dev/mem 访问
```

## 7. HLS 加速模式

```c
// Vitis HLS: C/C++ → RTL
void matrix_multiply(int A[64][64], int B[64][64], int C[64][64]) {
    #pragma HLS INTERFACE m_axi port=A bundle=gmem0
    #pragma HLS INTERFACE m_axi port=B bundle=gmem1
    #pragma HLS INTERFACE m_axi port=C bundle=gmem2
    for (int i = 0; i < 64; i++)
        for (int j = 0; j < 64; j++) {
            int sum = 0;
            for (int k = 0; k < 64; k++)
                sum += A[i][k] * B[k][j];
            C[i][j] = sum;
        }
}
```

HLS 生成的 IP 自带 AXI 接口，可直接连到 PS 的 HP 端口。

## 8. PS-PL 协同最佳实践

| 实践 | 说明 |
|------|------|
| PS 做控制面 | 启动/配置/异常处理由 CPU 负责 |
| PL 做数据面 | 流水线处理、加解密、DSP 由硬件加速 |
| DMA 搬运 | 大数据块用 DMA（AXI DMA / XDMA）而非 CPU 拷贝 |
| 中断通知 | PL 完成后触发 IRQ_F2P，CPU 响应处理 |
| 共享内存 | 通过 DDR 或 OCM（On-Chip Memory）传递参数/结果 |
| 一致性 | 用 ACP 端口保证 PL 读到 CPU cache 中最新数据 |

## 9. 常见坑

| 现象 | 原因 | 解决 |
|------|------|------|
| PL IP 地址全零 | 未 assign_bd_address | Vivado 中重新分配地址 |
| Linux 无法访问 PL | 缺少设备树 overlay | 确认 device tree 包含 PL IP 节点 |
| DMA 数据不一致 | cache 未 flush/invalidate | PL 访问前 CPU 做 cache maintenance |
| PS 启动卡死 | DDR 初始化失败 | 检查 MIO 配置、DDR 型号匹配 |
| 中断不触发 | GIC 未配置使能 | PS 端 `XScuGic_Enable` |

## 延伸

- AXI 总线：[[20-protocols/fpga-axi4-bus|AXI4 总线协议深度]]
- RISC-V 软核：[[20-protocols/fpga-riscv-softcore|RISC-V 软核在 FPGA 上部署]]
- IP 核：[[20-protocols/fpga-ip-catalog|FPGA 常用 IP 核速查]]
- 知识：[[20-protocols/fpga|FPGA 知识]]
