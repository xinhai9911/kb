---
title: CPU 虚拟化与 I/O 穿透
category: concepts
tags: [cpu, virtualization, vt-d, sriov, iommu, vfio, dpdk, active]
created: 2026-07-29
updated: 2026-07-29
summary: >-
    面向数据面的 CPU 虚拟化技术全览：Intel VT-x/VT-d 与 ARM Virtualization
    Extensions 硬件虚拟化支持、SR-IOV 网卡直通原理与配置、IOMMU/IOPT 地址翻译、
    VFIO 用户态驱动框架、vCPU 亲和与 NUMA 感知、DPDK/VPP 在 VM 中的部署模式、
    VMM（KVM/Xen）CPU 调度影响、PCIe passthrough 与 VF 分配。
base_confidence: 0.85
lifecycle: draft
---

# CPU 虚拟化与 I/O 穿透

> 前置 [[concepts/CPU 核心架构]]（NUMA），[[entities/CPU 隔离与实时调优]]。
> 本文聚焦虚拟化场景下数据面的 CPU 与 I/O 资源隔离。

## 1. CPU 虚拟化基础

### 1.1 Intel VT-x / AMD SVM

| 概念 | VT-x | SVM | 说明 |
|------|------|-----|------|
| 根模式 | VMX Root | Host | Hypervisor 运行模式 |
| 非根模式 | VMX Non-root | Guest | Guest OS 运行模式 |
| VM 切换 | VM Entry/Exit | VMRUN → #VMEXIT | Guest↔Host 上下文切换 |
| 二级地址翻译 | EPT (Extended Page Table) | NPT (Nested Page Tables) | Guest VA → Guest PA → Host PA |
| 中断虚拟化 | APICv (Virtual APIC) | AVIC | 减少 VM-Exit |
| PI (Posted Interrupt) | VT-d PI | — | 绕过 VMM 直接投递中断到 VM |

**VM-Exit 开销**：

| 事件 | 延迟（cy） | 说明 |
|------|----------|------|
| 简单 VM-Exit (IO 指令) | ~2000 cy | 需切换 vCPU 上下文 |
| EPT Violation | ~3000 cy | 二级页表缺页 |
| IPI (TPR 访问) | ~1000 cy | APICv 可优化 |
| MSI-X 中断注入 | ~500 cy | VT-d PI 可降为 ~100 cy |
| 上下文切换 (vmresume) | ~500 cy | 纯硬件开销 |

### 1.2 VT-d (Intel Virtualization Technology for Directed I/O)

```
                VM (Guest)
            ┌──────────────┐
            │ DPDK PMD     │  ← 用户态驱动直接操作设备
            │ VFIO         │  ← 控制 IOMMU 映射
            └──────┬───────┘
                   │ PCIe 配置空间 / MMIO / DMA
          ┌────────▼────────┐
          │ IOMMU (VT-d)    │  ← DMA 重映射+中断重映射
          │ DMAR / IRQ      │  ← 防 DMA 攻击（安全隔离）
          └────────┬────────┘
                   │ 物理地址
          ┌────────▼────────┐
          │ 物理设备 (VF)    │  ← SR-IOV 虚拟功能
          └─────────────────┘
```

**VT-d 三核心功能**：

| 功能 | 说明 | 数据面价值 |
|------|------|-----------|
| DMA Remapping | IOMMU 重映射 DMA 地址（GPA→HPA） | VM 直接 DMA，无需 VMM 介入 |
| Interrupt Remapping | 重映射 MSI-X 中断（重写 vector） | VM 直接收中断 |
| Posted Interrupts | 中断绕过 VMM 直接投到 VM | 减少 VM-Exit，降低中断延迟 |

## 2. SR-IOV

### 2.1 结构

```
PCIe 物理设备 (PF)
├── Physical Function (PF)       # 管理面：创建 VF、配置 VLAN/MAC
├── Virtual Function (VF) 0      # 数据面：直接分配给 VM
├── Virtual Function (VF) 1
├── Virtual Function (VF) 2
└── ... (最多 252 个 VF)
```

### 2.2 配置

