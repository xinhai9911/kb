---
aliases: ["hdr-production-pipeline"]
title: HDR 视频制作全流程
category: concepts
tags: [video-editing, hdr, dolby-vision, hlg, color-grading, rec2020, pq, post-production]
created: 2026-07-30
updated: 2026-07-30
summary: HDR 视频从拍摄到交付的完整工作流——HDR10/Dolby Vision/HLG 标准对比、色彩空间、调色流程、SDR-HDR 转换与交付格式
lifecycle: draft
base_confidence: 0.8
---

# HDR 视频制作全流程

## 概述

高动态范围 (High Dynamic Range, HDR) 是继彩色、高清之后视频技术的第三次重大飞跃。HDR 在三个维度上超越了 SDR：**更高亮度**（最高 10,000 nits vs 100 nits）、**更广色域**（Rec.2020 vs Rec.709）、**更深的位深度**（10-12 bit vs 8 bit）。

## HDR 标准对比

### 四种主要 HDR 标准

| 标准 | 元数据类型 | 位深 | 最大亮度 | 主要应用 | 特点 |
|------|-----------|------|---------|---------|------|
| **HDR10** | Static (SMPTE ST 2086) | 10-bit | 10,000 nits | **通用基础标准** | 全帧单组元数据，最广泛兼容 |
| **HDR10+** | Dynamic (每场景) | 10-bit | 10,000 nits | 三星/亚马逊/流媒体 | 动态元数据改善逐场景质量 |
| **Dolby Vision** | Dynamic (每帧) + RPU | 12-bit | 10,000 nits | **高端电影/流媒体** | 最先进的元数据+调色控制 |
| **HLG** (Hybrid Log-Gamma) | 无（场景参考） | 10-bit | 1,000+ nits | **广播电视/Live** | SDR 反向兼容，无需元数据 |

### 核心技术差异

- **传输函数**：HDR10/HDR10+/DV 使用 **PQ** (Perceptual Quantizer, SMPTE ST 2084) ——基于人眼感知的非线性曲线；HLG 使用 Hybrid Log-Gamma——联合 SDR 和 HDR 信号
- **色域**：全部基于 **Rec.2020** (BT.2020)，SDR 时代 Rec.709 的替代者
- **白点**：D65 （与 SDR 一致）
- **元数据**：SMPTE ST 2086 (Mastering Display Color Volume)、MaxFALL/MaxCLL (HDR10)、每场景/每帧动态元数据 (HDR10+/DV)

## HDR 色彩空间

### Rec.2020 + PQ

```
SDR (Rec.709)              HDR (Rec.2020)
┌─────────────┐            ┌───────────────────────┐
│ 色域：~35%    │            │ 色域：~75% CIE 1931    │
│ 伽马：2.4     │    →      │ 传输：PQ (ST 2084)     │
│ 白点：D65     │            │ 白点：D65              │
│ 8-bit        │            │ 10-bit / 12-bit        │
│ 0-100 nits   │            │ 0-10,000 nits          │
└─────────────┘            └───────────────────────┘
```

Rec.2020 色域覆盖约 75% 的 CIE 1931 可见光谱，远大于 Rec.709 的约 35%。PQ 曲线的关键特征：**绝对亮度编码**——每个码值对应一个绝对亮度（nits），与显示设备和观看环境无关。

### Color Volume

SDR 是一个二维概念（色域二维），HDR 引入三维的 **Color Volume**（色域 × 亮度）：

```
                     亮度轴 (nits)
                         ▲
                    10000│
                         │    HDR Color Volume
                     1000│  ┌───────────────┐
                         │  │               │
                      100│  │    SDR        │
                         │  │  ┌──────────┐ │
                         │  │  │          │ │
                       10│  │  │          │ │
                         │  │  └──────────┘ │
                         │  └───────────────┘
                         └──────────────────► 色度 x/y
```

## HDR 拍摄

### 摄影机 HDR 模式设置

| 机型 | HDR 模式 | 推荐 Log 曲线 | 注意事项 |
|------|---------|-------------|---------|
| ARRI Alexa 35 | ARRIRAW + LogC4 | LogC4 (+9 stops) | 原生 HDR 工作流 |
| RED V-RAPTOR | REDCODE RAW | REDWideGamutRGB + Log3G10 | 保留高光细节 |
| Sony Venice | X-OCN + S-Log3 | S-Gamut3.Cine/S-Log3 | 需匹配正确的 LUT |
| RED KOMODO | 5K/6K RAW | REDWideGamutRG + Log3G10 | 小型 HDR 制作利器 |
| Canon C500 Mark II | Cinema RAW Light | Canon Log 3 | 注意动态范围上限 |
| iPhone ProRes | ProRes RAW Log | Apple Log | 移动端 HDR 拍摄入门 |

**HDR 拍摄关键**：
- **曝光策略**：针对高光曝光（Expose for Highlights），利用 HDR 高亮保留优势
- **监看**：使用 HDR 监视器 + LUT 预览 PQ 曲线
- **假色辅助**：确认高光不会裁切
- **RAW 拍摄**：HDR 制作强烈推荐 RAW 格式

