---
title: 盛科 CTC7132 交换芯片资料蒸馏
tags: [reference, sources, centec, switch, ctc7132, asic, active]
created: 2026-07-29
updated: 2026-07-29
summary: >-
    | 文件名 | 类型 | 内容 |
category: reference
source_dir: Q:\芯片资料
sources: []
base_confidence: 0.6
lifecycle: reviewed
---

# 盛科 CTC7132 交换芯片资料蒸馏

> CTC7132（代号 **TsingMa**）是盛科（Centec）主流中端交换芯片。以下为编程指南（PG）与系列培训胶片（Overview / L2 / L3 / OAM / PTP / SCL / VXLAN / Stacking）的深度提炼。原文已提取至 `Q:/AI/extract_out/chips/`，主文件 `CTC7132_PG_R1.1_190916_ch交换芯片数据处理流程.txt`（约 1.6MB）。

## 文件清单（原文路径 `Q:\芯片资料\`）

| 文件名 | 类型 | 内容 |
|---|---|---|
| CTC7132_PG_R1.1_190916_ch交换芯片数据处理流程.txt | PG | 芯片数据处理流程（Pipeline） |
| CTC7132_training_L2_190104_ch.txt | Training | 二层转发 |
| CTC7132_training_L3_190122_ch.txt | Training | 三层路由 |
| CTC7132_Training_OAM_ch.txt | Training | OAM / BFD 检测 |
| CTC7132_Training_Overview_ch.txt | Training | 芯片总览 |
| CTC7132_Training_PTP_R1.0_181116_ch.txt | Training | 精确时间同步 PTP / SyncE |
| CTC7132_Training_SCL_R1.0_181116_ch.txt | Training | 通用业务分类 SCL |
| CTC7132_Training_VXLAN_ch.txt | Training | VXLAN overlay |
| CTC7132_Traning_Stacking_190401_ch.txt | Training | 堆叠 |

## 深度提炼

### 1. 芯片规格与定位（Overview）

**TsingMa CTC7132** 面向企业网 / 运营商接入与汇聚，核心规格：

- **SerDes**：24 × 12.5Gbps（HSS12G）+ 8 × 28Gbps（HSS28G）两种 Macro。
- **带宽**：440Gbps I/O 带宽、400G Core 交换容量。
- **内置 CPU**：双核 ARM A53（可跑 SDK 用户态 / 内核态）；典型功耗 ~30W。
- **典型端口形态**：
  - `24×10G + 2×40G/100G`
  - `48×1G/2.5G + 4×25G + 2×50G`
  - 同系 CTC5168：`48×1G/2.5G + 4×10G + 2×40G`
- **表项规模**：MAC 最多 **392K**、XGEM **64K**、ACL **12K**、Buffer 最高 **9MB**（Packet 9MB + Header 1.3MB，可 Share 出部分 Packet Buffer 作动态表项用）。

**二层特性**：基于 Port / Protocol / MAC / IP subnet / Flow 的 VLAN、Private VLAN、802.1x、Link Aggregation、IGMP Snooping、Storm Control、QinQ / Flexible QinQ、802.1ad Provider Bridge、DCB(PFC/ECN/ETS)、802.1br Bridge Port Extension。

**三层特性**：IPv4/IPv6 双栈、VLAN IP / 物理 IP / IP sub 接口、uRPF、PBR、VRRP、`(S,*)/(*,G)/(S,G)` 组播 RPF、NAT/NAPT/NAT-PT、IPv4 隧道(IP-in-IP/GRE/UDP)、过渡技术(6in4/6to4/ISATAP/DS-Lite/IVI)。

**安全**：Advanced ACL（标准/扩展、ingress+egress）、VLAN/MAC/Port/IP 绑定、MAC 过滤、802.1x、端口隔离、CPU 防 DoS、单播/组播/广播 Storm Control。

