---
title: kvm-image-check（公有云镜像自检脚本）
category: projects
tags: [project, kvm, image, cloud-init, shell, active]
created: 2026-10-16
updated: 2026-10-16
summary: >-
    公有云镜像发布前自检脚本：检查 fstab 设备寻址与 nofail、grub root=UUID、ESP removable fallback
    （按架构判 X64/AA64）、initramfs 三种挂载形态驱动、内核能力（CONFIG_FW_CFG_SYSFS / NVMe / virtio-blk）、
    cloud-init 安装与状态、机器身份残留（machine-id / SSH 主机密钥）、网络 MAC 绑定、growpart 与磁盘布局
    （LVM/swap/根分区位置）。支持在线（镜像内）与离线（--root 解包镜像树）两种模式，
    输出 PASS/WARN/FAIL/SKIP 与退出码，可做产线出图门禁；附 fixture 测试套件（51 项断言）。
    原理见 [[concepts/KVM 公有云 镜像 适配]]，操作上下文见 [[entities/公有云镜像 制作 与 导入 实战]]。
base_confidence: 0.9
lifecycle: reviewed
---

# kvm-image-check（公有云镜像自检脚本）

## 目标

镜像导入云端后"起不来 / 密码注入失效 / 批量实例身份撞车"这几类事故，根因都在镜像内部，且都在**导入前**可查。本脚本把所有可机检的硬性要求做成一次跑完的体检，用于产线出图门禁或发布前自查。

- **语言 / 依赖**：Bash，仅用系统自带工具（`lsblk` / `findmnt` / `lsinitrd` / `awk` / `grep`），无第三方依赖
- **目标系统**：RHEL8 系（CentOS/Rocky/Alma/麒麟/UOS 等同源发行版可用）
- **两种模式**：在线（镜像内直接跑）／离线（`--root DIR` 检查解包或挂载的镜像树）
- **退出码**：`0` 通过；`1` 存在 FAIL；`--strict` 下 `2` 存在 WARN
- **输出四级**：`PASS` / `WARN` / `FAIL` / `SKIP`（环境不适用时 SKIP，不误判为失败）

## 使用方式

### 方式一：镜像内部直接跑（最常用）

```bash
bash check-image.sh
bash check-image.sh --strict     # CI 门禁推荐
```

### 方式二：chroot 进镜像跑

```bash
mount /dev/nbd0p3 /mnt            # 或挂载已解包的系统盘
mount --bind /dev /mnt/dev; mount --bind /proc /mnt/proc; mount --bind /sys /mnt/sys
chroot /mnt /bin/bash
bash /path/to/check-image.sh
```

### 方式三：离线镜像（qcow2）不启动检查

```bash
# 用 libguestfs 把脚本拷进去执行，再取回输出
virt-copy-in -a appliance.qcow2 check-image.sh /root/
virt-customize -a appliance.qcow2 --run-command 'bash /root/check-image.sh' --no-selinux-relabel
```

### 方式四：离线模式（`--root`，直接查解包后的镜像树）

把镜像根目录解包（或挂载）到某目录后，不必启动、不必 chroot：

```bash
# 挂载出来（在线机器上）
mount /dev/nbd0p3 /mnt/imgroot
bash check-image.sh --root /mnt/imgroot
bash check-image.sh --strict --root /mnt/imgroot     # 门禁推荐

# 或 libguestfs 导出目录树后检查
virt-copy-out -a appliance.qcow2 /etc /mnt/imgroot/etc
```

离线模式下**只做文件级检查**；依赖运行环境的项（内核参数来自 `/proc/cmdline`、LVM/swap 分区、
根分区位置、分区表、systemd 服务）输出 `SKIP`，**不会误判为 FAIL**。

### 测试

```bash
bash tests/run-tests.sh
```

构造 BAD / GOOD / WARN-only 三个受控镜像树，断言每项检查的真阳性与真阴性（含伪文件系统不误报）、
以及退出码 `0 / 1 / 2`，共 51 项断言，不依赖真实镜像或 Linux 容器。

> 离线方式下 `/proc/cmdline`、`findmnt`、`lsblk` 反映的是**宿主**而非镜像，相关检查项（内核参数、根分区位置）会失真——这类项请在镜像内跑。
> 生产建议：**在 `virt-customize` 收尾阶段于镜像内执行本脚本**，把输出落进构建日志。

## 检查项

