---
aliases: ["qc-delivery-standards"]
title: QC 与交付标准
category: concepts
tags: [video-editing, qc, delivery, netflix-specs, dcp, loudness, broadcast, post-production]
created: 2026-07-30
updated: 2026-07-30
summary: 视频交付全流程质量控制和交付标准——技术QC/内容QC/合规QC、流媒体/广播/影院交付规范、QC工具与交付清单
lifecycle: draft
base_confidence: 0.8
---

# QC 与交付标准

## 概述

质量控制（Quality Control, QC）是视频后期制作交付前的最终验收环节。QC 不是"挑错"，而是确保媒介满足**平台技术规范**和**制作质量要求**的最后防线。

一次完整的 QC 流程涉及三个层面：**技术 QC**（格式合规） → **内容 QC**（画面/音频质量） → **合规 QC**（响度/字幕/PSE 闪烁）。

## 全面质检流程

### QC 三阶段

```
技术 QC ────→ 内容 QC ────→ 合规 QC ────→ 修复 ───→ 重检 ───→ 交付
（格式规范）    （主观判断）    （法规要求）    （不通过项）
```

### 1. 技术 QC

技术 QC 是自动化程度最高的环节，由 QC 软件自动扫描：

| QC 项目 | 检测内容 | 严重等级 |
|---------|---------|---------|
| **黑帧/静帧** | 全黑画面超过阈值（如 5 帧） | Critical |
| **音频同步** | 唇形同步偏移（> 2 帧） | Critical |
| **编码错误** | Macroblocking、解码失败 | Critical |
| **帧率错误** | 实际帧率 ≠ 声明帧率 | High |
| **色域违规** | 像素超出指定色域 | High |
| **Bitrate 异常** | 峰值码率超出规格 | Medium |
| **音频电平** | 削波（Clipping）、过低 | Medium |
| **时长不匹配** | 实际时长与声明不符 | High |
| **Drop Frame 问题** | 时码不连续 | Medium |
| **字幕同步** | 字幕与画面偏移 | Low |
| **视频标题/TC *** | 烧录标题信息错误 | Low |

### 2. 内容 QC

由 QC 操作员（或有经验的剪辑师）人工审查：

- **画面问题**：色偏、噪点过度、镜头划痕/灰尘、焦点软、曝光异常
- **剪辑问题**：跳帧、硬切意外、重复镜头、缺失帧
- **音频问题**：嗡嗡声（Hum）、嘶声（Hiss）、录音电平不一致、背景噪音
- **VFX 问题**：边缘不自然、合成光不一致、匹配不准
- **整体观感**：场景转换流畅性、节奏是否合适

### 3. 合规 QC

自动化 + 人工检查的组合：

- [[concepts/字幕 本地化|字幕合规]]：拼写、时间轴精确度、位置合规
- 响度合规：ITU-R BS.1770 规定的 LUFS 目标值
- **PSE 闪烁测试**：Harding Test（图像闪烁癫痫风险评估）
- 广告插播标记（SCTE-35 / 断点信号）
- 平台 Logo / 品牌标识位置
- 年龄分级信息（BBFC / TV-MA / PG-13）

## 流媒体交付标准

### Netflix 技术规范

Netflix 的交付规格是最严格、最具影响力的流媒体标准之一。

**视频规格（Source Mezzanine）**：

| 参数 | 要求 |
|------|------|
| 分辨率 | 4K (3840x2160) 或 HD (1920x1080) |
| 帧率 | 23.976 / 24 / 25 / 29.97 / 50 / 59.94 |
| 编码 | ProRes 422 HQ / DNxHR HQX |
| 位深 | 10-bit |
| 色彩 | Rec.709 / Rec.2020 (SDR / HDR) |
| 像素宽高比 | 1:1 Square Pixel |
| 音频 | 24-bit / 48kHz PCM |

**IMF (Interoperable Master Format)**：
Netflix 要求以 **IMF** (SMPTE ST 2067) 交付主文件：
- **CPL** (Composition Playlist) ——定义播放结构
- **OPL** (Output Profile List) ——定义各平台输出映射
- **PKL** (Packaging List) ——定义文件列表
- 音轨和字幕以独立 Track File 交付

