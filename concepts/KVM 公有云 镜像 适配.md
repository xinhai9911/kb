---
title: KVM 公有云 镜像 适配
category: concepts
tags: [kvm, virtio, nvme, uefi, cloud-init, image, alibaba, huawei, tencent, active]
created: 2026-10-16
updated: 2026-10-16
summary: >-
    把物理机/本地机制作的 Linux 系统镜像适配到阿里云/华为云/腾讯云 KVM 环境。
    核心：纠偏"阿里云不支持 NVMe"（老规格 virtio / 新规格 NVMe 云盘，须 virtio+NVMe 双驱动）；
    磁盘挂载形态协议级对比（virtio-blk / virtio-scsi / virtio disk / NVMe 协议云盘：驱动栈、请求格式、队列模型、识别方法）；
    三家镜像规范横向对比（LVM/swap 禁止、fstab UUID 与非系统盘挂载限制、cloud-init、密码注入）；
    UEFI vs Legacy 深挖（UEFI-Preferred 双引导、NVRAM fallback、华为 UEFI 强制 virtio-scsi）；
    initramfs 驱动清单、改造步骤与 qemu 本地验证矩阵。全部依据官方文档 2026-10-16 核实。
base_confidence: 0.9
lifecycle: reviewed
---

# KVM 公有云 镜像 适配

> 前置：[[concepts/CPU 虚拟化与IO穿透]]（KVM/VT-x 基础）、[[concepts/存储栈与io_uring]]（块设备栈）。
> 适用场景：appliance DOM 生产镜像（RHEL8 系，UEFI GPT + ESP + XFS /boot + LVM）上公有云；
> 结论对任何"物理机镜像迁云"场景通用。

## 1. 先纠偏：不要做"协议站队"

常见论断 **"阿里云不支持 NVMe，所以镜像上不了公有云"是不准确的**。三家全部是 KVM，磁盘协议按**规格代际**分叉而非厂商站队：

| 规格代际 | 阿里云                                                     | 华为云           | 腾讯云                  |
| ---- | ------------------------------------------------------- | ------------- | -------------------- |
| 老规格  | virtio-blk 云盘                                           | virtio 或 scsi | virtio disk（vda/vdb） |
| 新规格  | **NVMe 协议云盘**（ecs.g7se、ecs.g8i 等），镜像无 NVMe 驱动**反而启动失败** | virtio-scsi   | virtio disk          |

镜像导入后起不来的两个真实根因：

1. **设备名硬编码**：镜像产自 NVMe 盘，fstab / grub 写死 `/dev/nvme0n1pX`，云上根盘是 `/dev/vda` → 找不到 root fs
2. **驱动缺失**：initramfs 未含 virtio 驱动，早期用户空间看不到 virtio 盘 → kernel panic

**正确策略：virtio + NVMe 双驱动覆盖 + 全链路 UUID 寻址**，与磁盘协议彻底脱钩。阿里云导入镜像后还需在控制台把镜像的"NVMe 驱动"属性手动置为"支持"，否则新规格创建实例时选不到该镜像。四种挂载形态的协议级区别见 §2。

## 2. 磁盘挂载形态：virtio-blk / virtio-scsi / virtio disk / NVMe 协议云盘

盘在 guest 里"长什么样"由三件事决定：**通信协议、guest 驱动、设备命名**。四者的区别全在这条链上。

### 2.1 virtio-blk —— virtio 规范的原生块设备

- **协议**：OASIS virtio 规范 block 成员（设备 ID 2）。一个 virtio-blk 设备 = 一个 PCI function + 一组/多组 virtqueue
- **guest 驱动栈**：`virtio_pci` → `virtio_blk`（`drivers/block/virtio_blk.c`）→ 块层，**不经过 SCSI 中层**
- **请求格式**：`virtio_blk_req`（header + 数据描述符 + status 字节），type 仅 IN/OUT/FLUSH/DISCARD/WRITE_ZEROES/GET_ID 等，**无 SCSI CDB**
- **设备名**：`/dev/vdX`
- **队列模型**：blk-mq 多队列（`VIRTIO_BLK_F_MQ`），队列数默认与 vCPU 相关、约 64 封顶；virtqueue 为 avail/used ring，支持 indirect 描述符
- **特性边界**：flush、discard（粗粒度）；**无** UNMAP 细粒度描述、VPD、persistent reservation、TMF、SCSI 错误恢复
- **扩展性**：一块盘 = 一个 PCI 设备，盘多时 PCI function / 中断开销线性涨
- **地位**：第一代公有云标准形态；腾讯云文档"Virtio Disk，设备名 vda/vdb"即此

