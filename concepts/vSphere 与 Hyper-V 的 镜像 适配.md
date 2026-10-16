---
title: vSphere 与 Hyper-V 的 镜像 适配
category: concepts
tags: [vmware, vsphere, esxi, hyperv, ovf, vmdk, vhdx, virt-v2v, image, 交付, active]
created: 2026-10-16
updated: 2026-10-16
summary: >-
    KVM 之外的交付去向：客户现场的 VMware vSphere/ESXi 与 Hyper-V。
    与 KVM 的三处根本差异（设备模型 vmxnet3/pvscsi 与合成驱动、工具链 open-vm-tools/vmtoolsd 与 qemu-guest-agent、
    交付格式 OVA/OVF 与 VHD/VHDX）、VMware Guest Customization 与 cloud-init 的关系、
    Hyper-V 第 1/2 代与 enlightenments、EFI 与 Secure Boot 在两家的差异、
    以及本页的核心工具 **virt-v2v**（把 KVM/Xen 镜像转换成 vSphere/Hyper-V 可用镜像并注入驱动）；
    最后给出跨平台交付检查清单与"一套源码多平台出图"的策略。
base_confidence: 0.84
lifecycle: reviewed
---

# vSphere 与 Hyper-V 的 镜像 适配

> 相关：[[concepts/KVM 公有云 镜像 适配]]（KVM 主线）、[[concepts/裸金属 与 私有云 的 镜像 差异]]（交付去向的另一半）、
> [[entities/镜像格式 与 离线处理工具链]]（格式与 qemu-img）。

## 1. 为什么这是缺口：交付去向不止 KVM

本库主线覆盖了"公有云 KVM / 裸金属 / OpenStack 私有云"，但客户现场还有两大类：

| 平台 | 常见场景 | 与 KVM 的兼容性 |
|---|---|---|
| **VMware vSphere / ESXi** | 企业私有云、传统 IDC | 设备模型完全不同（vmxnet3/pvscsi），**镜像不能直接用** |
| **Hyper-V** | Windows 主导的企业环境、Windows 宿主机 | 合成驱动（netvsc/storvsc），**同样不能直接用** |

> 关键结论：**KVM 镜像 = virtio 世界；vSphere = VMware 设备世界；Hyper-V = 合成驱动世界。**
> 三者靠"驱动 + 格式 + 工具"三件套区分，不能互换。

## 2. 三处根本差异（一张表看懂）

| 维度 | KVM（本库主线） | VMware vSphere | Hyper-V |
|---|---|---|---|
| 磁盘控制器 | virtio-blk / virtio-scsi / NVMe | **PVSCSI** / LSI Logic SAS / SATA | **storvsc**（合成）/ IDE（Gen1） |
| 网卡 | virtio-net | **vmxnet3** / e1000e | **netvsc**（合成）/ legacy |
| guest 工具 | qemu-guest-agent | **open-vm-tools / vmtoolsd** | Linux Integration Services（多数已进内核）+ KVP |
| 初始化组件 | cloud-init | cloud-init **或** VMware Guest Customization | cloud-init |
| 磁盘格式 | qcow2 / raw | **VMDK**（thin/thick/lazy zeroed 置备） | **VHD / VHDX** |
| 分发格式 | qcow2 上传导入 | **OVA / OVF**（也可直接用 VMDK） | VHD/VHDX |
| 固件 | SeaBIOS / OVMF | BIOS / **EFI**（EFI 需 vSphere 对应版本） | Gen1(BIOS) / **Gen2(UEFI)** |
| 引导名 | `\EFI\BOOT\BOOTX64.EFI` + shim/grub | `\EFI\BOOT\BOOTX64.EFI`（EFI 固件同样走默认路径） | `\EFI\BOOT\BOOTX64.EFI` |
| 内存/CPU 热插拔 | 视机型 | 需 vmtoolsd 配合 | 需 LIS/KVP |

**引导链逻辑仍然通用**（见 [[concepts/Linux 启动链 与 引导]] §5.2）：NVRAM 行为、ESP fallback 路径这些机制在各家用同一套 UEFI 规则。

## 3. 核心工具：virt-v2v（本页最重要的一条）

`virt-v2v` 是专门做 **V2V 转换**的工具（libguestfs 家族），它不只是转格式：

```
源镜像（KVM/Xen 的 qcow2）
   ↓ virt-v2v -i libvirt -o vmx / -o rhv / -o openstack / -o local
① 转换磁盘格式
② **卸载源平台的 guest 工具（如 virtio 相关）**
③ **注入目标平台的驱动与工具**（vSphere → open-vm-tools + vmxnet3/pvscsi 支持；Hyper-V → 合成驱动）
④ 调整引导与 fstab（若设备名变化）
⑤ 产出目标平台可用的镜像/OVA
```

