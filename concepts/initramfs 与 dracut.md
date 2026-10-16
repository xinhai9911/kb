---
title: initramfs 与 dracut
category: concepts
tags: [linux, boot, initramfs, dracut, cpio, virtio, 引导, active]
created: 2026-10-16
updated: 2026-10-16
summary: >-
    initramfs 的本质（cpio 归档展开到 rootfs，解决"挂根需要驱动、驱动在根上"的悖论）、
    dracut 的构建输入与配置体系（dracut.conf.d、add_drivers、hostonly 陷阱、压缩格式）、
    内部结构（early_cpio 微码段 + 压缩主段、/init、模块树）、
    内核命令行交互（root=、rd.break、rd.driver.pre、rd.lvm）、
    驱动进入 initramfs 的三条途径、常见故障（initqueue timeout / VFS unable to mount root fs）
    与手工实验（摘模块复现 panic）。前置 Linux 启动链；应用见 KVM 公有云 镜像 适配 §5。
base_confidence: 0.88
lifecycle: reviewed
---

# initramfs 与 dracut

> 前置：[[concepts/Linux 启动链 与 引导]]（引导链全景）。
> 应用：[[concepts/KVM 公有云 镜像 适配]] §5（驱动清单）、[[entities/公有云镜像 制作 与 导入 实战]] §2.1（故障对照）。

## 1. 为什么需要 initramfs：一个悖论

```
要挂真正的根文件系统（/）
   → 需要块设备驱动（virtio_blk / nvme / 存储控制器）
   → 但驱动模块文件存放在 /lib/modules/...，而 / 还没挂上
```

解法：内核先挂一个**极小的临时根**（rootfs），把必要驱动和工具塞进去，由它去挂真根。这个"临时根的内容包"就是 **initramfs**。

> 历史上还有过 initrd（一个 loop 挂载的 ext2 镜像，需要驱动才能读 → 自举问题更严重）。
> initramfs 是 **cpio 归档**，内核直接展开到 tmpfs，不需要任何块设备驱动 —— 这也是它取代 initrd 的关键原因。

## 2. 它到底是什么

| 事实 | 说明 |
|---|---|
| 文件格式 | **cpio 归档**（`newc` 格式），通常整体 gzip/xz/zstd 压缩 |
| 展开位置 | 内核内的 `rootfs`（tmpfs 实例），不占持久存储 |
| 入口 | 归档内的 `/init`（RHEL8 由 dracut 生成） |
| 不是 | 不是文件系统镜像、不能用 `mount -o loop` 直接挂（要 cpio 解开） |
| 典型大小 | 20 ~ 60 MiB（取决于是否 hostonly 与包含的固件） |

**RHEL8/9 的真实布局（重要）**：dracut 生成的 initramfs 常常是**两段拼接**：

```
[ 未压缩 cpio：early_cpio 微码段 ] + [ 压缩 cpio：主段（模块/脚本/工具） ]
```

单段解析器在微码段的 `TRAILER!!!` 处就停了，会误判"没有驱动"——这正是 `projects/kvm-image-check` 里那个多段解析器要处理的坑。

## 3. dracut 怎么生成

### 3.1 输入与流程

```
内核版本 + /lib/modules/<ver>/modules.dep
        + /etc/dracut.conf、/etc/dracut.conf.d/*.conf
        + 命令行参数（--add-drivers / --force / --hostonly…）
        ↓ dracut 解析模块依赖（modprobe --show-depends 思路）
        ↓ 收集模块、固件、工具（/usr/bin、systemd 早期单元）
        ↓ 生成 /init 与 dracut 脚本
        ↓ 打包成 cpio → 按 conf 压缩 → 落到 /boot/initramfs-<ver>.img
```

### 3.2 配置体系

| 位置 | 作用 |
|---|---|
| `/etc/dracut.conf` | 主配置（较少直接改） |
| `/etc/dracut.conf.d/*.conf` | **推荐落点**，如 `virtio.conf` |
| `add_drivers+=" virtio_blk virtio_scsi nvme"` | 追加驱动（不动依赖解析结果） |
| `force_drivers+=" ..."` | 强制包含（即使依赖解析认为不需要） |
| `hostonly=yes/no` | **关键开关**，见下 |

