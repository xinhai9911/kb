---
title: Motorcomm 交换芯片资料蒸馏
tags: [reference, sources, motorcomm, switch, unmanaged, active]
created: 2026-07-29
updated: 2026-07-29
source_dir: Q:\芯片资料
---

# Motorcomm 交换芯片资料蒸馏

> 裕太微（Motorcomm）非管理型交换芯片开发资料索引。

## 文件清单（原文路径 `Q:\芯片资料\`）

| 文件名 | 体量 | 内容 |
|---|---|---|
| Motorcomm_Unmanaged_Switch_API_User_Guide_v1.006.pdf | ~2 MB | 非管理交换 API 用户指南 |
| Motorcomm_Unmanaged_Switch_Developer_Guide_v1.006.pdf | ~1.9 MB | 开发者指南 |
| Motorcomm_Unmanaged_Switch_Programming_Guide_v1.006.pdf | ~2.1 MB | 编程指南 |

## 关键要点

- **非管理交换**：即插即用二层交换，无需 CPU 控制面。
- **API / 编程**：寄存器配置、VLAN/端口默认行为。

## 适用场景

- 低端交换机 / 嵌入式交换方案开发时回查。
- 与盛科管理型交换芯片 [[sources/chips/centec-ctc7132]] 对比定位。

## 关联

- 盛科交换芯片：[[sources/chips/centec-ctc7132]]、[[sources/chips/centec-ctc8180]]

---

## 深度提炼

> 来源三份指南（均 V1.006 / 2023-07-18，裕太微 Motorcomm，Confidential，For 绿盟科技）：`Motorcomm_Unmanaged_Switch_API_User_Guide_v1_006.txt`（API 参考，40+ 头文件）、`Motorcomm_Unmanaged_Switch_Developer_Guide_v1_006.txt`（开发/调试手册）、`Motorcomm_Unmanaged_Switch_Programming_Guide_v1_006.txt`（编程指南，含完整 API 目录）。芯片以 **YT9215RB** 为例（5 电口 + 2 路 RGMII 外扩 CPU）。

### 1) 产品与定位

- **非管理型（Unmanaged）交换**：即插即用二层交换，无 CPU 控制面协议栈，出厂默认 5 电口直接工作（PC1↔PC2 可 ping 通即硬件 OK）。
- 代表芯片 **YT9215RB**：5 内置电口（Internal PHY 型号 861x）+ 2 个外置 GMAC（GMAC8/GMAC9，对应原理图 RG1/RG2）可经 RGMII 接外置 CPU 或 YT8531 外置 PHY。
- SDK 版本 **YT_SWITCH_SDK_1.1.004** 起，支持内核态 / 用户态编译（不分场景）。

### 2) SDK 架构与初始化流程

- **分层**：应用 → SDK API（FAL：Function Abstraction Layer）→ HAL → 平台接口（SMI/SPI/I2C）。最终对 switch 寄存器的读写都落到 `yt_smi_cl22_write/read` 等平台接口。
- **初始化调用链**（`SDK 源码介绍`）：
  `yt_init()` → `yt_basic_init()` → `cal_mgm_init()`（板型/Port/Phy/Led 配置，调用 `bprofile_YT9215RB_default_demo.c`）→ `hal_init()`（phy 驱动）→ `fal_dispatch_init()`（FAL 分发）→ `fal_init()`（寄存器 patch/led/port）→ `yt_modules_init()`（l2/port/vlan/rate/storm_ctrl/acl/stat/nic/dos）。
- **API 调用范式**：Write `yt_port_enable_set(unit, Port0, enable)` → `yt_smi_cl22_write()`；Read 类似。例：`yt_port_enable_get(unit, Port0, &enable)` → `yt_smi_cl22_read()`。
- **编译形态**：`build_kernel_buildin.sh`（编进内核）/ `build_kernel_module.sh`（独立 ko）；通过 `yt_sdk/make/env.h` 选板型（`Board_YT9215RB_Default_Demo`=5+2、`Board_YT9215RB_YT8531_Demo` 需开 `PHY_YT8531=YES`）；仅支持 vim 改 env.h，无 menuconfig。多芯片：挂不同 SMI 用不同 smi_write/read，挂同 SMI 则 phyaddr/switchId 不同。

### 3) 调试接口（SMI / MIB proc 调试法）

- **SMI（MDC/MDIO，CL22 协议）**：4 条 CL22 组成一个完整寄存器读写；读数据时注意 **Turn Around，有效数据为后 16 位**。调试期先导入 `yt_smi_mib_rw.c` 生成 `/proc/smi`，绕过 SDK 直接访问寄存器：
  `echo write 0xd0004 0x680 > /proc/smi` / `echo read 0xd0004 > /proc/smi`。
- **MIB 计数排查**：先 `echo mib enable > /proc/mib`（一次）→ `echo mib clear > /proc/mib` → `echo mib get 8 > /proc/mib`（抓 GMAC8 counter）。端口 MIB 基址宏 `#define YT9215_PORT_MIB_BASE(n) (0xc0100 + (n)*0x100)`，含 RxBcast/RxPause/RxCrcErr/RxSz64…RxJumbo/RxOkByte/Tx* 等（见 stat_mib[] 表）。
- **Delay 调整**：RGMII `0x80400`（P8）/ `0x80408`（P9），默认 Tx delay=2、Rx delay=1；bit[3:6]=Rx delay，bit[8]=Tx delay 使能，bit[13:16]=Tx delay。API：`yt_port_extif_rgmii_delay_set(unit, port, rxc_delay, txc_delay, txc_2ns_en)`。

