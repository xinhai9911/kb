---
title: Windows 镜像 云上适配
category: concepts
tags: [windows, image, cloudbase-init, sysprep, virtio-win, boot, 镜像, active]
created: 2026-10-16
updated: 2026-10-16
summary: >-
    Windows 系统镜像上公有云的差异点：初始化组件是 cloudbase-init 而非 cloud-init、
    身份清理靠 Sysprep（对应 Linux 的 machine-id/密钥清理）、
    virtio 驱动必须预装（viostor/vioscsi/NetKVM/Balloon）且关键启动驱动要在 CriticalDeviceDatabase 注册，
    Windows ESP 引导路径（bootmgfw.efi 与 \EFI\BOOT\BOOTX64.EFI fallback）与云上 NVRAM 为空的关系、
    系统盘容量与分区结构（EFI/MSR/恢复）、激活与 License 类型、
    NVMe 协议云盘对 Windows 版本的要求，以及 0x7B 蓝屏等典型故障的定位。
base_confidence: 0.83
lifecycle: reviewed
---

# Windows 镜像 云上适配

> 相关：[[concepts/KVM 公有云 镜像 适配]]（Linux 主线与三家规范）、[[concepts/Linux 启动链 与 引导]]（引导机制可对照读）。
> 本页只讲**与 Linux 不同**的部分；相同的规范（架构/启动模式/UUID/License）见主页面。

## 1. 全景对照：Linux 与 Windows 的镜像适配差异

| 关注点 | Linux | Windows |
|---|---|---|
| 初始化组件 | **cloud-init**（mandatory） | **cloudbase-init**（Windows 版，Python 实现） |
| 身份清理 | 清 `machine-id` + 删 SSH 主机密钥 | **Sysprep /generalize**（清 SID、清系统身份） |
| 虚拟化驱动 | 内核自带 virtio/nvme | **必须手工预装 virtio-win**（viostor/vioscsi/NetKVM…） |
| 设备名 | `/dev/vda`、`/dev/nvme0n1` | 磁盘/网卡由驱动与 GUID 标识，无设备名概念 |
| 引导文件 | `\EFI\redhat\shimx64.efi` | `\EFI\Microsoft\Boot\bootmgfw.efi` |
| fallback 路径 | `\EFI\BOOT\BOOTX64.EFI` | 同路径，通常是 `bootmgfw.efi` 的副本 |
| 日志查看 | 串口 `console=ttyS0` | 主要靠 VNC + 事件查看器；串口支持弱 |
| 激活 | 无 | **License 类型 / KMS**（导入时必须声明） |

## 2. 初始化：cloudbase-init

Windows 上不做"进程级初始化"，而是由 **cloudbase-init** 承担 cloud-init 的角色：

