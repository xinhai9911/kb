---
aliases: ["color-management-cinapex"]
kind: source
title: "Video Color Spaces and Color Management Explained"
alias: ["Cinapex 色彩管理与色域指南"]
creators: [Cinapex]
year: 2025
url: https://www.cinapex.pro/post/video-color-spaces-and-color-management-explained
related:
  - concepts/color-grading-workflow
  - concepts/delivery-codec
  - entities/davinci-resolve
tags:
  - color-grading
  - color-space
  - color-management
  - hdr
category: reference
updated: 2026-07-29
summary: 视频色彩管理基础：色域、Gamma、色彩空间（Rec.709 / Rec.2020 / Rec.2100）、LUT / CST 工作流
created: 2026-07-29
lifecycle: draft
sources: []
base_confidence: 0.7
---

# Video Color Spaces and Color Management Explained

## 概述

Cinapex 对视频色彩管理的基础讲解：从基本概念（色域、Gamma、色彩深度）到高级工作流（ACES、Color Managed、LUT / CST）。

## 基本概念

### Color Space（色彩空间）= Gamut + Gamma

- **Gamut（色域）**：颜色范围（三角形色度图）
  - **Rec.709**：SDR 标准，BT.1886 Gamma，约 35% CIE 1931
  - **Rec.2020**：UHD 标准，约 75% CIE 1931（仅色域定义，Gamma 由 Rec.2100 规定）
  - **DCI-P3**：数字影院标准，介于 Rec.709 与 Rec.2020 之间
  - **ACES AP0 / AP1**：学院色彩编码系统，覆盖整个可见光谱

- **Gamma（伽玛/电光传输函数）**：信号值与显示亮度之间的映射曲线
  - **Rec.709 / BT.1886**：SDR Gamma ~2.4（显示端）
  - **Rec.2100 PQ (ST 2084)**：HDR 感知量化，最大 10,000 nits
  - **Rec.2100 HLG**：HDR 混合对数 Gamma，向后兼容 SDR
  - **Log (S-Log / V-Log / BMD Film)**：相机原始 Log 曲线，保留高光/阴影细节

### Chroma Subsampling & Bit Depth

- **4:4:4**：全色彩信息（VFX / 键控/绿幕）
- **4:2:2**：广播级后期标准
- **4:2:0**：最终交付 / 流媒体
- **8-bit**：256 级/通道（SDR 交付）
- **10-bit**：1024 级/通道（HDR 交付、调色工作流）
- **12-bit**：4096 级/通道（Camera Raw）

## 色彩管理工作流

### 方法一：Manual LUT / CST（手动管理）

- 输入 Transform：Camera Log → Working Color Space（技术 LUT 或 CST）
- 调色节点调色
- 输出 Transform：Working Color Space → Deliverable（显示 LUT 或 CST）

### 方法二：Color Managed（自动色彩管理）

- **DaVinci Resolve Color Management (RCM)**：设置输入/时间线/输出色彩空间，自动转换
- **ACES**：学院标准色彩管线，Input Transform → ACEScc → Output Transform
  - 优势：精确的色彩匹配、设备无关的交换空间、标准化的存档格式
- **Primaries 不变原则**：ACES 保证主色调在转换中不偏移

## 常见色彩空间链

```
Camera Raw (BMD Film / S-Log3 / V-Log)

    ↓ Input Transform (CST / LUT / RCM)

Working Space (DaVinci Wide Gamut / ACEScc / Rec.709 Gamma 2.4)

    ↓ Color Grading (Primary + Secondary + HDR)

    ↓ Output Transform (CST / LUT / RCM)

Deliverable (Rec.709 / Rec.2100 PQ / DCI-P3)
```

## HDR 工作流

- **HDR10**：静态元数据（MaxFALL / MaxCLL），PQ ST 2084，10-bit
- **HDR10+**：动态元数据（逐场景），PQ ST 2084，10-bit
- **Dolby Vision**：12-bit、动态元数据、双层编码
- **HLG**：向后兼容 SDR，无元数据需求
