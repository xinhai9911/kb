---
title: PCIe 子系统
category: concepts
tags: [pcie, dma, bar, topology, pci, dpdk, nic, active]
created: 2026-07-29
updated: 2026-07-29
summary: >-
    PCIe 子系统深度：PCIe 拓扑（Root Complex/Switch/EP）、Bus/Device/Function
    枚举、配置空间与 Capabilities 链、BAR 空间与 MMIO/PIO、
    DMA（Legacy/MSI/MSI-X）、PCIe 原子操作、ATS/ACS/AER/DPC 等高级特性、
    PCIe Gen3/4/5/6 速率与编码、PCIe TLP 事务层包结构、
    DPDK/VPP 的 UIO/VFIO PCIe 枚举流程、PCIe 错误处理。
base_confidence: 0.85
lifecycle: draft
---

# PCIe 子系统

> 前置 [[concepts/CPU 核心架构]]（DDIO），[[entities/CPU 中断与MSI-X]]（MSI-X 中断模型）。
> 本文专注 PCIe 物理层到软件层的完整链路。

## 1. PCIe 拓扑

```
CPU
  │
  ├── Root Complex (RC)      # 内存控制器 + PCIe Root Ports
  │     │                        # 通常每个 Socket 含 64-128 lanes
  │     ├── Root Port 0 ─── Switch ── EP (网卡)
  │     │                       │
  │     │                       ├── EP (NVMe SSD)
  │     │                       └── EP (加速器)
  │     ├── Root Port 1 ─── EP (GPU)
  │     └── Root Port 2 ─── Switch ── ...
  │
  └── UPI to another Socket
```

| 术语 | 说明 |
|------|------|
| **RC** (Root Complex) | CPU 侧的 PCIe 主控，整合 Root Ports |
| **EP** (Endpoint) | 终端设备（网卡、NVMe、GPU） |
| **Switch** | 扩展 PCIe 树，含上游/下游端口 |
| **Root Port** | RC 上的 PCIe 端口 |
| **Upstream/Downstream** | 朝向 RC / 朝向 EP |
| **Lane** | 一个差分对（TX+RX），PCIe 最小带宽单元 |

## 2. PCIe 地址与枚举

### 2.1 BDF 编码

```
BDF: Bus:Device.Function
     00:00.0 → Root Complex
     00:01.0 → Root Port 0
     01:00.0 → 第一个 EP（Bus 1 上设备 0 功能 0）
     01:00.1 → 同一 EP 的 VF 1（SR-IOV）
```

```bash
# 枚举树
lspci -t             # 树形拓扑
lspci -v             # 详细信息
lspci -s 01:00.0 -vv # 指定设备 Verbose

# PCIe 拓扑
lspci -tv             # 包含总线号
```

### 2.2 配置空间

```
每个设备 256B 标准配置空间（Capability 结构）+
4096B 扩展配置空间（PCIe Extended Capabilities）

Standard Header (64B):
+0x00: Vendor ID / Device ID
+0x08: Class Code / Revision ID
+0x10: BAR 0-5（6 个 Base Address Register）
+0x3C: Interrupt Line / Pin
+0x3E: Min Gnt / Max Lat

Capabilities:
+0x40: Power Management Cap
+0x50: MSI Capability
+0x60: PCIe Capability (Device/Port Type, Link Status/Control)
+0x80: MSI-X Capability (Table Size/BIR/PBA BIR)
+0x100+: AER / ACS / ATS / SR-IOV / ...

DPDK 枚举：
EAL 通过 /sys/bus/pci/devices/ 读取：
/proc/bus/pci/devices → BAR 地址/大小
/sys/bus/pci/devices/*/resource → MMIO 窗口
/sys/bus/pci/devices/*/numa_node → NUMA node
```

## 3. BAR 空间

```bash
# 查看设备 BAR
lspci -s 01:00.0 -vv | grep "Region\|Memory"
# Region 0: Memory at ... (64-bit, prefetchable) [size=16M]
# Region 2: Memory at ... (64-bit, prefetchable) [size=64K]
# Region 4: Memory at ... (non-prefetchable) [size=32K]

# BAR 类型
# - Memory (MMIO): 通过 load/store 访问（NB: IO 空间已废弃）
# - IO (PIO): 通过 in/out 指令（x86 特有，ARM 无）
# - Prefetchable: 可合并、可缓存
# - Non-prefetchable: 不可合并（包含状态寄存器）

# DPDK PMD 通过 VFIO mmap BAR 到用户空间
# mmap /sys/bus/pci/devices/.../resource0 （MMIO BAR 0）
# mmap /sys/bus/pci/devices/.../resource0_wc （WC 映射版本）

# 内存类型（从 BAR 判定）：
# PCIe 配置中：BAR Type = 0 → 32-bit, 2 → 64-bit
# prefetchable bit = BAR 可合并
# 数据面网卡：所有 BAR 均是 Memory + Prefetchable
```

## 4. PCIe TLP 事务层包

```
TLP (Transaction Layer Packet):
┌────────┬──────────┬────────┬──────────┐
│ Header │  Data    │ ECRC   │ (可选)    │
│ (12/16B)│ (0-4KB) │ (4B)   │          │
└────────┴──────────┴────────┴──────────┘

TLP 类型：
- Memory Read/Write (MRd / MWr): 大部分数据传送
- Memory Read Lock (MRdLk): 原子读锁（传统）
- Completion (Cpl / CplD): 读请求的返回（带数据/不带）
- I/O Read/Write (IORd / IOWr): IO 空间访问
- Configuration Read/Write (CfgRd / CfgWr): 配置访问
- Message (MSG): INTx 中断、电源管理错误信号

TLP 路由：
- Address Routing: 基于地址（Memory/IO）
- ID Routing: 基于 BDF（Configuration/Completion）
- Implicit Routing: 基于消息类型（PM/ERR）
```