```bash
# 1. BIOS 开启 VT-d 和 SR-IOV
# 2. 内核开启 IOMMU
# 3. 启用 VF

# 查看 PF
lspci | grep Ethernet | grep -i "mlx5\|ice\|i40e\|bnxt"

# 启用 8 个 VF
echo 8 | sudo tee /sys/bus/pci/devices/0000:18:00.0/sriov_numvfs

# 查看 VF
lspci | grep "Virtual Function"

# 绑定 VF 到 vfio-pci（给 VM 直通用）
sudo modprobe vfio-pci
sudo dpdk-devbind.py -b vfio-pci 0000:18:01.0  # VF 0

# 启动 QEMU + vfio-pci 直通
qemu-system-x86_64 ... \
    -device vfio-pci,host=0000:18:01.0

# VF MAC 地址设置（libvirt）
virsh nodedev-detach pci_0000_18_01_0
<hostdev mode='subsystem' type='pci' managed='yes'>
  <source>
    <address domain='0x0000' bus='0x18' slot='0x01' function='0x0'/>
  </source>
</hostdev>

# 验证 VM 内 DPDK 可见
dpdk-devbind.py --status
```

### 2.3 NUMA 亲和（关键！）

```bash
# 创建 VF 时确保 PF 和 VF 同 NUMA node
# PF 所在 NUMA node:
cat /sys/bus/pci/devices/0000:18:00.0/numa_node
# → 返回 1，对应 NUMA node 1

# QEMU 的 vCPU 和内存必须绑到同 NUMA node
numactl --membind=1 --cpunodebind=1 \
    qemu-system-x86_64 ...
# 或 libvirt 中：
<numatune>
  <memory mode='strict' nodeset='1'/>
  <memnode cellid='0' mode='strict' nodeset='1'/>
</numatune>
<cputune>
  <vcpupin vcpu='0' cpuset='16'/>
  <vcpupin vcpu='1' cpuset='17'/>
</cputune>

# 若不配 NUMA：跨 socket 访问 VF → 延迟 2x → 吞吐大幅下降
```

## 3. IOMMU 与 VFIO

### 3.1 VFIO 原理

```
DPDK app           PMD
  ↓                ↓
VFIO ioctl      ┌─────────────────┐
│ open /dev/vfio/vfio    │
│ VFIO_GROUP_GET_DEV_FD  │ ← 获取设备 FD
│ VFIO_SET_IOMMU         │ ← 设置 IOMMU 类型
│ VFIO_DMA_MAP           │ ← 映射 DMA 地址（GPA→HPA）
│ MMAP(bar)              │ ← 映射 PCIe BAR 到用户空间
└─────────────────┘
```

```bash
# VFIO 流程验证
sudo cat /sys/kernel/iommu_groups/*/devices/*  # 查看 IOMMU 分组
ls /dev/vfio/                                    # VFIO 容器

# DPDK EAL + VFIO
./dpdk-l2fwd -a 0000:18:01.0 --log-level lib.eal:debug | grep iommu
# → IOMMU type: 1 (DMA)
# → VFIO group: 42
# → DMA map: 0x... size...

# 常见问题：IOMMU 分组不隔离
# 如果 PF+VF 在同一组 → 所有必须全直通！
# 检查：lspci -s 0000:18:00.0 -vv | grep IOMMU
# 物理机建议 split IOMMU groups（BIOS 设置）
```

### 3.2 IOPT（I/O Page Table）

```bash
# IOMMU 页表开销
# 跟 CPU 页表类似，也有 IOTLB（IOMMU TLB）
# IOTLB miss → IOMMU page walk → 内存访问

# IOMMU 页表大小与 IOTLB 覆盖：
# x86: 4K/2M/1G IOPT
# DPDK 应用用 1G 大页时，IOPT 只用 2 级
# 大幅减少 IOTLB miss

# 验证 IOTLB miss
perf stat -e dmar_drfaults  # Intel IOMMU 缺页
# 如果非零 → IOPT 不匹配，检查大页配置
```

## 4. vCPU 调度与隔离

### 4.1 vCPU pinning

