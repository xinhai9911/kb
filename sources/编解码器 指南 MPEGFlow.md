---
aliases: ["codec-guide-mpegflow"]
kind: source
title: "Video Codecs in Post-Production — The Ultimate Guide"
alias: ["MpegFlow 视频编解码器指南"]
creators: [MpegFlow]
year: 2025
url: https://www.mpegflow.com/blog/video-codecs-in-post-production-the-ultimate-guide/
related:
  - concepts/mezzanine-codec
  - concepts/delivery-codec
  - concepts/proxy-workflow
  - concepts/offline-online-workflow
tags:
  - codec
  - video-encoding
  - post-production
category: reference
updated: 2026-07-29
summary: 视频后期制作中的编码系统层次详解：Camera Raw → Mezzanine → Post-Production → Delivery 四层模型
created: 2026-07-29
lifecycle: draft
sources: []
base_confidence: 0.7
---

# Video Codecs in Post-Production — The Ultimate Guide

## 概述

MpegFlow 提出的四层编解码器模型：从拍摄原始格式到最终交付，每个阶段需要不同的编码策略。理解这个分层模型是专业后期流程的基础。

## 四层编解码器模型

### Layer 1: Camera Raw / Acquisition（拍摄原始格式）

- **特点**：数据量极大、高度未压缩、保留最大 sensor 信息
- **常见格式**：ARRIRAW、RED RAW (R3D)、Sony RAW、Blackmagic RAW (BRAW)、Canon Cinema RAW
- **处理策略**：尽快转码为中间格式；现代 NLE 可直接解码（如 Resolve 对 BRAW 的原生支持）

### Layer 2: Mezzanine / Intermediate（中间格式 / "点心"格式）

- **特点**：帧内编码、低压缩比、易于解码和编辑、保留色深和色度采样
- **常见格式**：Apple ProRes（Proxy/LT/422/422HQ/4444）、Avid DNxHD/DNxHR、Cineform
- **用途**：剪辑时间线上的主力格式
- **带宽参考**：ProRes 422 HQ (1080p29.97) ≈ 220 Mbps

### Layer 3: Post-Production / Review（后期审查格式）

- **特点**：在质量 / 文件大小 / 兼容性之间平衡
- **常见格式**：H.264 High Profile、H.265/HEVC 10-bit
- **用途**：样片分发、团队审查、临时导出

### Layer 4: Delivery / Distribution（交付格式）

- **特点**：面向最终观众的高度压缩格式
- **常见格式**：H.264 (Streaming)、H.265 (4K/HDR)、AV1 (新兴标准)、ProRes (影院母版)
- **平台要求**：Netflix（ProRes 4444 / DNxHR 444）、YouTube（H.264/H.265/AV1）、广播电视（XDCAM / DVCPRO HD）

## 关键色度与色深参数

| 参数 | 拍摄原始 / Mezzanine | 交付压缩 |
|------|---------------------|---------|
| Chroma Subsampling | 4:2:2 或 4:4:4 | 4:2:0 |
| Bit Depth | 10-bit 或 12-bit | 8-bit 或 10-bit |
| Color Space | Rec.2020 / ACES / Camera Raw | Rec.709 / Rec.2100 |

## ProRes 家族详解（Apple ProRes）

| 格式 | 比特率(1080p30) | 用途 |
|------|----------------|------|
| ProRes Proxy | ~45 Mbps | 离线剪辑代理 |
| ProRes LT | ~100 Mbps | 轻度后期 |
| ProRes 422 | ~150 Mbps | 通用剪辑格式 |
| ProRes 422 HQ | ~220 Mbps | 高质量后期 |
| ProRes 4444 | ~330 Mbps | 视觉特效/Alpha通道 |
| ProRes 4444 XQ | ~500 Mbps | 最高质量母版 |

## DNxHD / DNxHR 家族

- **DNxHD**：固定分辨率（720p/1080p）：DNxHD 36/45/145/220 等（数字 = 近似比特率 Mbps）
- **DNxHR**：可变分辨率（HD~8K）：DNxHR LB/LQ/SQ/HQ/444
- **DNxHR HQ** (4K) ≈ 600 Mbps; **DNxHR 444** (4K) ≈ 1800 Mbps
