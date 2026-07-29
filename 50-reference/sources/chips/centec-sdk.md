---
title: 盛科 SDK / 开发资料蒸馏
tags: [reference, sources, centec, sdk, development, active]
created: 2026-07-29
updated: 2026-07-29
summary: >-
    | 文件名 | 体量 | 内容 |
category: reference
source_dir: Q:\芯片资料
sources: []
base_confidence: 0.6
lifecycle: reviewed
---

# 盛科 SDK / 开发资料蒸馏

> 盛科交换芯片 SDK（软件开发包）相关文档蒸馏，配合 CTC7132/8180 使用。源文件在 `Q:/AI/extract_out/chips/`。

## 文件清单（原文路径 `Q:\芯片资料\`）

| 文件名 | 体量 | 内容 |
|---|---|---|
| SDK_Arch_Introduction.txt | ~20KB | SDK 架构总览 / 编译 / 初始化 |
| SDK_PG_R3.0_20201212_ch.txt | ~1.3MB | 编程指南 R3.0（API 设计原则、分层） |
| SDK_V5.6.x_用户开发指南_R1.0_20210106_ch.txt | ~1.84MB | 用户开发指南 V5.6.x（38 个 SDK_AN_* 分册，中文、含示例） |
| CENTEC_API_GUIDE_TM.txt | ~1.86MB | Centec API 指南（TM 流量管理，48 章英文参考） |
| SDK常用DEBUG命令.txt | ~16KB | 常用调试命令速查 |

---

## 1. SDK 架构（SDK_Arch_Introduction）

### 1.1 分层模型

```
┌─────────────────────────── System Applications ───────────────────────────┐
│  ctc_api / ctcs_api  (对外 API，统一命名，芯片无关)                         │
├─────────────── Dispatch ───────────────┬───────────────────────────────────┤
│  Greatbelt APIs │ Goldengate APIs │ USW APIs  (USW=Uniform Software 多芯片合一) │
├───────────────────────────────────────┼───────────────────────────────────┤
│  SDK Core (Functional: L2/L3/MPLS/ACL/QoS/OAM/Ipfix/Interface;             │
│            Low-layer Driver: DMA/Interrupt/Dal; Service: MemMgr/CLI;        │
│            Algo Lib: Linklist/Hash/Vector)                                 │
│  SDK App (应用层示例)                                                      │
│  SDK SAL (系统无关封装)      SDK DAL (设备驱动层: PCIe/芯片 I/O/Interrupt)  │
└───────────────────────────────────────────────────────────────────────────┘
```

- **核心目标**：通用性、兼容性、模块化、多平台兼容、多 Chip 管理、健壮可靠。
- **API 设计四原则**（SDK_PG）：最小化且完整、直观化易记、命名统一、硬件透明（与具体芯片无关，从业务应用找 API）。
  - 例：所有 FDB/IPUC/IPMC/L2UC/L2MC 相关功能仅用一个 API 族；VLAN Class 一个 API 支持 IP/MAC/Protocol VLAN。
  - 前向/后向兼容：不同代芯片 API 尽量不变。7132 完全继承 7148 API；7132 继承 8096 的 638 个 API 中 625 个兼容（84%）、新增 108（14%）、删 13（2%）。

### 1.2 代码目录（Makefile 视角）

```
cfg/       SDK 配置文件
core/       SDK 核心代码（API / ctc / sys 三层）
ctccli/     SDK CLI 命令代码
dal/        设备驱动层（PCIE 字符设备驱动）
driver/     sys 层访问芯片表项的驱动
sal/        与 OS 无关的代码
libctccli/  Centec CLI 公共函数
app/        初始化 SDK 的示例代码（用户可改/替换）
dkits/      调试芯片工具代码
docs/       Release notes / 差异文档
mk/         Makefile 目录
```

### 1.3 编译与移植

```bash
# 基于 ARM 平台编译 CTC7132 可执行文件
make targetbase=linux ARCH=arm BOARD=linux-board \
     CROSS_COMPILE=<xxx> CHIPNAME=tsingma VER=d M64=FALSE image
```

