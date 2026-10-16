---
title: Linux 启动链 与 引导
category: concepts
tags: [linux, boot, uefi, bios, grub, gpt, esp, shim, 引导, active]
created: 2026-10-16
updated: 2026-10-16
summary: >-
    从固件到 PID 1 的完整引导链：Legacy BIOS 与 UEFI 的本质差异、MBR/GPT 与 ESP/bios_grub 分区类型、
    shim 签名链与 GRUB2 两种模式的安装位置、RHEL8 的"两个 grub.cfg"stub 机制、内核与 initramfs 的交接、
    systemd 接管；以及公有云上"引导项不跟随"（NVRAM 为空 → 只能走 ESP 默认 fallback 路径）的机理、
    UEFI-Preferred 的由来、引导阶段故障对照与救援手段（GRUB e 编辑 / rd.break / 挂盘修复）。
    前置 PCIe 子系统与 CPU 虚拟化；应用见 KVM 公有云 镜像 适配。
base_confidence: 0.88
lifecycle: reviewed
---

# Linux 启动链 与 引导

> 前置：[[concepts/PCIe 子系统]]（设备枚举）、[[concepts/CPU 虚拟化与IO穿透]]（虚拟化基础）。
> 下一环：[[concepts/initramfs 与 dracut]]；挂载细节：[[concepts/磁盘分区 文件系统 与 挂载管理]]。
> 应用：[[concepts/KVM 公有云 镜像 适配]] §4、[[entities/公有云镜像 制作 与 导入 实战]] §2。

## 0. 全景：一台机器怎么变成 PID 1

```
上电
 └─ 固件（UEFI 或 Legacy BIOS）
     └─ 读分区表（GPT / MBR），找到引导位置
         └─ 加载引导加载器 GRUB2
             ├─ UEFI：shimx64.efi → grubx64.efi（ESP 内的 .efi 文件）
             └─ Legacy：MBR 前 446 字节的 boot.img
             └─ 读 grub.cfg → 加载 kernel + initramfs 到内存，传 root= 等参数
                 └─ 内核挂 rootfs(tmpfs)，展开 initramfs(cpio)，执行其 /init
                     └─ dracut initqueue 等设备就绪 → 按 root=UUID 找真根 → switch_root
                         └─ 真根上的 /sbin/init = systemd（PID 1）
                             └─ fstab → mount 单元；cloud-init 做一次性初始化
```

**每一环都可能成为"镜像起不来"的断点**，公有云适配踩的坑全在这条链上。记住这个顺序，排障时先定位"断在哪一环"，再谈原因。

## 1. 固件层：Legacy BIOS 与 UEFI

### 1.1 本质差异

| 维度 | Legacy BIOS | UEFI |
|---|---|---|
| 引导代码位置 | 磁盘 MBR（前 446 字节）+ 分区间空隙 | **ESP 分区内的 .efi 文件** |
| 固件是否认识文件系统 | 不认识（按扇区读） | 认识 FAT（ESP 必须 FAT32） |
| 引导项存放 | 无，固定读 MBR | **NVRAM 变量**（`efibootmgr` 读写） |
| 分区表要求 | MBR | GPT（UEFI 规范要求） |
| 安全启动 | 无 | Secure Boot（签名链校验） |
| 参数传递 | 内存固定位置 | Boot Services（LoadFile / GetMemoryMap…） |

> **一句话记住**：Legacy 引导"写死在磁盘上"，UEFI 引导"登记在固件变量里"。§5.2 的云端行为完全由这句话推出。

### 1.2 UEFI 启动时固件做的三件事

1. 枚举块设备，识别 **FAT 分区且分区类型为 ESP** 的那些
2. 按 NVRAM 里的 `BootOrder` / `Boot####` 找引导项；**NVRAM 为空时**退化为扫描**固定默认路径**：
   - x86_64：`\EFI\BOOT\BOOTX64.EFI`
   - aarch64：`\EFI\BOOT\BOOTAA64.EFI`
3. （若开 Secure Boot）校验签名后把控制权交给该 .efi

## 2. 分区层：MBR / GPT 与引导分区

### 2.1 分区表对比

| 维度 | MBR（msdos） | GPT |
|---|---|---|
| 容量上限 | 2 TiB（32 位 LBA） | 极大（64 位 LBA） |
| 分区数 | 4 主分区（扩展分区绕过） | 默认 128 |
| 冗余 | 无 | 主表 + 备份表 + CRC32 |
| 分区类型标识 | 1 字节 type code | 16 字节 GUID |
| 能否 UEFI 引导 | 不能 | 能 |

### 2.2 引导相关分区类型（背下来）

