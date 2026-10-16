---
title: cloud-init 与 云元数据服务
category: concepts
tags: [cloud-init, metadata, imds, provisioning, 云初始化, active]
created: 2026-10-16
updated: 2026-10-16
summary: >-
    云上"镜像克隆后每实例一次性初始化"的机制全景：云元数据服务（阿里 100.100.100.200 /
    腾讯 metadata.tencentyun.com / 华为 169.254.169.254）、可查询内容与 IMDS 加固模式；
    cloud-init 架构与生命周期（datasource 探测、init-local/init/config/final 四阶段、
    instance-id 驱动的状态机与 /var/lib/cloud）；配置体系（cloud.cfg、cloud.cfg.d、user-data、
    vendor-data、network-config v1/v2）；状态清理与重跑语义；
    排查三件套（status/analyze/query）与三类常见故障；与云厂商 agent 的分工；
    镜像制作侧的结合点（版本、内核前提、状态清理、密码注入顺序）。
base_confidence: 0.88
lifecycle: reviewed
---

# cloud-init 与 云元数据服务

> 应用：[[concepts/KVM 公有云 镜像 适配]] §7/§8、[[entities/公有云镜像 制作 与 导入 实战]] §1.2。

## 1. 它要解决的问题

一台物理机装好系统后，主机名、IP、密码、SSH 公钥都是"这台机器"的。
但云上**一个镜像会克隆出成百上千个实例**，每个实例需要：

| 需要差异化的东西 | 谁来做 |
|---|---|
| hostname、hosts | cloud-init / 云 agent |
| 登录密码、SSH 公钥 | cloud-init（+ 华为 CloudResetPwdAgent） |
| 网络配置（DHCP 或静态） | cloud-init + 云网络注入 |
| 系统盘扩容（growpart/resizefs） | cloud-init |
| 首次开机执行脚本 | cloud-init（user-data） |

关键约束：**只做一次**，且不能把 A 实例的身份带到 B 实例 —— 这决定了整个状态机设计。

## 2. 云元数据服务（IMDS）

guest 内可通过链路本地/专用地址查询自身实例信息：

| 云 | 地址 | 备注 |
|---|---|---|
| 阿里云 | `http://100.100.100.200/` | 专用内网地址（非 169.254 网段） |
| 腾讯云 | `http://metadata.tencentyun.com/` | 另有 169.254.169.254 口径 |
| 华为云 | `http://169.254.169.254/` | 通用链路本地地址 |

```bash
# 可查询内容示例（路径风格各家略有差异）
curl -s http://100.100.100.200/latest/meta-data/instance-id
curl -s http://100.100.100.200/latest/meta-data/hostname
curl -s http://100.100.100.200/latest/user-data
```

**IMDS 加固模式**：元数据接口可被 SSRF 类漏洞利用（攻击者借应用请求元数据偷取凭证）。
加固模式（类比 AWS IMDSv2）要求先取 token 再带 token 访问。阿里云建议 cloud-init ≥ 23.2.2 以支持。

> 排障含义：**元数据不可达时 cloud-init 会等待超时**（表现为开机卡 1~2 分钟），
> 169.254 网段被路由/防火墙干扰时尤其容易踩（见 §6）。

## 3. cloud-init 架构与生命周期

### 3.1 数据源（datasource）探测

cloud-init 启动时按 `datasource_list` 顺序尝试：

| 数据源 | 载体 | 典型场景 |
|---|---|---|
| `ConfigDrive` | 挂在 guest 的只读卷（label `config-2`） | 阿里云/腾讯云/华为云常用 |
| `NoCloud` | 本地卷或 kernel cmdline（`ds=nocloud`） | 本地测试、部分云 |
| 云厂商专用（如 Aliyun、TencentCloud、HuaweiCloud） | 元数据服务 | 与 ConfigDrive 二选一 |
| `None` | 不初始化 | 明确不需要 |

### 3.2 四个阶段（stage）

| 阶段 | 时机 | 网络 | 典型动作 |
|---|---|---|---|
| `init-local` | 最早，网络前 | 无 | datasource 探测、本地磁盘（growpart） |
| `init` | 网络就绪后 | 有 | 网络配置应用、拉取元数据 |
| `config` | 主要配置 | 有 | 用户/密码/SSH key/hostname/包安装 |
| `final` | 收尾 | 有 | user-data 的 runcmd、上报、清理 |

### 3.3 instance-id：一次性语义的核心

```
首次启动：local instance-id 不存在 → 执行全部阶段 → 把 instance-id 写入本地状态
再次启动：本地 instance-id == 云端 instance-id → 跳过（"已初始化"）
克隆实例：新实例云端 instance-id 变 → 但镜像里带的是旧状态
          → 若状态未清理，可能被判定为"已初始化"而跳过全部初始化 ❌
```

这就是**镜像发布前必须 `cloud-init clean`** 的原因（见 [[entities/公有云镜像 制作 与 导入 实战]] §1.2）。

## 4. 配置体系