| 用法 | 说明 |
|---|---|
| `virt-v2v -i disk img.qcow2 -o local -of qcow2` | 本地转换（改驱动、便于再打包） |
| `-o vmx` | 直接产出 **VMX + VMDK**（vSphere 可用） |
| `-o libvirt` | 转成 libvirt 可管理的形态（再手工导出） |
| 对 Hyper-V | 通常先转成本地/VHD，再用 Hyper-V 侧导入 |

> **对你的产线意味着什么**：不必为 vSphere 维护第二条构建流水线 ——
> **以 KVM 镜像为唯一源头，用 virt-v2v 派生目标平台版本**。
> 这是"一套源码多平台出图"的现实解法。

## 4. vSphere 侧要点

| 项 | 说明 |
|---|---|
| 磁盘控制器选择 | **PVSCSI** 性能最好（大 IOPS 场景）；LSI Logic SAS 兼容性最好；不要用 IDE |
| 磁盘置备 | thin / thick（lazy zeroed / eager zeroed）：影响空间与首次写性能 |
| 网卡 | **vmxnet3**（有队列与卸载能力）；e1000e 仅兼容用 |
| open-vm-tools | 提供优雅关机/冻结/内存气球/时间同步；**建议装发行版仓库版**（别用 VMware 打包的旧版） |
| Guest Customization | VMware 自有的 guest 定制（改 hostname/IP 等），与 cloud-init **功能重叠**；两者同时开启可能冲突 → 选一个（容器/云原生环境选 cloud-init） |
| EFI 引导 | 需 vSphere 版本支持；开启后同样是 `\EFI\BOOT\BOOTX64.EFI` 机制 |
| OVF/OVA | OVA = OVF 描述文件 + 若干 VMDK 的 tar 包；跨团队/客户交付的常见形态 |
| 时间同步 | vmtoolsd 可做时间同步；生产仍建议独立 NTP/chrony |

## 5. Hyper-V 侧要点

| 项 | 说明 |
|---|---|
| **Generation 1 vs 2** | Gen1 = 传统 BIOS + IDE；Gen2 = **UEFI** + 合成驱动（更现代）。镜像必须与代次匹配，**Gen2 需显式声明**（对应 OpenStack 的 `hw_machine_type=hyperv-gen2`，见 [[concepts/裸金属 与 私有云 的 镜像 差异]] §2.1） |
| 合成驱动 | Linux 的 `netvsc`/`storvsc` 等多数已在发行版内核；**老发行版需装 LIS** |
| KVP 数据交换 | 宿主机与 guest 交换键值（IP、hostname）——cloud-init 可借助它做部分注入 |
| Windows guest | 见 [[concepts/Windows 镜像 云上适配]]；Hyper-V enlightenments 会影响 Windows 性能与行为 |
| 磁盘格式 | VHD（Gen1 常见）与 VHDX（Gen2/现代）；qemu-img 可转 VHD |
| 检查点（Checkpoint） | 与快照语义类似，但恢复后 guest 的时间/时钟行为要注意 |

## 6. 跨平台交付检查清单

```
□ 目标平台明确（vSphere 版本 / Hyper-V 代次）
□ 用 virt-v2v 派生目标平台镜像（而不是手工装驱动"试试看"）
□ 磁盘控制器与网卡：目标平台的驱动已注入并在 initramfs 内（与 KVM 侧同理）
□ guest 工具替换：open-vm-tools（vSphere）/ LIS+KVP（Hyper-V）；避免与 cloud-init 冲突
□ 初始化组件二选一：cloud-init 或 平台 Guest Customization（别都开）
□ 格式与打包：VMDK → OVA/OVF；VHD/VHDX 供 Hyper-V
□ 固件与代次：EFI/Gen2 需显式声明并有 fallback
□ 时间同步：chrony 或平台工具，二者不要互斥
□ 在**目标平台实测**启动（不要只在 KVM 里验证）
□ 版本台账记录"同一版本派生出的各平台镜像"（见 [[concepts/镜像 资产 治理 与 成本]]）
```

## 7. 自测

1. 为什么 KVM 镜像不能直接在 vSphere 上启动？缺的是哪三样？
2. `virt-v2v` 除了转格式还做了什么？为什么它比自己装驱动更可靠？
3. VMware Guest Customization 与 cloud-init 同时启用会有什么问题？
4. Hyper-V Gen1 与 Gen2 的关键差异是什么？镜像层面要注意什么？
5. 一套源码要交付三种平台（KVM/vSphere/Hyper-V），怎么组织构建最省力？

## 来源

- libguestfs / virt-v2v 文档 https://libguestfs.org/virt-v2v.1.html
- VMware 文档（PVSCSI/vmxnet3、open-vm-tools、Guest Customization、OVF 规范）
- Microsoft Learn（Hyper-V Generation 1/2、Linux Integration Services、KVP）
- 本库：[[entities/镜像格式 与 离线处理工具链]]、[[concepts/Windows 镜像 云上适配]]

> 断言分级：三平台设备模型/工具链/格式差异为通用事实；具体版本支持矩阵（如 vSphere 版本与 EFI、LIS 与发行版内核）
> 以厂商文档当日版本为准。