## 5. DMA

### 5.1 DMA 类型

| 类型 | 描述 | 数据面用途 |
|------|------|-----------|
| Legacy DMA | ISA 总线 DMA（已淘汰） | 无 |
| Bus Master DMA | 设备直接发起 Memory Read/Write TLP | 网卡收发数据 |
| MSI/MSI-X | 设备写 Message 到特定地址 → 触发 CPU 中断 | 中断通知 |
| Peer-to-Peer | EP→EP 直接 DMA（经 Switch，不经过 CPU） | GPU→NIC、NVMe→NIC |

```c
// DMA 流程（网卡收包）
// 1. 驱动在 Host Memory 中准备 RX 描述符环
//    (DMA 地址由 IOMMU 翻译或直接物理地址)
// 2. 网卡收到包 → DMA Write 到描述符中指定地址
//    → TLP: MWr (32B 包体写入 mbuf 数据区)
// 3. 网卡更新描述符状态（DD bit）
//    → TLP: MWr (4B 描述符更新)
// 4. 网卡发出 MSI-X 中断（可选，轮询模式不中断）
//    → TLP: Msg (MSI-X write to APIC)
```

### 5.2 DMA 地址映射

```bash
# VFIO 下 DMA 映射
# IOMMU 把用户空间 GPA 映射到 HPA
# DPDK rte_malloc → rte_mem_virt2iova()

# 验证 DMA 映射
cat /sys/kernel/debug/vfio/groups/42  # VFIO 设备 iommu 映射表

# 没有 IOMMU 时（uio_pci_generic）：
# 用户空间直接使用物理地址
# 需要 hugepages 且在 4GB 以下（32-bit DMA 限制）
# 不推荐生产环境！
```

## 6. PCIe 速率

| 代际 | 编码 | 每 Lane 速率 (GT/s) | 每 Lane 带宽 (GB/s) | x16 总带宽 |
|------|------|-------------------|-------------------|-----------|
| Gen1 | 8b/10b | 2.5 | 0.25 | 4 GB/s |
| Gen2 | 8b/10b | 5.0 | 0.5 | 8 GB/s |
| Gen3 | 128b/130b | 8.0 | 0.985 | 15.75 GB/s |
| Gen4 | 128b/130b | 16.0 | 1.97 | 31.5 GB/s |
| Gen5 | 128b/130b | 32.0 | 3.94 | 63 GB/s |
| Gen6 | 1b/1b (PAM4) | 64.0 | 7.56 | 121 GB/s |

```bash
# 查看当前链路状态
lspci -s 01:00.0 -vv | grep -E "Speed|Width|LnkSta"
# LnkSta: Speed 16GT/s (PCIe Gen4), Width x16
# → 当前链路 x16 Gen4 = 31.5 GB/s

# 协商带宽不够时排查
# - BIOS PCIe 配置（Gen1/2/3/4 Auto）
# - 线缆/背板/retimer 质量
# - 卡槽物理 x 长度
```

## 7. 高级特性

| 特性 | 全称 | 作用 |
|------|------|------|
| **ACS** | Access Control Services | 隔离虚拟化环境中的 EP 间 Direct P2P |
| **ATS** | Address Translation Services | 设备通过 IOMMU 预翻译地址，减少 IOTLB miss |
| **AER** | Advanced Error Reporting | 错误寄存器扩展（Correctable/Fatal/Non-fatal） |
| **DPC** | Downstream Port Containment | 隔离下游设备错误，防止桥传播 |
| **ARI** | Alternate Routing-ID Interpretation | 扩展 Function 号到 256（SR-IOV VF 多时） |
| **SR-IOV** | Single Root I/O Virtualization | 1 PF → 多 VFs（见 [[concepts/CPU 虚拟化与IO穿透]]） |
| **PASID** | Process Address Space ID | 共享虚拟内存（SVM）：设备访问进程虚拟地址 |

```bash
# 检查 AER 错误
sudo cat /sys/devices/pci0000:00/0000:00:01.0/aer_dev_correctable
sudo cat /sys/devices/pci0000:00/0000:00:01.0/aer_dev_nonfatal

# AER 日志
dmesg | grep -i "PCIe.*error\|aer.*error"
```

## 8. DPDK/VPP PCIe 枚举流程

```bash
# DPDK EAL PCI scan:
# 1. /sys/bus/pci/devices/ 扫描所有设备
# 2. 匹配白名单 (-a) / 黑名单 (-b)
# 3. 读取 vendor_id, device_id, BAR 地址
# 4. VFIO 绑定 → IOMMU 组加入
# 5. VFIO_GROUP_SET_IOMMU → dma_map
# 6. MMIO → mmap BAR (WC 映射)
# 7. rte_pci_device 注册到 PMD

# DPDK 绑定/解绑脚本
dpdk-devbind.py -b vfio-pci 01:00.0   # 绑定 DPDK
dpdk-devbind.py -b i40e 01:00.0       # 退回内核驱动

# VPP: 同样通过 DPDK EAL 绑定
# 也支持直接接管（netlink + vfio）

# 常见问题
# - "no PCI device found" → VFIO 模块未加载
# - "IOMMU group not isolated" → 分组内有其他设备
# - "BAR mmap failed" → 权限或资源冲突
# - "link timeout" → PCIe 链路训练失败（热插拔/retimer 问题）
```

## 参考来源

- [[entities/CPU 中断与MSI-X]]
- [[concepts/CPU 虚拟化与IO穿透]]
- PCI Express Base Specification (Rev 5.0, 6.0)
- Intel VT-d Specification
- DPDK EAL PCI Probe documentation
- Linux kernel: PCI enumeration & sysfs walkthrough
