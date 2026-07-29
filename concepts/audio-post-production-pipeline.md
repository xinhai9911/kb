---
title: 音频后期制作管线
category: concepts
tags: [audio, post-production, sound-design, dialogue-editing, mixing, foley]
created: 2026-07-29
updated: 2026-07-29
summary: 视频音频后期全流程——从 NLE 交接（AAF/OMF）到最终缩混的六个阶段
relationships:
  - target: "[[concepts/offline-online-workflow]]"
    type: part_of
  - target: "[[concepts/split-edits-j-cut-l-cut]]"
    type: related_to
  - target: "[[entities/avid-pro-tools]]"
    type: uses
base_confidence: 0.7
lifecycle: draft
lifecycle_changed: 2026-07-29
sources:
  - "[[sources/audio-post-forte-ai]]"
---

# 音频后期制作管线

## 概述

音频后期（Audio Post-Production）是将剪辑阶段的"临时"音频加工为最终影院 / 流媒体品质混音的过程。完整的管线分为六个阶段，从与画面剪辑的交接开始，到最终混音回填（Layback）结束。

## 阶段一：交接（Handoff）

- **AAF / OMF**：从 NLE 导出音频编辑到 DAW 的标准格式
  - OMF（老标准，有 2GB 文件限制）
  - AAF（现代标准，无大小限制，保留编辑 / 淡变 / 时间伸缩）
- **嵌入式 vs 参考式**：音频直接嵌入文件 / 或链接到源音频文件
- **时码同步**：每个音轨锁定到 SMPTE 时码轨道

## 阶段二：对白编辑（Dialogue Editing）

- **清理与修复**（Denoise / De-click / De-clip / Mouth Click 去除）
- **电平统一**：贯穿整片的对白音量标准化（-24 LUFS / -12 dB 峰值）
- **ADR（自动对白替换）**：现场录音不可用时的棚录解决方案
  - 同步标记（Slate + 2-Pop + Beep Track）
  - 口型同步 + Room Tone 环境匹配
- **BGM 与现场音**：背景群杂（Walla）替换 / 增强

## 阶段三：音效设计（Sound Design）

- **硬效果（Hard Effects）**：精确同步的动作声音（开关门、脚步、枪声）
- **Foley（拟音）**：在录音棚按画面实时录制同步音效
  - 脚步声（不同地面材质）
  - 衣物摩擦
  - 道具操作（拿杯子、翻书）
- **环境音（Ambience / BG）**：场景基础氛围音（森林、城市、室内空调）
- **设计音效（Design Effects）**：合成/分层的声音（科幻、怪物、魔法）

## 阶段四：配乐（Music）

- **对点配乐（Spotting Session）**：与导演/作曲家确定配乐入出点
- **配乐版权管理**：原创配乐 vs 授权音乐（Needle Drop）vs 免版权库
- **混音角色**：情绪铺底、高潮渲染、转场桥接、沉默对比

## 阶段五：缩混（Mixing）

- **电平平衡参考**：对白 ~ -12 dB、音效 ~ -18 dB、音乐 ~ -24 dB
- **空间定位**：立体声全景 → 5.1 / 7.1 / Dolby Atmos（对象音频）
- **动态处理**：压缩器（电平控制）+ 限制器（True Peak 保护）+ 扩展器
- **EQ 与空间**：高低切（Hi-Pass / Low-Pass）、混响（Reverb）、延迟（Delay）

## 阶段六：最终混音与回填（Final Mix & Layback）

- **Stem 分组导出**：对白 / 音效 / 音乐 分别导出（Stem）
- **Layback**：最终混音回填到 NLE 时间线 → 与画面同步导出母版
- **M&E（Music & Effects）**：无对白的国际声道版

## 响度标准（LUFS）

| 平台 | 集成响度 | True Peak |
|------|---------|-----------|
| YouTube | -14 LUFS | -1 dB |
| 广播（ITU-R BS.1770） | -23 LUFS | -2 dB |
| 影院 / Netflix | -27 LUFS | -3 dB |
| Spotify / Apple Music | -14 LUFS | -1 dB |
