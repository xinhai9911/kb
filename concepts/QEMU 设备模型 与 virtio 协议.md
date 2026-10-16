---
title: QEMU 设备模型 与 virtio 协议
category: concepts
tags: [kvm, qemu, virtio, virtqueue, ovmf, seabios, virtualization, 虚拟化, active]
created: 2026-10-16
updated: 2026-10-16
summary: >-
    KVM 只做 CPU/内存虚拟化、设备由 QEMU 提供的分工；设备三形态（全模拟 / 半虚拟化 virtio / VFIO 直通）；
    virtio 协议核心：virtqueue 三环（descriptor table / avail ring / used ring）、feature 协商、
    设备 ID 表、modern 与 legacy（transitional）区分、virtio-pci 通知机制；
    三种磁盘设备的 QEMU 命令行与 guest 侧驱动/设备名对应（含 scsi-hd、nvme-ns、多队列）；
    virtio-net 多队列；固件 SeaBIOS 与 OVMF（UEFI 变量存储、Secure Boot）；
    本地起虚拟机与挂镜像的常用命令；与公有云设备选择的映射；性能视角对照块层与 NVMe 队列。
    前置 PCIe 子系统、存储栈与 io_uring；应用见 KVM 公有云 镜像 适配 §2/§8。
base_confidence: 0.87
lifecycle: reviewed
---

# QEMU 设备模型 与 virtio 协议

> 前置：[[concepts/PCIe 子系统]]（设备如何被枚举与访问）、[[concepts/存储栈与io_uring]]（块层与 NVMe 队列）、
> [[concepts/CPU 虚拟化与IO穿透]]（VT-x/VT-d、IOMMU、VFIO）。
> 应用：[[concepts/KVM 公有云 镜像 适配]] §2（挂载形态）、§12（qemu 验证矩阵）。

## 1. 分工：KVM 管 CPU/内存，QEMU 管设备

```
┌──────────────────────────── 宿主机 ────────────────────────────┐
│  QEMU 进程（用户态）                                            │
│   ├─ 设备模型：virtio-blk/scsi、nvme、virtio-net、VGA、固件…     │
│   ├─ 线程：vCPU 线程、IO 线程、主循环                           │
│   └─ 通过 ioctl(/dev/kvm) 使用内核模块 ↓                        │
│  KVM（内核态）：VT-x/EPT 执行 guest、中断注入、MMIO/PIO 退出     │
└────────────────────────────────────────────────────────────────┘
```

**关键认知**：KVM 本身**不提供任何设备**。guest 看到的所有设备（磁盘、网卡、NVMe 控制器）都是 QEMU 在用户态模拟/半模拟出来的。云端同理——只是换成云厂商自己的虚拟化组件（可能基于 QEMU，也可能是自研 virt 实现）。

## 2. 设备虚拟化的三种形态

| 形态 | 机制 | 典型设备 | 性能 | 代价 |
|---|---|---|---|---|
| **全模拟** | 逐寄存器/逐命令模拟真实硬件 | IDE/AHCI、e1000、RTL8139 | 低（每次 IO 大量 VM-Exit） | 兼容老系统 |
| **半虚拟化（virtio）** | guest 侧专用驱动 + 共享内存队列 | virtio-blk/scsi/net/console | 高 | guest 必须有驱动 |
| **直通（VFIO）** | IOMMU 把物理设备映射给 guest | SR-IOV VF、整卡 | 接近裸机 | 无共享、需 IOMMU、迁移难 |

> 云上系统盘的三种形态（virtio-blk / virtio-scsi / NVMe 协议云盘）都属于"半虚拟化"家族，
> 只是**协议与队列模型不同**（见 §3、§4）。NVMe 协议云盘的特殊性在于：guest 用**标准 NVMe 驱动**，
> 不需要"知道自己被虚拟化"。

## 3. virtio 协议核心

### 3.1 virtqueue：三个环 + 一个描述符表

```
guest                                    host（QEMU）
  │ 把请求写进 descriptor table
  │ 更新 avail ring（idx++）      ─────►  QEMU 轮询/被通知
  │                                      │ 处理请求
  │ 读 used ring（idx++）         ◄─────  写结果 + 更新 used ring + 发中断
```