- 位置：`C:\Program Files\Cloudbase Solutions\Cloudbase-Init\conf\`
- 服务名：`cloudbase-init`（**须设为自动启动**）
- 作用：设置 hostname、注入管理员密码、执行 user-data（PowerShell）、配置网络
- 与云平台的关系：阿里/腾讯/华为都提供 Windows 公共镜像内置；**导入自有镜像时必须自己装**

```powershell
# 检查服务状态
Get-Service cloudbase-init | Select-Object Name,Status,StartType
# 日志（排障第一站）
Get-Content 'C:\Program Files\Cloudbase Solutions\Cloudbase-Init\log\cloudbase-init.log' -Tail 100
```

> 对应 Linux 的 `cloud-init status --long`：Windows 侧就看这个日志文件。

## 3. 身份清理：Sysprep 而不是删文件

```powershell
# 通用化（关机前执行；参数按需求调整）
%windir%\System32\Sysprep\sysprep.exe /generalize /oobe /shutdown /unattend:C:\unattend.xml
```

| Sysprep 做了什么 | 对应 Linux 的哪一步 |
|---|---|
| 移除机器 SID 与唯一标识 | 清 `/etc/machine-id` |
| 清计算机名 | 清 hostname 配置 |
| 重置 OOBE，使下次启动重新初始化 | 清 `/var/lib/cloud`（触发重新初始化） |
| `/generalize` 会重装即插即用驱动匹配 | 重建 initramfs（让新硬件重新探测） |

**关键点**：`/generalize` 后**必须关机再导出**（不要开机又改动，否则 Sysprep 状态被破坏）。

## 4. virtio 驱动：Windows 镜像最硬的门槛

Windows 没有内核自带 virtio 驱动，**必须预装 `virtio-win` 驱动包**：

| 驱动 | 对应设备 | 缺失后果 |
|---|---|---|
| **viostor** | virtio-blk | **系统盘不认识 → 0x7B 蓝屏**（INACCESSIBLE_BOOT_DEVICE） |
| **vioscsi** | virtio-scsi | 同上（华为云 UEFI 镜像走 scsi，这个必须有） |
| **NetKVM** | virtio-net | 起来但没网卡 |
| Balloon | 内存气球 | 内存回收失效 |
| vioserial / qxldod | 串口 / 显示 | 控制台/串口不可用 |

### 4.1 关键：**启动关键驱动要能"最早期"加载**

Windows 与 Linux 的 initramfs 问题同构：如果存储驱动不在启动早期可用，就是 0x7B。
做法（install 驱动的正确姿势）：

```powershell
# ① 把驱动解压到镜像（viostor/w10/amd64 等目录）
# ② 逐个 inf 安装并写入注册表关键服务数据库
pnputil /add-driver X:\viostor\w10\amd64\viostor.inf /install
# 或用厂商提供的 install.bat / silent_install.bat
# ③ 确认服务为 boot 启动类型
reg query HKLM\SYSTEM\CurrentControlSet\Services\viostor /v Start
#   Start 应为 0（boot 型驱动）
```

> 与 Linux 对照记忆：**viostor/vioscsi 之于 Windows = virtio_blk/virtio_scsi 之于 initramfs**，
> 都是"根盘驱动必须在最早阶段可用"，只是 Windows 没有 initramfs 这个显式载体。

### 4.2 NVMe 协议云盘

- Windows **原生自带 NVMe 驱动**（`stornvme.sys`，Server 2012 R2 起），较新版本无需额外装
- 老版本（2008 R2 等）需补丁/厂商驱动 → 若目标云有新代 NVMe 规格，**老 Windows 版本可能直接不可用**
- 与 Linux 的结论一致：**NVMe 能力是"规格代际 × 镜像内核/驱动"两侧共同决定的**

## 5. 引导：和 Linux 同一套机制

| 项 | 内容 |
|---|---|
| UEFI 引导文件 | `\EFI\Microsoft\Boot\bootmgfw.efi`（通常还有 `\EFI\BOOT\BOOTX64.EFI` 副本作 fallback） |
| Legacy 引导 | 系统保留分区里的 BCD + MBR 引导代码 |
| 云上关键点 | **NVRAM 为空 → 依赖 fallback 路径**（与 Linux 完全相同，见 [[concepts/Linux 启动链 与 引导]] §5.2） |
| 分区结构 | EFI 系统分区 + **MSR**（Microsoft Reserved）+ 系统分区（+ 常见恢复分区） |
| 启动模式声明 | 导入时必须与镜像实际一致（BIOS / UEFI） |

> 因此 Windows 镜像同样要做**"双引导/指定启动模式"的决策**，逻辑与 Linux 页 §4 一致。

## 6. 系统盘与激活

| 项 | 说明 |
|---|---|
| 系统盘容量 | Windows 比 Linux 吃空间（更新缓存/WinSxS），**最小要求通常更大（常见 40 GiB 起，以云文档为准）** |
| 扩容 | 云侧扩盘后需在 Windows 内"磁盘管理 → 扩展卷"（对应 Linux 的 growpart） |
| 激活 | 云厂商多提供 KMS；导入自有镜像要选对 **License 类型**，自带 License 需合规 |
| 数据盘 | 初始化后需"联机 + 初始化磁盘 + 新建卷"（Linux 侧的 mkfs + fstab 对应物） |

## 7. 典型故障定位

| 现象 | 根因 | 处置 |
|---|---|---|
| **0x7B INACCESSIBLE_BOOT_DEVICE** | 系统盘驱动（viostor/vioscsi）未装或未在 boot 期加载 | 装 vioscsi/viostor，确认注册表 `Start=0`；在 virtio 环境下重做 |
| **0x0000007E / 反复重启** | 驱动签名/版本与虚拟化设备不匹配 | 用官方 virtio-win 对应 Windows 版本目录 |
| 起来了但没网卡 | NetKVM 未装 | 装 NetKVM 并确认网卡服务启动 |
| 能起但 cloudbase-init 不执行 | 服务未设自动启动 / 日志报错 | §2 的日志与 StartType |
| Sysprep 后仍是旧计算机名 | 未 `/generalize` 或 generalize 后又改动了系统 | 重新 Sysprep，导出前不再启动系统 |
| 导入时平台报尺寸/分区不符 | 缺 MSR/EFI 分区，或系统盘过小 | 按 §5/§6 检查分区结构 |

## 8. 交付前检查清单（Windows 版对应）

```
□ virtio 驱动：viostor + vioscsi + NetKVM + Balloon（按目标云设备类型）
□ viostor/vioscsi 的 Start 值 = 0（boot 型）
□ cloudbase-init 已安装且服务为自动启动
□ Sysprep /generalize 已执行，且之后未再启动系统
□ ESP 存在且 \EFI\BOOT\BOOTX64.EFI 存在（UEFI 镜像）
□ 启动模式声明与镜像实际一致
□ 系统盘容量满足要求；分区结构（EFI/MSR/系统）完整
□ License 类型已确认（含 KMS/自带授权）
□ 在 KVM + 对应设备类型下实测启动过（不要只在 VMware/Hyper-V 里测）
```

## 9. 自测

1. Windows 上 cloud-init 的对应物是什么？日志在哪？
2. Sysprep `/generalize` 对应 Linux 的哪两部操作？
3. 为什么 virtio 存储驱动必须"boot 期可用"？缺失时 Windows 报什么错？
4. Windows 镜像在云上依赖 fallback 路径的机制与 Linux 是否相同？
5. 为什么在 VMware 里测好的 Windows 镜像搬到 KVM 上会 0x7B？

## 来源

- 阿里云《Windows 自定义镜像制作与导入规范》 https://help.aliyun.com/zh/ecs/user-guide/requirements-on-alibaba-cloud-marketplace-windows-images
- 腾讯云《制作 Windows 镜像》（云服务器文档）
- 华为云《Windows 私有镜像制作》与 Cloudbase-Init 相关章节
- Fedora/Red Hat virtio-win 项目（驱动与安装脚本）https://github.com/virtio-win

> 断言分级：cloudbase-init/Sysprep/virtio-win 驱动职责为通用事实；Windows 版本对 NVMe 的原生支持与各家系统盘最小容量以厂商文档为准。