### 2.2 virtio-scsi —— 把 SCSI 协议跑在 virtqueue 上

- **协议**：virtio 规范 SCSI host 成员（设备 ID 8）。QEMU 侧一个 controller（`virtio-scsi-pci`）+ 多 LUN
- **guest 驱动栈**：`virtio_scsi` → `scsi_mod` → `sd_mod`，**走完整 SCSI 中层**
- **请求格式**：完整 SCSI CDB（READ(10/16) / WRITE(10/16) / UNMAP…）+ sense data；支持 TMF（abort / lun reset）
- **设备名**：SCSI 栈枚举，通常 `/dev/sdX`（云厂商可用 udev 规则固定别名）
- **队列模型**：controller 级共享队列，一个 controller 挂数十至上百 LUN
- **特性边界**：完整 SCSI 特性——UNMAP 细粒度回收（云盘 thin provisioning 靠它）、VPD 暴露云盘序列号、persistent reservation、dm-multipath、在线 rescan、SCSI 重试语义
- **开销**：每 IO 多一层 CDB 封装 + SCSI 中层，略高于 virtio-blk（通常个位数百分比）
- **谁在用**：OpenStack 生态标准；华为云 Stack 明确 Linux 镜像磁盘设备类型须 virtio 或 scsi，**UEFI 镜像必须 scsi**

### 2.3 "virtio disk" —— 泛称，不是第四种协议

- 指"通过 virtio 半虚拟化暴露的盘"大类，virtio-blk 与 virtio-scsi 都属于 virtio disk
- 相对的两个极端：**全设备模拟**（IDE/AHCI，hdX，qemu `-drive if=ide`，兼容老系统但慢）与 **PCIe 直通**（物理盘/VF 透传单 guest，无共享能力）
- 腾讯云文档口径的 "Virtio Disk" 落地形态是 virtio-blk

### 2.4 NVMe 协议云盘 —— guest 侧就是一块标准 NVMe SSD

- **协议**：NVM Express。guest 看到标准 NVMe 控制器（PCI class `010802`，lspci 显示 "Non-Volatile memory controller"），**每块云盘 = 一个 namespace**
- **guest 驱动栈**：`nvme` + `nvme_core`（`drivers/nvme/`）——与裸机 NVMe SSD 同一套驱动，nvme-cli / smartctl 通用
- **请求格式**：NVMe 命令（Read/Write/Flush/Write Zeroes/Dataset Management），SQ/CQ 队列对机制（PRP/SGL 描述符）
- **设备名**：`/dev/nvme0n1`，分区 `nvme0n1p1`
- **队列模型**：NVMe 原生 64K 队列 × 64K 深度（理论上限），每 namespace 独立 SQ/CQ 对——相对 virtio-blk multiqueue（约 64 封顶）是代差，匹配 ESSD 数十万 IOPS 的并行度
- **实现**：QEMU 验证用 `-device nvme,drive=d0`（`hw/block/nvme.c`，自动带一个 namespace）；生产云 host 侧多为轻量 virt / 硬件 offload，guest 协议语义仍是标准 NVMe
- **阿里云口径**：ecs.g8i / ecs.g7se 等新规格支持基于 NVMe 协议挂载云盘；镜像须带 NVMe 驱动，导入后把镜像"NVMe 驱动"属性置为支持
- **边界澄清**：本文所指 ≠ NVMe 本地盘机型（物理 SSD 本地直挂，如 i4/g7se 本地盘部分）≠ NVMe-oF（网络 NVMe，RDMA/TCP）

### 2.5 总对比表

