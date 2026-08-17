---
aliases: ["audio-post-forte-ai"]
kind: source
title: "Audio Post-Production for Video: A Complete Guide"
alias: ["Forte AI 音频后期指南"]
creators: [Forte AI]
year: 2025
url: https://blog.forte-ai.com/audio-post-production-for-video-a-complete-guide/
related:
  - concepts/audio-post-production-pipeline
  - concepts/offline-online-workflow
  - entities/avid-pro-tools
tags:
  - audio
  - post-production
  - sound-design
  - mixing
category: reference
updated: 2026-07-29
summary: 视频音频后期全流程：从与剪辑的交接到最终混音，涵盖对白编辑、ADR、Foley、音效设计等环节
created: 2026-07-29
lifecycle: draft
sources: []
base_confidence: 0.7
---

# Audio Post-Production for Video: A Complete Guide

## 概述

Forte AI 提供的一套完整的视频音频后期制作指南，涵盖从剪辑交接（Handoff）到最终混音（Final Mix）的全流程。

## 音频后期管线

### Step 1: Handoff（从剪辑交接）

- **AAF/OMF**：从 NLE 导出到 DAW 的标准格式；包含时间线编辑、交叉淡变、时间伸缩
- **Session 传输**：直接传递 DAW Session（Pro Tools）、或通过回填 OMF 完成
- **Timecode 同步**：每个音轨锁定到 SMPTE 时码轨道

### Step 2: Dialogue Editing（对白编辑）

- **清理**：去除环境噪音、口唇声、口水音（De-click / De-noise）
- **电平标准化**：保持对白贯穿一致的音量（-24 LUFS / -12 dB 峰值为标准）
- **ADR（自动对白替换）**：无法使用的录制 → 录音棚重新录制同期声
  - 同步标记（Beep track / 2-pop）、口型同步、环境匹配（Room Tone）

### Step 3: Sound Design（音效设计）

- **硬效果（Hard Effects）**：与画面同步的精确动作声音（关门、脚步声、枪声）
- **Foley（拟音）**：在录音棚对照画面录制同步音效（脚步声、衣物摩擦、道具操作）
- **背景环境音（Ambience / BG）**：场景的基础氛围音（室外风声、室内空调嗡嗡声）
- **设计音效**：需要合成或分层设计的特殊声效（科幻武器、怪物叫声）

### Step 4: Music（配乐）

- **对点配乐（Spotting）**：与导演/作曲家标记配乐入出点
- **版权管理**：原创配乐、授权音乐库（Needle Drop）、免版权音乐
- **混音中的音乐角色**：铺设情绪、渲染高潮、转场过渡

### Step 5: Mixing（混音）

- **电平平衡**：对白 ~ -12 dB、音效 ~ -18 dB、音乐 ~ -24 dB（参考值，视内容调整）
- **全景声**：5.1 / 7.1 / Dolby Atmos 定位（对象音频 vs 声道音频）
- **响度标准化**：ITU-R BS.1770 标准（YouTube -14 LUFS、广播 -23 LUFS、影院 -27 LUFS 等）
- **动态处理**：压缩器（压缩比例）、限制器（True Peak 控制）、扩展器

### Step 6: Final Mix & Layback

- **Stem 交付**：对白 / 音效 / 音乐 分组导出（Stem）
- **Layback**：最终混音回填到 NLE 时间线 → 与画面同步导出母版
- **M&E（Music & Effects）**：不包含对白的国际声道版本（用于海外发行）

## 关键工具

- **DAW**：Avid Pro Tools（行业标准）、Adobe Audition、Steinberg Nuendo、Blackmagic Fairlight（内建于 Resolve）
- **插件**：iZotope RX（降噪/修复）、Waves（混响/压缩）、Soundtoys（创意效果）
- **硬件**：调音台（Avid S6 / SSL）、监听音箱（Genelec / Yamaha NS-10）、话筒（Sennheiser MKH 416）
