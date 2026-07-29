---
kind: source
title: "Offline and Online Video Editing: The Ultimate Guide"
alias: ["Shot AI 工作流管线"]
creators: [Shotstack]
year: 2025
url: https://shotstack.io/learn/offline-online-video-editing/
related:
  - concepts/offline-online-workflow
  - concepts/proxy-workflow
  - concepts/mezzanine-codec
tags:
  - workflow
  - offline-editing
  - online-editing
  - conform
category: reference
updated: 2026-07-29
summary: 离线/在线编辑流程详解：从离线剪辑（代理/粗剪）到在线精编（回套/调色/最终输出）的完整管线
created: 2026-07-29
lifecycle: draft
sources: []
base_confidence: 0.7
---

# Offline and Online Video Editing: The Ultimate Guide

## 概述

Shotstack（云视频 API 提供商）对离线/在线（Offline / Online）编辑流程的系统讲解。这是专业视频后期制作的经典分阶段工作流模型。

## Offline 阶段（离线剪辑）

**目标**：在低分辨率代理文件上完成剪辑决策（故事结构、节奏、镜头选择），最大化效率和可协作性。

- **代理文件（Proxies）**：Camera Raw → 媒体管理 → 生成低分辨率代理（如 1080p ProRes Proxy / DNxHR LB）
- **核心工作**：素材浏览、挑选、初剪（Assembly Cut）、精剪（Fine Cut）
- **输出**：EDL/XML/AAF + 时间线元数据 → 回套给 Online 阶段
- **关键角色**：剪辑师（Editor）主导

## Online 阶段（在线精编）

**目标**：将离线决策恢复为全分辨率原始素材，完成最终视觉效果。

- **回套（Conform）**：导入离线 EDL/XML/AAF，自动重新连接（Reconnect）高分辨率原始素材
- **核心工作**：调色（Color Grading）、视觉特效（VFX/Compositing）、音频精加工（Audio Post-Production）
- **审核与批注**：生成样片（Answer Print / Digital Intermediate）供导演/制片审核
- **关键角色**：调色师（Colorist）、特效师（VFX Artist）、混音师（Sound Mixer）

## Conform（回套）的挑战

- **Reconnect 失败**：素材改名、路径移动 → 手动重新定位（Relink）
- **速度变化**：离线中的变速剪辑需 Online 精确重建
- **多层复合**：嵌套时间线 / Adjustment Layer / Compound Clip 需要展平
- **跨平台**：Avid → Resolve / Premiere → Resolve 的 EDL/XML 兼容性问题

## 现代趋势

- **云端 / SaaS**：Blackbird、Mimir、Shotstack 云编辑打破传统 Offline/Online 物理边界
- **无代理回套**：Resolve、FCP 可直接编辑原始素材（现代硬件 + 高效编解码器）
- **轻量级 Online**：YouTuber / 独立制作人将 Offline 和 Online 合二为一
- **AI 辅助**：自动转写、基于文本的剪辑、AI 粗剪

## 关键术语

- **EDL (Edit Decision List)**：最基础的剪辑决策表（CMX3600 格式）
- **高级回套格式**：AAF（Avid）、FCPXML（Final Cut）、DRP（Resolve）
- **时间线互操作**：Time In/Out、Reel Name、Source File Path 的精确对应
- **Master File**：最终交付的母版文件（无字幕的完成版本）