- **Makefile 入参**：`CHIPNAME`(humber/greatbelt/goldengate/duet2/tsingma)、`targetbase`(linux/vxworks)、`BOARD`、`ARCH`(mips/powerpc/x86/arm/arm64)、`VER`(r/d)、`CROSS_COMPILE`、`M64`、`LINUX_LK`(kernel/user mode)、`KDIR`(kernel 源码树)。
- **运行形态**：支持 Linux/VxWorks；用户态（需内核 dal.ko 提供 I/O）或内核态（整 SDK 编为 ko）。支持 mips/powerpc/x86/arm/arm64；一个 image 可管理多款芯片。
- **裁剪**：基于 feature（Basic l2 / Basic l2l3 / Full）；基于模块（裁剪 dkits / CLI）；裁剪 driver 中不用表项；删 Debug 信息（代价：不能用 gdb）。

### 1.4 初始化流程

| 函数 | 必选/可选 | 作用 |
|---|---|---|
| `ctc_app_sdk_init()` | 必选 | 完成 SDK/芯片初始化，可从配置文件读取或走默认配置 |
| `ctc_app_usr_init()` | 可选 | 用户自定义 API 调用 / CLI 命令 |
| `ctc_app_sample_init()` | 可选 | 软件学习老化、端口 Link Change、CPU 收包等示例 |
| `ctc_master_cli()` | 可选 | 初始化 SDK CLI 并集成进系统 |

**配置文件**（init 阶段加载）：
- `chip_profile.cfg`：ChipID、中断类型、Logic port 数、Cut-through 等。L2 学习模式 `[FDB Hw Learning]=1`(硬件学习)/0(软件学习)。
- `datapath_cfg.txt`：按板型指定 SerDes 形态、动态切换信息。
- `mem_profile.cfg`：Tcam/Ram 资源分配。
- `start_up.cfg`：init 后加载 CLI 配置。
- `resrc_profile.cfg`：Buffer 资源分配。

### 1.5 关键功能模块

- **KNET**：内核态收发包模型，协议栈与 SDK 收发不经用户态，提升效率。
- **Warmboot**：不中断转发重启驱动；可把 SDK 软表存本地/外部存储，重启后重建。
- **SER（Software Error Recover）**：ECC 纠错（中断触发 Recover）；Chip Reset（严重 fatal 时恢复挂死前数据，无需重启 SDK）。
- **MiniSDK**：u-boot 阶段最小 SDK，支持 CC 直转、L2 ucast/mcast、MAC stats、LED、MDIO、设速率、LinkAgg、Serdes FFE。

---

## 2. 关键 API 与调用序列（V5.6.x 指南 + API 手册）

SDK API 命名统一：`ctc_*` 单芯片 / `ctcs_*` 多芯片（带 `lchip` 首参）。下列为常见调用范式。

### 2.1 初始化与端口

```c
ctc_app_sdk_init();                       /* 必选：芯片初始化 */
/* 端口使能（CLI 等价见 §4） */
ctc_port_set_enable(gport, CTC_PORT_DIR_RX, 1);
ctc_port_set_speed(gport, CTC_PORT_SPEED_10G);
ctc_port_set_link_up(gport);
```

### 2.2 L2 / FDB / VLAN

```c
ctc_vlan_create(vlan_id);                /* 创建 VLAN */
ctc_vlan_add_port(vlan_id, gport);       /* 加成员 */

ctc_l2_addr_t l2_addr;                   /* 添加 MAC 表项 */
memset(&l2_addr, 0, sizeof(l2_addr));
l2_addr.fid      = fid;
l2_addr.gport    = gport;
memcpy(l2_addr.mac, mac, 6);
l2_addr.flag     = CTC_L2_FLAG_NONE;
ctc_l2_add_fdb(&l2_addr);

ctc_port_set_vlan_filter_en(gport, 2 /*both*/, 1);   /* 开关 VLAN 过滤 */
ctc_aging_set_property(0 /*MAC*/, type, value);       /* 老化配置 */
```

### 2.3 L3 接口与路由

```c
ctc_l3if_create(l3if_id, &l3if);          /* 创建 L3 接口(VLAN if / Routed port / Sub-if) */
ctc_ipuc_add(&ipuc_param);                /* 添加 IPv4 单播路由 (IPDA+VRF → Nexthop) */
ctc_ipuc_add_default_route(...);
```

### 2.4 Nexthop（多表组成的转发对象）

Nexthop 在 Centec SDK 中并非单表，而是一组表：`DsFwd / DsMet / DsNexthop / DsL2Edit / DsL3Edit`。典型链路：
- L2UC：`DsFwd → DsNexthop`
- L2MC：`DsMet → DsNexthop`
- IPUC：`DsFwd(opt) → DsNexthop`

