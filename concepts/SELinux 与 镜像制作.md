---
title: SELinux 与 镜像制作
category: concepts
tags: [selinux, security, image, cloud-init, hardening, 安全, active]
created: 2026-10-16
updated: 2026-10-16
summary: >-
    SELinux 在镜像制作与云上首次启动中的实际影响：强制模式（enforcing）下"文件内容对但标签错"仍会被拒、
    离线改镜像（qemu-nbd / virt-customize）导致的标签丢失与其典型故障（改 fstab 后进不去系统、
    cloud-init 写入被拒、服务起不来）、restorecon/autorelabel/semanage 的正确用法与代价、
    加固基线（CIS/等保）与云上密码注入机制的冲突及正确顺序、"关 SELinux 换省事"的代价评估。
    前置 Linux 启动链（autorelabel 与引导的关系）；应用见 公有云镜像 制作 与 导入 实战。
base_confidence: 0.87
lifecycle: reviewed
---

# SELinux 与 镜像制作

> 前置：[[concepts/Linux 启动链 与 引导]]（`/.autorelabel` 与引导阶段）。
> 应用：[[entities/镜像格式 与 离线处理工具链]]（离线改镜像的标签问题）、[[entities/公有云镜像 制作 与 导入 实战]]。

## 1. 为什么镜像制作必须懂 SELinux

SELinux 的判定是**三元组**：`主体标签(域) × 客体标签(类型) × 策略规则`。
所以出现下列组合时：

| 文件内容 | 文件标签 | 结果 |
|---|---|---|
| 正确 | 正确 | ✅ 正常 |
| **正确** | **错误** | ❌ **被拒**（最容易误判为"配置明明是对的"） |
| 错误 | 正确 | ❌ 语法/逻辑报错（常规排错） |

**镜像制作的特殊性**：镜像常被**离线**修改（宿主机挂载、libguestfs、virt-customize），
而这些手段**不写 xattr**（或写出的标签上下文是宿主机的），于是"内容对、标签错"大量出现。

## 2. 典型故障：改完镜像起不来 / 服务起不来

| 现象 | 机理 | 处置 |
|---|---|---|
| 离线改完 `/etc/fstab` 或 `/etc/ssh/sshd_config`，重启后进不去 / 服务失败 | 新写入的文件标签为 `unlabeled_t` / 继承宿主上下文，被策略拒绝 | 离线改完后打标签（§3） |
| `chroot` 进 rescue 改完 root 密码，重启后登录仍失败 | `/etc/shadow` 标签丢失 | `chroot` 后 `touch /.autorelabel` 再重启 |
| cloud-init 写 hostname/密钥失败 | cloud-init 目标文件类型未授权/标签错 | 正确安装 cloud-init 包（自带策略），别手工拷二进制 |
| 自研二进制/bin 放 `/usr/local/sbin` 无法执行 | 未打 `bin_t` 类标签 | `restorecon`；或按策略定义类型 |
| **离线挂载改盘后系统反复 relabel 或耗时极长** | `.autorelabel` 触发全盘打标签 | 一次性动作，接受；或改用 `restorecon` 精确修复 |

**一个常见误判**：`ls -Z` 看起来"都有标签"，但仍是错的——要**对文件**看
`ls -Z /etc/shadow`、`ls -Z /etc/fstab`，并与同目录正常文件对比。

## 3. 正确工具与用法

### 3.1 查看

```bash
getenforce                     # Enforcing / Permissive / Disabled
sestatus
ls -Z /etc/fstab               # 对比同目录正常文件的类型
matchpathcon /etc/fstab        # 按策略查"这个路径应该是什么标签"
ps -eZ | grep cloud-init
ausearch -m avc -ts recent     # 看被拒记录（关键排障手段）
sealert -a /var/log/audit/audit.log
```

### 3.2 修标签

| 手段 | 粒度 | 场景 |
|---|---|---|
| `restorecon -Rv /etc` | 按策略重打（递归） | **首选**，精确、快 |
| `touch /.autorelabel` + 重启 | 全盘重打 | 大量文件丢失标签（离线改盘后） |
| `semanage fcontext -a -t <type> "<regex>"` + `restorecon` | 自定义路径类型 | 自研组件放在非常规路径 |
| `setenforce 0` | 临时 | **仅调试**，重启失效 |

### 3.3 离线改镜像时的落地做法