| # | 分组 | 检查项 | 判级 |
|---|---|---|---|
| 1 | fstab | 无 `/dev/` 硬编码设备路径 | FAIL |
| 2 | fstab | 根分区使用 UUID | FAIL |
| 3 | fstab | 非根挂载点带 `nofail` | WARN |
| 4 | fstab | 无 swap 条目 | WARN |
| 5 | 引导 | ESP removable fallback 存在（x86→`BOOTX64.EFI` / Arm→`BOOTAA64.EFI`） | FAIL |
| 6 | 引导 | 内核参数 `root=` 为 `UUID=` | FAIL |
| 7 | 引导 | 内核参数含 `net.ifnames=0` | WARN |
| 8 | 引导 | 内核参数含 `console=ttyS0` | WARN |
| 9 | initramfs | 含 `virtio_blk` / `virtio_scsi` / `nvme`（逐个内核核对） | FAIL |
| 10 | initramfs | 存在 `/etc/dracut.conf.d/virtio.conf` 持久化配置 | WARN |
| 11 | 内核 | `CONFIG_FW_CFG_SYSFS=y`（云上改密码依赖） | FAIL |
| 12 | 内核 | `CONFIG_BLK_DEV_NVME` 存在（阿里新规格 NVMe 云盘依赖） | FAIL |
| 13 | 内核 | `CONFIG_VIRTIO_BLK` 存在 | FAIL |
| 14 | 云初始化 | cloud-init 已安装 | FAIL |
| 15 | 云初始化 | cloud-init 状态已清理（`/var/lib/cloud/instances` 为空） | WARN |
| 16 | 云初始化 | qemu-guest-agent 已安装 | WARN |
| 17 | 云初始化 | 检测到云平台 agent 服务 | WARN |
| 18 | 机器身份 | `/etc/machine-id` 已清空 | FAIL |
| 19 | 机器身份 | SSH 主机密钥已删除 | WARN |
| 20 | 机器身份 | 无 `authorized_keys` 残留 | WARN |
| 21 | 机器身份 | 无 `bash_history` 残留 | WARN |
| 22 | 网络 | NM keyfile 无写死 `mac-address=` | FAIL |
| 23 | 网络 | 无 `70-persistent-net.rules` | FAIL |
| 24 | 网络 | ifcfg 无 `HWADDR` | WARN |
| 25 | 磁盘 | 已装 `growpart` | WARN |
| 26 | 磁盘 | 无 LVM 卷（阿里云规范禁止） | WARN |
| 27 | 磁盘 | 无 swap 分区 | WARN |
| 28 | 磁盘 | 根分区位于最后一个分区（扩容链路前提） | WARN |
| 29 | 磁盘 | 分区表为 GPT（UEFI 必要） | WARN |

判级说明：**FAIL** 表示必然导致云端故障，必须修；**WARN** 表示规范符合性或隐患，按目标云与场景取舍。`--strict` 把 WARN 也当门禁失败。

> **离线模式（`--root`）**：依赖真实块设备或运行环境的检查项（#26 LVM、#27 swap 分区、#28 根分区位置、
> #29 分区表；以及取不到内核参数时的 #7 / #8）输出 `SKIP` 而非 FAIL。
> **已自测覆盖**：§1 fstab、§2 引导与内核参数、§4 内核能力、§5 cloud-init 与 agent、§6 机器身份、
> §7 网络痕迹、§8 growpart 共 8 组检查有 fixture 断言；§3 initramfs（需 `lsinitrd`）与
> §8 块设备类检查需在 Linux 主机上验证。

## CI / 产线集成

```bash
# 出图流水线里做门禁（任一 FAIL 即中断）
virt-customize -a appliance.qcow2 --run-command 'bash /root/check-image.sh --strict' \
  || { echo "镜像自检未通过，终止发布"; exit 1; }
```

## 已知限制

- 只覆盖**可机检**项；"能否真正引导"仍必须走 qemu 实测与云上实测（见 [[concepts/KVM 公有云 镜像 适配]] §12 验收矩阵）
- 离线模式不做块设备与运行环境检查（见上表说明），这类项需在镜像内或 Linux 主机上跑
- `initramfs` 驱动检查依赖 `lsinitrd`（dracut 包）；缺失时 SKIP，需在 Linux 主机上补跑
- 云平台 agent 检测按服务名关键字匹配（`aliyun` / `cloudmonitor` / `CloudResetPwd` / `OpsAgent`），
  不同镜像包名可能不一致，命中失败按 WARN 处理，需人工确认
- 分区表与分区号解析依赖 `lsblk` / `parted` 输出格式，跨发行版差异需实测
- fixture 测试覆盖文件级检测逻辑；块设备类检查的逻辑尚未有自动化断言（需 Linux 环境构造 loop 设备）

## 相关文档

- [[concepts/KVM 公有云 镜像 适配]] — 原理、三家规范、扩容链路、验收矩阵
- [[entities/公有云镜像 制作 与 导入 实战]] — 清理清单、排障手册、导入操作