### 3.3 hostonly 陷阱（云镜像必须知道）

| 模式 | 行为 | 风险 |
|---|---|---|
| `hostonly=yes`（发行版常见默认） | 只收**当前机器**实际用到的模块 | 把这台机器的 initramfs 搬到存储协议不同的云上 → 找不到根盘 |
| `hostonly=no`（generic） | 收全量候选模块 | 体积大，但**跨硬件/跨云更稳** |

> 云镜像的做法：显式 `dracut -f --add-drivers "virtio_blk virtio_scsi nvme ..."`，
> 并落盘 `/etc/dracut.conf.d/virtio.conf` 防止内核升级重建时丢失。

### 3.4 何时会自动重建

- 内核包安装/升级时（`dracut` 由内核 postinstall 触发）
- 某些驱动包（如 `kmod-*`）安装时
- 手动：`dracut -f [选项] /boot/initramfs-$(uname -r).img $(uname -r)`

> 所以**手工 dracut 的成果会在内核升级后消失**——固化配置是必须的，不是可选项。

## 4. 内部结构与查看方法

```bash
# 列内容（dracut 提供）
lsinitrd /boot/initramfs-$(uname -r).img | head -50
lsinitrd -m /boot/initramfs-$(uname -r).img      # 只看模块列表
lsinitrd -f <文件名> /boot/initramfs-*.img       # 提取单个文件

# 手工解析（无 lsinitrd 时）：cpio + 解压
gzip -dc initramfs.img | cpio -t | head          # 需要 cpio 包
python3 -c '...'                                  # 或自写 cpio newc 解析（见 kvm-image-check）

# 内含驱动的验证（镜像适配的必查项）
lsinitrd /boot/initramfs-$(uname -r).img | grep -E 'virtio|nvme|xfs|dm_mod'
```

典型目录结构（概念性）：

```
/                       根（展开后的 rootfs）
├── init                dracut 主脚本（内核执行的入口）
├── usr/lib/modules/<ver>/kernel/...   需要的驱动模块
├── usr/lib/udev/、usr/bin/            早期可用工具
├── etc/cmdline.d/、etc/conf.d/        dracut 运行期配置
└── sysroot/                           真根将挂到这里
```

## 5. 驱动进入 initramfs 的三条途径

| 途径 | 说明 | 镜像适配相关性 |
|---|---|---|
| 内核**内建**（`=y`） | 不依赖模块，天然可用 | 最稳；检查 `/boot/config-<ver>` 里 `CONFIG_VIRTIO_BLK=y` |
| 被 dracut **自动收集** | 依赖解析认为挂根需要它 | hostonly 下可能漏 |
| **显式 `add_drivers`** | 手动兜底 | 云镜像的标准做法 |

云镜像需要显式兜底的清单（对应 [[concepts/KVM 公有云 镜像 适配]] §5）：
`virtio_blk` / `virtio_scsi`+`scsi_mod` / `nvme`+`nvme_core` / `xfs` / `dm_mod`（+ 需要时的 `virtio_net`）。

## 6. 与内核命令行的交互（救急必备）

| 参数 | 作用 |
|---|---|
| `root=UUID=...` | 真根定位（必须 UUID，见磁盘页） |
| `rd.break` | 在 initramfs 阶段停住，给 shell 用于救急 |
| `rd.debug` | 打开 initramfs 调试日志（输出非常啰嗦，排障时用） |
| `rd.udev.log_priority=debug` | 打印 udev 设备事件，看设备是否出现 |
| `rd.driver.pre=virtio_blk` | 提前加载指定驱动 |
| `rd.lvm.lv=klas/root` | 指定 LVM 逻辑卷作为根 |
| `rd.shell` | 失败时进 shell（而非无限等待） |
| `console=ttyS0,115200n8` | 让云端串口能看到这些日志 |

