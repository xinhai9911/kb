---
title: 盛科 CTC8180 交换芯片资料蒸馏
tags: [reference, sources, centec, switch, ctc8180, asic, active]
created: 2026-07-29
updated: 2026-07-29
source_dir: Q:\芯片资料
---

# 盛科 CTC8180 交换芯片资料蒸馏

> CTC8180 是 CTC7132 的增强系列，培训胶片覆盖更全的特性（ACL/FlexE/MPLS/SRv6/QoS 等）。

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

## 关键要点

- **SRv6 / MPLS**：IPv6 分段路由与 MPLS 标签转发（与 [[sources/books/network-hcna-hcnp]] MPLS 理论对应）。
- **FlexE**：物理层时隙灵活切分。
- **QoS**：流量分类、调度、整形（与 HCNP QoS 章节对应）。
- **ACL**：基于字段的流分类与动作。

## 适用场景

- 实现 SRv6 / MPLS / QoS 功能时回查培训胶片。
- 与 [[sources/chips/centec-ctc7132]]、[[sources/chips/centec-sdk]] 配套。

## 关联

- 前代 CTC7132：[[sources/chips/centec-ctc7132]]
- SDK/开发：[[sources/chips/centec-sdk]]
- 网络基础：[[sources/books/network-hcna-hcnp]]
