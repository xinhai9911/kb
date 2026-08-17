---
title: 高速 SerDes/PHY 物理层
tags: [chip, serdes, phy, pcie, ethernet, high-speed, active]
created: 2026-08-07
summary: >-
    高速串行收发器 SerDes/PHY 架构：SerDes 基本结构（PMA/PCS/PMD）、PCIe PHY、以太网 PHY、SerDes IP 选型、信号完整性（眼图/均衡/CDR）、在 FPGA/ASIC 中的角色。
category: reference
updated: 2026-08-07
sources:
  - ieee.org
  - amd.com
base_confidence: 0.81
lifecycle: draft
---

# 高速 SerDes/PHY 物理层

> 高速 SerDes（Serializer/Deserializer）是所有现代高速接口（PCIe/以太网/USB/SATA）的物理层基础。

## 1. SerDes 基本结构

### 三层架构

| 层 | 名称 | 功能 |
|----|------|------|
| **PMA** | Physical Media Attachment | 串并转换、驱动、CDR（时钟数据恢复） |
| **PCS** | Physical Coding Sublayer | 编解码（8b/10b、64b/66b）、弹性缓冲 |
| **PMD** | Physical Media Dependent | 连接器/光纤接口（SFP/QSFP） |

### 信号通路

```
TX: 并行数据 → 并串转换 → TX EQ(预加重) → 差分驱动 → 通道(铜/光纤)
RX: 通道 → CDR(时钟恢复) → RX EQ(均衡) → 串并转换 → 并行数据
```

### 关键组件

| 组件 | 功能 |
|------|------|
| **PLL** | 生成高频串行时钟（如 25Gbps 需 12.5GHz VCO） |
| **并串转换器** | N-bit 并行 → 1-bit 串行 |
| **TX EQ（预加重）** | 补偿通道高频衰减（pre-emphasis/de-emphasis） |
| **CDR** | 从数据流中恢复时钟（无独立时钟线） |
| **RX EQ** | 接收端均衡（CTLE + DFE） |
| **弹性缓冲** | 吸收频率偏差（PPM 差异） |

## 2. SerDes 关键指标

| 指标 | 说明 | 典型值 |
|------|------|--------|
| **数据速率** | 每 lane 速率 | 1~112 Gbps/lane |
| **Lane 数** | 串行通道数 | 1~32 lanes |
| **总带宽** | 速率 x Lane 数 | 100G/200G/400G/800G |
| **抖动（Jitter）** | 时钟/数据抖动 | < 0.1 UI (RMS) |
| **功耗** | 每 Gbps 功耗 | 5~20 mW/Gbps |
| **均衡能力** | TX EQ + RX EQ | CTLE/DFE/FFE |
| **BER** | 误码率 | < 10^-12 |

## 3. 信号完整性

### 眼图（Eye Diagram）

```
       ┌──────┐      ┌──────┐
      /        \    /        \
─────/──────────\──/──────────\─────
     \          /  \          /
      \        /    \        /
       └──────┘      └──────┘

眼高 (Eye Height) = 信号质量（越大越好）
眼宽 (Eye Width)  = 时序裕量（越大越好）
```

- **眼图张开** = 信号质量好，BER 低
- **眼图闭合** = 需要均衡或降低速率

### 均衡技术

| 技术 | 位置 | 功能 |
|------|------|------|
| **FFE（前馈均衡）** | TX | 预加重，补偿通道高频衰减 |
| **CTLE（连续时间线性均衡）** | RX | 高通滤波，增强高频分量 |
| **DFE（判决反馈均衡）** | RX | 消除 ISI（码间干扰） |
| **MLSE（最大似然序列估计）** | RX | 最优但最复杂的均衡 |

### 通道损耗

| 通道 | 损耗 @10GHz | 说明 |
|------|:-----------:|------|
| 1 英寸 PCB 走线 | ~1 dB | FR4 材质 |
| 10 英寸 PCB | ~10 dB | 长走线 |
| 1 米铜缆 (DAC) | ~20 dB | 直连铜缆 |
| 连接器 | ~1 dB | 每个连接器 |

## 4. PCIe PHY