**高级 / 云特性**：QoS（4K 队列/芯片、ingress+egress 分类、每包最多 4 次 policing、MEF BWP、RED+4 阈值、priority/WDRR 调度）；MPLS（LSR/LER、Martini、VPWS/VPLS/H-VPLS、L3 VPN、13 级 MPLS Label Segment Routing）；时间同步（1588-2008、802.1AS、SyncE）；OAM/APS（CFM/Y.1731、EFM、MPLS-TP BHH/BFD、SAT、TWAMP、RFC2544）。
CloudFusion / CloudGoodPut / CloudResilience / CloudTelemetry / CloudInsight：VXLAN/VXLAN-GPE/NVGRE/GENEVE L2&L3 Overlay、DCTCP/HULL、Elephant Flow DLB、Intelligent ECMP、硬件流自愈、Buffer/Latency Monitor、Microburst 检测、On-chip Flow Tracing、SDC、EM Aware、大象流检测。

---

### 2. 数据通路（Datapath）架构 — Pipeline

CTC7132 的转发是一条 **IPE → TM → EPE** 的硬流水线，另挂 OAM Engine 与共享表项资源。整体结构：

```
                        ┌──────────────── Shared Resource ────────────────┐
                        │  MAC FDB / IPUC / SCL / ACL TCAM / XGEM / ...   │
                        └──────────────────────────────────────────────────┘
   ingress port
        │
        ▼
   ┌─────────── IPE (Ingress Pipeline Engine) ───────────────────────────────┐
   │ 1st Parsing → SCL → Interface Mapper → Decap → 2nd Parsing              │
   │   → Lookup Manager → L3 Routing / L2 Bridging / TRILL-FCoE              │
   │   → QoS 分类&监管 → OAM → ACL/TCAM(8次并行) → QoS PHB(4模式)           │
   │   → CoPP / Storm Control / Policing(两级8K) → Learning → Dest Process   │
   └───────────────────────────────┬──────────────────────────────────────────┘
                                    │ BridgeHeader + Packet
                                    ▼
   ┌─────────── TM (Traffic Management) ──────────────────────────────────────┐
   │ BufferStore(Pkt 9MB / Hdr 1.3MB) → MetFifo(组播复制)                     │
   │   → Queue(入队/整形/调度) → BufRetrv(按 DestMap 取回报文)               │
   └───────────────────────────────┬──────────────────────────────────────────┘
                                    ▼
   ┌─────────── EPE (Egress Pipeline Engine) ────────────────────────────────┐
   │ Header Adjust → Egress Parsing → NextHop Mapper                         │
   │   → Egress Feature Op(Routing/MPLS/Bridging/FCoE/TRILL)                 │
   │   → L3 Packet Edit(DsL3EditMpls/Nat/Tunnel)                             │
   │   → L2 Packet Edit(DsL2EditEth/L2Flex/Loopback/Log)                     │
   │   → EPE ACL(3次) → EpePolicing → Egress OAM → Header Editing → TX       │
   └──────────────────────────────────────────────────────────────────────────┘
```

#### 2.1 IPE 流水线（PG §2.4.1，p58）

