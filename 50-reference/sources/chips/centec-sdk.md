---
title: 盛科 SDK / 开发资料蒸馏
tags: [reference, sources, centec, sdk, development, active]
created: 2026-07-29
updated: 2026-07-29
source_dir: Q:\芯片资料
---

# 盛科 SDK / 开发资料蒸馏

> 盛科交换芯片 SDK（软件开发包）相关文档索引，配合 CTC7132/8180 使用。

## 文件清单（原文路径 `Q:\芯片资料\`）

| 文件名 | 体量 | 内容 |
|---|---|---|
| SDK_Arch_Introduction.pdf | ~1.8 MB | SDK 架构总览 |
| SDK_PG_R3.0_20201212_ch.pdf | ~2.3 MB | 编程指南 R3.0 |
| SDK_V5.6.x_用户开发指南_R1.0_20210106_ch.pdf | ~28 MB | 用户开发指南 V5.6.x（最完整） |
| SDKTypicalConfiguration_APP_5.6.8RC.chm | ~11 MB | 典型配置应用（CHM 帮助） |
| SDK常用DEBUG命令.pdf | ~319 KB | 常用调试命令速查 |
| CENTEC_API_GUIDE_TM.pdf | ~11 MB | Centec API 指南（TM 流量管理） |

## 关键要点

- **SDK 架构**：HAL / 驱动 / 应用层分层。
- **典型配置**：端口、VLAN、路由、隧道配置范式。
- **DEBUG**：寄存器读写、表项 dump 等常用命令（见《SDK常用DEBUG命令》）。

## 适用场景

- 进行交换芯片功能开发、调测时回查 API 与配置样例。
- 配合 [[sources/chips/centec-ctc7132]] / [[sources/chips/centec-ctc8180]] training 落地代码。

## 关联

- 芯片资料：[[sources/chips/centec-ctc7132]]、[[sources/chips/centec-ctc8180]]
- 逆向工具：[[sources/books/reverse-ida-pro]]

---

## 深度提炼