**音频规格**：
- 主音频：5.1 或 5.1 + Stereo
- 响度：**-27 LUFS** (LKFS) integrated (SDR) / **-24 LUFS** (HDR)
- True Peak：≤ -2 dBTP
- 对音频语言必须提供 CC (Closed Captions) 或 SDH 字幕

**Netflix IMS (Image Master Specification)**：
- 色域裁切测试
- 无 3:2 pulldown
- 黑电平必须为合法 (100% 黑位)
- 必须有至少 2 帧 Bar Code（100% 黑）在开头

### Apple iTunes Store 交付

- 编码：ProRes 422 HQ
- 分辨率：HD (1920x1080) / 4K (3840x2160)
- HDR：Dolby Vision Profile 5 (MEL) + HDR10
- 音频：5.1 + Stereo, -24 LUFS
- 字幕：iTT (iTunes Timed Text)
- 必须通过 Apple Compressor 或第三方认证发布工具打包

### YouTube 推荐规格

- **上传格式**：ProRes 422 / H.264
- **推荐编码**：H.264 High Profile, 10-20 Mbps (1080p), 35-50 Mbps (4K)
- **音频**：AAC-LC 320kbps 或 FLAC
- **HDR 格式**：PQ (HDR10) 或 HLG，请务必上载前套正确色彩元数据
- **最大文件**：256 GB
- **内容 ID**：版权声明系统

## 广播交付标准

### PSE (Photosensitive Epilepsy) 闪烁测试

这是广播交付中最独特的合规要求：

- 基于 Ofcom (英国) / ITC / ARIB 标准
- 检测画面中红色闪光频率（禁止 > 3Hz 且超过某一区域占比）
- 使用 **Harding Test** 或 **PSE Analyzer**
- Netflix / Amazon / YouTube 也逐步引入闪烁风险检测

### 响度标准 (ITU-R BS.1770)

| 地区/平台 | 整合响度 | 宽容度 |
|----------|---------|--------|
| ITU-R BS.1770 (全球) | -24 LUFS | -24 ±2 LUFS |
| ATSC A/85 (美国) | -24 LKFS | -24 ±2 |
| EBU R128 (欧洲) | -23 LUFS | -23 ±0.5 |
| OP-59 (日本) | -24 LKFS | -24 ±2 |
| Netflix | -27 LUFS | -27 ±2 |
| YouTube | -14 LUFS | (参考值，不严格) |
| Apple 播客 | -16 LUFS | -16 ±1 |

响度归一化的核心工具：
```
# FFmpeg 响度归一化（EBU R128）
ffmpeg -i input.wav -af loudnorm=I=-23:LRA=7:tp=-2 output.wav
```

### 字幕合规 (广播)

- 字幕必须以独立格式交付（不是 Burn-in）
- **OP-47 / DVB Subtitling**：欧洲广播字幕标准
- **CEA-608/708**：北美/ATSC 字幕标准
- 字幕延迟必须在 ±2 帧内

## 影院交付标准

### DCP (Digital Cinema Package)

DCP 是影院发行的数字母版格式，基于 DCI 规范。

| 参数 | 规格 |
|------|------|
| **视频编码** | JPEG 2000 (每帧独立编码) |
| **分辨率** | 2K (1998x1080) / 4K (3996x2160) |
| **帧率** | 24 / 48 |
| **位深** | 12-bit XYZ |
| **色域** | DCI-P3 (XYZ 编码) |
| **音频** | 24-bit / 48kHz / 16 通道 |
| **字幕** | PNG 图像序列 |
| **加密** | AES-128 |
| **密钥** | KDM (Key Delivery Message) |

### ISDCF 命名规范

DCP 文件必须遵循 ISDCF (Inter-Society Digital Cinema Forum) 命名：

```
Title_Version-Type_Resolution_AspectRatio_Rate_Language_Subtitles_etc
```
例如：
```
THE_MATRIX_REVIVAL_TRL_L_2K_S_DR_24_EN-XX_51_200101_FOX_VF
```