### 4) 关键 API 列表（Programming Guide 目录节选）

- **yt_acl.h**：`yt_acl_init` / `yt_acl_port_en_set` / `yt_acl_udf_rule_set` / `yt_acl_rule_key_add` / `yt_acl_rule_action_add` / `yt_acl_rule_create` / `yt_acl_rule_active` / `yt_acl_rule_del`（ACL 规则增删改）。
- **yt_l2.h（最庞大，60+ 接口）**：`yt_l2_fdb_ucast_addr_add/del` / `yt_l2_mcast_addr_add/del` / `yt_l2_fdb_all_ucast_flush` / `yt_l2_port_learnlimit_*` / `yt_l2_system_learnlimit_*` / `yt_l2_fdb_aging_time_set` / `yt_l2_fdb_drop_sa/da_set` / `yt_l2_filter_mcast/bcast/unknown_ucast_set` / `yt_l2_rma_bypass_unknown_mcast_filter_set`。
- **yt_vlan.h**：`yt_vlan_fid_set` / `yt_vlan_port_set` / `yt_vlan_port_igrPvid_set` / `yt_vlan_port_egrTagMode_set` / `yt_vlan_port_igrFilter_enable_set` / `yt_vlan_port_egrFilter_enable_set`。
- **yt_port.h**：`yt_port_enable_set` / `yt_port_extif_mode_set` / `yt_port_mac_force_set` / `yt_port_extif_rgmii_delay_set`。
- **yt_nic.h**：`yt_nic_cpuport_mode_set` / `yt_nic_ext_cpuport_en_set` / `yt_nic_ext_cpuport_port_set` / `yt_nic_ext_cputag_en_set`（CPU 口模式/Tag）。
- **其他**：`yt_lag.h`（hash/trunk 组）、`yt_led.h`（模式/闪烁/强制）、`yt_dot1x.h`、`yt_dos.h`、`yt_ctrlpkt.h`（arp/nd/lldp 行为）、`yt_interrupt.h`、`yt_debug.h`（phy 回环测试）、`yt_storm_ctrl.h`、`yt_rate.h`、`yt_mirror.h`、`yt_qos.h`、`yt_sec.h`、`yt_ptp.h`、`yt_ip.h`、`yt_igmp.h` 等。

### 5) 典型应用示例（CPU 口 + VLAN）

```c
yt_init();
/* 设 Port5=物理GMAC8 为 RGMII, Force 1G Full, delay rx=1/tx=2 */
yt_port_extif_mode_set(unit, 5, YT_EXTIF_MODE_RGMII);
port_ctrl.speed_dup = PORT_SPEED_DUP_1000FULL; port_ctrl.rx_fc_en=1; port_ctrl.tx_fc_en=1;
yt_port_mac_force_set(unit, 5, port_ctrl);
yt_port_extif_rgmii_delay_set(unit, 5, 1, 2, 1);
/* 外部 CPU 口, 关 CPU Tag */
yt_nic_cpuport_mode_set(unit, CPUPORT_MODE_EXTERNAL);
yt_nic_ext_cpuport_en_set(unit, enable); yt_nic_ext_cpuport_port_set(unit, 5); yt_nic_ext_cputag_en_set(unit, 0);
/* VLAN1: P0~P3 untagged, PVID=1 */
member.portbits[0]=0xF; untag.portbits[0]=0xF;
yt_vlan_fid_set(unit,1,1); yt_vlan_port_set(unit,1,member,untag);
yt_vlan_port_igrPvid_set(unit,0,Port0,1); /* P1~P3 同理 */
/* 出/入方向 VLAN Filter 使能 ... */
```
> 逻辑 Port5=物理 GMAC8，逻辑 Port6=物理 GMAC9（依硬件连接选）。

### 6) 数据通路排查流程（Developer Guide §4）

- **上行** PC→P0 RX→Switch GMAC8 TX→CPU eth0 RX：逐段比对 counter（P0 Rx、GMAC8 Tx、`ifconfig/ethtool -S eth0` Rx），CRC 异常则调 RGMII Tx delay。
- **下行** eth0 TX→GMAC8 RX→P0 TX→PC：比对 eth0 Tx 与 GMAC8 Rx，Rx=0 无 CRC 查 RXC/RXD 信号，有 CRC 调 Rx delay。
- eth0 经 `brctl addif br-lan eth0` 加入桥后查 `ifconfig br-lan`。

### 7) 与盛科 SDK 对比

- 裕太微 SDK 聚焦**非管理/二层即插即用**，API 以 `yt_*` 单芯片直配、FAL→HAL→SMI 直写寄存器为主，**无 HAL 多芯片抽象、无 Diag/FTM/ACL TCAM 编程模型**；盛科 SDK（[[sources/chips/centec-sdk]]）为管理型、含 USW 多芯片合一、wikibase 配置体系与 TM 流量管理，定位更高端。

### 双链

- 管理型交换对照：[[sources/chips/centec-ctc7132]]、[[sources/chips/centec-ctc8180]]、[[sources/chips/centec-sdk]]
