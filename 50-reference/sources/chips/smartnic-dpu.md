---
title: SmartNIC 与 DPU 网络加速芯片
tags: [chip, smartnic, dpu, nvidia, intel, networking, active]
created: 2026-08-07
summary: >-
    SmartNIC 与 DPU（Data Processing Unit）架构：从基础网卡到可编程数据面的演进、NVIDIA BlueField、Intel IPU/E2000、AMD Pensando、国产 DPU、FPGA SmartNIC、卸载模式（OVS/Virtio/加密）、性能指标与选型。
category: reference
updated: 2026-08-07
sources:
  - nvidia.com/networking
  - intel.com/dpu
base_confidence: 0.83
lifecycle: draft
---

# SmartNIC 与 DPU 网络加速芯片

> 传统网卡只做 DMA 搬包；SmartNIC/DPU 在网卡上加了**可编程处理器**，把网络/存储/安全功能从主机 CPU 卸载到网卡侧，释放 30~50% 的主机 CPU。

## 1. 演进路线

```
传统 NIC        SmartNIC           DPU              IPU
(纯 DMA)    (FPGA/ASIC 加速)  (CPU+加速器)    (基础设施处理器)
│                │                │                │
▼                ▼                ▼                ▼
Intel 82599    Netronome        NVIDIA BlueField  Intel IPU
  10GbE       nF系列            DPU               E2000
              FPGA 可编程       ARM + 加速引擎    ARM + 网络加速
```

| 阶段 | 特征 | 代表 |
|------|------|------|
| **传统 NIC** | 纯 DMA，主机 CPU 处理所有包 | Intel 82599/X710、Mellanox CX3 |
| **SmartNIC** | FPGA 或 ASIC 做包分类/卸载 | Netronome nF、Xilinx Alveo |
| **DPU** | 多核 ARM + 硬件加速器，可跑 OS | NVIDIA BlueField-3、Intel IPU |
| **IPU** | 云厂商定制基础设施处理器 | AWS Nitro、阿里云神龙 |

## 2. DPU 架构（NVIDIA BlueField-3 为例）

```
┌──────────────────────────────────────────────────┐
│              BlueField-3 DPU                      │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ ARM      │  │ ConnectX │  │ 加速引擎       │  │
│  │ Cortex-  │  │ -7 网络  │  │ - IPsec/ TLS  │  │
│  │ A78 ×16  │  │ 引擎     │  │ - 压缩/解压   │  │
│  │ (200Gbps)│  │ (400GbE) │  │ - SHA/AES     │  │
│  └────┬─────┘  └────┬─────┘  │ - XOR/RAID    │  │
│       │              │        └───────────────┘  │
│  ┌────┴──────────────┴─────────────────────────┐ │
│  │           PCIe 5.0 x16 (→ Host CPU)         │ │
│  └─────────────────────────────────────────────┘ │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ DDR5     │  │ eMMC/SSD │  │管理接口       │  │
│  │ 32GB     │  │ 启动存储  │  │ BMC/BMC SPI  │  │
│  └──────────┘  └──────────┘  └───────────────┘  │
└──────────────────────────────────────────────────┘
```

### 关键组件

| 组件 | 功能 |
|------|------|
| **ARM 多核** | 运行嵌入式 Linux（DPDK/OVS/VPP 全在 DPU 上跑） |
| **网络引擎** | ConnectX 引擎，线速收发 400GbE |
| **加密加速器** | IPsec/TLS 线速加解密（~200Gbps） |
| **压缩引擎** | zlib/zstd 硬件压缩 |
| **PCIe 接口** | 与 Host CPU 通信（virtio 直通） |
| **管理固件** | 固件/BMC 远程管理 |

## 3. 主要 DPU 厂商对比

| 厂商 | 产品 | ARM 核心 | 网络速率 | 特点 |
|------|------|---------|---------|------|
| **NVIDIA** | BlueField-3 | 16× A78 | 400GbE | 生态最全（DOCA SDK） |
| **Intel** | IPU E2000 | 4× A76 | 200GbE | 与 Intel CPU 协同 |
| **AMD/Pensando** | P4 | 无通用 ARM | 400GbE | P4 可编程数据面 |
| **Marvell** | OCTEON 10 | 24× A78 | 400GbE | DPU + 安全加速 |
| **Broadcom** | Stingray | 8× A72 | 100GbE | 集成交换 |
| **华为** | 智能网卡 | 自研 ARM | 100GbE+ | 国产替代 |
| **中科驭数** | K2 DPU | RISC-V + ARM | 100GbE | 国产 DPU |