| 结构 | 作用 |
|---|---|
| **descriptor table** | 描述符数组，每个描述符指向一块 guest 物理内存（buffer） |
| **avail ring** | guest → host：哪些描述符可用（生产者索引） |
| **used ring** | host → guest：哪些已完成（消费者索引）+ 写回长度 |

- **间接描述符（indirect）**：请求很大时，用一层额外描述符表避免撑爆环
- **通知（kick / interrupt）**：`VIRTIO_PCI_QUEUE_NOTIFY`（MMIO 写）通知 host；host 用中断通知 guest。
  两者都可抑制（event idx）以省 VM-Exit
- **多队列**：每个队列一对 avail/used ring；块设备的队列数 = vCPU/IO 线程并行度

### 3.2 feature 协商与设备 ID

guest 驱动与设备通过 feature bits 协商能力（如 `VIRTIO_BLK_F_FLUSH`、`_F_DISCARD`、`_F_MQ` 多队列）。
设备 ID（virtio 规范）常见：

| ID | 设备 |
|---|---|
| 1 | network |
| 2 | **block** |
| 3 | console |
| 4 | entropy |
| 5 | memory balloon |
| 8 | **SCSI host** |

PCI 层：**transitional（legacy）设备 ID 在 `0x1000+n`，modern 设备在 `0x1040+n`**
（例如 virtio-blk modern = `0x1042`），厂商 ID = `0x1af4`（Red Hat/virtio）。

```bash
lspci -nn | grep -i virtio          # 看 vendor 1af4 与 device id
lspci -vv -s 00:04.0 | head -40     # 看 cap 结构与 MSI-X
```

### 3.3 与 SCSI / NVMe 的关系（不要混淆层次）

| 形态 | guest 协议 | 是否走 SCSI 中层 | guest 驱动 |
|---|---|---|---|
| virtio-blk | `virtio_blk_req` | 否 | `virtio_blk` |
| virtio-scsi | **SCSI CDB**（跑在 virtqueue 上） | **是**（`scsi_mod`/`sd_mod`） | `virtio_scsi` |
| NVMe 协议云盘 | NVMe 命令（SQ/CQ） | 否 | `nvme` / `nvme_core` |

> virtio-scsi 是"**传输层用 virtio、命令层用 SCSI**"；NVMe 云盘则完全不走 virtio，是标准 NVMe 控制器模型。

## 4. 三种磁盘设备的 QEMU 命令行与 guest 侧对应

```bash
# ① virtio-blk：一块盘 = 一个 PCI 设备
qemu-system-x86_64 -drive file=disk.qcow2,if=virtio,format=qcow2
#   guest：/dev/vda   驱动：virtio_blk

# ② virtio-scsi：一个 controller 挂多个 LUN
qemu-system-x86_64 \
  -device virtio-scsi-pci,id=scsi0 \
  -drive if=none,id=d0,file=disk.qcow2,format=qcow2 \
  -device scsi-hd,drive=d0,bus=scsi0.0
#   guest：/dev/sda   驱动：virtio_scsi + scsi_mod + sd_mod

# ③ NVMe：标准 NVMe 控制器 + namespace
qemu-system-x86_64 \
  -drive if=none,id=d0,file=disk.qcow2,format=qcow2 \
  -device nvme,drive=d0,serial=deadbeef
#   guest：/dev/nvme0n1   驱动：nvme / nvme_core（与裸机同一套）
```

**固件选择（决定 guest 走 Legacy 还是 UEFI）**：

```bash
# Legacy（默认 SeaBIOS）
qemu-system-x86_64 -drive ... 
# UEFI（OVMF = 开源 UEFI 固件，来自 edk2）
qemu-system-x86_64 -bios /usr/share/OVMF/OVMF.fd -drive ...
# 或分别指定 code/vars（现代用法，便于持久化 UEFI 变量）
qemu-system-x86_64 \
  -drive if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE.fd \
  -drive if=pflash,format=raw,file=./OVMF_VARS.fd
```

> **OVMF_VARS 文件 ≈ 云上实例的 NVRAM**。本地把变量存在这个文件里 → 换台机器/换文件就"引导项不见了"，
> 这就是云上必须依赖 ESP 默认 fallback 路径的同一机制（见 [[concepts/Linux 启动链 与 引导]] §5.2）。

## 5. 网卡：virtio-net

```bash
qemu-system-x86_64 \
  -netdev user,id=n0 -device virtio-net-pci,netdev=n0,mq=on,vectors=10
```