| 阶段 | 关键动作 |
|---|---|
| **Ingress 1st Parsing** | 解析出 `LocalPhyPort`（网络口取 channelID；MUX/DEMUX/EVB 口由 VLAN TAG 得；Loopback 口由环回报文 header 得；Stacking 报文先剥 Stacking Header）。由 LocalPhyPort 得 `PacketType`，并解析 L2/L3/L4 字段（支持最长 144Byte 解析）。 |
| **SCL** | 传统 UserId 功能，查 DsUserId 出：IP Source Guard、QinQ、VLAN Translation、VLAN Classification、VPLS/VPWS Ingress PE（Port+VLAN 出 FID 或转发）、L3VPN（内层标签查 UserId 出转发或 VRFID）。支持 **2 次 HASH + 2 次 TCAM** 或 **2 次 TCAM** 共 4 种接入业务识别。 |
| **Interface Mapper** | 取 VLAN/端口属性、L3 source interface ID、L3 interface 属性；做 ingress Port/VLAN 校验；确定后续 VLAN ID。 |
| **Decapsulation / 2nd Parsing** | 对 Tunnel 报文解封装后做第二次解析，得到 inner L2/L3/L4。 |
| **Lookup Manager** | 决定查哪种表：IPv4/IPv6 Ucast DA、Ucast RPF、Multicast、MAC DA/SA、OAM。 |
| **L3 Routing / L2 Bridging / TRILL-FCoE** | 单播/组播 IPDA、ECMP、RPF 校验；NAT/NATPT；二层桥接；TRILL/FCoE。 |
| **QoS 分类与监管** | QoS 监管 + 分类，重标记优先级与着色。 |
| **OAM** | 得 Local MEP Index；LM 使能时做 LM Counter；标记 OAM 报文送 OAM 引擎。 |
| **ACL/TCAM** | **ingress 8 次并行 TCAM 查找**，冲突按优先级判别；动作 permit/deny/redirection/random log/VLAN TAG 编辑/设优先级/着色/copy-to-CPU；输出 flow policer pointer、flow statistics pointer。 |
| **QoS PHB** | 4 模式：Domain / MPLS / MQC / Wireless。 |
| **CoPP / Storm Control / Policing** | 控制面保护限速；风暴抑制；ingress 两级 8K Policer（Port/Flow/Aggregate/Flow+Port，SrTCM/TrTCM/BWP/HBWP）。 |
| **MAC Learning / Destination Processing** | 学习/老化、MAC 安全与 MAC Limit；生成 BridgeHeader 送 TM。 |

#### 2.2 TM 流水线（PG §2.4.2，p62）

- **BufferStore**：把 IPE 送来的 Packet Payload 存 Packet Buffer、Bridge Header 存 Header Buffer（9MB + 1.3MB）。支持 **Shared Buffer**：把部分 Packet Buffer 动态共享给大表项场景。
- **MetFifo**：针对广播/组播做报文复制。组播两模式：
  - **Linklist**：每 DsMetEntry 对应一个出口，可独立编辑，但占表多。
  - **Bitmap**：每 DsMetEntry 含 126 出口，`portBitMap`/`portBitMapHigh` 每 bit 一端口，省表但共享编辑。
- **Queue**：按优先级/颜色入队、整形、调度出队。
- **BufRetrv**：按 `DestMap`（含 chipId+portId）从 Buffer 取回报文送 EPE。

#### 2.3 EPE 流水线（PG §2.4.3，p63）

- **EPE Header Adjust**：剥 L2 Header / Pop 标签 / VLAN Tag 编辑。
- **Egress Parsing**：对编辑后报文再解析。
- **NextHop Mapper**：按 Nexthop Pointer 查 `DsNextHop` 得下一跳；查 `DsDestPort`/`DsDestVlan` 得目的端口/VLAN。
- **Egress Feature Operation**：Routing / MPLS / Bridging / FCoE / TRILL。
- **L3/L2 Packet Editing**：`DsL3EditMpls/Nat/Tunnel`、`DsL2EditEth/L2Flex/Loopback/Log`。
- **EPE ACL（3 次查找）→ EpePolicing → Egress OAM → Header Editing → TX**。

#### 2.4 回环（Loopback）

- **Iloop**：TM → IPE，需把目的端口指定为 Iloop Port 回 IPE 重处理。
- **Eloop**：EPE → TM，两种方式：映射到 ELoop channel 的内部 port，或普通 port 在 NextHop 指定 eloop。

---

### 3. 二层转发（L2 Training）

交换原理：基于 **MACDA + VLAN** 查 FDB 转发（单播→1 出口；组播→一组出口）；基于 **MACSA + VLAN** 学习。