## HDR 调色工作流

### DaVinci Resolve HDR 调色

Resolve 是 HDR 调色的主流工具，提供专用 HDR 色轮：

**色轮布局**（HDR 模式）：
- **Global**：整体调整
- **Highlight**：高光区域（与 SDR 的一级色轮不同）
- **Shadow**：暗部区域
- **Midtone**：中间调

**HDR Scopes**：
- **HDR Waveform**：0-10,000 nits 轴向显示
- **HDR Histogram**：PQ 码值分布的直方图
- **False Color HDR**：实时亮度伪色映射

### 核心 HDR 调色步骤

1. **色彩空间转换**：输入色彩空间 → Resolve Color Managed 或 ACES
2. **一级调色**：使用 HDR 色轮调整全局黑位/亮度/对比度
3. **HDR 范围选择**：基于亮度的二级选区（例如仅调整 500-1000 nits 区域）
4. **动态元数据**：为 Dolby Vision 或 HDR10+ 生成 Trim Passes
5. **SDR Trim Pass**：同时创建 SDR 版本（反向色调映射）

### ACES 与 HDR

ACES 1.3+ 完整支持 HDR 工作流：

```
ACEScc (Log) → ACES 2065-1 (AP0) → Output Transform (PQ + Rec.2020)
```

ACES Output Device Transform (ODT) 选项：
- `Rec.2020-ST2084 (1000 nits)`：Dolby Vision 家庭显示
- `Rec.2020-ST2084 (2000 nits)`：高亮监看
- `Rec.2020-ST2084 (4000 nits)`：影院级参考

## SDR → HDR 转换

有时需要将 SDR 素材上变换为 HDR——这是色调映射的逆操作。

**方法**：
1. **AI 辅助**：Topaz Video AI (SDR to HDR model)、DaVinci Resolve Neural Engine
2. **手动重建**：扩宽对比度、恢复高光裁切区域、扩展色域
3. **生成式 AI**：填补 SDR 中不存在的高光细节

**关键约束**：
- SDR 中裁切的高光**无法真正恢复**
- 噪点面板在 PQ 曲线下会被放大
- SDR 转 HDR 是**创意决策**而非校正

## HDR 交付格式

| 格式 | Profile | 位深 | Color Space | 元数据 |
|------|---------|------|-------------|--------|
| **Dolby Vision Profile 5** | 单层 + IPT | 12-bit | Rec.2020+P3 | 每帧动态 RPU |
| **Dolby Vision Profile 8** | 单层 + MEL | 10-bit | Rec.2020 | 最小增强层 |
| **HDR10** | SMPTE ST 2086 | 10-bit | Rec.2020 | 静态元数据 |
| **HDR10+** | SMPTE ST 2094-40 | 10-bit | Rec.2020 | 每场景动态 |
| **HLG** | ARIB STD-B67 | 10-bit | Rec.2020 | 无需元数据 |

**流媒体交付**：
| 平台 | HDR 格式要求 |
|------|-------------|
| Netflix | Dolby Vision Profile 5 (MEL) / HDR10 |
| Apple TV+ | Dolby Vision Profile 5 |
| YouTube | HDR10 (PQ) / HLG |
| Amazon Prime | HDR10+ / Dolby Vision |
| Disney+ | Dolby Vision |
| 全球广播 | HLG (BBC NHK 标准) |

### Dolby Vision 母版编码

Dolby Vision 母版流程：
1. 从调色系统输出 **HDR10 基础层**（Profile 5 或 8）
2. 生成 **RPU** (Reference Processing Unit) ——包含每帧动态元数据
3. 可选：添加 **增强层** (EL) 支持 12-bit
4. 生成 **Trim Passes**——将调色师的创意决策映射到不同峰值亮度的显示设备

## HDR 监控与 QC

| 监看设备 | 峰值亮度 | 适用阶段 |
|---------|---------|---------|
| Sony BVM-HX3110 | 4,000 nits | 调色参考（参考级） |
| Dolby Pulsar (PRM-4220) | 4,000 nits | Dolby Vision 认证 |
| Flanders Scientific XM311K | 1,000 nits | 调色参考（性价比） |
| Apple Pro Display XDR | 1,600 nits | 参考/HDR 预监 |
| LG OLED C/G 系列 | 800-1000 nits | 消费者级代理监看 |

**QC 检查**：
- 亮度合规：控制 APL (Average Picture Level) 避免过度刺激
- 色域裁切：检查 Rec.2020 边界
- 元数据正确性：MaxCLL / MaxFALL 值
- 跨设备一致性：在不同峰值亮度显示器验证 Trim Passes
- SDR Trim Pass：确认 SDR 版本不是"扁平的 HDR"

## 关键链接

- [[concepts/进阶 调色 调色|调色进阶（ACES/HDR）]] — 已有的调色/ACES 内容
- [[concepts/调色 理论 影调|色彩理论与调色方案]]
- [[concepts/调色 调色 工作流|调色工作流]]
- [[concepts/摄影机 RAW 格式|摄影机 RAW 格式]]
- [[concepts/进阶 视频 压缩|视频压缩与编码参数]] — HDR 编码相关