### 影院 QC 特殊项

- **JPEG 2000 编码质量验证**：检查 Quantization 伪影
- **XYZ 色彩转换正确性**：P3 色域检查
- **KDM 时效性**：密钥有效期验证
- **音频通道对应**：16 通道正确映射
- **字幕可读性**：字幕位置不遮挡画面关键内容

## QC 工具

### 自动化 QC 平台

| 工具 | 开发商 | 核心能力 | 价格 |
|------|--------|---------|------|
| **Aurora** | Venera Technologies | 全面技术 QC，云/本地 | 企业起 |
| **Interra Baton** | Interra Systems | IMF/DCP/流媒体全格式覆盖 | 企业起 |
| **VidChecker** | DaVinci Resolve Studio | Resolve 内置 QC 工具（Studio 版） | 免费内置 |
| **MediaAnalyzer** | IABM / 多家 | 响度 + 视频分析 | 按需 |
| **Telestream Switch** | Telestream | 人工 QC + 播放检查 | $299 |

### DaVinci Resolve QC 工作流

Resolve 提供强大的内置 QC 能力（Studio 版）：
1. **VidChecker**：自动扫描黑帧、静帧、音频 dropout、编码错误
2. **Live QC**：播放中实时检查（帧率、电平、色域）
3. **Scopes**：Waveform / Vectorscope / RGB Parade 质检
4. **响度表**：利用 Fairlight 的 Loudnorm 完成 ITU-R BS.1770 合规

### 流媒体 QC 组合建议

| 预算级别 | 推荐工具链 |
|---------|-----------|
| 低预算 / 独立 | DaVinci Resolve VidChecker + 人工 QC |
| 中等预算 | Telestream Switch + 人工 QC + 手写检查清单 |
| 企业预算 | Interra Baton (自动) + Aurora (云 QC) + 人工复审 |

## 交付清单模板

### 通用交付检查清单

**文件层面**：
- [ ] 文件命名符合规范
- [ ] 主文件格式正确（ProRes / DNxHR / IMF）
- [ ] 无黑帧（≤ 5 帧异常）
- [ ] 无静帧（≤ 5 帧异常）
- [ ] 视频起始正确（无错误黑帧或 Slate 未移除）

**视频层面**：
- [ ] 分辨率正确（检查实际分辨率 vs 声明分辨率）
- [ ] 帧率正确（23.976 / 29.97 / 25 / 24 / 50 / 59.94）
- [ ] 像素宽高比正确（1:1 Square Pixel）
- [ ] 色域合规（Rec.709 / Rec.2020）
- [ ] 位深合规（8-bit / 10-bit）
- [ ] 无编码伪影

**音频层面**：
- [ ] 采样率：48kHz
- [ ] 位深：24-bit
- [ ] 整合响度（ITU-R BS.1770）
- [ ] True Peak ≤ -2 dBTP
- [ ] 最低响度通道无中断
- [ ] 音频同步（唇形同步在 ±2 帧内）
- [ ] 无削波

**字幕层面**：
- [ ] 格式正确（SRT / VTT / SCC / iTT）
- [ ] 时间轴对齐（±2 帧）
- [ ] 语法/拼写错误为 0
- [ ] 显示时长足够（最少 1s，最多 7s 每行）
- [ ] 位置不覆盖关键画面

**合规层面**：
- [ ] PSE 闪烁测试通过（Harding Pass）
- [ ] 品牌标识位置正确
- [ ] 年龄分级信息嵌入
- [ ] 广告标记（如适用）

## 关键链接

- [[concepts/交付 编解码器|交付 Codec 选择]]
- [[concepts/夹层 编解码器|中间件编码]]
- [[concepts/字幕 本地化|字幕与本地化]]
- [[concepts/视频 规格 兼容性|视频规格兼容性]]
- [[concepts/进阶 视频 压缩|视频压缩与编码参数进阶]]
- [[concepts/音频 后期 制作 流水线|音频后期流水线]]
- [[concepts/DIT 工作流|现场 DIT 与数据管理]] — Dailies QC 基础