- **端口类型**：Access（单 VLAN，接主机）、Trunk（多 VLAN，交换机互联）、Hybrid（多 VLAN，可接主机或交换机）。
- **VLAN Tag**：TPID=0x8100；TCI = 3bit PRI(CoS) + 1bit CFI + 12bit VLAN ID（0~4095，0 与 4095 保留）。
- **FDB 学习/老化**：Learning 将 MACSA+VLAN+入端口写入 FDB；Security 含端口安全、MAC Limit（端口/VLAN/系统三维限制）、STP 检查；Aging = Update 置位 + Scan 周期扫描，AgingStatus=0 的条目被清理。
- **SDK L2 API（PG §3.3）**：
  ```c
  /* 添加/删除 MAC 表项 */
  ctc_l2_add_fdb(ctc_l2_addr_t *l2_addr);
  /* struct ctc_l2_addr_s { mac, mask, mask_valid, fid, gport, flag }; */

  ctc_port_set_vlan_filter_en(gport, dir, enable); /* dir: 0 ingress / 1 egress / 2 both */
  ctc_set_learning_action(ctc_learning_action_t *a);
  /* enum CTC_LEARNING_ACTION_ALWAYS_CPU / CACHE_FULL_TO_CPU / CACHE_ONLY /
          DONT_LEARNING / MAC_TABLE_FULL / MAC_HASH_CONFLICT_LEARNING_DISABLE */
  ctc_aging_set_property(tbl_type, type, value);  /* tbl_type: 0 MAC / 1 SCL / 2 IPUC */
  ctc_vlan_add_ports(vlan_id, port_bitmap);
  ctc_port_set_vlan_ctl(gport, mode);
  ```
- **排障示例**：单播变广播→查 FDB 条目；期望不 tag 却带 tag→查端口是否 Trunk，改 Access；期望 tag 却在入向丢弃→Access 改 Trunk 或加允许 VLAN。

---

### 4. 三层路由（L3 Training）

- **L3 Interface 类型**：VLAN Interface（含多物理口）、Routed Port（含 1 物理口）、Sub-Interface（Port+VLAN）；每个 L3 Interface 有独立 MAC。
- **查找**：IPDA+VRFID 查路由表（LPM），IPSA+VRFID 查表做 uRPF；最长匹配（bit-by-bit），Private 优先于 Public（`L3DA_LOOKUP_PRI/PUB`、`L3SA_LOOKUP_PRI/PUB`）。
- **安全检查**：RPF（Strict：源 IP 与接口均须匹配；Loose：源 IP 在路由表即可）、TTL Check（ingress 低于 limit 丢弃/copy CPU；egress TTL-1，==0 丢弃/copy CPU）、MTU Check（超 MTU 送 CPU 分片）、Martian Address（0/127/Class E 等非法地址）。
- **NPLM（芯片 LPM）**：TCAM 前缀匹配 + SRAM 完整路由；每个 TCAM index 对应 SRAM 容纳 6×IPv4 / 3×64bit IPv6 / 2×128bit IPv6；规格 8K（LPM TCAM）或 16K（LPM+NAT TCAM）。
- **Egress Router**：MTU 检查（`DsDestInterface.mtuCheckEn` + `DsNextHop.mtuCheckEn`，超则送 CPU 分片，可 `mtuExceptionEn` 丢弃）、TTL 检查（`IpeRouteCtl.ipTtlLimit`、`DsNextHop.ttlNoDecrease`、`EpePktProcCtl.discardRouteTtl0`、`ucastTtlFailExceptionEn`）。
- **Ethernet 编辑**：`PAYLOADOPERATION_ROUTE_COMPACT`（MacDa 存 DsNextHop，MacSa/VLAN 存 DsDestInterface）与 `PAYLOADOPERATION_ROUTE`（MacDa/VLAN 存 DsL2Edit，MacSa 存 DsDestInterface）。

---

### 5. OAM / BFD（OAM Training）