```c
ctc_nexthop_add(nhid, &nh);               /* 添加 nexthop，内部关联上述表 */
```

### 2.5 ACL 安装（完整 Group→Entry→Key/Action 流程）

```c
/* 1) 创建 Group（ingress，port-class 1） */
ctc_acl_create_group(0, CTC_ACL_GROUP_TYPE_INGRESS, 0 /*priority*/, gport);
/* 2) 加 Entry */
ctc_acl_add_entry(0, 0);                  /* group 0, entry 0 */
/* 3) 加 Key Field */
ctc_acl_add_key_field(0, 0, &key_mac_sa); /* 例：匹配 MAC SA */
/* 4) 加 Action Field */
ctc_acl_add_action_field(0, 0, &act_permit);
ctc_acl_set_entry_priority(0, 0, 1);      /* 默认 1，0xFFFFFFFF 最高 */
/* 5) 安装 */
ctc_acl_install_group(0);
```

- **Group/Entry/Key/Action/League/Presel/Aset** 是 SDK ACL 模型核心概念；key 支持传统 Key field 模式与灵活 Key field 模式。
- 支持基于 Port/Vlan/L3if 使能；UDF、Category Based ACL、SGACL、CID Based ACL、Flex key fields。
- `ctcs_acl_set_flex_key_fields()`（TsingMa.MX）创建灵活 Key type；`ctc_acl_set_field_to_hash_field_sel()` 控制 Hash Key 选择。

### 2.6 QoS / Policer

```c
ctc_qos_policer_t policer;                /* 创建 policer */
memset(&policer, 0, sizeof(policer));
policer.id         = 1;
policer.type       = CTC_QOS_POLICER_TYPE_FLOW;
policer.mode       = CTC_QOS_POLICER_MODE_RFC2698;
policer.cir        = 100000; policer.pir = 200000;
ctcs_qos_set_policer(lchip, &policer);    /* 经 ACL/SCL/MPLS/Tunnel 引用 */
ctc_qos_map_color_domain(...);            /* cos→priority / priority→cos 映射 */
```

### 2.7 统计

```c
ctc_stats_statsid_t statsid;
ctc_stats_create_statsid(&statsid);       /* 创建 stats ID，供 MPLS/ACL/policer 引用 */
```

---

## 3. 文档组织与双文档对照

- **SDK_V5.6.x 用户开发指南**（中文，874 页 / 1604 书签 / 38 个 `SDK_AN_*` 分册）：每分册 = 修订记录 → 适用芯片 → 概述/原理 → API 使用（概念+步骤） → 使用示例代码 → 附录（Key/Action）。分册含 ACL/APS/BFD/BPE/CPU_REASON/Debug_SDK/DOT1AE/EthOAM_Y1731/FCOE/FDB/FlexE/FTM/INIT/Interrupt_DMA/IPFIX/IPUC/LB_HASH/Linkagg/MLAG/MPLS/Multicast/NAT/Nexthop/NPM/Overlay/PTP/QoS/Security/SER/SRv6/Stacking/Stats/Telemetry/TRILL/VLAN/warmboot/WLAN/XGPON。
- **CENTEC_API_GUIDE_TM**（英文，1229 页 / 1043 书签 / 48 章）：每章 Overview → Associate Structures → APIs。代表章：Port Config、Chip Mgmt、Vlan Mgmt、L2 Mgmt、Learning&Aging、Mirroring、L3 Interface、IP Unicast、IP Multicast、MPLS、APS、Nexthop、Packet、Parser、PDU、Statistics、Service ACL、ACL、QoS、Security、OAM、PTP、SyncE、IPFIX、Buffer&Latency Monitor、Register、Diagnosis、FlexE、SRv6、Data Plane Telemetry 等。

| 维度 | SDK_V5.6.x 用户开发指南 | CENTEC_API_GUIDE_TM |
|---|---|---|
| 语言 | 中文 | 英文 |
| 定位 | 应用开发（怎么用） | API 参考（函数/结构体原型） |
| 组织 | 38 个 SDK_AN_* 分册，含示例 | 48 章，Overview/Structures/APIs |
| 适合阶段 | 选型、流程理解、抄示例 | 写代码查参数/字段 |
| 互补 | 看调用步骤 | 看精确签名 |

---

## 4. 调试命令速查（SDK常用DEBUG命令）

SDK CLI 模式：`Sdk` → `Internal` → `Dkits`。常用范式：