```bash
# KVM: vCPU 固定到物理核
# libvirt (per-guest)
<cputune>
  <vcpupin vcpu='0' cpuset='16'/>
  <vcpupin vcpu='1' cpuset='17'/>
  <emulatorpin cpuset='0-3'/>
</cputune>

# QEMU 命令行
-chardev socket,id=charmonitor,path=/tmp/monitor.sock,server,nowait \
-parallel none \
-smp 4,maxcpus=4,cores=4,threads=1,sockets=1 \
-numa node,nodeid=0,cpus=0-3,memdev=mem0 \
-object memory-backend-file,id=mem0,size=8G,mem-path=/mnt/huge,share=on

# 数据面 VM 必须：
# - vCPU pin 到 non-isolated 核（隔离核已从 Host 调度器剥离）
# - 开启 hugepages（1G 最佳）
# - 关掉 vCPU overcommit（pCPU : vCPU = 1:1）
# - 关掉 KSM / THP
# - 设置 vCPU 的 CPU affinity → 对应的 pCPU affinity
```

### 4.2 中断虚拟化：Posted Interrupts

```
传统模式：
网卡中断 → VMM (IOMMU 重映射) → VM-Exit → VMM 注入虚拟中断 → VM-Entry
                                                                ~2000 cy

Posted Interrupts：
网卡中断 → IOMMU 直接写入 VM 的 Posted Interrupt Descriptor (PIR) → VM 收到 IRQ
               ↓
VM 在 VM-Entry 时自动检查 PIR → 处理中断
               ~0 VM-Exit
```

### 4.3 vCPU 调度影响

| 调度策略 | 适用 | 风险 |
|---------|------|------|
| default (CFS) | 管理 VM | vCPU 可被抢占，延迟不可控 |
| SCHED_FIFO | 数据面 VM | 优先级反转（如果其他 FIFO 进程竞争） |
| SCHED_RR | 数据面 VM | 时间片轮转，非实时 |
| pin + isolcpus | 数据面 VM | 独占核，无竞争（推荐） |

**实际部署规范**：

```bash
# Host 侧隔离
# 物理核 0-7: 系统 + 管理面 VM
# 物理核 8-15: 控制面 VM
# 物理核 16-31: 数据面 VM（isolcpus）
# 每个数据面 VM 固定 2-4 个 vCPU，各自独占物理核

# QEMU vCPU 线程优先级调整
ps -eLf | grep qemu | grep "CPU.*KVM"
# vCPU 线程名: CPU 0/KVM, CPU 1/KVM ...
for pid in $(pgrep -f "CPU.*KVM"); do
    chrt -f -p 1 $pid   # SCHED_FIFO 优先级 1
done
```

## 5. 虚拟化开销实测参考

| 场景 | 吞吐损失 | 延迟增加 |
|------|---------|---------|
| 裸机 DPDK | 0% | 0% |
| VFIO 直通 (SR-IOV) | 3-7% | 1-3μs |
| OVS-DPDK (vhost-user) | 10-15% | 5-10μs |
| virtio (非直通) | 20-40% | 20-50μs |
| virtio + vDPA | 5-10% | 3-5μs |

## 6. 常见问题

```bash
# Q: VF 在 VM 内不可见
# A: 检查 VT-d 是否开启
dmesg | grep "DMAR.*IOMMU"

# Q: DPDK EAL 无法 probe VF
# A: VFIO 权限问题，或 IOMMU 分组冲突
echo 1 | sudo tee /sys/module/vfio_iommu_type1/parameters/allow_unsafe_interrupts

# Q: 跨 NUMA 导致吞吐减半
# A: VF、vCPU、内存全绑到同 NUMA
cat /sys/bus/pci/devices/0000:18:01.0/numa_node  # 确认 VF 所在 NUMA
```

## 参考来源

- [[concepts/CPU 核心架构]]
- [[entities/CPU 隔离与实时调优]]
- Intel VT-d Specification (Doc 513228)
- DPDK VFIO / SR-IOV docs
- KVM Forum: Posted Interrupts deep dive
- libvirt Domain XML format (vCPU pinning / NUMA)
