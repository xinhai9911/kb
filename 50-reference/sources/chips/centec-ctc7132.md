---
title: 盛科 CTC7132 交换芯片资料蒸馏
tags: [reference, sources, centec, switch, ctc7132, asic, active]
created: 2026-07-29
updated: 2026-07-29
source_dir: Q:\芯片资料
---

# 盛科 CTC7132 交换芯片资料蒸馏

> CTC7132 是盛科（Centec）主流交换芯片，以下为编程指南与系列培训胶片索引。

## 文件清单（原文路径 `Q:\芯片资料\`）

| 文件名 | 类型 | 内容 |
|---|---|---|
| CTC7132_PG_R1.1_190916_ch交换芯片数据处理流程.pdf | PG | 芯片数据处理流程（Pipeline） |
| CTC7132_training_L2_190104_ch.pdf | Training | 二层转发 |
| CTC7132_training_L3_190122_ch.pdf | Training | 三层路由 |
| CTC7132_Training_OAM_ch.pdf | Training | OAM 检测 |
| CTC7132_Training_Overview_ch.pdf | Training | 芯片总览 |
| CTC7132_Training_PTP_R1.0_181116_ch.pdf | Training | 精确时间同步 PTP |
| CTC7132_Training_SCL_R1.0_181116_ch.pdf | Training | 通用逻辑 SCL |
| CTC7132_Training_VXLAN_ch.pdf | Training | VXLAN  overlay |
| CTC7132_Traning_Stacking_190401_ch.pdf | Training | 堆叠 |

## 关键要点

- **数据处理流水线**：入向解析 → L2/L3 查找 → 转发/改写 → 出向。
- **Overlay**：VXLAN 封装/解封装。
- **时间同步**：PTP（与 CTC8180 PTP 培训一致）。
- **堆叠**：多芯片逻辑统一。

## 适用场景

- 开发交换芯片 SDK 功能、排查转发问题时回查 training。
- 与 [[sources/chips/centec-sdk]]、[[sources/chips/centec-ctc8180]] 配套使用。

## 关联

- SDK/开发：[[sources/chips/centec-sdk]]
- 同系升级款：[[sources/chips/centec-ctc8180]]
- 网络原理基础：[[sources/books/network-hcna-hcnp]]