| 位置 | 作用 |
|---|---|
| `/etc/cloud/cloud.cfg` | 主配置：默认用户、模块列表、datasource 顺序 |
| `/etc/cloud/cloud.cfg.d/*.cfg` | 覆盖片段（推荐落点） |
| `user-data` | 实例创建时由用户提供（cloud-config YAML 或脚本） |
| `vendor-data` | 云厂商/镜像提供方提供 |
| `network-config` | 网络配置（v1 旧式 / v2 按 netplan 风格） |

```yaml
# user-data 示例（cloud-config 格式）
#cloud-config
hostname: node-01
users:
  - name: ops
    ssh_authorized_keys:
      - ssh-rsa AAAA...
runcmd:
  - [ systemctl, restart, sshd ]
```

## 5. 状态、重跑与排查

| 项 | 位置 |
|---|---|
| 状态目录（决定是否重跑） | `/var/lib/cloud/`（`instances/<id>/`、`sem/`） |
| 日志 | `/var/log/cloud-init.log`、`/var/log/cloud-init-output.log` |
| 运行时数据 | `/run/cloud-init/`（含 datasource 探测结果） |

```bash
cloud-init status --long            # 当前状态 + 各阶段耗时
cloud-init analyze show             # 时间线，定位卡在哪
cloud-init analyze blame            # 按耗时排序
cloud-init query -a                 # 当前实例所有元数据（验证注入内容对不对）
cloud-init query --format '{{ v1.instance_id }}'
cloud-init clean --logs --reboot    # 测试用：清状态并重跑
```

## 6. 三类常见故障

| 症状 | 根因 | 定位/处置 |
|---|---|---|
| 开机卡 1~2 分钟后继续 | datasource 探测超时（元数据不可达 / 169.254 被干扰） | `cloud-init analyze show`；`curl` 元数据地址验证 |
| 控制台改密码无效 | ① `/var/lib/cloud` 未清理 → 不重跑 ② 内核缺 `CONFIG_FW_CFG_SYSFS` ③ sshd 禁密码登录 | 逐项核对（原理页 §3 有完整表） |
| hostname 不更新 / 网卡没 IP | 网络配置写死 MAC、`net.ifnames` 变化、network-config 版本不匹配 | 见 [[concepts/磁盘分区 文件系统 与 挂载管理]] §5 与原理页 §7 |
| user-data 未执行 | datasource 未识别 / 语法错 / 阶段被跳过 | `cloud-init query -a` 看是否拿到 user-data；查日志报错行 |

## 7. 与云厂商 agent 的分工（别混为一谈）

| 组件 | 归属 | 职责 |
|---|---|---|
| cloud-init | 社区标准 | 首次初始化（主机名/用户/密钥/网络/脚本） |
| qemu-guest-agent | 社区/QEMU | 宿主机与 guest 交互（优雅关机、文件系统冻结、fstrim） |
| 阿里云云助手 Agent | 阿里云专有 | 免登录执行命令、补丁、运维（规范要求必装） |
| 华为 CloudResetPwdAgent | 华为云专有 | 控制台"一键重置密码"（不装则该功能不可用） |
| OpsAgent | 华为云专有 | 监控/运维 |

> 记忆点：**cloud-init 解决"开机初始化"，厂商 agent 解决"运行期运维与重置"**。

## 8. 与镜像制作的结合点

1. **必须安装**（阿里/腾讯规范明文；华为可选但强烈建议）
2. **版本**：阿里云建议 ≥ 23.2.2（支持加固模式访问元数据）
3. **内核前提**：改密码依赖 `CONFIG_FW_CFG_SYSFS=y`（4.6+ 内核/Linux，CentOS 3.10.0-826+）
4. **发布前清理**：`cloud-init clean --logs --seed` + 清 `/var/lib/cloud/*`
5. **顺序陷阱**：等保加固会禁用密码登录/锁 root，而注入密码需要密码登录
   → **先具备注入能力，后加固**（[[concepts/KVM 公有云 镜像 适配]] §9.2）
6. **验证**：本地起 VM 跑一遍 → `cloud-init status --long` 应为 `done`；`query -a` 能看到注入内容

## 9. 自测

1. cloud-init 靠什么判断"这个实例是否已初始化过"？为什么克隆镜像会导致初始化被跳过？
2. ConfigDrive 与元数据服务两种数据源，分别在什么条件下被选中？
3. 开机卡 1~2 分钟再继续，最可能是哪个环节？怎么确认？
4. `cloud-init` 与 `qemu-guest-agent`、云助手、CloudResetPwdAgent 各管什么？
5. 为什么等保加固必须在密码注入能力之后做？

## 来源

- cloud-init 官方文档 https://cloud-init.readthedocs.io/
- 阿里云《安装 cloud-init》《实例元数据》（见 [[concepts/KVM 公有云 镜像 适配]] §15 来源清单）
- 腾讯云《制作 Linux 镜像》（cloud-init 安装与配置）
- 华为云《安装 Cloud-Init》《安装一键式重置密码插件》

> 断言分级：cloud-init 阶段/状态机/datasource 类型为上游通用事实；各家元数据地址与 agent 名称以厂商文档当日版本为准。
