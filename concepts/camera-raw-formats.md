---
title: RAW 格式与摄影机系统
category: concept
tags: [video-editing, camera, raw, codec, log, color-science, sensor]
created: 2026-07-30
updated: 2026-07-30
summary: 主流摄影机 RAW 格式对比（ARRIRAW、REDCODE、BRAW、ProRes RAW 等），压缩策略，传感器尺寸的后期含义，Log 曲线对比，以及 RAW vs Log vs 709 的选择策略
base_confidence: 0.7
lifecycle: draft
lifecycle_changed: 2026-07-30
sources:
  - "[[sources/codec-guide-mpegflow]]"
  - "[[sources/color-management-cinapex]]"
---

# RAW 格式与摄影机系统

## 概述

选择摄影机 RAW 格式是前期拍摄最重要的技术决策之一。它决定了后期管线的起点——色彩深度、数据量、压缩策略、兼容性。理解不同 RAW 格式的异同，是剪辑师与 DIT 沟通、制定后期策略的基础。

## 主流 RAW 格式

### ARRIRAW (.ari)

- **厂商**：ARRI
- **搭载机型**：ALEXA 65 / ALEXA LF / ALEXA Mini LF / ALEXA 35
- **技术特性**：ARRI 自有无损压缩 RAW。记录拜耳传感器原始数据。在 ALEXA 35 上称为 ARRIRAW Compact（改进压缩效率）。
- **色彩科学**：ALEXA 的色彩科学（至今仍是"肤色黄金标准"）基于 Log C 曲线和 AWG（ARRI Wide Gamut）色域。
- **数据率**：ALEXA 35 在 4.6K 约 340 MB/s（ARRIRAW Compact）。巨大但质量无可挑剔。
- **后期**：几乎所有 NLE 原生支持（Avid 通过 ARRI 插件、Premiere 原生、Resolve 原生）。

### REDCODE RAW (.r3d)

- **厂商**：RED Digital Cinema
- **搭载机型**：RED Komodo / RED V-RAPTOR / RED KOMODO-X
- **技术特性**：RED 自研小波压缩（Wavelet-based）RAW。独特之处：压缩比可调（3:1 损失极小到 22:1 高压缩）。RED 传感器的双原生 ISO。
- **分辨率**：最高 8K 甚至 12K V-RAPTOR XL。
- **后期**：RED 提供 R3D SDK，所有主流 NLE 均支持。Resolve 支持 GPU 加速 R3D 解码。Premiere 需安装 RED 插件。可调整色温/ISO/色调后在时间线上实时回放。
- **Redcine-X Pro**：RED 官方转码/调色工具。

### Blackmagic RAW (.braw)

- **厂商**：Blackmagic Design
- **搭载机型**：BMPCC 6K / URSA Mini Pro 12K / URSA Cine 12K
- **技术特性**：Blackmagic 自研 RAW，强调**性能效率**。采用固定质量编码（Constant Quality），非固定码率。压缩系数从 3:1 到 12:1。
- **优势**：解码极其轻量（部分计算放在摄影机内），不需要 RED 那样强大的 GPU 就能流畅播放。性能最佳 RAW 格式之一。
- **后期**：DaVinci Resolve 的"亲生"格式，原生支持。Premiere 和 Avid 需安装 Blackmagic RAW Player/SDK。

### ProRes RAW

- **厂商**：Apple
- **搭载机型**：与 Atomos Ninja V+/Shogun 等外录设备联动使用；DJI Zenmuse X7；部分 Canon/Nikon/Sony 相机通过 HDMI 输出。
- **技术特性**：Apple ProRes 家族的 RAW 版本。不同于传感器 RAW，ProRes RAW 记录的是**经管线处理后的 Bayer 数据**——保留了 RAW 的可调白平衡/ISO，但文件更小。
- **ProRes RAW HQ**：更高数据率，更低压缩损失。
- **后期**：macOS 上 FCP 和 Resolve 原生支持。Windows 支持有限，Premiere 依赖 Apple 的 ProRes RAW 解码器。

### Canon Cinema RAW Light

- **厂商**：Canon
- **搭载机型**：EOS C500 Mark II / C300 Mark III / EOS R5 C
- **技术特性**：Canon 的轻量级 RAW，有三种压缩等级：RAW / RAW LT / SRAW。SRAW 牺牲色度分辨率。
- **色彩科学**：Canon Log 2 / Canon Log 3 伽马曲线。
- **后期**：需 Canon 插件（Premiere / Avid），Resolve 原生支持有限。CFexpress 存储。

### Sony X-OCN (eXtended tonal range Original Camera Negative)

