---
title: 色彩管理管线与调色工作流
category: concepts
tags: [color-grading, color-management, color-space, lut, hdr, workflow]
created: 2026-07-29
updated: 2026-07-29
summary: 专业视频调色的完整管线——从摄像机 Log 到交付母版的色彩空间变换链路
relationships:
  - target: "[[concepts/offline-online-workflow]]"
    type: part_of
  - target: "[[concepts/delivery-codec]]"
    type: related_to
  - target: "[[entities/davinci-resolve]]"
    type: uses
base_confidence: 0.7
lifecycle: draft
lifecycle_changed: 2026-07-29
sources:
  - "[[sources/color-management-cinapex]]"
  - "[[sources/nle-comparison-larry-jordan]]"
---

# 色彩管理管线与调色工作流

## 概述

颜色分级（Color Grading）是后期流程中最关键的环节之一。从摄像机捕获的 Log 画面到最终交付的正片，需要经过一条明确的色彩空间变换（Color Space Transform / CST）链路。

## 核心概念

### 色彩空间 = 色域（Gamut）× Gamma

| 色彩空间 | 色域 | Gamma / EOTF | 亮度范围 |
|----------|------|-------------|---------|
| Rec.709 (SDR) | ~35% CIE 1931 | BT.1886 (Gamma 2.4) | 0–100 nits |
| DCI-P3 (影院) | ~45% CIE 1931 | Gamma 2.6 | 0–48 nits |
| Rec.2020 (UHD) | ~75% CIE 1931 | PQ / HLG | 0–10,000 nits |
| ACES AP0 | 全可见光谱 | Linear | Scene Referred |

### 色深与色度采样

- **8-bit** (256 级)：SDR 交付，可见色带风险
- **10-bit** (1024 级)：HDR 交付 / 调色工作流最低要求
- **12-bit** (4096 级)：Camera Raw / 视觉特效母版
- **4:4:4** → **4:2:2**（后期）→ **4:2:0**（交付）

## 色彩管理工作流

### 方法 A：手动 CST / LUT 管理

1. **输入 Transform**：Camera Log (S-Log3 / V-Log / BMD Film / RED Log3G10) → 工作色彩空间
2. **调色**：一级调色（对比度/饱和度/白平衡）+ 二级调色（限定器/窗口/跟踪）
3. **输出 Transform**：工作色彩空间 → 交付色彩空间 (Rec.709 / Rec.2100)

### 方法 B：自动色彩管理

- **DaVinci Resolve Color Management (RCM)**：在项目设置中指定输入/时间线/输出色彩空间，Resolve 自动管理所有转换
- **ACES (Academy Color Encoding System)**：开放标准色彩管线
  - Input Transform (IDT) → ACEScc（调色空间）→ Output Transform (ODT)
  - 优点：设备无关、精确色彩、标准化存档

## LUT（Look-Up Table）的类型

| 类型 | 用途 |
|------|------|
| 技术 LUT (Technical) | Camera Log → Rec.709 |
| 创意 LUT (Creative / Look) | 模拟胶片、风格化色调 |
| 显示 LUT (Display / Output) | 从工作空间 → 交付色彩空间 |
| 1D LUT | Gamma 曲线（仅亮度） |
| 3D LUT | 全色彩变换（RGB 三维） |

## 一级 vs 二级调色

- **一级调色（Primary）**：作用于整帧——对比度、亮度、饱和度、色温、Gamma 偏移
- **二级调色（Secondary）**：限定特定区域/颜色——肤色分离、Hue vs Sat 曲线、Power Window + 跟踪
- **HDR 调色**：在 PQ 空间使用色轮 + HDR 色板，高光可达 1000+ nits

## 常见调色风格

- **胶片模拟**：S-Curve（肩/趾）、色偏（Teal & Orange）、颗粒感
- **漂白效果（Bleach Bypass）**：降低饱和度、提高对比度
- **低饱和度 / 褪色**：近年主流风格（Mad Max / 银翼杀手 2049）
- **高对比硬朗**：犯罪片 / 战争片
