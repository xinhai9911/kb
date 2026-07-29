---
title: 网络基础书籍蒸馏（HCNA / HCNP）
tags: [reference, sources, network, routing, switching, huawei, active]
created: 2026-07-29
updated: 2026-07-29
source_dir: Q:\常规书籍
---

# 网络基础书籍蒸馏（HCNA / HCNP）

> 华为认证路由交换学习指南两册，是后续交换芯片/协议资料（[[sources/chips/centec-ctc7132]]、[[sources/chips/centec-ctc8180]]）的理论基础。

> ⚠️ **扫描版 / 无文本层**：
> - `665665 HCNP路由交换学习指南.pdf`（728页）为**扫描件，无文本层**，本会话未做 OCR，以下仅索引、未提炼正文。
> - `HCNA网络技术学习指南_.pdf` 虽含少量文本层，但极不完整，实质仍接近扫描版。
> - 如需深入正文，需对原 PDF 做 OCR（如 tesseract / 百度OCR）后再蒸馏。
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
- **MPLS / VPN**：与交换芯片 [[sources/chips/centec-ctc8180]] 的 MPLS 培训直接对应。
- **QoS**：拥塞管理、流量监管，对应 CTC8180 QoS 培训。

## 适用场景

- 阅读交换芯片 datasheet / training 前补齐网络原理。
- 排障路由交换问题时回查协议细节。

## 关联

- 交换芯片 L2/L3 培训：[[sources/chips/centec-ctc7132]]、[[sources/chips/centec-ctc8180]]
- NPP 定时器机制（已有笔记）：[[50-reference/npp-timer-mechanism]]

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

### B. HCNP 路由交换学习指南（扫描版，文本层缺失）

> 来源：`Q:\AI\extract_tmp\out\665665_HCNP路由交换学习指南.txt`。提取文本仅含 `----- PAGE n -----` 分页符，**无正文，扫描版需 OCR 未提取**。
> 已知价值（来自原笔记与书目定位）：进阶路由交换——OSPF/IS-IS/BGP、MPLS/VPN、QoS、路由策略。待 OCR 后回填本笔记，再与 [[sources/chips/centec-ctc8180]] 的 MPLS/QoS 培训对接。
