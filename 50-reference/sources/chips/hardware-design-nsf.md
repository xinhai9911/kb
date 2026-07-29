---
title: 硬件设计资料蒸馏（NSF / 框式机架）
tags: [reference, sources, hardware, nsf, chassis, design, active]
created: 2026-07-29
updated: 2026-07-29
source_dir: Q:\芯片资料
---

# 硬件设计资料蒸馏（NSF / 框式机架）

> 网络设备硬件设计报告与框式机架文档索引。

> ⚠️ **WB4U11U 框式机架 PDF 加密无法提取**：`WB4U11U框式机架框图-各板卡规格及软硬件接口文档-20240629【NSF】.pdf`（~7 MB）经 OCR 流程尝试打开时报 `ValueError: cannot initialize - document still encrypted` —— 即**该 PDF 带密码保护/加密**，PyMuPDF 无法初始化，因此既无文本层也无法 OCR（另含 `corrupt object stream (9060 0 R)` 损坏告警）。**非纯图片型，而是加密文件**，需提供密码才能解密提取。**同批 `NSF1N10TG801MA-NSF1N10TG8B01MA硬件设计报告V1.1.docx` 此前已成功提取**（见下方深度提炼，内容来自该次提取）。
> 原始路径：`Q:\芯片资料\`

## 文件清单（原文路径 `Q:\芯片资料\`）

| 文件名 | 体量 | 内容 | 提取状态 |
|---|---|---|---|
| NSF1N10TG801MA-NSF1N10TG8B01MA硬件设计报告V1.1.docx | ~1.5 MB | 绿盟科技 沐创N10 自研网卡硬件设计报告 | ✅ 已提取（281 行，下方提炼源自此） |
| WB4U11U框式机架框图-各板卡规格及软硬件接口文档-20240629【NSF】.pdf | ~7 MB | WB4U11U 框式机架框图、板卡规格与软硬接口 | ❌加密PDF·需密码·无法OCR |

---

## 深度提炼（NSF1N10TG801MA / 8B01MA 硬件设计报告）

> 来源：绿盟科技《NSF1N10TG801MA-NSF1N10TG8B01MA硬件设计报告V1.1.docx》（以沐创 N10 网卡芯片为核心的国产自研网卡设计）。

### 1. 项目背景与目的
- **替代动机**：2021 年起 Intel XL710 等网卡芯片缺货、价格翻 5-10 倍；引入国产**沐创 N10**（中芯国际代工）作为紧急补充，满足**信创自主可控**。
- **适配平台**：海光 3、海光 5 等国产平台。

### 2. 系统方案（整体框图逻辑）
- **核心芯片**：沐创 N10，兼容 Intel XL710 系列（指令/寄存器层面可作替代）。
- **上行通道**：PCIe 3.0 ×8（Gen3，8 GT/s）。
- **面板接口**：
  - NSF1N10TG401MA（即 401MA）：4×SFP+ & 4×SFP（均支持 10G）
  - NSF1N10TG4B01MA（即 4B01MA）：4×SFP+，含 **bypass 模块**（由 MCU 控制，掉电/异常时物理旁路保障链路不中断）
- **其他**：电子标签（I²C 存单板信息，用于资产管理）、光模块信息访问（通过 I²C 读取光模块 EEPROM）、预留调试接口（JTAG/UART 等）。

### 3. 高速以太接口（N10 SerDes 配置）
- N10 内部四个 SerDes 通道可灵活配置多种模式：`2×QSFP+` / `2×SFP+` / `4×SFP+` / `8×SFP+`。
- 本设计采用：
  - 方案 3（4×SFP+，对应 4 口 bypass 网卡 4B01MA）
  - 方案 2 思路延伸（8×SFP+，对应八口网卡 401MA 的 4+4 组合）
- 每个 SerDes 速率可达 10G，外接 PHY/光模块经 SFP+ 连接器出面板。

### 4. PCIe 接口（与主机桥接）
- N10 集成 Gen3 ×8 PCIe PHY：速率 8 GT/s、支持 **SR-IOV**、**2 PF + 128 VF**（2 个物理功能、最多 128 个虚拟功能），满足虚拟化直通场景。
- 板级需做好 PCIe 差分对等长、阻抗控制（100Ω）与参考时钟（100 MHz）分配。

### 5. 关键器件与电源/时钟
- **主芯片**：沐创 N10（集成 MAC + SerDes + PCIe PHY）。
- **外部组件**：SFP+ 笼子与光模块、MCU（bypass 控制）、EEPROM/I²C 电子标签、时钟发生器（为 SerDes/PCIe 提供参考钟）。
- **电源**：多路 DC-DC 为 N10 核电压、SerDes、PCIe、MCU 分别供电；需满足上电时序与纹波要求。
- **PCB 考虑**：高速差分信号（PCIe ×8、SerDes ×4）需阻抗连续、等长、远离噪声源；光模块侧注意 EMI。

### 6. 引用规范
- 绿盟 NIC 网卡设计规范 V1.6、PCIe 3.0 CEM、沐创 N10 datasheet、单板设计需求跟踪矩阵（需求→实现的可追溯）。

> 注：WB4U11U 框式机架（机框背板、线卡/主控卡规格、软硬件接口）因 PDF 加密无法提取，以下"框式机架"要点为**文件名推测，未核实**，请勿作为已提炼内容。

- **框式机架（待解密）**：机框背板、线卡/主控卡规格、软硬件接口定义 —— 需提供 PDF 密码后走解密→OCR 流程回填。

## 适用场景
- 硬件方案评审、板卡接口对接时回查规格。
- 与交换芯片 [[sources/chips/centec-ctc7132]] / [[sources/chips/centec-ctc8180]] 配套理解整机设计。

## 关联
- 交换芯片：[[sources/chips/centec-ctc7132]]、[[sources/chips/centec-ctc8180]]
- SDK/开发：[[sources/chips/centec-sdk]]
- 同 N10 平台的软件/驱动与 DPDK 适配：[[sources/chips/nic-dpdk]]