| 用途 | GPT 类型 GUID | sgdisk / parted 写法 | 建议大小 |
|---|---|---|---|
| ESP（EFI 系统分区） | `C12A7328-F81F-11D2-BA4B-00A0C93EC93B` | `ef00` / `esp` | 200 ~ 600 MiB，FAT32 |
| BIOS boot（GPT + Legacy 时 GRUB 的嵌入位） | `21686148-6449-6E6F-744E-656564454649` | `ef02` / `bios_grub` | 1 MiB |
| Linux 文件系统 | —（按文件系统标识） | `8300` | — |

- **只做 UEFI**：有 ESP 就够
- **做双引导（UEFI + Legacy）**：ESP 与 EF02 都要有（见 [[concepts/KVM 公有云 镜像 适配]] §4.4）
- 实测查看：`lsblk -o NAME,SIZE,FSTYPE,PARTTYPENAME,PARTTYPE`

## 3. 引导加载器层：shim 与 GRUB2

### 3.1 UEFI 下的签名链

```
固件 → \EFI\redhat\shimx64.efi → \EFI\redhat\grubx64.efi → /boot/grub2/grub.cfg
```

- **shim**：被微软签名（UEFI CA）的极小引导器，是 Secure Boot 能成立的关键；否则要自己签 GRUB 与内核。RHEL/CentOS 系的标准做法
- **grubx64.efi**：真正的 GRUB，由 shim 校验后加载

### 3.2 RHEL8 的"两个 grub.cfg"（高频困惑点）

| 位置 | 角色 | 内容 |
|---|---|---|
| `/boot/efi/EFI/redhat/grub.cfg` | **stub** | 仅几行：`search --fs-uuid <boot分区UUID> --set=root` + `set prefix=(...)/grub2`，指向真配置 |
| `/boot/grub2/grub.cfg` | **真配置** | menuentry、`linux`/`linux16` 行、`root=UUID=…`、`initrd` 行 |

**自己验证谁是真配置，别靠记忆**：

```bash
head -5 /boot/efi/EFI/redhat/grub.cfg     # 只有 search/set prefix → 是 stub
grep -c menuentry /boot/grub2/grub.cfg    # 真配置在这里
```

> 改引导项的正确姿势：改 `/etc/default/grub` 或 `/etc/grub.d/*` → 跑 `grub2-mkconfig`。
> 手改 `/boot/grub2/grub.cfg` 会在下次 mkconfig 时被覆盖。
> 注：不同发行版/代际对 mkconfig 输出路径的约定不同（RHEL 文档示例与 ESP stub 机制并存），以本机实测为准。
> Legacy 模式只有 `/boot/grub2/grub.cfg` 一份，没有 ESP stub。

### 3.3 安装与生成命令对照

| 目的 | UEFI | Legacy |
|---|---|---|
| 装引导代码 | `grub2-install --target=x86_64-efi --efi-directory=/boot/efi --bootloader-id=redhat` | `grub2-install --target=i386-pc /dev/vda` |
| 生成配置 | `grub2-mkconfig -o /boot/grub2/grub.cfg`（并按发行版约定同步 ESP 侧） | `grub2-mkconfig -o /boot/grub2/grub.cfg` |
| 查看登记项 | `efibootmgr -v` | 无此机制 |
| Arm 平台 | `--target=arm64-efi`，fallback `BOOTAA64.EFI` | 不适用（Arm 无 Legacy） |

### 3.4 内核参数的三个来源

1. `/etc/default/grub` 的 `GRUB_CMDLINE_LINUX`（永久，需重新 mkconfig）
2. GRUB 菜单按 `e` 临时编辑（救急，不落盘）
3. 查看生效值：`cat /proc/cmdline`

## 4. 内核与 initramfs 的交接（最容易出事的一环）

细节见 [[concepts/initramfs 与 dracut]]，此处只记链路：

1. GRUB 把 kernel 与 initramfs 一起载入内存，并把 `root=` 等参数传给内核
2. 内核挂载 **rootfs（tmpfs 实例）**，把 initramfs（**cpio 归档**）展开进去
3. 内核执行其中的 `/init`（dracut 生成），进入用户空间准备阶段
4. dracut 的 initqueue 等设备就绪（**此处需要 virtio/NVMe/存储驱动**），按 `root=UUID=` 找真根
5. `switch_root` 切根 → 执行真根上的 `/sbin/init`

> **按断点分类故障**：
> 第 4 步之前失败 → `VFS: Unable to mount root fs` / `dracut-initqueue timeout`（initramfs 无对应驱动，或 UUID 不存在）
> 第 5 步之后失败 → systemd 阶段（fstab 挂载失败、单元依赖等）

## 5. 云上差异：为什么"本地能起、上云起不来"

### 5.1 根设备名会变

本地 NVMe 盘 → 云上 virtio 盘，`/dev/nvme0n1p3` 变成 `/dev/vda3`。
→ **fstab 与 grub 的 `root=` 必须 UUID 化**（原理见 [[concepts/磁盘分区 文件系统 与 挂载管理]]）

