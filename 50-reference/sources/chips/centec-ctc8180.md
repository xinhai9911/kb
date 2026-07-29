---
title: 盛科 CTC8180 交换芯片资料蒸馏
tags: [reference, sources, centec, switch, ctc8180, asic, active]
created: 2026-07-29
updated: 2026-07-29
source_dir: Q:\芯片资料
---

# 盛科 CTC8180 交换芯片资料蒸馏

> CTC8180（代号 TM.MX）是 CTC7132 的增强系列，SerDes 速率与规模大幅提升，并新增 FlexE、SRv6、更强 ACL programmable key 等特性。培训胶片覆盖 Overview / ACL / FlexE / L2 / L3 / MPLS / PTP / SCL / SRv6 / QoS。原文已提取至 `Q:\AI\extract_tmp\out\`。

## 文件清单（原文路径 `Q:\芯片资料\`）

| 文件名 | 内容 |
|---|---|
| CTC8180_PG_R1.1_20211203_ch.pdf | 编程指南（Pipeline/特性） |
| CTC8180_TrainingPPT_Overview_R1.0.pdf | 总览 |
| CTC8180_Training_ACL_ch.pdf | ACL 访问控制 |
| CTC8180_Training_FlexE_ch.pdf | FlexE 灵活以太网 |
| CTC8180_Training_L2_ch.pdf | 二层转发 |
| CTC8180_Training_L3_ch.pdf | 三层路由 |
| CTC8180_Training_MPLS_ch.pdf | MPLS |
| CTC8180_Training_PTP_ch.pdf | 精确时间同步 |
| CTC8180_Training_SCL_ch.pdf | 通用逻辑 |
| CTC8180_Training_SRv6_ch.pdf | SRv6 分段路由 |
| CTC8180_Traning_QoS_ch.pdf | QoS 服务质量 |

## 深度提炼

### 1. 芯片规格与接口（Overview）
- **SerDes**：两种 Macro——**HS SerDes**（仅支持 QSGMII）与 **CS SerDes**（仅支持 200G/400G 高速端口），同一 SerDes IP。
- **端口配置矩阵**（部分）：
  - 400G：400GAUI-8，KR8/CR8，8 lane，RS(544,514)/RS(272,257)，26.5625G PAM4（53.125G）
  - 200G：200GAUI-4，4 lane，PAM4
  - 100G：KR4/CR4/CAUI-4，4 lane，RS(544,514) 或 RS(528,514) NRZ，可选 2 lane（KR2/CR2 PAM4）
  - 50G/40G/25G/10G/2.5G/1G/10M-1000M 均支持，含 QSGMII
- **二层/三层/安全特性**：与 CTC7132 大体一致（基于 Port/Protocol/MAC/IP subnet/Flow 的 VLAN、Private VLAN、802.1x、Link Agg、IGMP Snooping、Storm Control、QinQ/Flexible QinQ、802.1ad、DCB(PFC/ECN/ETS)、802.1br；IPv4/v6 双栈、uRPF、PBR、VRRP、`(S,*)/(*,G)/(S,G)` 组播、NAT/NAPT/NAT-PT、IPv4 隧道、6in4/6to4/ISATAP/DS-Lite/IVI；Advanced ACL ingress+egress、MAC/端口绑定、CPU 防 DoS、Storm Control、Flex Editing(GTP Tunnel)）。

### 2. CTC8180 相对 CTC7132 的新增/增强点
- **QoS 队列**：**12K queues per chip**（CTC7132 为 4K）；ingress+egress 分类、每包最多 4 次 policing、MEF BWP、RED+4 阈值、priority/WDRR 调度。
- **Segment Routing IPv6（SRv6）**：支持 Standard SID、uSID、xSID、gSID（详见 §6）。
- **负载均衡**：新增 **ANT based LB/DLB**（蚁群算法 LB/DLB），与 Intelligent ECMP、Elephant Flow DLB 并列；云特性 CloudFusion/CloudGoodPut/CloudResilience/CloudTelemetry/CloudInsight 同 CTC7132。
- **ACL programmable key**（详见 §3）。

### 3. ACL（CTC8180_Training_ACL_ch，显著增强）
- **Ingress ACL**：支持 **16 次并行 TCAM 查找**（CTC7132 为 8 次）；每次查找规格 160bits×2K；Key 长度支持 **160/320/480 bits**；通过 logic table（TCAM 16×32 条目）选 key，每次 ACL 支持 32 种；**action 优先级可配**。
- **新增 programmable key 模式**：兼容历代 fixed key，不限制全局固定 14 种 key type，可经 logic table 映射从 Bus 灵活抽取报文信息组成 key，实现更灵活 ACL；默认优先级 ACL0>ACL1>…>ACL15，多次查找结果合并。
- **Egress ACL**：4 次并行 TCAM 查找，每块 1K×160bits，fixed key；支持 8 种 key 类型：MACKEY_160 / L3KEY_160 / L3KEY_320 / IPV6KEY_320 / IPV6KEY_640 / MACL3KEY_320 / MACL3KEY_640 / MACIPV6KEY_640。
- **Tunnel 报文 ACL**：独立寄存器控制内外层信息选取，ACL 使能。
- IPE ACL TCAM / EPE ACL TCAM 两套；通过 ACL 得到 flow policer pointer 与 flow statistics pointer。

### 4. FlexE（CTC8180_Training_FlexE_ch）
- **概念**：灵活以太网（OIF-FLEXE-2.1），通过 FlexE Shim 层把多个 FlexE Client 在任意 FlexE Group（PHY 组）上映射传输，实现业务速率与端口速率解耦。
- **组件**：FlexE Client（客户 MAC）、FlexE Group（PHY 组）、FlexE Shim（核心，时隙分配）。
- **功能**：捆绑（Bonding）、子速率（Sub-rate）、通道化（Channelization）、Client 带宽调整、L1 交叉。
- **CTC8180 实现**：
  - 基础功能按 OIF-FLEXE-2.1：Group/Client 绑定、Calendar A/B 切换（支持 CR 发起端与 CA 回复端）、L1 交叉（基于 Client 切换分组转发或 L1 交叉模式，源宿 Client 可跨 Group/DP 配置）。
  - 支持 **120 个 Client**（两个 DP 各 60 个），一个 Group 内 Client 只属一个 DP。
  - 扩展功能承载：**FlexE OAM**（Idle 码块承载 OAM 消息，按优先级拆分多码块发送；OAM 消息类型 BAS/CV/DM/CS，由芯片内 OAM Engine 处理，未知类型上送 CPU）、**FlexE PTP**。

### 5. MPLS / PTP / SCL / L2 / L3 / QoS
- **MPLS**：LSR/LER、global/per-interface label space、multicast labels、E-LSP/L-LSP、Martini、VPWS/VPLS/H-VPLS、MPLS L3 VPN、**13 级 MPLS Label Segment Routing**。
- **PTP**：IEEE 1588-2008、802.1AS、SyncE；One-Step/Two-Step、Peer Delay；芯片 TsEngine/SyncCapture/Sync Interface（与 CTC7132 一致，速率与时戳能力增强）。
- **SCL**：Service Classification List，接入业务识别（Adv-Vlan / IP Source Guard / Tunnel 解封装 / VPLS-VPWS / OpenFlow），Ingress 在 IPE 靠前、Egress 在 EPE 靠前；Hash + TCAM 两种查找。
- **L2/L3**：转发模型与 CTC7132 一致（MACDA+VLAN 桥接、IPDA+VRF LPM、uRPF、TTL/MTU 检查、NPLM TCAM）。
- **QoS**：12K 队列/芯片，分类/监管/调度/丢弃同前文。

### 6. SRv6（CTC8180_Training_SRv6_ch，重点特性）
- **SR 原理**：基于源路由，IPv6 场景在 SRH（Segment Routing Header）携带 SID 列表；SL（Segments Left）= 剩余 SID 数，Last Entry 为 SID List 下标，`Segment List[0]` 为最后一个 SID。
- **SID 类型**（RFC8402/8754）：Locator（可细分 B:N）、Standard SRv6 SID、gSID（G-SRv6，与 Common Prefix 拼接，Common Prefix 一般 64bit、gSID 一般 32bit）。
- **Endpoint 行为**：End（prefix SID）、End.X（L3 cross-connect / Adj SID）、End.T（绑定 SRv6 Policy，封装）、End.B6.Encaps（reduced SRH，Binding SID）、End.B6（绑定 SR-MPLS Policy）。
- **Flavors**：PSP（Penultimate Segment Pop）、USP（Ultimate Segment Pop）、USD（Ultimate Segment Decapsulation）。
- **uSID**：uSID Block + 被压缩的可变长 uSID（如 16bit uSID）。
- **gSID（G-SRv6）**：解决标准 SRH 携带完整 IPv6 地址导致有效载荷率低、跳数受限问题；由 Cisco 推动形成 Draft，盛科从技术跟进。G-SID 32bit + Padding(0) + SI(2bit 位置参数)；**COC Flavor** 指示用下一 32bit G-SID 更新 IPDA 的 G-SID 部分（不带 COC 的最后一个 G-SID 用下一 128bit SID 更新 IPDA）。
- **芯片处理流程（IPE→EPE）**：SCL UDF Lookup（UDF 按 Parser CAM 提取 SRH + XI → udfindex 区分不同 SL+XI 组合）→ IPv6 Routing → Nexthop Map → ALU Process（Copy X-SID 到 Outer IPv6 DA）→ EPE Parser 提取 SL/XI 做 ALU 运算 → 提取 Next-SID 转 IPv6 DA 查路由表；支持纯 IPv6 DA 默认 key（Outer IPv6 DA + Default VRF）。

## 适用场景
- 实现 SRv6 / MPLS / QoS / FlexE 功能时回查培训胶片（CTC8180 特性明显多于 CTC7132）。
- 与 [[sources/chips/centec-ctc7132]]、[[sources/chips/centec-sdk]] 配套。

## 关联
- 前代 CTC7132：[[sources/chips/centec-ctc7132]]
- SDK/开发：[[sources/chips/centec-sdk]]
- 网络基础：[[sources/books/network-hcna-hcnp]]
