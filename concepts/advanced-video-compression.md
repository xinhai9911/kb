---
title: 视频压缩与编码参数进阶
category: concepts
tags: [video-editing, compression, encoding, h264, hevc, av1, codec, post-production]
created: 2026-07-30
updated: 2026-07-30
summary: 视频压缩编码核心参数、码率控制策略、编码器选型与 FFmpeg 实战——从 H.264 到 AV1 的完整技术图谱
lifecycle: draft
base_confidence: 0.8
---

# 视频压缩与编码参数进阶

## 概述

视频压缩是后期制作交付环节最核心的技术之一。从 H.264 到 AV1，编码参数的选择直接影响画质、文件大小、渲染速度和播放兼容性。本文不讨论编解码基础原理，而是聚焦**实际编码决策**——参数调优与编码策略。

## H.264 / x264 参数深度

x264 是目前最成熟、文档最完善的视频编码器。关键参数分四层：

### Preset（速度/压缩比）

| Preset | 使用场景 | 相对速度 |
|--------|---------|---------|
| ultrafast | 代理预览、Live 流 | 基准 |
| veryfast | 快速审查 | ~50% slower |
| faster | 日常编码 | ~100% slower |
| fast | 质量与速度平衡 | ~150% slower |
| medium | **默认档**，通用场景 | ~200% slower |
| slow | 高质离线编码 | ~300% slower |
| slower | 归档级质量 | ~500% slower |
| veryslow | 最终交付，极致压缩 | ~800% slower |
| placebo | 几乎无收益的超慢档 | ~1000%+ slower |

**Preset 越高 → 编码越慢 → 压缩率越高（同等 CRF 下文件越小）**。

### Profile 与 Level

Profile 决定编码功能集：

| Profile | 功能支持 | 典型使用 |
|---------|---------|---------|
| Baseline | I/P-frame, CAVLC | 低端设备、视频会议 |
| Main | I/P/B-frame, CABAC, MBAFF | 较老设备 |
| High | 8-bit, 4:2:0 | **通用交付标准** |
| High 10 | 10-bit 支持 | x265 常见 |
| High 422 / High 444 | 专业色度采样 | VFX 中间件、归档 |

Level 约束分辨率和码率上限（如 Level 4.1 = 1080p@30fps, Level 5.1 = 4K@30fps）。

### CRF vs 2-pass VBR

| 模式 | 原理 | 适用场景 |
|------|------|---------|
| **CRF** (单 Pass) | 设定感知质量（默认 23），编码器自动分配码率 | 归档、本地存储、调色参考 |
| **1-pass VBR** | 设定目标码率，编码器一次通过 | 实时流、低延迟 |
| **2-pass VBR** | 第一遍分析复杂度 → 第二遍精确分配码率 | **流媒体交付**、广播 |
| **CBR** | 恒定码率 | Live 流、硬件约束 |

**CRF 数值建议**：
- 18–19：视觉无损（归档级）
- 20–22：高端流媒体交付
- 23（默认）: 高质量通用
- 24–26：主流流媒体（Netflix/YouTube 实际值）
- 27–28：轻量存储 / 移动端

2-pass VBR 流媒体典型命令：
```
ffmpeg -i input -c:v libx264 -b:v 8000k -pass 1 -f null -
ffmpeg -i input -c:v libx264 -b:v 8000k -pass 2 output.mp4
```

## H.265 / HEVC 与 x265 参数差异

x265 在 x264 参数体系基础上增加了更多高级控制：

**关键差异**：
- 默认 CRF 偏移：x265 默认 28（视觉等价于 x264 的 23）
- Preset 名称一致但每档的速度差异更大
- Profile：Main (8-bit) / Main10 (10-bit, **强烈推荐**) / Main12
- Level 分号相同，但码率效率比 H.264 高约 30–50%

x265 独有参数：

| 参数 | 作用 | 建议 |
|------|------|------|
| `-x265-params limit-sao=0` | 关闭 SAO 滤波器 | 部分场景防模糊 |
| `-x265-params no-strong-intra-smoothing=1` | 关闭帧内平滑 | 保留纹理细节 |
| `-x265-params aq-mode=3` | 自适应量化模式 3（自动） | 提升暗部质量 |
| `-x265-params deblock=1:1` | 去块滤波器强度 | 默认即可 |
| `-x265-params subme=5` | 运动搜索精度（1-7） | 存档推荐 7 |

## AV1 编码现状与前景

### 编码器对比

| 编码器 | 速度 | 压缩率 | 成熟度 |
|--------|------|--------|--------|
| **libaom (aomenc)** | 极慢 | 最高 | 参考实现 |
| **SVT-AV1** | 中快 | 高 | 生产可用 |
| **rav1e** | 中 | 高 | 持续开发中 |
| **NVENC AV1** | 极快 | 中高 | RTX 40 系列硬件编码 |

### 现状评估

AV1 相比 HEVC 可再节省约 30% 码率（同等感知质量），但编码速度仍是软编码的瓶颈：