### 5.2 引导项不跟随（NVRAM 为空）

本地 `efibootmgr` 写的 `Boot####` 是**这台机器固件的变量**。云上实例是全新固件实例，NVRAM 为空 → 固件只能走 §1.2 的默认路径：

```bash
ls /boot/efi/EFI/BOOT/BOOTX64.EFI          # 存在否，决定云上能否引导
# 修复：把厂商目录里的 shim 复制成默认路径
cp /boot/efi/EFI/redhat/shimx64.efi /boot/efi/EFI/BOOT/BOOTX64.EFI
```

**这就是阿里云 "UEFI-Preferred" 能通吃的底层原因**：镜像同时具备 BIOS + UEFI 两套引导能力，导入时由平台按规格选择（见 [[concepts/KVM 公有云 镜像 适配]] §4.1）。

### 5.3 Secure Boot

云端一般不开；若开，链上每一环都必须签名（shim/grub 有微软签名，自编译内核没有 → 校验失败）。

## 6. 引导阶段排障对照表

| 现象 | 断点 | 根因 | 处置 |
|---|---|---|---|
| 掉进 UEFI shell / no bootable device | 固件 | ESP 无 fallback，且 NVRAM 空 | 补 `\EFI\BOOT\BOOTX64.EFI` |
| 直接进 `grub>` 提示符（无菜单） | GRUB | 找不到 grub.cfg 或语法错 | `ls (hd0,gpt1)/boot/grub2/` 手工定位；进系统后重跑 mkconfig |
| `VFS: Unable to mount root fs` | 内核/initramfs | initramfs 无驱动，或 `root=` 设备不存在 | 重建 initramfs；核对 `blkid` 与 `root=` |
| `dracut-initqueue timeout` | initramfs | 同上 | 同上 |
| `You are in emergency mode` | systemd | fstab 有挂不上的项 | 加 `nofail` 或修正条目 |
| 云控制台看不到早期日志 | — | 内核参数缺 `console=ttyS0` | 加上后重新 mkconfig |

### 救援手段（侵入性由低到高）

1. **GRUB 菜单按 `e`**：临时改 `root=` / 追加参数，`Ctrl-X` 启动
2. **`rd.break`**：进 initramfs shell 救急
   ```bash
   mount -o remount,rw /sysroot
   chroot /sysroot
   passwd root            # 或修 /etc/fstab、grub
   touch /.autorelabel    # SELinux enforcing 时必须
   exit; exit
   ```
3. **挂盘修复**：卸系统盘挂到正常实例，或本地 `qemu-nbd` 挂载改（见 [[entities/镜像格式 与 离线处理工具链]]）
4. **云控制台**：VNC 图形终端 / 串口（需内核参数带 `console=ttyS0`）

## 7. 动手清单（建议在可丢弃的 VM 里做，破坏性操作前先快照）

```bash
# ① 判断当前启动模式
ls /sys/firmware/efi >/dev/null 2>&1 && echo UEFI || echo Legacy

# ② 看引导项与分区类型
efibootmgr -v
lsblk -o NAME,SIZE,FSTYPE,PARTTYPENAME,PARTTYPE

# ③ 分辨 stub 与真配置
head -5 /boot/efi/EFI/redhat/grub.cfg; grep -c menuentry /boot/grub2/grub.cfg

# ④ 复现"云上起不来"并修复（理解 > 记忆）—— 完整实验步骤见 §8
mv /boot/efi/EFI/BOOT/BOOTX64.EFI{,.bak}     # NVRAM 空 + 无 fallback = 引导失败
# 从救援盘/UEFI shell 进系统后复制回来

# ⑤ 看内核参数与 initramfs 交接
cat /proc/cmdline
lsinitrd /boot/initramfs-$(uname -r).img | head
```

## 8. 破坏实验：证明"引导项不跟随"（L1 实验单）

**目标**：把两个常被混为一谈的机制**分离证明** —— 固件 NVRAM 里的引导项（本地有、云上无）
与 ESP 里的兜底路径（云上唯一依靠）。

**安全前置**：用可丢弃的 VM；先打快照；不要在产线机上做。

### 步骤 0 · 基线取证

```bash
ls /sys/firmware/efi >/dev/null 2>&1 && echo "UEFI ✅" || echo "Legacy ❌ 本实验不适用"
efibootmgr -v                                  # 记下 BootCurrent（例：0003）
ls -l /boot/efi/EFI/BOOT/ /boot/efi/EFI/redhat/
# 备份：cp -a /boot/efi/EFI/BOOT/. /root/l1-backup/
```

### 步骤 1 · 只删兜底文件（不删 NVRAM）→ 预期**照常启动**