> 本笔记覆盖两本最大的 SDK 文档，均来自 `Q:\AI\extract_tmp\out\`：
> - `SDK_V5_6_x_用户开发指南_R1_0_20210106_ch.txt`（约 134.9 万字符 + meta.json，874 页 / 1604 书签）
> - `CENTEC_API_GUIDE_TM.txt`（约 167.4 万字符 + meta.json，1229 页 / 1043 书签）
>
> 前者是"应用开发指南"（按特性分 38 个 SDK_AN_* 分册，中文、含 API 使用示例代码）；后者是"API 参考手册"（按模块分 48 章，英文、每章含 Overview / Associate Structures / APIs 三段式）。两者互补：指南看"怎么用"，API 手册看"函数/结构体原型"。

### 1) SDK_V5.6.x 用户开发指南 R1.0

- **文档概况**：**874 页 / 1604 书签 / 38 个 `SDK_AN_*` 应用分册**。
- **组织方式**：每个分册统一含"版本修订记录 → 适用芯片列表 → 概述/技术原理 → SDK API 使用（基本概念+调用步骤） → 使用示例（代码） → 附录（Key/Action 内容）"。
- **分册清单（38 个）**：ACL、APS、BFD、BPE、CPU_REASON(上 CPU)、Debug_SDK、DOT1AE、EthOAM_Y1731、FCOE、FDB、FlexE、FTM、INIT、Interrupt_DMA、IPFIX、IPUC、LB_HASH、Linkagg、MLAG、MPLS、Multicast、NAT、Nexthop、NPM、Overlay、PTP、QoS、Security、SER、SRv6、Stacking、Stats、Telemetry、TRILL、VLAN、warmboot、WLAN、XGPON。
- **抽样主题**：
  - **SDK_AN_ACL（p3）**：SDK ACL 模型核心概念——**Group（分组，含类型/Group ID/优先级）、Entry（表项，含 Entry id/优先级/Key Field/Action Field）、League、Key Type（传统 Key field 模式 / 灵活 Key field 模式）、Presel、Aset**；下发流程为 Create Group → Add Entry → Add Key/Action Field → Change Priority → Install。支持基于 Port/Vlan/L3if/业务使能，以及 UDF、Category Based ACL、SGACL、CID Based ACL、Flex key fields。
  - **SDK_AN_QoS（p648）**：从 QoS 功能总述入手，强调 Internet 中 QoS 评估的是"网络转发分组服务能力"，并区分服务供需关系下的条件好坏分析。
  - **SDK_AN_Nexthop（p537）**：先讲 Nexthop 概念来源、组成与工作模式，再描述各 Nexthop 类型及对应 API 接口；适用芯片 Greatbelt/Goldengate/Duet2/TsingMa/TsingMa.MX。
  - **SDK_AN_VLAN（p810）**：VLAN 虚拟局域网作用——物理互联网络在逻辑上划分为互不相干、广播隔离的多个网络。
  - **SDK_AN_Debug_SDK（p134）**：按模块给出诊断/显示命令范式，覆盖 Port/Linkagg/L3if、VLAN、Nexthop、L2 Ucast/Mcast、L3 IPUC/IPMC、MPLS(ILM/VPLS/VPWS/L3VPN)、OAM/APS、SCL、ACL、QoS、Packet、PDU、Stats、IPFIX、FTM、Interrupt/DMA、Dot1ae、FCOE、Trill、WLAN、Mirror、CPU Reason、Overlay Tunnel、Stacking、LB Hash、SRv6 等。

### 2) CENTEC_API_GUIDE_TM（TM 流量管理 API 参考）

- **文档概况**：**1229 页 / 1043 书签 / 48 章**。英文参考手册，每章结构 **Overview → Associate Structures（结构体定义） → APIs of XXX（函数原型与说明）**。
- **章节地图（48 章，节选代表性模块）**：
  1. Preface　2. Error Codes　3. **Port Configuration**（100M–100G 铜缆/光纤）　4. Chip Management　5. **Vlan Management**　6. Spanning Tree　7. Link Aggregation　8. Layer 2 Management　9. Learning and Aging　10. Mirroring　11. Layer 3 Interface　12. IP Unicast　13. IP Multicast　14. **MPLS Management**　15. APS　16. **Nexthop Management**（最长章，p399–453）　17. Packet Management　18. Parser　19. PDU Management　20. Statistics　21. Service ACL　22. **Access Control List**　23. **Quality Of Service**　24. Security　25. OAM　26. PTP　27. SyncE　28. IPFIX　29. Buffer and Latency Monitor　30. NvGRE/VxLAN Overlay　31. TRILL　32. FCoE　33. Stacking　34. Bridge Port Extension　35. Internal Port　36. DMA　37. Interrupt　38. Elephant Flow Detect　39. Flexible Table Management　40. **Register**　41. Networks Performance Metrics　42. Dot1ae　43. Segment Routing IPv6　44. Data Plane Telemetry　45. Diagnosis　46. SPN Channel OAM　47. Flex Ethernet　48. Appendix（API 速查 / 错误码速查）。
- **抽样主题**：
  - **3.1 Port Configuration Overview**：SDK 端口模块是资源模块，提供对大量端口属性的控制；每个端口有若干 abilities，整体能力取各因素最小公倍数，可由 API 设定。支持 100M–100G 铜缆/光纤，遵循 IEEE 802.3。
  - **5.1 Vlan Management Overview**：实现 basic vlan、vlan classification、vlan mapping 三类功能；basic vlan 支持 802.1Q VLAN 定义的创建与销毁。
  - **16.1 Nexthop Overview**：Nexthop 源自 IP 路由下一跳概念，在 Centec SDK 中由**一组多表**组成，可能含 **DsFwd / DsMet / DsNexthop / DsL2Edit / DsL3Edit** 等；这些表决定目的端口与发包前编辑动作。示例：L2UC: DsFwd→DsNexthop；L2MC: DsMet→DsNexthop；IPUC: DsFwd(opt)→DsNexthop。
  - **22.1 ACL Overview**：CTC ACL 模块基于 L2–L4 预定义协议字段分类报文；可动作包括丢弃、送 CPU、送镜像口、送不同 CoS 队列等。
  - **23.1 QoS Overview**：基于 DiffServ（DS）架构——在 DS 域边界按类分类并标记报文，域内部节点按标记类执行 PHB（per-hop behavior）；DS 是粗粒度、基于类的机制，对比 IntServ 细粒度、基于流但扩展性差。
  - **26.1 PTP Overview**：IEEE 1588v2 PTP 是基于报文的时间同步方法，提供频率/相位/时刻信息，精度达亚微秒级；芯片另支持 Sync Interface 等时钟相位同步接口。
  - **29.1 Buffer and Latency Monitor Overview**：实时监控端口拥塞与排队时延并上报，外部应用可据此预测拥塞、做流量调度决策，支持微突发（microburst）早期检测。
  - **40.1 Register Overview**：初始化驱动并向公共表/寄存器写默认值；关联结构体如 `ctc_global_capability_type_t` 描述芯片能力。
  - **45.1 Diagnosis Overview**：诊断模块提供 packet trace、丢包上报、表操作、负载均衡分布、内存使用等功能，部分可用于可视化方案。

### 开发闭环提示

- **定位特性 → 查指南 → 查 API**：先用 `SDK_AN_*` 分册确认 SDK 模型（Group/Entry/Key/Action、Nexthop 表项链等）与调用步骤，再到 API 手册按模块查结构体与函数原型，最后用 `SDK_AN_Debug_SDK` 的诊断/显示命令与《SDK常用DEBUG命令》验证。
- **指南与芯片 PG 的对应**：两本芯片 PG（见 [[sources/chips/centec-ctc7132]]、[[sources/chips/centec-ctc8180]]）每章末尾的"SDK Support"小节即对应本 SDK 指南中的分册；遇到寄存器/表项级问题，回到 PG 的"寄存器简介/列表"子节。

### 文档差异对照

| 维度 | SDK_V5.6.x 用户开发指南 | CENTEC_API_GUIDE_TM |
|---|---|---|
| 语言 | 中文 | 英文 |
| 定位 | 应用开发（怎么用） | API 参考（函数/结构体原型） |
| 组织 | 38 个 SDK_AN_* 分册，含示例代码 | 48 章，Overview/Structures/APIs 三段式 |
| 适合阶段 | 选型、流程理解、抄示例 | 写代码时查参数、结构体字段 |
| 互补 | 看调用步骤 | 看精确签名 |

### 双链

- 芯片资料（落地对象）：[[sources/chips/centec-ctc7132]]、[[sources/chips/centec-ctc8180]]
- 培训 / 项目：[[10-projects/training]]（SDK 开发、API 使用属于培训与项目落地范畴）
- 逆向工具参考：[[sources/books/reverse-ida-pro]]