- **Ethernet OAM 架构**：IPE(parser/ingress OAM) / EPE(edit/egress OAM) / TM(流量管理/入星) / OAM Engine(报文识别、时间戳、报文生成、Defect)。
- **EFM (802.3ah)**：链路级 OAM，端口间直连，链路事件上报、远端环回。
- **CFM (802.1ag) / Y.1731**：网络级 OAM，故障管理(CC/LB/LT)、性能测量(LM/DM)。Up MEP（内向，经其他口发 CCM）/ Down MEP（外向，经所在口发 CCM）。
- **Y.1731 测试**：LB 环回（LBM→LBR）、LT 链路追踪（LTM→LTR）、LM 丢包（LMM/LMR，单/双端，近/远端丢包）、DM 时延（DMM/DMR，单/双向，DownMEP 在 IPE 取时间戳、UpMEP 在 EPE 取）。
- **BFD**：支持 IPv4/v6、LSP、PW VCCV、TP、micro、S-BFD；检测时间 1ms~1023ms（含 3.3ms）；状态机 AdminDown/Down/Init/Up；时间协商 DMTI/RMRI/DM。
- **测量标准**：RFC 2544（吞吐/丢包/时延，L2 用 ETH_OAM 的 LBM/TLM，L3 用 UDP ECHO port 7）、TWAMP/OWAMP（控制 TCP 861/862 送 CPU，测试报文 OAM Engine 处理）、Y.1564、MEF SAT（FLPDU 单向、FDPU=Y.1731 1SL 双向）。

---

### 6. PTP / SyncE（PTP Training）

- **1588 原理**：One-Step（Sync 携带 t1）/ Two-Step（Sync + Follow_Up 携带 t1）；Slave 记录 t2，Delay_Req/Resp 测 Path Delay；Peer Delay 机制。
- **芯片实现**：Timestamp Engine (TsEngine)、ACL/TCAM Process、Egress Feature Operation、Bootup/TAI Timestamp、SyncCapture Function Block、Sync Interface。
- **SyncE（Synchronous Ethernet）**：SyncClock / SyncPulse 实现频率同步，可穿透非 1588 网络。

---

### 7. SCL 业务分类（SCL Training）

- **SCL (Service Classification List)**：完成接入业务识别（匹配 {Port,SVLAN} 接入 QinQ、L2VPN、VXLAN 等）。Ingress SCL 在 IPE 极靠前；Egress SCL 在 EPE 靠前（NextHop Mapper 位置）。
- **UserId**：SCL 出的 AD 行为，本质与 SCL Key 相同；**FID**：二层转发域标识，MAC 学习/桥接以 {MAC,FID} 为键。
- **主要功能**：① Adv-Vlan（vlan translation / QinQ）；② IP Source Guard；③ Tunnel 解封装；④ VPLS/VPWS（VPLS 出 FID 做 L2 转发，VPWS 出 dsfwd(nhid)）；⑤ OpenFlow。
- **查找机制**：
  - **Hash 模式**：`DsUserId` 各类 Key：DoubleVlan/Svlan/Cvlan/SvlanCos/CvlanCos/Mac/Ipv4/Mac Port Hash 等。
  - **TCAM 模式**：`SCLTCAMLOOKUPTYPE_TCAML2/L3/USERID/UDFSHO/UDFLON`，`SCLTCAMKEYTYPE_MACKEY160/L3KEY160/IPV6KEY320/MACIPV6KEY/USERIDKEY/UDFKEY`。

---

### 8. VXLAN（VXLAN Training）

- **报文封装**（外层 → 内层）：
  ```
  Outer MAC (MACDA=下一跳, MACSA=源VTEP)
    + Outer IP (Src/Dst = VTEP IP)
    + UDP (目的端口 4789, 源端口由原始报文哈希得, 用于 ECMP)
    + VXLAN Header (Flag=00001000, 24bit VNI, Reserved)
    + Original L2 Frame + FCS
  ```
  UDP 目的端口固定 **4789**；源端口由内层报文哈希得到以在 VXLAN 网络节点间做 ECMP。不同 VNI 的 VM 不能二层互通。