- `mq=on`：多队列（配合 guest 内多队列/RSS，提升网络吞吐）
- guest 侧设备名：`eth0`（需 `net.ifnames=0` 才稳定）
- 性能相关：队列数、中断亲和、GSO/GRO、vhost-net（内核态加速）——与 DPDK/数据面认知直接衔接

> 你的 DPDK/SR-IOV 经验在这里可以直接迁移：virtio-net 是"半虚拟化网卡"，
> 而 VFIO 直通 + PMD 是"直通网卡"，两者性能与部署复杂度差一个量级。

## 6. 常用命令速查（镜像工作必备）

```bash
# 起一台最小 VM（串口直出，无需图形）
qemu-system-x86_64 -enable-kvm -m 4096 -smp 4 \
  -drive file=img.qcow2,if=virtio,format=qcow2 \
  -netdev user,id=n0 -device virtio-net-pci,netdev=n0 \
  -nographic

# 看镜像格式/大小/虚拟大小
qemu-img info img.qcow2

# 格式转换（raw ⇄ qcow2 / vhd / vmdk）
qemu-img convert -p -f raw -O qcow2 disk.raw disk.qcow2

# 直接从裸盘导出
qemu-img convert -f raw -O qcow2 /dev/sda out.qcow2

# 检查镜像一致性
qemu-img check img.qcow2
```

> 镜像的离线改动（挂载、改 fstab、装包）不靠 QEMU 启动，而靠 `qemu-nbd` / `libguestfs`
> —— 见 [[entities/镜像格式 与 离线处理工具链]]。

## 7. 与公有云设备选择的映射

| 云/规格 | host 侧提供 | guest 看到 | 对镜像的要求 |
|---|---|---|---|
| 阿里云老规格、腾讯云 | virtio-blk（vdX） | `/dev/vda` | initramfs 有 `virtio_blk` |
| 华为云（UEFI 镜像强制） | virtio-scsi | `/dev/sda` 或经 udev 别名 | initramfs 有 `virtio_scsi`+`scsi_mod` |
| 阿里云新规格（g7se/g8i 等） | NVMe 协议云盘 | `/dev/nvme0n1` | initramfs 有 `nvme`+`nvme_core` |

**一句话**：云厂商换的是 host 侧设备实现，guest 侧看到的协议与设备名随之改变 —— 所以镜像必须"三种都能起"。

## 8. 性能视角（接存储与网络主线）

| 维度 | virtio-blk | virtio-scsi | NVMe 协议云盘 |
|---|---|---|---|
| 每 IO 软件路径 | virtqueue + blk 层 | virtqueue + **SCSI 中层** + blk 层 | NVMe SQ/CQ + blk 层 |
| 队列扩展 | multiqueue（受 virtio 环与通知开销限制） | controller 级共享 | 每 namespace 独立 SQ/CQ，深度大 |
| 典型瓶颈 | 通知开销、单环争用 | CDB 封装 + SCSI 中层 | host 侧存储后端（ESSD 档位） |
| 与块层调优的关系 | 见 [[concepts/存储栈与io_uring]]（io scheduler、队列深度、中断亲和） | 同上 | 同上，NVMe 场景常用 `none` 调度器 |

## 9. 自测

1. KVM 与 QEMU 各负责什么？为什么说"KVM 不提供设备"？
2. virtqueue 的三个环分别是谁写、谁读？通知机制为什么要抑制？
3. virtio-scsi 与 virtio-blk 在 guest 侧的最大区别是什么（从驱动栈角度）？
4. 本地 OVMF 的 VARS 文件与云上 NVRAM 是什么关系？
5. 为什么 NVMe 协议云盘不需要 guest"知道"自己被虚拟化？

## 来源

- QEMU 文档（System Emulation / Device URLs）https://www.qemu.org/docs/master/
- OASIS virtio 规范（virtqueue、设备 ID、feature bits）https://docs.oasis-open.org/virtio/
- UEFI 规范与 edk2/OVMF 项目 https://uefi.org/specifications 、https://github.com/tianocore/edk2
- Linux 内核文档（virtio、nvme）https://www.kernel.org/doc/html/latest/

> 断言分级：virtqueue 结构、设备 ID、QEMU 命令行参数为通用事实（以本机 QEMU 版本 `-device help` 实测为准）；
> 各云 host 侧的具体实现属厂商内部细节，本页只描述 guest 可观测行为。
