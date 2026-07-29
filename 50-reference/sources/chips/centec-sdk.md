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