| 维度 | virtio-blk | virtio-scsi | "virtio disk" | NVMe 协议云盘 |
|---|---|---|---|---|
| 协议规范 | virtio blk | virtio scsi | 泛称（含上两者） | NVM Express |
| 每 IO 请求格式 | virtio_blk_req | SCSI CDB + sense | — | NVMe command（SQ/CQ） |
| guest 驱动 | virtio_blk | virtio_scsi + scsi_mod | virtio_blk / virtio_scsi | nvme + nvme_core |
| 经过 SCSI 中层 | 否 | **是** | 视形态 | 否 |
| 设备名 | /dev/vda | /dev/sda（可 udev 改） | vdX | /dev/nvme0n1 |
| 一块盘 = | 一个 PCI 设备 | 一个 controller 的一个 LUN | — | 一个 namespace |
| 队列扩展性 | 多队列 ~64 封顶 | controller 级共享 | 视形态 | 每 ns 独立 SQ/CQ，64K 级 |
| TRIM/回收 | discard（粗） | UNMAP（细粒度） | — | DSM deallocate / Write Zeroes |
| SCSI 高级特性 | 无 | 全（VPD/PR/TMF/多路径） | 视形态 | 无 SCSI，有 NVMe 原生 SMART/日志/ns 管理 |
| 每 IO 开销 | 最低 | 中（CDB 封装） | — | 低（原生队列，云侧可 offload） |
| 多盘扩展 | PCI 开销随盘数涨 | 单 controller 多 LUN | — | 单 controller 多 ns |

### 2.6 guest 内识别当前形态

```bash
lspci -vv                                    # Virtio block device / Virtio SCSI / Non-Volatile memory controller
ls -l /sys/block/vda                         # → .../virtioN/block/vda     (virtio-blk)
ls -l /sys/block/sda                         # → .../host0/...             (virtio-scsi)
ls -l /sys/block/nvme0n1                     # → .../nvme/nvme0/nvme0n1    (NVMe)
udevadm info -q property /dev/vda | grep ID_BUS   # virtio / scsi
nvme list                                    # 有 nvme-cli 时直接列 namespace
```

### 2.7 对镜像适配的结论

1. 同一镜像要三种形态都能起 → initramfs 三驱动齐全（见 §5）
2. 设备名三种形态各异（vda / sda / nvme0n1）→ fstab、grub `root=` 必须 UUID
3. 华为云 UEFI 强制 scsi → `virtio_scsi` 对华为不是可选项
4. qemu 本地验证三种挂法分别用 `-drive if=virtio`、`-device virtio-scsi-pci`、`-device nvme`

## 3. 三家镜像规范横向对比

以下为各家官方文档明文要求（已核实，见 §9 来源）：

| 约束项 | 阿里云 | 华为云 | 腾讯云 |
|---|---|---|---|
| 磁盘布局 | 物理分区；**根分区必须放最后一个**（否则系统盘扩容失败） | 启动分区与系统分区必须在同一磁盘 | 镜像至少包含根分区 + MBR |
| swap 分区 | **禁止** | — | — |
| LVM | **规范明文禁止** LVM 管理磁盘分区 | — | — |
| fstab | 必须 UUID；配置不当重启后无法运行 | **禁止非系统盘的自动挂载** | **勿挂载其它硬盘**（磁盘缺失会导致无法启动） |
| 镜像格式 | OSS 导入：qcow2 / raw / vhd / vmdk | raw / qcow2（以文档为准） | qcow2 / vhd / raw / vmdk |
| 系统盘 | ≥ 20 GiB | — | — |
| cloud-init | **必须**，建议 23.2.2（加固模式访问元数据）；内核需 `CONFIG_FW_CFG_SYSFS` | 可选（hostname/网络自定义） | **必须** |
| 密码注入 | cloud-init | **CloudResetPwdAgent** 一键重置密码插件 | cloud-init |
| 运维 agent | 云助手 Agent **必须** | OpsAgent 可选 | 无强制 |
| 启动模式 | 导入时声明；双引导镜像可设 **UEFI-Preferred** 通吃所有规格 | 一般 BIOS，UEFI 有操作系统支持列表 | 导入时声明，与镜像不一致影响启动 |
| 磁盘设备类型 | virtio / NVMe | Linux 须 virtio 或 scsi；**UEFI 镜像必须 scsi** | virtio |

**对 appliance 镜像的硬冲突（对照当前布局 ESP 599M + XFS /boot + LVM root/backup）：**