| 版本 | 速率/lane | 编码 | 典型带宽(x16) |
|------|:---------:|:----:|:-------------:|
| PCIe 3.0 | 8 GT/s | 128b/130b | 16 GB/s |
| PCIe 4.0 | 16 GT/s | 128b/130b | 32 GB/s |
| PCIe 5.0 | 32 GT/s | 128b/130b | 64 GB/s |
| PCIe 6.0 | 64 GT/s | PAM4 + FLIT | 128 GB/s |
| PCIe 7.0 | 128 GT/s | PAM4 | 256 GB/s |

**PAM4（6.0 起）**：用 4 个电平（而非 NRZ 的 2 个）编码，每符号 2 bit，速率翻倍但眼高缩小。

## 5. 以太网 PHY

| 速率 | 编码 | Lane 速率 | 接口 | 典型芯片 |
|------|------|:---------:|------|---------|
| 1GbE | 8b/10b | 1.25G | RGMII/SGMII | RTL8211 |
| 10GbE | 64b/66b | 10.3125G | XFI/SFI | Intel 82599 |
| 25GbE | 64b/66b | 25.78125G | 25GUSX | Intel E810 |
| 50GbE | 64b/66b | 25.78G x2 | 50GAUI | — |
| 100GbE | 64b/66b | 25.78G x4 | 100GAUI | Broadcom Tomahawk |
| 200GbE | 64b/66b | 53.125G x4 | 200GAUI | — |
| 400GbE | 64b/66b | 53.125G x8 | 400GAUI-8 | NVIDIA Spectrum-4 |

## 6. SerDes IP 选型

| 厂商 | IP 名称 | 覆盖 | 适用 |
|------|---------|------|------|
| **Synopsys** | DesignWare | PCIe/USB/SerDes/112G | ASIC 全覆盖 |
| **Cadence** | PHY IP | PCIe/Ethernet/DDR | ASIC |
| **Alphawave** | 多协议 SerDes | 112G PAM4 | ASIC |
| **AMD/Xilinx** | GTH/GTY/GXP | PCIe/以太网/JESD | FPGA 硬核 |
| **Intel** | HSSI/EMIB | PCIe/以太网 | FPGA 硬核 |
| **国产（澜起）** | PCIe/DDR PHY | PCIe 5.0/DDR5 | 国产 ASIC |

## 7. SerDes 在 FPGA 中的体现

| FPGA 系列 | SerDes 类型 | 最高速率 | 支持协议 |
|-----------|------------|:--------:|---------|
| Xilinx 7 系列 | GTP/GTH | 12.5G/16G | PCIe 3.0, 10GbE |
| Xilinx UltraScale | GTH/GTY | 16.3G/25.7G | PCIe 3.0/4.0, 25GbE |
| Xilinx UltraScale+ | GTH/GTY | 16.3G/25.7G | PCIe 3.0/4.0, 25GbE |
| Xilinx Versal | GTH/GTY/GXP | 最高 112G | PCIe 5.0, 100GbE |

> FPGA 用户通常不直接操作 SerDes，而是通过 IP（如 PCIe Endpoint、10GbE MAC）间接使用。

## 8. 常见坑

| 现象 | 原因 | 解决 |
|------|------|------|
| 链路训练失败 | TX/RX EQ 参数不对 | 调整均衡参数、检查通道损耗 |
| 误码率高 | 抖动过大/通道损耗 | 改 PCB 走线/换低损耗材质 |
| CDR 失锁 | 数据模式太单一 | 加扰码/加 DC balance 编码 |
| 功耗超标 | SerDes 数量多 | 关闭未用 lane、降速率 |

## 延伸

- FPGA 知识：[[20-protocols/fpga|FPGA 知识]]（SerDes 是 FPGA 硬核资源）
- NVMe SSD：[[50-reference/sources/chips/nvme-ssd-controller|NVMe/SSD 控制器]]（PCIe PHY 是 NVMe 物理层）
- SmartNIC/DPU：[[50-reference/sources/chips/smartnic-dpu|SmartNIC/DPU]]（高速网络接口依赖 SerDes）
- ASIC 设计：[[50-reference/sources/chips/asic-design-flow|ASIC 芯片设计全流程]]（SerDes IP 是 ASIC 常见硬核）
