---
title: DaVinci Resolve
category: entities
tags: [nle, color-grading, davinci-resolve, post-production, blackmagic-design]
created: 2026-07-29
updated: 2026-07-29
summary: Blackmagic Design 开发的集剪辑、调色、音频、合成于一体的专业后期软件——调色行业标准
relationships:
  - target: "[[concepts/color-grading-workflow]]"
    type: implements
  - target: "[[concepts/offline-online-workflow]]"
    type: implements
  - target: "[[concepts/audio-post-production-pipeline]]"
    type: implements
  - target: "[[concepts/proxy-workflow]]"
    type: implements
base_confidence: 0.8
lifecycle: draft
lifecycle_changed: 2026-07-29
sources:
  - "[[sources/nle-comparison-larry-jordan]]"
  - "[[sources/color-management-cinapex]]"
---

# DaVinci Resolve

## 概述

DaVinci Resolve 由 Blackmagic Design 开发，最初仅作为调色工具（DaVinci 2K/4K），逐步发展为涵盖剪辑（Cut / Edit）、调色（Color）、合成（Fusion）、音频（Fairlight）、媒体管理（Media）的全功能后期套件。**调色领域事实上的行业标准**。

## 核心特性

- **节点式调色**：与层式调色不同，节点提供更灵活的信号流拓扑（并行 / 串行 / 键混合）
- **Native GPU 加速**：CUDA / OpenCL / Metal
- **免费版极强**：无限轨道、无限分辨率、HDR 调色——仅限部分特效 / 降噪 / NR 需要 Studio 版
- **Studio 版 $295 买断**：无订阅，一次购买永久使用
- **协作模式**：Project Server（多用户同时协作）

## 内置模块

| 模块 | 功能 |
|------|------|
| Media | 素材管理、元数据、Sync Bin |
| Cut | 快速剪辑工作间（针对社交 / 短视频优化） |
| Edit | 传统时间线剪辑（工具齐全） |
| Fusion | 节点式合成与视觉特效（替代 After Effects） |
| Color | 一级/二级调色、CST、HDR 色板、色彩扭曲 |
| Fairlight | 多轨音频编辑与混音（内置 -24 LUFS 标准化） |
| Deliver | 多格式导出、Preset 管理 |

## 生态定位

- **调色**：No.1 选择，几乎所有专业调色师使用
- **剪辑**：近年快速追赶，Cut 页面针对社交视频
- **音频**：Fairlight 已具备基本混音能力，但复杂项目仍需 Pro Tools
- **价格**：性价比最高，$295 买断 vs Premiere $22.99/月

## FCPXML 兼容性

通过 [[entities/apple-final-cut-pro|FCP]] 导入项目需借助第三方工具（XtoCC / DaVinci Resolve 原生 FCPXML 导入器），但复杂时间线回套仍存在问题。

## 相关页面

- [[concepts/color-grading-workflow]]：色彩管理管线
- [[concepts/offline-online-workflow]]：离线/在线编辑流程
- [[sources/nle-comparison-larry-jordan]]：NLE 对比