1. **LVM 是最大冲突**——阿里云明文禁止，且云盘 growpart 扩容对 LVM 支持差；根分区须为物理分区且位于末尾
2. **fstab 里的 /data、/backup 必须摘掉**（或 `noauto`）——三家都要求镜像不含非系统盘挂载，云上数据盘缺失时直接进 emergency mode
3. swap 分区去掉
4. ESP 599M 保留即可（远超各家 100~200M 隐性要求）

## 4. 启动模式：UEFI vs Legacy

### 4.1 基本规则

- 三家导入时都必须**声明与镜像实际一致的启动模式**（腾讯云文档原话：不一致"可能影响您实例的正常启动"）
- **阿里云独有 UEFI-Preferred**：镜像同时带 BIOS + UEFI 引导能力时，导入选 UEFI-Preferred，自动适配所有实例规格的启动模式——唯一"一套镜像通吃"的选项
- **规格代际约束**：新规格（g7/g8/c7/r7 等）多要求 UEFI；老规格（n1/sn1 等）仅 Legacy。只做单一模式会直接砍掉一半可选规格

### 4.2 UEFI 的三个真坑

1. **NVRAM 不跟随**：本地 `efibootmgr` 写入的引导项在云上实例里不存在（NVRAM 为空）。ESP 中必须存在 removable fallback 路径 `\EFI\BOOT\BOOTX64.EFI`（各云 UEFI 固件启动时扫描的标准路径）。验证：
   ```bash
   mount /boot/efi && ls /boot/efi/EFI/BOOT/BOOTX64.EFI
   ```
   缺失则从厂商目录拷贝 shim：`cp /boot/efi/EFI/redhat/shimx64.efi /boot/efi/EFIBOOT/BOOTX64.EFI`
2. **华为云 UEFI 镜像磁盘设备类型必须 scsi（virtio-scsi）**——initramfs 里的 `virtio_scsi` 不是可选项，是华为 UEFI 的强制项
3. **Secure Boot**：需要签名的 shim + grub + 内核。RHEL8 的 shim/grub 自带微软签名可以开；自编译内核无签名则不行。默认关闭，除非客户明确要求

### 4.3 Legacy 要点

- MBR 分区表，或 GPT + 1MiB `bios_grub`（EF02）分区 + `grub2-install --target=i386-pc`
- 腾讯云明确：导出的镜像至少包含根分区以及 MBR

### 4.4 双引导做法（推荐路线）

```bash
# UEFI 侧（保留现有 ESP 引导）
grub2-install --target=x86_64-efi --efi-directory=/boot/efi --bootloader-id=redhat
ls /boot/efi/EFI/BOOT/BOOTX64.EFI   # 确认 fallback 存在

# Legacy 侧：GPT 表加 1MiB EF02 分区后
grub2-install --target=i386-pc /dev/vda
```

导入策略：阿里云选 **UEFI-Preferred**；腾讯/华为按 `/sys/firmware/efi` 检测结果声明 UEFI。

## 5. 驱动与 initramfs

```bash
dracut -f --add-drivers "virtio_blk virtio_scsi virtio_net virtio_console virtio_pci nvme nvme_core xfs" \
    /boot/initramfs-$(uname -r).img $(uname -r)
```

为防止内核升级丢失，落盘 `/etc/dracut.conf.d/virtio.conf`：

```
add_drivers+=" virtio_blk virtio_scsi virtio_net virtio_console nvme"
```

| 驱动 | 为什么必须 | 对应挂载形态（见 §2） |
|---|---|---|
| `virtio_blk` / `virtio_pci` | 老规格 virtio 云盘 | virtio-blk |
| `virtio_scsi` | 华为云 UEFI 强制；部分机型走 scsi | virtio-scsi |
| `nvme` / `nvme_core` | 阿里云 g7se/g8i 新规格 NVMe 协议云盘 | NVMe 协议云盘 |
| `virtio_net` | virtio 网卡（默认只提供 eth0） | — |
| `virtio_console` | 云上串口/VNC 辅助通道 | — |
| `xfs` / `dm_mod` | 根文件系统与设备映射 | — |

验证：`lsinitrd /boot/initramfs-$(uname -r).img | grep -E 'virtio|nvme'`

## 6. 系统配置清单（阿里云规范，兼容三家）