**版本/芯片**
```bash
show version                 # SDK 版本
show chip device info        # 芯片版本
show chip sensor temp        # 结温
show ftm info                # SDK 表项分配
```

**端口**
```bash
port GPORT mac enable/disable                 # MAC 开关
port GPORT port-en enable/disable             # pipeline 收发包开关
port GPORT speed ge                           # 速率 eth/fe/ge/2g5/xg...
port GPORT if-mode 10G KR                     # 端口模式切换(SerDes 动态切换时)
port GPORT bridge enable/disable              # L2 转发开关
port GPORT dot1q-type svlan-tagged            # untagged/cvlan/svlan/double-tagged
port GPORT learning enable/disable            # MAC 学习开关
port GPORT max-frame-size 9216                # MTU <64-16127>
port GPORT vlan-ctl allow-all                 # VLAN 动作(allow-all/drop-all/drop-stag...)
port GPORT vlan-filtering direction ingress enable  # 入向 VLAN 检查
show port GPORT all ; show port mac-link      # 属性/link 查看
```

**VLAN / FDB**
```bash
vlan create vlan 100 default-entry
vlan add port GPORT vlan 100
l2 fdb add mac 00:11:22:33:44:55 fid 100 port GPORT static
l2 fdb flush by mac
aging interval 300              # 老化间隔(秒)
l2 fdb hw-learn enable          # 硬件学习开关
```

**ACL 限速示例（MCAST 限速）**
```bash
port 0x0002 dir-property acl-en direction egress value 1
qos policer attach flow 1 mode rfc2698 cir 100000 pir 200000 drop-color red
acl create group 0 direction egress lchip 0 gport 0x0002
acl add group 0 entry 0 mac-entry field-mode
acl entry 0 add key-field mac-da 01:00:00:00:00:00 ffff.ffff.ffff
acl entry 0 add action-field micro-flow-policer 1
acl install group 0
```

**QoS 映射**
```bash
qos domain 7 map cos 0 to priority 15 color green
port 0x0001 property qos-trust stag-cos
port 0x0001 dir-property qos-domain direction ingress value 7
qos policer attach port 0x0001 in mode rfc2697 color-blind cir 100000 cbs 16 ebs 1000
qos shape port 0x0002 pir 100000
```

**上 CPU 报文 / 限速**
```bash
pdu l2pdu global-action bpdu entry-valid 1 action-index 0
vlan 100 arp action copy-to-cpu
qos shape reason-shape-pkt enable
qos shape queue reason-id 5 pir 1000 cir 500
show packet stats ; show packet rx packet-header
```

**报文问题定位**
```bash
Dkits Show discard [detail]      # 丢包原因
Dkits Show discard-stats         # 丢包统计
# Pipeline 抓包：安装 capture 规则看报文在流水线处理流程
Dkits Install capture 0 flow gport GPORT mac-da 00:11:22:33:44:55
Dkits Show path capture 0 detail clear result
```
Capture KEY 可选：`src-channel/mac-da/mac-sa/svlan-id/cvlan-id/ether-type/ipv4/ipv6/mpls/l4-src-port/l4-dest-port/to-cpu-en/lchip`。

**SerDes 信号**
```bash
dkits serdes SERDESID eye width-slow times 5   # 眼图
Chip serdes SERDESID loopback internal enable  # 内外环回
```

---

## 5. 开发闭环建议

1. **定位特性 → 查指南 → 查 API**：先用 `SDK_AN_*` 分册确认 SDK 模型（Group/Entry/Key/Action、Nexthop 表项链）与调用步骤，再到 API 手册按模块查结构体与函数原型，最后用 `SDK_AN_Debug_SDK` + 《SDK常用DEBUG命令》验证。
2. **指南与芯片 PG 对应**：两本芯片 PG（见 [[50-reference/sources/chips/centec-ctc7132]]、[[50-reference/sources/chips/centec-ctc8180]]）每章末尾的 "SDK Support" 小节即对应本 SDK 指南分册；寄存器/表项级问题回 PG 的"寄存器简介/列表"子节。

---

## 双链

- 芯片资料（落地对象）：[[50-reference/sources/chips/centec-ctc7132]]、[[50-reference/sources/chips/centec-ctc8180]]
- 培训 / 项目：[[10-projects/training]]
- 逆向工具参考：[[50-reference/sources/books/reverse-ida-pro]]