用法：GRUB 菜单按 `e` 追加 → `Ctrl-X` 启动（临时生效）。

## 7. 常见故障与定位

| 现象 | 根因 | 定位手段 |
|---|---|---|
| `dracut-initqueue timeout` | initramfs 里没有对应存储驱动，或 `root=` 指向不存在的设备 | 加 `rd.shell` 进 shell：`ls /dev` 看有没有 `vda`/`nvme0n1`；`blkid` 看 UUID |
| `VFS: Unable to mount root fs on unknown-block(0,0)` | 同上（设备未出现） | 同上 |
| 设备出现但仍是 emergency | UUID 错 / 文件系统驱动（xfs）没打进去 | `lsinitrd | grep -E 'vda|xfs'` |
| 换机器就起不来 | hostonly 模式 + 硬件不同 | 改 `hostonly=no` 或显式 add_drivers |
| 内核升级后又起不来 | add_drivers 没固化到 dracut.conf.d | 落盘配置再重建 |
| 云上串口看不到日志 | 缺 `console=ttyS0` | 加到 GRUB_CMDLINE_LINUX |

## 8. 手工实验（在可丢弃的 VM 里做）

```bash
# ① 看当前 initramfs 里有没有三种挂载形态的驱动
lsinitrd /boot/initramfs-$(uname -r).img | grep -E 'virtio_blk|virtio_scsi|nvme'

# ② 造一个"缺驱动"的 initramfs 复现 panic（先快照！）
cp /boot/initramfs-$(uname -r).img /tmp/initramfs.bak
dracut -f --omit-drivers "virtio_blk virtio_scsi nvme" /boot/initramfs-$(uname -r).img $(uname -r)
# 重启 → 预期 dracut-initqueue timeout 或 VFS panic
# 用 GRUB e + rd.break 或救援盘恢复：
#   dracut -f /boot/initramfs-$(uname -r).img $(uname -r)

# ③ 固化并验证
printf 'add_drivers+=" virtio_blk virtio_scsi virtio_net virtio_console nvme"\n' \
  > /etc/dracut.conf.d/virtio.conf
dracut -f /boot/initramfs-$(uname -r).img $(uname -r)
lsinitrd /boot/initramfs-$(uname -r).img | grep -cE 'virtio_blk|virtio_scsi|nvme'

# ④ 用自检脚本离线核对（不启动镜像）
bash projects/kvm-image-check/check-image.sh --root /mnt/imgroot
```

## 9. 与镜像适配的关系（一句话总结）

**镜像能不能在某个云上起来，取决于 initramfs 里有没有那个云用的存储驱动。**
云上三种挂载形态（virtio-blk / virtio-scsi / NVMe 协议云盘）对应三种驱动，
少一个就是一类规格起不来 —— 这就是驱动清单必须"全覆盖 + 固化"的原因。

## 10. 自测

1. initramfs 解决的是什么悖论？为什么它不需要块设备驱动就能被内核展开？
2. `hostonly=yes` 的 initramfs 为什么搬到云上容易起不来？
3. RHEL8 的 initramfs 为什么可能是"未压缩段 + 压缩段"拼接？解析时要注意什么？
4. 手工 `dracut -f --add-drivers ...` 之后，为什么还必须写 `/etc/dracut.conf.d/`？
5. `rd.break` 与 `rd.shell` 的区别？各自适合什么场景？

## 来源

- dracut 手册与命令行说明（上游 dracut 项目 / man dracut、man dracut.cmdline）
- Linux 内核文档 ramfs-rootfs-initramfs https://www.kernel.org/doc/html/latest/filesystems/ramfs-rootfs-initramfs.html
- Red Hat Enterprise Linux 文档（管理 initramfs / dracut）

> 断言分级：cpio 归档、rootfs 展开、initqueue 机制、hostonly 语义为通用事实；
> 具体发行版的默认压缩格式与 early_cpio 拼接口径随版本变化，以本机 `lsinitrd` 实测为准。
