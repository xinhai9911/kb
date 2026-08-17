---
aliases: ["centec-ctc8180"]
title: 盛科 CTC8180 交换芯片资料蒸馏
tags: [reference, sources, centec, switch, ctc8180, asic, active]
created: 2026-07-29
updated: 2026-07-29
summary: >-
    | 文件名 | 内容 |
category: reference
source_dir: Q:\芯片资料
sources: []
base_confidence: 0.6
lifecycle: reviewed
---

# 盛科 CTC8180 交换芯片资料蒸馏

> CTC8180（代号 **TsingMa.MX / TM.MX**）是 CTC7132 的增强系列，SerDes 速率与规模大幅提升，并新增 FlexE、SRv6、更强 ACL programmable key 等特性。培训胶片覆盖 Overview / ACL / FlexE / L2 / L3 / MPLS / PTP / SCL / SRv6 / QoS。主文件 `CTC8180_PG_R1.1_20211203_ch.txt`（约 1.48MB），原文已提取至 `Q:/AI/extract_out/chips/`。

## 文件清单（原文路径 `Q:\芯片资料\`）

| 文件名 | 内容 |
|---|---|
| CTC8180_PG_R1.1_20211203_ch.txt | 编程指南（Pipeline/特性） |
| CTC8180_TrainingPPT_Overview_R1.0.txt | 总览 |
| CTC8180_Training_ACL_ch.txt | ACL 访问控制（programmable key） |
| CTC8180_Training_FlexE_ch.txt | FlexE 灵活以太网 |
| CTC8180_Training_L2_ch.txt | 二层转发 |
| CTC8180_Training_L3_ch.txt | 三层路由 |
| CTC8180_Training_MPLS_ch.txt | MPLS |
| CTC8180_Training_PTP_ch.txt | 精确时间同步 |
| CTC8180_Training_SCL_ch.txt | 通用逻辑 |
| CTC8180_Training_SRv6_ch.txt | SRv6 分段路由 |
| CTC8180_Traning_QoS_ch.txt | QoS 服务质量 |

## 深度提炼

### 1. 芯片规格与接口（Overview）

- **SerDes Macro**：两种 —— **HS SerDes**（仅支持 QSGMII）与 **CS SerDes**（仅支持 200G/400G 高速端口），同一 SerDes IP。
- **端口配置矩阵**（部分）：

  | 速率 | 接口 | Lane | 编码 |
  |---|---|---|---|
  | 400G | 400GAUI-8, KR8/CR8 | 8 | RS(544,514)/RS(272,257), 26.5625G PAM4（53.125G） |
  | 200G | 200GAUI-4 | 4 | PAM4 |
  | 100G | KR4/CR4/CAUI-4 | 4 | RS(544,514) 或 RS(528,514) NRZ；可选 2 lane（KR2/CR2 PAM4） |
  | 50/40/25/10/2.5/1G/10M-1000M | 均支持，含 QSGMII | — | NRZ |

- **二层/三层/安全特性**：与 CTC7132 大体一致（基于 Port/Protocol/MAC/IP subnet/Flow 的 VLAN、Private VLAN、802.1x、Link Agg、IGMP Snooping、Storm Control、QinQ/Flexible QinQ、802.1ad、DCB(PFC/ECN/ETS)、802.1br；IPv4/v6 双栈、uRPF、PBR、VRRP、`(S,*)/(*,G)/(S,G)` 组播、NAT/NAPT/NAT-PT、IPv4 隧道、6in4/6to4/ISATAP/DS-Lite/IVI；Advanced ACL ingress+egress、MAC/端口绑定、CPU 防 DoS、Storm Control、Flex Editing(GTP Tunnel)）。

---

### 2. 相对 CTC7132 的新增 / 增强点

| 维度 | CTC7132 (TsingMa) | CTC8180 (TsingMa.MX) |
|---|---|---|
| SerDes | 12.5G×24 + 28G×8 | HS(QSGMII) + CS(200G/400G PAM4)，400G 支持 |
| QoS 队列 | 4K / chip | **12K / chip** |
| Ingress ACL | 8 次并行 TCAM | **16 次并行 TCAM** + programmable key |
| 新特性 | — | **FlexE、SRv6、ANT-based LB/DLB** |
| 负载均衡 | Intelligent ECMP / Elephant Flow DLB | 同上 + **ANT based LB/DLB**（蚁群算法） |

- **QoS 队列**：12K queues per chip；ingress+egress 分类、每包最多 4 次 policing、MEF BWP、RED+4 阈值、priority/WDRR 调度。
- **SRv6**：支持 Standard SID、uSID、xSID、gSID。
- **ACL programmable key**（见 §3）。云特性 CloudFusion/CloudGoodPut/CloudResilience/CloudTelemetry/CloudInsight 同 CTC7132。

---

### 3. ACL（CTC8180_Training_ACL_ch，显著增强）

#### 3.1 Ingress ACL —— programmable key 机制

CTC8180 的 Ingress ACL 是相对 7132（8 次并行）最大的增强点：

