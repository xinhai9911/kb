---
title: 盛科 CTC7132 交换芯片资料蒸馏
tags: [reference, sources, centec, switch, ctc7132, asic, active]
created: 2026-07-29
updated: 2026-07-29
source_dir: Q:\芯片资料
---

# 盛科 CTC7132 交换芯片资料蒸馏

> CTC7132（代号 TsingMa）是盛科（Centec）主流交换芯片。以下为编程指南与系列培训胶片（Overview / L2 / L3 / OAM / PTP / SCL / VXLAN / Stacking）的深度提炼，原文已提取至 `Q:\AI\extract_tmp\out\`。

## 文件清单（原文路径 `Q:\芯片资料\`）

| 文件名 | 类型 | 内容 |
|---|---|---|
| CTC7132_PG_R1.1_190916_ch交换芯片数据处理流程.pdf | PG | 芯片数据处理流程（Pipeline） |
| CTC7132_training_L2_190104_ch.pdf | Training | 二层转发 |
| CTC7132_training_L3_190122_ch.pdf | Training | 三层路由 |
| CTC7132_Training_OAM_ch.pdf | Training | OAM / BFD 检测 |
| CTC7132_Training_Overview_ch.pdf | Training | 芯片总览 |
| CTC7132_Training_PTP_R1.0_181116_ch.pdf | Training | 精确时间同步 PTP / SyncE |
| CTC7132_Training_SCL_R1.0_181116_ch.pdf | Training | 通用业务分类 SCL |
| CTC7132_Training_VXLAN_ch.pdf | Training | VXLAN overlay |
| CTC7132_Traning_Stacking_190401_ch.pdf | Training | 堆叠 |

## 深度提炼

### 1. 芯片规格（Overview）
- **TsingMa CTC7132** 核心规格：
  - SerDes：24 × 12.5Gbps（HSS12G）+ 8 × 28Gbps（HSS28G）
  - 带宽：440Gbps I/O、400G Core
  - 内置 CPU：Dual Core ARM A53；典型功耗 ~30W
  - 典型端口形态：`24×10G + 2×40G/100G`，或 `48×1G/2.5G + 4×25G + 2×50G`；另 CTC5168：`48×1G/2.5G + 4×10G + 2×40G`
  - 表项规模：MAC 最多 392K、XGEM 64K、ACL 12K、Buffer 最高 9MB
- **二层特性**：基于 Port / Protocol / MAC / IP subnet / Flow 的 VLAN、Private VLAN、802.1x、Link Aggregation、IGMP Snooping、Storm Control、QinQ / Flexible QinQ、802.1ad Provider Bridge、DCB(PFC/ECN/ETS)、802.1br Bridge Port Extension。
- **三层特性**：IPv4/IPv6 双栈、VLAN IP / 物理 IP / IP sub 接口、uRPF、PBR、VRRP、`(S,*)/(*,G)/(S,G)` 组播 RPF、NAT/NAPT/NAT-PT、IPv4 隧道(IP-in-IP/GRE/UDP)、过渡技术(6in4/6to4/ISATAP/DS-Lite/IVI)。
- **安全**：Advanced ACL（标准/扩展、ingress+egress）、VLAN/MAC/Port/IP 绑定、MAC 过滤、802.1x、端口隔离、CPU 防 DoS、单播/组播/广播 Storm Control。
- **高级**：QoS（4K 队列/芯片、ingress+egress 分类、每包最多 4 次 policing、MEF BWP、RED+4 阈值、priority/WDRR 调度）；MPLS（LSR/LER、Martini、VPWS/VPLS/H-VPLS、L3 VPN、13 级 MPLS Label Segment Routing）；时间同步（1588-2008、802.1AS、SyncE）；OAM/APS（CFM/Y.1731、EFM、MPLS-TP BHH/BFD、SAT、TWAMP、RFC2544）。
- **云特性 CloudFusion / CloudGoodPut / CloudResilience / CloudTelemetry / CloudInsight**：VXLAN/VXLAN-GPE/NVGRE/GENEVE L2&L3 Overlay、DCTCP/HULL、Elephant Flow DLB、Intelligent ECMP、硬件流自愈、Buffer/Latency Monitor、Microburst 检测、On-chip Flow Tracing、SDC、EM Aware、大象流检测。

### 2. 数据通路（Datapath）架构
- 模块化：**IPE**（入方向解析/查找/编辑）→ **TM**（Traffic Management 调度/资源）→ **EPE**（出方向编辑）→ **OAM**（检测）→ **Shared Resource**（共享表项）→ Parser / Flow Tracing / NetFlow / Security Engine(MACSEC/CloudSec)。
- **IPE 流程**：1st Parsing（解 L2/L3/L4 字段）→ SCL（UserId / IP SourceGuard / QinQ / VLAN Translation / VLAN Class / VPLS-VPWS Ingress PE / L3VPN 出标签→RPF ID / Tunnel 解封装）→ Interface Mapper（取 VLAN/Port 属性、L3 source interface ID）→ Lookup Manager（IPv4/IPv6 Ucast DA、Ucast RPF、MAC DA/SA、OAM 查找）→ L3 Routing / L2 Bridging / Trill-FCoE → QoS 分类与监管 → OAM → ACL/TCAM（ingress 最多 8 次并行查找，支持优先级；动作 permit/deny/redirection/random log/VLAN TAG 编辑/设优先级/着色/copy-to-CPU；输出 flow policer pointer、flow statistics pointer）→ QoS PHB（Domain/MPLS/MQC/Wireless 4 模式）→ CoPP / Storm Control / Learning → Destination Processing。
- **TM 流程**：BufferStore（Packet 9MB + Header 1.3M 共享缓冲）→ MetFifo（组播复制）→ Queue（按优先级/颜色入队、shaping、调度）→ BufRetrv（按 DestMap 取回报文送 EPE）。组播两模式：**Linklist**（每 DsMetEntry 一出口、可独立编辑，占表多）与 **Bitmap**（每 DsMetEntry 含 126 出口、portBitMap/portBitMapHigh 每 bit 一端口，省表但共享编辑）。
- **EPE 流程**：Header Adjust（去 L2 header / PoP 标签 / VLAN 编辑）→ Egress Parsing → NextHop Mapper（DsNexthop 得下一跳、DsDestPort/DsDestVlan）→ Egress Feature Operation（Routing/MPLS/Bridging/FCoE/Trill）→ L3 Packet Editing（DsL3EditMpls/Nat/Tunnel）、L2 Packet Editing（DsL2EditEth/L2Flex/Loopback/Log）→ EPE ACL（egress 3 次 ACL 查找）→ EpePolicing → Egress OAM → Header Editing → TX。
- **回环**：Iloop（TM→IPE，需指定 dest port 为 Iloop Port 回 IPE）；Eloop（EPE→TM，两种方式：映射到 ELoop channel 的内部 port，或普通 port 在 NextHop 指定 eloop）。

### 3. 二层转发（L2 Training）
- 交换原理：基于 MACDA+VLAN 查 FDB 转发（单播→1 出口；组播→一组出口）；基于 MACSA+VLAN 学习（无表项则学，端口漂移可控制是否学）。
- **端口类型**：Access（单 VLAN，接主机）、Trunk（多 VLAN，交换机互联）、Hybrid（多 VLAN，可接主机或交换机）。
- **VLAN Tag**：TPID=0x8100；TCI 含 3bit PRI(CoS) + 1bit CFI + 12bit VLAN ID（0~4095，0 与 4095 保留）。
- **FDB 学习/老化**：Learning 将 MACSA+VLAN+入端口写入 FDB；Security 含端口安全、MAC Limit（端口/VLAN/系统三维限制）、STP 检查、Aging（Update 置位 + Scan 周期扫描，AgingStatus=0 的条目被清理）。
- **关键 SDK API（附录）**：
  - `ctc_l2_add_fdb(&l2_addr)` — `struct ctc_l2_addr_s{mac, mask, mask_valid, fid, gport, flag}`
  - `ctc_port_set_vlan_filter_en(gport, dir, enable)` — dir: 0 ingress / 1 egress / 2 both
  - `ctc_set_learning_action(&learning_action)` — enum `CTC_LEARNING_ACTION_ALWAYS_CPU / CACHE_FULL_TO_CPU / CACHE_ONLY / DONLEARNING / MAC_TABLE_FULL / MAC_HASH_CONFLICT_LEARNING_DISABLE`
  - `ctc_aging_set_property(tbl_type, type, value)` — tbl_type: 0 MAC / 1 SCL / 2 IPUC
  - `ctc_vlan_add_ports(vlan_id, port_bitmap)`、`ctc_port_set_vlan_ctl(gport, mode)`
- 排障示例：单播变广播→查 FDB 条目；期望不 tag 却带 tag→查端口是否 Trunk，改 Access；期望 tag 却在入向丢弃→Access 改 Trunk 或加允许 VLAN。

### 4. 三层路由（L3 Training）
- **L3 Interface 类型**：VLAN Interface（含多物理口）、Routed Port（含 1 物理口）、Sub-Interface（Port+VLAN）；每个 L3 Interface 有独立 MAC（可相同/不同）。
- **查找**：IPDA+VRFID 查路由表（LPM），IPSA+VRFID 查表做 uRPF；最长匹配（bit-by-bit），Private 优先于 Public（L3DA_LOOKUP_PRI/PUB、L3SA_LOOKUP_PRI/PUB）。
- **安全检查**：RPF（Strict：源 IP 与接口均须匹配；Loose：源 IP 在路由表即可）、TTL Check（ingress 低于 limit 丢弃/copy CPU；egress TTL-1，==0 丢弃/copy CPU）、MTU Check（超 MTU 送 CPU 分片）、Martian Address（0/127/Class E 等非法地址）。
- **NPLM（芯片 LPM）**：TCAM 前缀匹配 + SRAM 完整路由；每个 TCAM index 对应 SRAM 容纳 6×IPv4 / 3×64bit IPv6 / 2×128bit IPv6 条目；规格 8K（LPM TCAM）或 16K（LPM+NAT TCAM）。
- **Egress Router**：MTU 检查（`DsDestInterface.mtuCheckEn` + `DsNextHop.mtuCheckEn`，超则送 CPU 分片，可 `mtuExceptionEn` 丢弃）、TTL 检查（`IpeRouteCtl.ipTtlLimit`、`DsNextHop.ttlNoDecrease`、`EpePktProcCtl.discardRouteTtl0`、`ucastTtlFailExceptionEn`）。
- **Ethernet 编辑**：`PAYLOADOPERATION_ROUTE_COMPACT`（MacDa 存 DsNextHop，MacSa/VLAN 存 DsDestInterface）与 `PAYLOADOPERATION_ROUTE`（MacDa/VLAN 存 DsL2Edit，MacSa 存 DsDestInterface）。

### 5. OAM / BFD（OAM Training）
- **Ethernet OAM 架构**：IPE(parser/ingress OAM) / EPE(edit/egress OAM) / TM(流量管理/入星) / OAM Engine(报文识别、时间戳、报文生成、Defect)。
- **EFM (802.3ah)**：链路级 OAM，端口间直连，支持链路事件上报、远端环回。
- **CFM (802.1ag) / Y.1731**：网络级 OAM，故障管理(CC/LB/LT)、性能测量(LM/DM)。Up MEP（内向，经其他口发 CCM）/ Down MEP（外向，经所在口发 CCM）。
- **Y.1731 测试**：LB 环回（LBM→LBR）、LT 链路追踪（LTM→LTR）、LM 丢包（LMM/LMR，单/双端，近/远端丢包）、DM 时延（DMM/DMR，单/双向，DownMEP 在 IPE 取时间戳、UpMEP 在 EPE 取）。
- **BFD**：支持 IPv4/v6、LSP、PW VCCV、TP、micro、S-BFD；检测时间 1ms~1023ms（含 3.3ms）；状态机 AdminDown/Down/Init/Up；时间协商 DMTI/RMRI/DM。
- **测量标准**：RFC 2544（吞吐/丢包/时延，L2 用 ETH_OAM 的 LBM/TLM，L3 用 UDP ECHO port 7）、TWAMP/OWAMP（控制 TCP 861/862 送 CPU，测试报文 OAM Engine 处理）、Y.1564、MEF SAT（FLPDU 单向、FDPU=Y.1731 1SL 双向）。

### 6. PTP / SyncE（PTP Training）
- **1588 原理**：One-Step（Sync 携带 t1）/ Two-Step（Sync + Follow_Up 携带 t1）；Slave 记录 t2，Delay_Req/Resp 测 Path Delay；Peer Delay 机制。
- **芯片实现**：Timestamp Engine (TsEngine)、ACL/TCAM Process、Egress Feature Operation、Bootup/TAI Timestamp、SyncCapture Function Block、Sync Interface。
- **SyncE（Synchronous Ethernet）**：SyncClock / SyncPulse 实现频率同步，可穿透非 1588 网络。

### 7. SCL 业务分类（SCL Training）
- **SCL (Service Classification List)**：完成接入业务识别（匹配 {Port,SVLAN} 接入 QinQ、L2VPN、VXLAN 等）。Ingress SCL 在 IPE 极靠前；Egress SCL 在 EPE 靠前（NextHop Mapper 位置）。
- **UserId**：SCL 出的 AD 行为，本质与 SCL Key 相同；**FID**：二层转发域标识，MAC 学习/桥接以 {MAC,FID} 为键。
- **主要功能**：① Adv-Vlan（vlan translation / QinQ）；② IP Source Guard；③ Tunnel 解封装；④ VPLS/VPWS（VPLS 出 FID 做 L2 转发，VPWS 出 dsfwd(nhid)）；⑤ OpenFlow。
- **查找机制**：Hash 模式（DsUserId 各类 Key：DoubleVlan/Svlan/Cvlan/SvlanCos/CvlanCos/Mac/Ipv4/Mac Port Hash 等）与 TCAM 模式（`SCLTCAMLOOKUPTYPE_TCAML2/L3/USERID/UDFSHO/UDFLON`、`SCLTCAMKEYTYPE_MACKEY160/L3KEY160/IPV6KEY320/MACIPV6KEY/USERIDKEY/UDFKEY`）。

### 8. VXLAN（VXLAN Training）
- **报文封装**：Outer MAC（MACDA=下一跳、MACSA=源 VTEP） + Outer IP（Src/Dst = VTEP IP） + UDP（目的端口 **4789**，源端口由原始报文哈希得用于 ECMP） + VXLAN Header（8bit Flag=00001000、24bit **VNI**、Reserved）。
- VXLAN 网络标识 VNI 区分转发域；不同 VNI 的 VM 不能二层互通。

### 9. 堆叠（Stacking Training）
- 多芯片逻辑统一为单设备。**CFlex header** 封装跨芯片报文；编辑模式区分本地/远端。
- 转发流程：单播 / 组播（跨堆叠口复制）。
- **破环机制**：在 Stacking Port 上丢弃源 Chip+本地 stacking Port+本地出口 Port 匹配的报文，阻止从某 Stacking 口进来的某源 Chip 报文环路。

## 适用场景
- 开发交换芯片 SDK 功能、排查转发问题时回查 training。
- 与 [[sources/chips/centec-sdk]]、[[sources/chips/centec-ctc8180]] 配套使用；CTC8180 为增强款，特性更全（ACL/FlexE/MPLS/SRv6/QoS）。

## 关联
- SDK/开发：[[sources/chips/centec-sdk]]
- 同系升级款：[[sources/chips/centec-ctc8180]]
- 网络原理基础：[[sources/books/network-hcna-hcnp]]