- **软件编码**：SVT-AV1 preset 8 约等于 x265 medium 速度的 1/5
- **硬件编码**：NVIDIA NVENC AV1 已接近 HEVC 效率，速度极快
- **规模化部署**：Netflix/YouTube/Apple 全面支持 AV1，B 站等国内平台跟进中
- **解码支持**：几乎所有现代设备（手机/电视/浏览器）支持 AV1 硬解

```
# SVT-AV1 编码示例
ffmpeg -i input.mov -c:v libsvtav1 -preset 8 -crf 30 -svtav1-params tune=0 output.mp4
```

## 按内容类型的编码策略

不同内容类型的视觉特性需要不同的编码参数：

| 内容类型 | 特性 | CRF 建议 | 额外调整 |
|---------|------|---------|---------|
| **电影/剧情片** | 低运动、暗部多 | 18–22 | 高 `aq-mode`，低 `deblock` |
| **动画/CGI** | 大面积纯色、锐利边缘 | 16–20 | 高强度 `deblock`，关闭 `psy` |
| **屏幕录制** | 文字/UI、变化少 | 19–24 | 8x8 DCT，`profile=high444` |
| **纪录片/实景** | 混合运动、自然纹理 | 20–23 | 默认即可 |
| **体育/动作** | 高强度运动、噪点多 | 22–26 | 相对较高 CRF（运动掩蔽效应） |
| **音乐视频** | 快切、特效多 | 19–22 | 低 `subme` 保留细节 |

## 码率分配策略

### 场景检测编码 (Scene-Aware Encoding)

传统编码器对整段视频使用相同质量参数。场景检测编码在场景切换处插入 **关键帧 (IDR)**，让分配更高效：

```
ffmpeg -i input.mp4 -c:v libx264 -force-key-frames "expr:gte(t,n_forced*5)" ...
```

更高级的方案——**Per-Title Encoding**（Netflix 首创）：

1. 分析内容复杂度（Motion / Spatial 指标）
2. 对每种分辨率使用多个 CRF 测试编码
3. 计算 VMAF 等质量指标
4. 选择"感知无损"的最低码率
5. 生成自定义编码 Ladder

Netflix 的每标题编码优化法的核心文献：`De Cock et al., "A Practical Per-title Encoding Method", NAB 2016`。

### GOP 结构

GOP (Group of Pictures) 结构决定编码效率和随机访问能力：

| GOP 参数 | 作用 | 典型值 |
|---------|------|--------|
| Keyint (GOP 长度) | 两关键帧之间的帧数 | `keyint=250`（~10s@24fps） |
| B-frame 数量 | B 帧越多人均码率越低但解码越重 | `bframes=3`（通用），`bframes=8`（HEVC 高效率） |
| B-pyramid | 层级 B 帧引用结构 | H.264/HEVC 默认开启 |
| Open GOP vs Closed GOP | 是否允许跨 GOP 引用 | Open GOP 更高效但精度略低 |

### 主观视觉优化 (Psychovisual Tuning)

编码器的"视觉心理学"——牺牲不敏感的精细度换取敏感区域的质量：

| 控制 | 含义 | 效果 |
|------|------|------|
| `psy-rd=1.0:0.15` (x264) | 心理视觉率失真优化 | 保留纹理感，过多导致伪影 |
| `aq-mode=3` (x265) | 自适应量化（按区域分配码率） | 改善暗部/平坦区质量 |
| `deblock=1:1` | 去块滤波器 | 减少块效应，过度则模糊 |
| `SAO` (x265) | 采样点自适应偏移 | HEVC 特有，减少振铃 |
| `no-cutree` | 关闭动态码率树 | 平稳场景不推荐 |

## FFmpeg 编码命令模板

### 存档级 H.264
```
ffmpeg -i input.mov -c:v libx264 -preset slow -crf 18 -profile:v high -level 4.1 \
  -pix_fmt yuv420p -c:a aac -b:a 320k output.mp4
```

### Netflix 风格 H.264 流媒体
```
ffmpeg -i input.mov -c:v libx264 -preset medium -b:v 8000k -maxrate 10000k -bufsize 16000k \
  -profile:v high -level 4.1 -x264-params "keyint=48:min-keyint=48:bframes=4" output.mp4
```

### H.265 (10-bit) 归档
```
ffmpeg -i input.mov -c:v libx265 -preset medium -crf 22 -pix_fmt yuv420p10le \
  -tag:v hvc1 -c:a aac -b:a 320k output.mp4
```

### AV1 流媒体
```
ffmpeg -i input.mov -c:v libsvtav1 -preset 8 -crf 30 -g 240 \
  -svtav1-params "tune=0:enable-overlays=1" -c:a libopus -b:a 192k output.mp4
```

### 代理预览 (H.264 ultrafast)
```
ffmpeg -i input.mov -c:v libx264 -preset ultrafast -crf 28 -vf "scale=1280:720" \
  -c:a aac -b:a 128k proxy.mp4
```

## 关键链接

- [[concepts/delivery-codec|交付 Codec 选择]]
- [[concepts/mezzanine-codec|中间件编码]]
- [[concepts/video-specs-compatibility|视频规格兼容性]]
- [[concepts/storage-archive-strategy|存储与归档策略]]
- [[concepts/proxy-workflow|代理工作流]]