- **16 次并行 TCAM 查找**（Level0~Level15），每次查找规格 **160bits × 2K**；Key 长度支持 **160 / 320 / 480 bits**（320/480 由相邻 block 横向拼接，须物理连续）。
- **Logic Table（LGT）**：在真正 ACL TCAM 查找前，先做一次 TCAM 查找（规格 16×32 条，即 16 次查找 × 每次 32 种 key 组合），决定如何从资源池抽 key。兼容历代 fixed key 模式。
- **Programmable key 资源池**：从 IPE 的 PI/PR/UDF 抽取共 **877 bits** 放入 *Ingress ACL Input Bus*，经 `Field selector → Logic Table lookup → ProgramAcl*Bus` 组 key：
  ```
  IngAclInputBus(877bits)
      → Field selector
      → Logic Table lookup (DsLtidSelectTcam0-15 → ltidIndex)
      → DsLtidSelectAd0-15 / DsProgramKeyGenProfile0-15
      → ProgramAcl32bBus / 16b / 8b / 4b / 2b Bus
      → IngAclLookupKey [159:0] (或 319 / 479)
  ```
  programAcl*Bus 按 32/16/8/4/2 bits 为单位组织，最终拼成 160/320/480 bits key。
- **Ingress ACL Input Bus 关键字段**：`globalSrcPort[15:0]`(gport)、`logicSrcPort[15:0]`、`localPhyPort[7:0]`、`interfaceId[12:0]`、`svlanId/cvlanId` 及 cos/cfi、`nextHopPtr[17:0]`、`l3DaLookupHit/l3SaLookupHit/macDaLookupHit`、ARP check 结果等。
- **Flex Key 模式优点**（相对 7132）：① 可同时匹配 Gport + LogicPort（旧芯片二选一）；② 一条 entry 全端口匹配（旧芯片需多条）；③ UDF 128 byte 可部分字节当 key（旧芯片只能全匹配或全不匹配）。
- **Action 合并**：16 次查找得 `resultValid` + `hitIndex[10:0]`，多 level 结果 merge；默认优先级 ACL0>ACL1>…>ACL15，可配。常见 AD：denyBridge/denyLearning/denyRoute、exceptionToCpu、statsPtr、policerPtr、adNextHopPtr、dscp、U1.g1.dsFwdPtr、ecmpGroupId、clearPktEditOperation、各色 prio 赋值。
- **资源规划**：IPE ACL TCAM 共 **2K×160bits×16**；block 可串联扩表（level0+level1 逻辑合并成 1 次串行查找）；block 优先级可经物理→逻辑一级映射重排（如 2>1>0>3>6>5>4）。

#### 3.2 Egress ACL

- **4 次并行 TCAM 查找**，每块 **1K×160bits**，fixed key；支持 8 种 key 类型：
  `MACKEY_160 / L3KEY_160 / L3KEY_320 / IPV6KEY_320 / IPV6KEY_640 / MACL3KEY_320 / MACL3KEY_640 / MACIPV6KEY_640`。
- 使能维度：Port / VLAN / L3 Interface / 全局（每 Level 单独使能，寄存器 `EpeAclQosCtl.gGlbAcl[2,0].aclEnable`）。
- EPE AD：TruncateLenProfId、aclLogId、coppValid/policerPtr、exceptionToCpu*、discardOpTypeGreen[1:0]（0 not care / 1 discard / 2 cancel discard）等。

#### 3.3 Flow ACL / UDF

- **Flow ACL**：`DsSrcPort.aclFlowHashType(1..3)` 选 Hash Lookup Type（L2 / L3IPv4 / L3IPv6 / L3MPLS / L2L3 / FLEX），结果存 `DsFlow`，action 含 denyBridge/denyLearning/denyRoute/logicSrcPort/policerPtr/adNextHopPtr 等。
- **UDF（User Defined Field）**：芯片未支持 parser 的报文，用 UDF 按需抽字段。三次抽取流程：
  1. Parser 中 `UdfCamLookup`（CAM 深度 512，key=`udfLabel[7:0]`+Layer2/3/4Type+vlanNum 等）→ `UdfHitIndex[9:0]` → AD 表抽 **udfdata1 (PktUdf, 128bits，8×16bit offset)**。
  2. SCL 中 udfdata1 可作 SCL key；SCL action 可重设 UdfHitIndex 供后续抽 **udfdata2**。
  3. Lookup Manager / ACL 中抽 **udfdata3 (PktUdfAcl)**。
  udfdata1/2 称 PktUdf，udfdata3 称 PktUdfAcl，最终填入不同位宽 ACL Bus 组 key。
- **表项规格**：IPE ACL HASH 64K；IPE ACL TCAM 160bit×2K×16；EPE ACL TCAM 160bit×1K×4；UDF 1024（parser 512 + service 512）。

---

### 4. FlexE（CTC8180_Training_FlexE_ch）