```bash
rm -f /boot/efi/EFI/BOOT/BOOTX64.EFI && sync && reboot
```

结果：正常启动。因为固件优先走 NVRAM 里登记的 `Boot####`（指向 `\EFI\redhat\shimx64.efi`），
**根本没用兜底路径** —— 这就是"本地能起"的真相。

### 步骤 2 · 再删 NVRAM 引导项 → 预期**起不来**（= 云上现场）

```bash
efibootmgr -b 0003 -B          # 用步骤 0 记下的编号
efibootmgr -v                  # 确认 BootOrder 已无此项
sync && reboot
```

结果：掉进 UEFI Shell / `No bootable option or device was found` / 无限重启。
**这就是云上全新实例的处境**：NVRAM 为空，只剩兜底路径，而它已被你删掉。

### 步骤 3 · 救援（三选一）

| 路线 | 做法 |
|---|---|
| **A. UEFI Shell 手工引导** | 重启按 `ESC` 进固件菜单 → UEFI Shell → `map` 找 `FS0:` → `FS0:\EFI\redhat\shimx64.efi` 直接进系统 |
| **B. 宿主机离线修盘（推荐）** | `modprobe nbd max_part=16 && qemu-nbd -c /dev/nbd0 disk.qcow2` → `mount /dev/nbd0p1 /mnt` → `cp -a /mnt/EFI/redhat/shimx64.efi /mnt/EFI/BOOT/BOOTX64.EFI` → 卸载 |
| **C. 救援 ISO** | 挂 Linux 救援盘，`chroot` 进系统修 |

### 步骤 4 · 恢复并验证

```bash
cp -a /boot/efi/EFI/redhat/shimx64.efi /boot/efi/EFI/BOOT/BOOTX64.EFI
efibootmgr -c -d /dev/vda -p 1 -L "Red Hat Enterprise Linux" -l '\EFI\redhat\shimx64.efi'
efibootmgr -v && ls -l /boot/efi/EFI/BOOT/BOOTX64.EFI
reboot        # 应正常进入系统
```

### 实验记录表

| 步骤 | 操作 | 预期 | 实际 | 结论 |
|---|---|---|---|---|
| 1 | 只删 `BOOTX64.EFI` | 仍能启动 | | 固件用 NVRAM，不依赖 fallback |
| 2 | 再删 NVRAM 项 | 启动失败 | | 云上现场 = NVRAM 空 |
| 3 | Shell / 离线修盘 | 能救回 | | 救援路径可用 |
| 4 | 恢复两者 | 正常启动 | | 两套机制都必要 |

### 进阶变体（选做）

| 变体 | 做法 | 收获 |
|---|---|---|
| 用 `-bios OVMF.fd` 单文件起 VM | 不持久化 VARS | **每次重启都等于"云上 NVRAM 空"**，删文件即失败，无需步骤 2 |
| 把 fallback 指向 `grubx64.efi` 而非 shim | `cp grubx64.efi BOOTX64.EFI` | 理解 shim 在 Secure Boot 链中的作用 |
| Arm 镜像 | 检查 `\EFI\BOOT\BOOTAA64.EFI` | 路径随架构变（自检脚本按架构判断的原因） |
| 做双引导再走一遍 | 加 EF02 + `grub2-install --target=i386-pc` | fallback 与 NVRAM 都失效时 Legacy 侧仍可能起来（UEFI-Preferred 由来） |

**一句话结论**（做完请自己写一遍）：＿＿＿＿＿＿＿＿＿＿＿＿

## 9. 自测（能答上即可跳过本页）

1. Legacy 与 UEFI 的引导代码分别放在哪？为什么只有 UEFI 需要 ESP？
2. RHEL8 的 `/boot/efi/EFI/redhat/grub.cfg` 为什么不含 menuentry？
3. 本地 `efibootmgr` 的引导项上云后为什么失效？固件退化成什么行为？
4. 内核是"先有根文件系统还是先有驱动"？这个悖论由谁解决？
5. `You are in emergency mode` 属于启动链的哪一环？

## 10. 来源

- GNU GRUB 手册 https://www.gnu.org/software/grub/manual/grub/
- UEFI 规范（EFI System Partition、Boot Manager，UEFI Forum）https://uefi.org/specifications
- Linux 内核文档 ramfs-rootfs-initramfs https://www.kernel.org/doc/html/latest/filesystems/ramfs-rootfs-initramfs.html
- Red Hat Enterprise Linux 文档（Managing GRUB 2、引导与启动流程）

> 断言分级：GRUB/shim/ESP/分区类型码/UEFI 启动行为为通用事实；具体发行版路径（grub.cfg stub 位置、mkconfig 输出路径）以本机 `rpm -ql grub2-efi-x64` 与发行版文档为准。