- **二层转发（Bridging）**：相同 VNI 内不同主机通信，在 VXLAN 网络查 FDB 转发。流程：Host A→VTEP-1 收包→查 FDB→出方向加 VXLAN 封装→转发。封装靠 `DsMacDa.adNextHopPtr`→`DsNextHop`→`DsL3EditTunnel`(outer IP/UDP/VXLAN header) + `DsL2EditEth`(outer MAC)；VNI 由 FID 经 `DsEgressVsi` 映射得到。

- **三层转发（Routing）**：跨 VNI 互访走路由表。查 `DsIpDa`(IPDA+VRFID)→`adNextHopPtr`→`DsNextHop`，用 `DsL2EditInnerSwap` 改 inner MACDA，再经 `DsL3EditTunnel`/`DsL2EditEth` 加隧道头。芯片支持隧道终结后再入新隧道（不同隧道封装不同 VNI）。

- **解封装**：第一次 Parser 解析 Tunnel IPDA/IPSA/VNI（`ParserLayer4AppCtl.vxlanEn=1`、`vxlanUdpDestPort` 配 UDP 目的端口）；SCL 查 `USERIDPORTHASHTYPE_TUNNEL` 得 FID/VRF ID、`PayloadOffset`（决定剥掉的 tunnel header 长度）、Logic Port；之后 Bridge/Routing 流程与封装侧一致。

---

### 9. 堆叠（Stacking Training）

- 多芯片逻辑统一为单设备，规格支持 **127 chip**；互联形态支持环网、链形、Full-mesh。
- **CFlex header**：芯片间通信封装头，支持 16/24/32/40 bytes 模式，按业务动态选择。
- **转发流程**：
  - 单播：Ingress chip 查表得 destPort→按 destChip 选 trunk Port→trunk 内负载选 port→Ingress 模式加 CFlex header（含 destChip/destPort）→Transmit chip 按 CFlex 转发→Egress chip 按 CFlex 的 destPort 转发并 Egress 模式编辑。
  - 组播：Ingress chip 查组播组→本地成员复制；复制成员到 trunk port→trunk 负载选 port→加 CFlex header；Transmit/Egress chip 按组播组复制。
- **破环机制**：
  - 机制一（基于“源 Chip + 本地 stacking Port + 本地出口 port”丢弃）：阻止从某 Stacking 口进来的某源 Chip 报文从某本地口出去。
    ```
    stacking block port 0x:0101 remote-chip 3 dest pbmp0 0x4
    stacking block port 0x0402 remote-chip 5 dest pbmp0 0x18
    ```
  - 机制二（保护机制，SDK 默认）：基于“源 Chip + 目的 chip”丢弃，从源 Chip 经其他 chip 又回到本 chip 的报文被丢（防止环路）。
    ```
    stacking discard port 0x0401 remote-chip 3 enable
    ```
- **通信机制**：邻居发现（Neighbor Discover 建堆叠）、心跳保活（设备/端口状态）、配置管理同步。
- **CPU 间报文（C2C）**：Neighbor Discover 报文；P2MP/P2P；流量保证——C2C 控制报文按优先级入专用 16/8 个 Queue，数据报文走各 Port 的 Queue0-7。

---

## 适用场景

- 开发交换芯片 SDK 功能、排查转发问题时回查 training。
- 与 [[50-reference/sources/chips/centec-sdk]]、[[50-reference/sources/chips/centec-ctc8180]] 配套使用；CTC8180 为增强款，特性更全（ACL 16 次查找 / FlexE / MPLS / SRv6 / QoS 12K 队列）。

## 关联

- SDK/开发：[[50-reference/sources/chips/centec-sdk]]
- 同系升级款：[[50-reference/sources/chips/centec-ctc8180]]
- 网络原理基础：[[50-reference/sources/books/network-hcna-hcnp]]