- **时钟**：UTC（`timedatectl set-local-rtc 0`），写 `/etc/adjtime`
- **SSHD**：`PasswordAuthentication yes`——cloud-init 注入密码依赖密码登录；若不需要密码登录再 `passwd -l root`
- **网络**：默认 DHCP；GRUB 内核参数加 `net.ifnames=0 console=tty0 console=ttyS0,115200n8`
- **firewalld**：关闭（云上靠安全组）
- **清理宿主痕迹**：VMware/Xen/VirtualBox tools、写死 MAC 的 NetworkManager keyfile、`70-persistent-net.rules`
- **按云加 agent**：阿里云云助手（必须）、华为 CloudResetPwdAgent（一键重置密码）
- **扩容**：装 `cloud-utils-growpart`，cloud-init 的 growpart 模块负责系统盘在线扩容

## 7. 改造路线

**推荐在 KVM 里重铸而非手工改造**：appliance 镜像本就是 anaconda 安装的，在 qemu 挂 virtio 盘重装一遍，anaconda 自动做对分区/引导决策，比手工迁移可靠得多。

手工改造（备选）步骤：

1. 布局改为：ESP（保留 599M）+ XFS `/boot` 1G + **物理 XFS `/`（剩余空间，放最后）**；去 LVM/swap/backup
2. fstab、grub.cfg 全 UUID 化，`grub2-mkconfig -o /boot/efi/EFI/redhat/grub.cfg` 重新生成
3. 按 §5 重建 initramfs
4. 按 §4.4 做双引导
5. 装 cloud-init 23.2.2 + qemu-guest-agent + 按云的 agent
6. 按 §6 改系统配置
7. 导出：`qemu-img convert -O qcow2`，分别上传 OSS / OBS / COS 导入

## 8. 本地验证矩阵（导入前必跑）

| 组合 | qemu 关键参数 | 对应场景 |
|---|---|---|
| virtio-blk + Legacy BIOS | `-drive if=virtio` + 默认 SeaBIOS | 阿里老规格 Legacy |
| virtio-blk + UEFI | `-drive if=virtio` + `-bios /usr/share/OVMF/OVMF.fd` | 新规格 UEFI + virtio |
| virtio-scsi + UEFI | `-device virtio-scsi-pci,id=scsi0 -drive if=none,id=d0 -device scsi-hd,drive=d0,bus=scsi0.0` + OVMF | 华为云 UEFI（强制 scsi） |
| NVMe + UEFI | `-drive if=none,id=d0 -device nvme,drive=d0` + OVMF | 阿里 g7se/g8i NVMe 云盘 |

每次确认三项：能引导到登录、DHCP 拿到地址、cloud-init 正常执行。全过再上传导入。

## 9. 来源（2026-10-16 核实）

- 阿里云《镜像规范（Linux）》 https://help.aliyun.com/zh/ecs/user-guide/cloud-marketplace-mirror-specification （2026-05-20 更新）
- 阿里云《NVMe 使用限制、相关操作及设备名称》 https://help.aliyun.com/zh/ecs/user-guide/nvme-disks/ （2026-06-07 更新）
- 阿里云《如何为已有自定义镜像安装 NVMe 驱动》 https://help.aliyun.com/zh/ecs/user-guide/adapt-linux-custom-images-to-nvme-based-system-disks （2026-08-31 更新）
- 阿里云《Linux 镜像和 Windows 镜像导入流程》 https://help.aliyun.com/zh/ecs/user-guide/import-an-image
- 腾讯云《制作 Linux 镜像》 https://cloud.tencent.com/document/product/213/17814 （2025-09-02 更新）
- 腾讯云《启动模式 Legacy BIOS 和 UEFI 最佳实践》 https://cloud.tencent.com/document/product/213/102522 （2025-02-14 更新）
- 华为云《准备镜像文件（Linux）》 https://support.huaweicloud.com/usermanual-ims/zh-cn_topic_0030713198.html
- 华为云Stack 8.2.1《计算资源管理》（virtio/scsi、UEFI 必须 scsi） https://support.huawei.com/enterprise/zh/doc/EDOC1100296027/4b6b88e3

> 注：各厂商文档持续更新，落地前以当日文档为准；本文结论基于上述版本。

## 相关

- [[concepts/CPU 虚拟化与IO穿透]] — KVM / VT-x / IOMMU 基础
- [[concepts/存储栈与io_uring]] — Linux 块设备栈