- **概念**：灵活以太网（OIF-FLEXE-2.1），通过 **FlexE Shim** 层把多个 FlexE Client 在任意 FlexE Group（PHY 组）上映射传输，实现业务速率与端口速率解耦。
- **组件**：FlexE Client（客户 MAC）、FlexE Group（PHY 组）、FlexE Shim（核心，时隙分配）。**Calendar** 时隙颗粒度 **5Gbps/slot**。
- **功能**：捆绑（Bonding）、子速率（Sub-rate）、通道化（Channelization）、Client 带宽调整、L1 交叉。
- **CTC8180 实现**：
  - 基础按 OIF-FLEXE-2.1：Group/Client 绑定、Calendar A/B 切换（CR 发起端 / CA 回复端）、L1 交叉（源宿 Client 可跨 Group/DP 配置）。
  - 支持 **120 个 Client**（两个 DP 各 60 个），一个 Group 内 Client 只属一个 DP。
  - 扩展：承载 **FlexE OAM**（Idle 码块承载 OAM，按优先级拆分多码块；消息类型 BAS/CV/DM/CS，由 OAM Engine 处理，未知类型上送 CPU）、**FlexE PTP**。

---

### 5. MPLS / PTP / SCL / L2 / L3 / QoS

- **MPLS**：LSR/LER、global/per-interface label space、multicast labels、E-LSP/L-LSP、Martini、VPWS/VPLS/H-VPLS、MPLS L3 VPN、**13 级 MPLS Label Segment Routing**。标签头 4 字节，S 位 1 表示最底层标签。
- **PTP**：IEEE 1588-2008、802.1AS、SyncE；One-Step/Two-Step、Peer Delay；TsEngine/SyncCapture/Sync Interface（速率与时戳能力增强）。
- **SCL**：Service Classification List，接入业务识别（Adv-Vlan / IP Source Guard / Tunnel 解封装 / VPLS-VPWS / OpenFlow），Ingress 在 IPE 靠前、Egress 在 EPE 靠前；Hash + TCAM 两种查找。
- **L2/L3**：转发模型与 CTC7132 一致（MACDA+VLAN 桥接、IPDA+VRF LPM、uRPF、TTL/MTU 检查、NPLM TCAM）。
- **QoS**：12K 队列/芯片；pipeline 含 Enqueue/Dequeue；流分类→标记（color 作 policer 输入）→policerPtr0/1 选择（service policer / flow policer）→调度。支持 WRED。

---

### 6. SRv6（CTC8180_Training_SRv6_ch，重点特性）

- **SR 原理**：基于源路由，IPv6 场景在 **SRH（Segment Routing Header）** 携带 SID 列表；`SL`（Segments Left）= 剩余 SID 数，`Last Entry` 为 SID List 下标，`Segment List[0]` 为最后一个 SID（从 SR Policy 最后一个 SID 开始填）。
- **SID 类型**（RFC8402/8754）：Locator（可细分 B:N）、Standard SRv6 SID、gSID（G-SRv6，Common Prefix 一般 64bit + gSID 一般 32bit）。
- **Endpoint 行为**：End（prefix SID）、End.X（L3 cross-connect / Adj SID）、End.T（绑定 SRv6 Policy，封装）、End.B6.Encaps（reduced SRH，Binding SID）、End.B6（绑定 SR-MPLS Policy）。
- **Flavors**：PSP（Penultimate Segment Pop）、USP（Ultimate Segment Pop）、USD（Ultimate Segment Decapsulation）。
- **uSID**：uSID Block + 被压缩的可变长 uSID（如 16bit uSID）。
- **gSID（G-SRv6）**：解决标准 SRH 携带完整 IPv6 地址导致有效载荷率低、跳数受限问题。G-SID 32bit + Padding(0) + SI(2bit 位置参数)；**COC Flavor** 指示用下一 32bit G-SID 更新 IPDA 的 G-SID 部分（不带 COC 的最后一个 G-SID 用下一 128bit SID 更新 IPDA）。
- **芯片处理流程（IPE→EPE）**：
  ```
  IPE: SCL UDF Lookup (UDF 按 Parser CAM 提取 SRH + XI → udfindex 区分不同 SL+XI 组合)
       → IPv6 Routing → Nexthop Map → ALU Process (Copy X-SID 到 Outer IPv6 DA)
  EPE: EPE Parser 提取 SL/XI 做 ALU 运算 → 提取 Next-SID 转 IPv6 DA 查路由表
       支持纯 IPv6 DA 默认 key (Outer IPv6 DA + Default VRF)
  ```
  Headend 行为示例：添加带 SRH 的 IPv6 头 `(S3,S2,S1; SL=2)`；`H.Encaps.Red` 通过排除 SRH 第一个 SID 减少头开销。

---

## 适用场景

- 实现 SRv6 / MPLS / QoS / FlexE 功能时回查培训胶片（CTC8180 特性明显多于 CTC7132）。
- 与 [[50-reference/sources/chips/Centec CTC 7132]]、[[50-reference/sources/chips/Centec SDK]] 配套。

## 关联

- 前代 CTC7132：[[50-reference/sources/chips/Centec CTC 7132]]
- SDK/开发：[[50-reference/sources/chips/Centec SDK]]
- 网络基础：[[50-reference/sources/books/网络 HCNA HCNP]]