## 4. 卸载场景

### 网络虚拟化卸载

| 卸载目标 | Host CPU 释放 | DPU 实现 |
|----------|-------------|---------|
| **OVS** | ~30% CPU | 硬件流表匹配 + 转发 |
| **Virtio-net** | ~20% CPU | DPU 上跑 virtio 后端 |
| **SR-IOV** | ~10% CPU | 硬件 VF 直通给 VM |
| **VXLAN/GRE** | ~15% CPU | 硬件封解隧道 |

### 安全卸载

| 卸载目标 | Host CPU 释放 | DPU 实现 |
|----------|-------------|---------|
| **IPsec** | ~40% CPU | 线速 AES-GCM 加密 |
| **TLS** | ~25% CPU | 线速 TLS 握手/加解密 |
| **MACsec** | ~10% CPU | 链路层加密 |

### 存储卸载

| 卸载目标 | Host CPU 释放 | DPU 实现 |
|----------|-------------|---------|
| **NVMe-oF** | ~30% CPU | DPU 做 NVMe-oF Target |
| **vhost-NVMe** | ~20% CPU | VM 直通 NVMe |
| **存储虚拟化** | ~15% CPU | 虚拟盘加速 |

## 5. FPGA SmartNIC

FPGA 做 SmartNIC 的优势：**可编程、低延迟、可定制**。

| 产品 | FPGA | 网络速率 | 特点 |
|------|------|---------|------|
| **Xilinx Alveo U55C** | UltraScale+ | 100GbE | 高性能计算 + 网络 |
| **Intel Agilex** | Agilex | 100GbE | FPGA + 网络 |
| **Netronome nF系列** | 多芯片 | 100GbE | 流处理器架构 |

FPGA SmartNIC 典型应用：
- 线速包分类/过滤（ACL/防火墙）
- 自定义协议解析（非标协议）
- 数据库日志捕获
- 低延迟交易（HFT）

## 6. DPU vs FPGA vs ASIC 选型

| 维度 | DPU | FPGA SmartNIC | ASIC SmartNIC |
|------|-----|--------------|--------------|
| 灵活性 | 高（跑 OS + SDK） | 最高（RTL 可编程） | 低（固化功能） |
| 延迟 | ~5μs | ~1μs | ~2μs |
| 吞吐 | 400Gbps | 100Gbps | 400Gbps |
| 成本 | $500~2000 | $1000~5000 | $200~500 |
| 生态 | DOCA/DPDK | Vitis/Verilog | 厂商私有 |
| 适用 | 云数据中心 | 定制/科研 | 大批量部署 |

## 7. DPU 在云数据中心的部署

```
┌─────────────────────────────────────────┐
│              服务器                       │
│  ┌──────────┐     ┌──────────────────┐  │
│  │ Host CPU │◄───►│     DPU          │  │
│  │ (应用)   │PCIe │ ┌──────────────┐ │  │
│  │          │     │ │ OVS 卸载      │ │──►── 交换机
│  │ VM/容器  │     │ │ IPsec 加速    │ │  │
│  │          │     │ │ NVMe-oF      │ │  │
│  └──────────┘     │ │ 虚拟化管理    │ │  │
│                    │ └──────────────┘ │  │
│                    └──────────────────┘  │
└─────────────────────────────────────────┘
```

- **东-西流量**：DPU 处理 VM 间通信，Host CPU 不参与
- **安全边界**：DPU 做零信任网络策略（微分段）
- **存储后端**：DPU 做 NVMe-oF Target，远程 SSD 暴露为本地盘

## 常见坑

| 现象 | 原因 | 解决 |
|------|------|------|
| DPU 性能不达标 | SDK 未开启硬件卸载 | 检查 DOCA/Pensando 配置 |
| Host 看不到 DPU | PCIe 链路训练失败 | 检查 BIOS PCIe 配置 |
| OVS 卸载失败 | 流表溢出 | 增大 DPU 流表容量 |
| 延迟抖动 | DPU ARM 过载 | 将关键路径卸载到硬件加速器 |

## 延伸

- 网卡资料：[[50-reference/sources/chips/nic-dpdk|网卡与 DPDK 资料蒸馏]]（Intel 82599/沐创）
- VPP：[[20-protocols/vpp|VPP 知识]]（用户态转发，与 DPU 卸载互补）
- eBPF：[[concepts/eBPF 核心架构|eBPF 核心架构]]（DPU 上也可跑 eBPF）
- FPGA：[[20-protocols/fpga|FPGA 知识]]