- **厂商**：Sony
- **搭载机型**：VENICE / VENICE 2 / VENICE 2 8K
- **技术特性**：Sony 的轻量 RAW 格式。目标是在 VENICE 传感器的巨大动态范围（16+ 档）与文件大小之间取得平衡。
- **三种压缩**：X-OCN XT（Extreme，接近无损）、X-OCN ST（Standard）、X-OCN LT（Light，数据率降低 60%）。
- **色彩科学**：S-Gamut3 / S-Gamut3.Cine + S-Log3 曲线。
- **后期**：Catalyst Prepare 管理，Resolve / Premiere / Avid 均通过 SDK 原生支持。

## 压缩策略对比

| 格式 | 压缩类型 | 压缩比范围 | 解码性能 | 比特深度 |
|------|---------|-----------|---------|---------|
| ARRIRAW | 无损 | ~4:1 | 中等 | 16-bit |
| REDCODE RAW | 小波有损 | 3:1 ~ 22:1 | GPU 依赖大 | 16-bit |
| Blackmagic RAW | 固定质量有损 | 3:1 ~ 12:1 | 极优 | 12-bit |
| ProRes RAW | 有损 | ~6:1 ~ 10:1 | 中等（macOS 优） | 12-bit |
| Cinema RAW Light | 有损 | ~3:1 ~ 8:1 | 中等 | 12-bit |
| X-OCN LT | 有损 | ~10:1 | 优 | 16-bit |

## 传感器尺寸的后期含义

传感器尺寸直接影响画面**景深、透视、信噪比**。后期流程需要考虑：

- **Super 35**（~24mm x 13.5mm）：电影行业传统标准。镜头选择最多（PL 卡口）。适合纪录片和手持。
- **Full Frame**（36mm x 24mm）：ALEXA LF、VENICE 2、RED V-RAPTOR。更浅景深，更大动态范围，但需要更精细的跟焦。后期中抠像（绿幕）效果更好，因为传感器像素更多。
- **IMAX**（~70mm x 52mm）和**大画幅**：ARRI ALEXA 65、IMAX 胶片。超浅景深。后期需处理大量数据，存储和渲染压力极大。
- **MF（中画幅）**：Hasselblad 等，极少用于视频。

影响：传感器越大→分辨率越高→RAW 数据量越大→存储/转码/调色渲染时间越长。

## Log 伽马曲线对比

Log 曲线将传感器的线性光信号映射为对数曲线，保留更多高光和阴影细节，用于后期调色。

| 曲线 | 厂商 | 动态范围 | 中灰点 | 特性 |
|------|------|---------|-------|------|
| Log C | ARRI | 14+ stops | 32% IRE | 肤色最优秀，调色起点最高 |
| S-Log3 | Sony | 15+ stops | 41% IRE | VENICE 使用，暗部噪点需注意 |
| V-Log | Panasonic | 14 stops | 42% IRE | Varicam/V-LogL 用于 GH 系列 |
| BMD Film | Blackmagic | 13-15 stops | 40% IRE | 四代版本不断改进 |
| Canon Log 2/3 | Canon | 14-15 stops | 32% IRE | C-Log 3 高光保留极佳 |
| N-Log | Nikon | 12 stops | 35% IRE | Z 系列摄影机使用 |
| Fujifilm F-Log | Fujifilm | 13 stops | ~40% IRE | 胶片仿真色彩为基础 |

**关键选择因素**：后期工具对特定 Log 转换 LUT（Log to Rec.709 / Log to ACES）的支持程度。DaVinci Resolve 的色彩管理内置了几乎所有 Log 曲线的自动识别和转换。

## RAW vs Log vs Rec.709 的选择策略

- **RAW**：最大调色灵活性（白平衡、ISO、色温可后期调整）。但数据量巨大，需要高性能后期管线。仅用于高端制作（长片、广告、高预算电视剧）。
- **Log（Log C / S-Log3 等）**：折中方案。保留传感器大部分信息但文件大小可控（通常以 ProRes 或 DNxHR 记录）。适合大多数专业制作。需 LUT 辅助监看和调色。
- **Rec.709**：直接出片。无后期调色空间。适合新闻、活动记录、内容创作者不需要调色时。

**实践建议**：
- 长片/Netflix 剧集：拍摄 RAW → 代理离线剪辑 → 在线回套 RAW → ACES 调色
- 独立电影/纪录片：拍摄 Log（ProRes/DNxHR）→ 离线剪辑 → 直接调色 Log → 母版
- 自媒体/YouTube：拍摄 Log 或 Rec.709。Log 提供更多空间，但需要调色知识
- 新闻/快剪：Rec.709 直出，追求速度

## 交叉参考

- [[concepts/offline-online-workflow|离线/在线工作流]]
- [[concepts/proxy-workflow|代理工作流]]
- [[concepts/mezzanine-codec|中间格式编解码器]]
- [[concepts/delivery-codec|交付编解码器]]
- [[concepts/advanced-color-grading|调色进阶]]
- [[concepts/color-grading-workflow|调色工作流]]
- [[entities/davinci-resolve|DaVinci Resolve]]