```bash
# 方式一：virt-customize 自带重打标签（推荐）
virt-customize -a disk.qcow2 \
  --edit '/etc/fstab: s/defaults/nofail,x-systemd.device-timeout=0/' \
  --selinux-relabel

# 方式二：qemu-nbd 手工改完之后
chroot /mnt /bin/bash -c 'touch /.autorelabel'      # 代价：下次启动慢
# 或 chroot 后精确修
chroot /mnt /bin/bash -c 'restorecon -Rv /etc /usr/local'

# 方式三：libguestfs 的对应开关
virt-customize -a disk.qcow2 --run-command 'restorecon -Rv /etc' --selinux-relabel
```

> **产线建议**：所有离线改镜像的操作，**收尾统一加一次重打标签**（`--selinux-relabel` 或 `touch /.autorelabel`），
> 把它当成清理清单里的固定一步，而不是出问题再补。

## 4. 与云上首次启动的交互

| 交互点 | 说明 |
|---|---|
| `.autorelabel` 会**拖慢首次启动** | 大镜像可能几分钟；云平台可能判为"启动超时" → 出图前确保已完成重打（不要在交付镜像里留标记） |
| cloud-init 的写操作受策略约束 | 用发行版官方包安装；自编译/拷贝二进制会导致域转换失败 |
| systemd 服务自定义路径 | 需要 `semanage fcontext` 定义，否则启动失败（表现为 `status=203/EXEC` 或 AVC 拒绝） |
| 云端串口/VNC 里看到 AVC | `ausearch -m avc -ts recent` 定位；别直接关 SELinux |

## 5. 加固基线与云注入的冲突（顺序问题）

等保/CIS 类加固常包含：

- 禁用 root 直接登录、`PasswordAuthentication no`
- 密码复杂度/有效期策略
- 关闭不需要的服务、限制 su

而云上**密码注入依赖密码登录能力**（见 [[concepts/KVM 公有云 镜像 适配]] §9.2）：

```
❌ 错误顺序：先加固（禁密码登录）→ 云上注入密码 → 永久失败，且只能靠 VNC 修
✅ 正确顺序：先确保注入链路可用 → 再加固 → 若要禁密码登录，应先确保密钥注入可用
```

**实践答案**：云镜像的常态是"**SSH 密钥注入 + 禁密码登录**"（既安全又能登录），
把"密码登录"只当作过渡或救急手段；控制台改密码能力（`CONFIG_FW_CFG_SYSFS` + cloud-init）保留但不作为登录主路径。

## 6. "直接关掉 SELinux"值不值：代价清单

| 关掉的代价 | 说明 |
|---|---|
| 失去进程隔离的一道防线 | 对本库场景（安全 appliance）尤其不划算 |
| 部分发行版/合规要求不通过 | 等保测评项常直接检查 SELinux 状态 |
| 掩盖真实配置问题 | 后续开回来会集中爆发（历史遗留标签全错） |
| 迁移成本转嫁 | 客户/交付环境可能强制 enforcing → 现场返工 |

**折中方案**：开发/调试期用 `Permissive`（记录但放行，不阻塞）+ `ausearch` 看完再决定策略；
交付镜像恢复 `Enforcing`。

## 7. 镜像制作的 SELinux 检查清单

```
□ 离线改动的文件是否重打过标签（--selinux-relabel 或 restorecon）
□ 交付镜像里是否残留 /.autorelabel（应清掉，避免首次启动被拖慢/判超时）
□ cloud-init / agent 是否用发行版官方包安装
□ 自研组件路径是否定义了 fcontext 类型
□ getenforce 是否为 Enforcing（按交付要求）
□ 加固脚本是否在"注入能力已具备"之后执行
□ 首次启动后 ausearch -m avc -ts recent 是否干净（云上验收项）
```

## 8. 自测

1. 为什么"配置内容正确但 SELinux 拒绝"这种情况在镜像制作里特别常见？
2. `restorecon` 与 `touch /.autorelabel` 分别适合什么场景？代价各是什么？
3. 为什么交付镜像里不该留 `/.autorelabel`？
4. 加固基线与云上密码注入的冲突，正确顺序是什么？推荐的折中方案是什么？
5. 在云端看到服务启动失败，`ls -Z` 看着正常，下一步查什么？

## 来源

- Red Hat Enterprise Linux 文档（Using SELinux：restorecon / semanage / troubleshooting）
- SELinux 上游文档与 `man` 页（`man 8 restorecon`、`man 8 semanage-fcontext`、`man 8 audit2allow`）
- 各云《镜像规范》中与安全加固/密码注入相关的条目（见 [[concepts/KVM 公有云 镜像 适配]] §15）

> 断言分级：SELinux 三元组判定、restorecon/autorelabel 语义为通用事实；
> 具体发行版的默认标签与策略随版本变化，以本机 `matchpathcon` 实测为准。
