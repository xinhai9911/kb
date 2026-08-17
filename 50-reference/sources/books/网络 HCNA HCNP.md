---
aliases: ["network-hcna-hcnp"]
title: 网络基础书籍蒸馏（HCNA / HCNP）
tags: [reference, sources, network, routing, switching, huawei, active]
created: 2026-07-29
updated: 2026-07-29
summary: >-
    | 文件名 | 体量 | 侧重点 |
category: reference
source_dir: Q:\常规书籍
sources: []
base_confidence: 0.6
lifecycle: reviewed
---

# 网络基础书籍蒸馏（HCNA / HCNP）

> 华为认证路由交换学习指南两册，是后续交换芯片/协议资料（[[50-reference/sources/chips/Centec CTC 7132]]、[[50-reference/sources/chips/Centec CTC 8180]]）的理论基础。

> ✅ **HCNP 已 OCR 蒸馏**：`665665 HCNP路由交换学习指南.pdf`（728页）经 easyocr 抽样 OCR（目录+各章首页），正文已提炼。HCNA 仍为少量文本层（目录可见）。
> 原始路径：`Q:\常规书籍\665665 HCNP路由交换学习指南.pdf`、`Q:\常规书籍\HCNA网络技术学习指南_.pdf`

## 书目清单（原文路径 `Q:\常规书籍\`）

| 文件名 | 体量 | 侧重点 |
|---|---|---|
| HCNA网络技术学习指南_.pdf | ~55 MB | 网络入门：TCP/IP、VLAN、路由基础 |
| 665665 HCNP路由交换学习指南.pdf | ~79 MB | 进阶：OSPF/IS-IS/BGP、MPLS、QoS |

## 关键要点

> 以下要点基于**书名与目录推测**，因原书为扫描版未做 OCR，**待 OCR 核实**，不可视为已提炼的可靠正文。

- **二层**：以太网、VLAN、STP/RSTP、链路聚合。
- **三层**：静态路由、OSPF、BGP、路由策略。
- **MPLS / VPN**：与交换芯片 [[50-reference/sources/chips/Centec CTC 8180]] 的 MPLS 培训直接对应。
- **QoS**：拥塞管理、流量监管，对应 CTC8180 QoS 培训。

## 适用场景

- 阅读交换芯片 datasheet / training 前补齐网络原理。
- 排障路由交换问题时回查协议细节。

## 关联

- 交换芯片 L2/L3 培训：[[50-reference/sources/chips/Centec CTC 7132]]、[[50-reference/sources/chips/Centec CTC 8180]]
- NPP 定时器机制（已有笔记）：[[50-reference/NPP 定时器 机制]]

---

## 深度提炼

### A. HCNA 网络技术学习指南（提取文本可辨，含完整目录）

> 来源：`Q:\AI\extract_tmp\out\HCNA网络技术学习指南_.txt`。提取文本正文为分页符 + 末尾完整目录页（第1–13章 + 附录），目录结构清晰，可提炼章节地图。

**章节地图（13 章 + 附录）**：
1. 网络通信基础（通信与网络、OSI/TCP-IP 模型、网络类型、传输介质）
2. VRP 基础（华为命令行 VRP、登录设备 Console/MiniUSB/Telnet、配置与文件管理）
3. 以太网（网卡、以太网帧/MAC、交换机转发原理、ARP）
4. STP 协议（环路问题、STP 树生成、BPDU、端口状态、改进）
5. VLAN（作用、802.1Q、端口类型、GVRP 动态注册）
6. IP 基础（有类/无类编址、子网掩码、IP 转发、报文格式）
7. TCP 与 UDP（会话建立/终止、段格式、确认重传、端口）
8. 路由协议基础（路由来源/优先级/开销、RIP、OSPF 区域化/LSA/DR-BDR）
9. VLAN 间的三层通信（多臂/单臂路由、三层交换机 VLANIF）
10. 链路技术（链路聚合/LACP、Smart Link、Monitor Link）
11. DHCP 及 NAT（DHCP 中继、静态 NAT/动态 NAT/NAPT/Easy IP）
12. PPP 与 PPPoE（PPP 建链/认证、PPPoE）
13. 网络安全与网络管理（ACL 基本/高级、SNMP/SMI/MIB）

**提炼要点**：华为数通入门体系，覆盖二层的以太网/STP/VLAN、三层的 IP/TCP/OSPF/RIP、以及 NAT/DHCP/PPP/ACL/SNMP，并围绕华为 VRP 命令行组织。与交换芯片培训直接对应。

### B. HCNP 路由交换学习指南（OCR 已提炼）

> 来源：`Q:\AI\ocr_out\665665_HCNP路由交换学习指南.txt`（easyocr 抽样 OCR，含目录页与各章首页，共约 80 页）。
> 华为 ICT 认证系列丛书，朱仕耿编著，人民邮电出版社。HCNP-R&S 认证核心知识点配套教材（与《HCNP 路由交换实验指南》姊妹篇）。

**章节地图（全书 14 章）**：
1. 路由基础（路由表、优先级、度量值、静态路由与 BFD/NQA 联动、最长前缀匹配、路由汇总、黑洞路由、路由表与 FIB 关系）
2. RIP（距离矢量、更新机制、防环——最大跳数/水平分割、RIPv2 特性、华为配置）
3. OSPF（Router-ID、LSDB、网络类型/DR-BDR、区域、LSA 类型串讲、特殊区域、路由汇总、Virtual Link）
4. IS-IS（华为数通产品上的配置与实现）
5–6. 路由进阶（路由重分发、路由策略、PBR 策略路由）
7. BGP（华为数通产品上的配置与实现）
8–10. 以太网技术（VLAN/VLANIF、链路聚合/LACP、STP/RSTP/MSTP、Smart Link 等）
11. VRRP（网络高可靠性）
12. 组播（Multicast）
13. MPLS 与 MPLS VPN（与 [[50-reference/sources/chips/Centec CTC 8180]] MPLS 培训直接对应）
14. 附录（全书习题答案）

**核心概念提炼**：
- **路由基础**：路由表查询→最长前缀匹配；路由来源（直连/静态/动态）与优先级、度量值；静态路由 + BFD/NQA 联动实现快速检测；黑洞路由防环；FIB（转发信息库）由路由表下发。
- **动态路由**：RIP（距离矢量、防环机制）、OSPF（链路状态、LSA 为核心、区域化设计）、IS-IS、BGP（EGP）；进阶含重分发/路由策略/PBR。
- **二层与可靠性**：VLAN/VLANIF 三层互通、链路聚合、STP 族、VRRP。
- **MPLS VPN**：LSP、VPN 实例、与 MPLS 交换芯片能力对齐。
- **认证范围**：HCNP-R&S 涵盖网络基础、华为路由交换产品、TCP/IP、路由协议、访问控制、eSight/Agile Controller、SDN/VXLAN/NFV、QoS、网络安全、PDIOI。

> OCR 注：少量错字（如"IP"误为"卫"、"RIP"误为"RI"），已据上下文修正；结构信息完整可靠。
