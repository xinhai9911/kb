---
title: 视频后期制作流水线全景
category: synthesis
tags: [video-editing, pipeline, post-production, workflow, workflow-overview]
created: 2026-07-29
updated: 2026-07-30
summary: 视频后期制作流水线的完整图景——从拍摄原始素材到最终交付的端到端流程
relationships:
  - target: "[[concepts/offline-online-workflow]]"
    type: synthesizes
  - target: "[[concepts/color-grading-workflow]]"
    type: synthesizes
  - target: "[[concepts/audio-post-production-pipeline]]"
    type: synthesizes
  - target: "[[concepts/mezzanine-codec]]"
    type: synthesizes
  - target: "[[concepts/delivery-codec]]"
    type: synthesizes
  - target: "[[concepts/proxy-workflow]]"
    type: synthesizes
  - target: "[[concepts/narrative-psychology-editing]]"
    type: synthesizes
  - target: "[[50-reference/montage-techniques]]"
    type: synthesizes
base_confidence: 0.8
lifecycle: draft
lifecycle_changed: 2026-07-29
sources:
  - "[[sources/nle-comparison-larry-jordan]]"
  - "[[sources/workflow-pipeline-shot-ai]]"
  - "[[sources/codec-guide-mpegflow]]"
  - "[[sources/audio-post-forte-ai]]"
  - "[[sources/color-management-cinapex]]"
  - "[[sources/film-cognition-plos-one]]"
  - "[[sources/codec-guide-mpegflow]]"
  - "[[sources/nle-comparison-larry-jordan]]"
  - "[[sources/workflow-pipeline-shot-ai]]"
relationships:
  - target: "[[concepts/offline-online-workflow]]"
    type: synthesizes
  - target: "[[concepts/color-grading-workflow]]"
    type: synthesizes
  - target: "[[concepts/audio-post-production-pipeline]]"
    type: synthesizes
  - target: "[[concepts/mezzanine-codec]]"
    type: synthesizes
  - target: "[[concepts/delivery-codec]]"
    type: synthesizes
  - target: "[[concepts/proxy-workflow]]"
    type: synthesizes
  - target: "[[concepts/narrative-psychology-editing]]"
    type: synthesizes
  - target: "[[50-reference/montage-techniques]]"
    type: synthesizes
  - target: "[[concepts/ai-in-post-production]]"
    type: synthesizes
  - target: "[[concepts/collaboration-versioning]]"
    type: synthesizes
  - target: "[[concepts/camera-raw-formats]]"
    type: synthesizes
  - target: "[[concepts/nle-power-tips]]"
    type: synthesizes
  - target: "[[concepts/storage-archive-strategy]]"
    type: synthesizes
  - target: "[[concepts/advanced-vfx-matchmove]]"
    type: synthesizes
  - target: "[[concepts/color-science-gamut]]"
    type: synthesizes
  - target: "[[concepts/adr-dubbing-workflow]]"
    type: synthesizes
  - target: "[[concepts/music-video-editing]]"
    type: synthesizes
  - target: "[[concepts/sports-fast-cut-editing]]"
    type: synthesizes
---

# 视频后期制作流水线全景

## 概述

视频后期制作（Post-Production）是将拍摄原始素材（Camera Raw）最终加工为交付成品的过程。这不是一条简单直线，而是一条**多阶段、多角色、多工具协作**的流水线。本文整合 8 个核心概念、6 个实体工具和 6 个来源，呈现当代视频后期制作的完整图谱。

## 流水线总览

```
Camera / Production                    Post-Production                      Distribution
┌─────────────────┐     ┌─────────────────────────────────────────┐     ┌─────────────────┐
│ 拍摄原始素材     │     │                                          │     │ 最终交付         │
│ ARRIRAW / RED   │────→│  Offline  →  Online  →  Master  → QC   │────→│ YouTube / Netflix│
│ BRAW / H.264  │     │  (剪辑)     (调色/VFX)   (母版)    (质检) │     │ 广播 / 影院     │
│ S-Log / V-Log   │     │                                          │     │ HLS / DCP       │
└─────────────────┘     └─────────────────────────────────────────┘     └─────────────────┘
                              ↓ 并行协作 ↑
                         ┌────────────────┐
                         │ 音频后期        │
                         │ 对白→Foley→混音  │
                         └────────────────┘
```

## 三条并行的子流水线

### 1. 画面流水线（Picture Pipeline）

核心路径：**拍摄格式 → 代理剪辑 → 回套 → 调色 → VFX → 母版**

| 阶段 | 关键工作 | 主导角色 | 核心工具 |
|------|---------|---------|---------|
| 媒体管理 | 转码、归档、元数据 | DIT / 助理剪辑 | Resolve / Silverstack |
| [[concepts/proxy-workflow|代理剪辑]] | 粗剪→精剪→定剪 | 剪辑师 | Avid / Premiere / FCP / Resolve |
| [[concepts/offline-online-workflow|回套]] | 恢复全分辨率 | Online 剪辑师 | Resolve / Premiere |
| [[concepts/color-grading-workflow|调色]] | 一级→二级→HDR | 调色师 | Resolve / Baselight |
| VFX / 合成 | 绿幕、跟踪、粒子 | 特效师 | Fusion / Nuke / AE |
| 母版 | ProRes 4444 / DNxHR 444 | Online 剪辑师 | Resolve / Compressor |

### 2. 音频流水线（Audio Pipeline）

核心路径：**交接 → 对白编辑 → 音效设计 → 配乐 → 混音 → Stem 交付**

| 阶段 | 关键工作 | 主导角色 | 核心工具 |
|------|---------|---------|---------|
| [[concepts/audio-post-production-pipeline|Handoff]] | AAF/OMF 交接 | 音效剪辑师 | Pro Tools / Fairlight |
| 对白编辑 | Denoise / ADR / 电平统一 | 对白剪辑师 | Pro Tools + iZotope RX |
| [[concepts/audio-post-production-pipeline|Foley / 音效]] | 拟音录制、硬效果、环境 | 音效设计师 | Pro Tools / Soundminer |
| 配乐 | 对点、版权管理 | 作曲家 | Cubase / Logic Pro |
| [[concepts/audio-post-production-pipeline|Mixing]] | 全景声、LUFS 标准化 | 混音师 | Pro Tools HDX |
| Layback | Stem 输出 / 回填 NLE | 混音师 | Pro Tools / Fairlight |

### 3. 交付流水线（Delivery Pipeline）

核心路径：**母版 → 编码 → QC → 分發**

| 格式 | 场景 | Codec | 响度标准 |
|------|------|-------|---------|
| [[concepts/delivery-codec|流媒体]] | YouTube / Netflix | H.264 / AV1 / H.265 | -14~-27 LUFS |
| [[concepts/delivery-codec|广播电视]] | 电视台 / 新闻 | XDCAM / H.264 | -23 LUFS |
| [[concepts/delivery-codec|影院]] | DCP / DLP | JPEG 2000 | -27 LUFS |
| 母版归档 | 存档 / 重制 | ProRes 4444 XQ | N/A |

## 编解码器分层策略

```
Camera Raw (ARRIRAW / BRAW / S-Log)
    │
    ▼ 转码
[[concepts/mezzanine-codec|Mezzanine]] (ProRes 422 HQ / DNxHR HQ) ← 时间线主力格式
    │
    ▼ 调色 + VFX
[[concepts/mezzanine-codec|母版格式]] (ProRes 4444 / DNxHR 444)
    │
    ▼ 编码
[[concepts/delivery-codec|交付格式]] (H.264 / HEVC / AV1)
```

选择策略：Mezzanine 保质量，Delivery 保效率。

## 剪辑的心理学

后期不仅是一套技术流程。[[concepts/narrative-psychology-editing|剪辑的叙事心理学]]揭示了一个关键事实：**观众的大脑在被动观影时主动构建因果联系**。

- [[sources/film-cognition-plos-one|fMRI 证据]]：有序剪辑激活前额叶皮层，随机剪辑则否
- **预测编码**：J-Cut 的音频先入让大脑预测未来画面
- **剪辑流暢度**：流畅剪辑 → 沉浸吸收；不流畅剪辑 → 理性距离

这意味着优秀剪辑师不仅掌握工具和流程，还凭直觉利用人脑的认知机制。

## NLE 选择矩阵

| 项目类型 | 首选 NLE | 备选 | 原因 |
|---------|---------|------|------|
| 好莱坞长片 | [[entities/avid-media-composer|Avid MC]] | [[entities/davinci-resolve|Resolve]] | 合作 + Change List 不可替代 |
| 独立电影 / 短片 | [[entities/davinci-resolve|Resolve]] | [[entities/apple-final-cut-pro|FCP]] | 一体化流程 + 免费 |
| 调色为主项目 | [[entities/davinci-resolve|Resolve]] | Baselight | 调色行业标准 |
| YouTube / 自媒体 | [[entities/adobe-premiere-pro|Premiere]] / [[entities/apple-final-cut-pro|FCP]] | [[entities/capcut|CapCut]] | AE 生态 / 快速交付 |
| 竖屏社交 | [[entities/capcut|CapCut]] | Premiere | AI 功能 + 易用 |
| 音频后期 | [[entities/avid-pro-tools|Pro Tools]] | Fairlight | 行业标准 |

## 总结

视频后期制作不是一条单一流水线，而是**画面 + 音频 + 交付**三条并行的协作网络。每个环节涉及不同的工具、角色和标准。关键理解是：
1. **分层编解码**：从拍摄到交付的每一层需要不同的编码策略
2. **离线/在线分离**：将剪辑决策与视觉精加工分离，是专业流程的基石
3. **音频不可忽视**：好的画面 + 差的音频 → 失败的成品
4. **观众认知**：剪辑的心理学基础决定了哪些"手感"是对的

## 深挖补充

本篇第一轮覆盖了流水线全貌。以下第二轮深挖补充的知识点，提供更细粒度的技术概念和行业生态信息。

### 剪辑技术细节

| 方向 | 核心贡献 | 关联页面 |
|-----|---------|---------|
| 转场类型 | 硬切、溶解、淡入淡出、擦除、匹配切、Jump Cut、隐形剪辑等十几种转场的适用场景 | [[concepts/editing-transitions]] |
| 多机位剪辑 | 时间码/波形/打板同步、角度切换策略、各 NLE 多机位操作差异 | [[concepts/multicam-editing]] |
| 绿幕/合成 | 绿幕 vs 蓝幕选择、抠像工具（Delta Keyer / Keylight / Ultra Key）、跟踪基础 | [[concepts/chroma-key-compositing]] |
| 效率与素材管理 | 元数据标记体系、Bin 组织策略、各 NLE 杀手级功能（Magnetic Timeline / Auditions / ScriptSync） | [[concepts/editing-efficiency-workflow]] |
| 案例拆解 | 巴里·林登、教父、现代启示录、好家伙、落水狗逐镜头分析 | [[concepts/case-studies-famous-edits]] |
| 技术简史 | 物理剪辑→线性编辑→NLE 革命→AI 辅助的完整技术演进 | [[concepts/history-editing-technology]] |
| 行业生态 | 剪辑师在剧组的角色、助理剪辑师分级、Dailies → Picture Lock 全流程 | [[concepts/editor-industry-role]] |

### 关键人物

| 人物 | 核心贡献 | 关联页面 |
|-----|---------|---------|
| Walter Murch | 剪辑 6 优先级法则、"眨眼"理论、声音先行剪辑思维 | [[entities/walter-murch]] |
| Thelma Schoonmaker | Sprung Rhythm（断裂节奏）、暴力美学剪辑风格、Scorsese 50 年搭档 | [[entities/thelma-schoonmaker]] |

### 全景更新

```
                                                                                ┌─ [[concepts/editing-transitions]] ───┐
                                                                                ├─ [[concepts/multicam-editing]] ──────┤
                       第一轮覆盖流水线主干                                          ├─ [[concepts/chroma-key-compositing]] ─┤
                       ┌────────────────────────────────────────┐                ├─ [[concepts/editing-efficiency-workflow]]┤
                       │  拍摄 → 代理 → 离线剪辑 → 在线 → 调色 → VFX → 交付 │                ├─ [[concepts/case-studies-famous-edits]] ─┤
                       └────────────────────────────────────────┘                ├─ [[concepts/history-editing-technology]] ─┤
                                       +                                         ├─ [[concepts/editor-industry-role]] ─────┤
                                   音频流水线                                      ├─ [[entities/walter-murch]] ────────────┤
                                   交付流水线                                      └─ [[entities/thelma-schoonmaker]] ──────┘
                                                                                             第二轮补充
```

以上内容均为第二轮深挖成果。

## 第三轮深挖

本节是第三轮深挖的扩展方向，覆盖调色进阶、声音设计深挖、VFX/动态图形、纪录片剪辑，以及新增的关键人物实体。

### 调色进阶

| 方向 | 核心贡献 | 关联页面 |
|-----|---------|---------|
| ACES 色彩管理管线 | 设备无关的开源色彩标准：IDT → ACEScc → RRT → ODT 架构，AP0/AP1 色域定义 | [[concepts/advanced-color-grading]] |
| HDR 调色 | Dolby Vision / HDR10+ / HLG 技术对比；Trim Passes 工作流；SDR→HDR 上变换 | [[concepts/advanced-color-grading]] |
| 风格化调色流派 | Teal/Orange、Bleach Bypass、Desaturated Look、Film Emulation——每种风格的原理与实现 | [[concepts/advanced-color-grading]] |
| 颜色叙事节奏 | 时空区分、角色成长、情绪预警——调色如何作为剪辑语言 | [[concepts/advanced-color-grading]] |
| 知名调色师 | Walter Volpatto、Jill Bogdanowicz、Tom Poole、Company 3 现象 | [[entities/colorist-grades]] |

### 声音设计深挖

| 方向 | 核心贡献 | 关联页面 |
|-----|---------|---------|
| 声音三层次 | 对白 / 环境音 / 效果音的层次结构和优先级 | [[concepts/sound-design-deep-dive]] |
| Foley 艺术 | 历史起源（Jack Foley）、核心类别（脚步声/道具/衣物）、常见道具映射 | [[concepts/sound-design-deep-dive]] |
| 环境音构建 | 从立体声、5.1、7.1 到 Dolby Atmos 沉浸声场的工作流差异 | [[concepts/sound-design-deep-dive]] |
| 声音心理学 | 低频恐惧、高频紧张、沉默的力量——声音如何直接触发生理反应 | [[concepts/sound-design-deep-dive]] |
| 声音设计大师 | Ben Burtt（物理主义）vs Gary Rydstrom（情感主义）的哲学对比 | [[entities/sound-designer-ben-burtt]] / [[entities/gary-rydstrom]] |

### VFX / 动态图形

| 方向 | 核心贡献 | 关联页面 |
|-----|---------|---------|
| 运动跟踪 | 点跟踪、平面跟踪（Mocha）、3D Camera Tracking 的原理与工具 | [[concepts/vfx-motion-graphics]] |
| 画面稳定 | 完全锁定 / 轨迹平滑 / 局部稳定的策略差异 | [[concepts/vfx-motion-graphics]] |
| 混合模式 | Multiply / Screen / Overlay / Color 等核心模式的数学原理与合成应用 | [[concepts/vfx-motion-graphics]] |
| AE 工作流 | Comp 结构、Pre-compose、Null 对象、关键帧动画、表达式入门 | [[concepts/vfx-motion-graphics]] |
| 标题动画 | Lower Third、Kinetic Typography、MOGRT 模板导出、Text Animator | [[concepts/vfx-motion-graphics]] |

### 纪录片剪辑

| 方向 | 核心贡献 | 关联页面 |
|-----|---------|---------|
| 纪录片 vs 剧情片差异 | 素材比率、叙事发现 vs 演绎、剪辑师作为调查员的角色 | [[concepts/documentary-editing]] |
| 采访处理 | 全稿转录、金句标记、纸剪、Select Reel、伦理审查 | [[concepts/documentary-editing]] |
| B-roll 策略 | 覆盖/信息/情绪/节奏四大功能——"先声后画"编辑原则 | [[concepts/documentary-editing]] |
| 档案素材 | 版权风险评估、质感统一、格式内嵌、Ken Burns Effect | [[concepts/documentary-editing]] |
| 六种叙事模式 | Bill Nichols 的诗意/阐释/观察/参与/反身/展演型模式 | [[concepts/documentary-editing]] |
| 剪辑伦理 | 时间压缩、选取偏见、语境剥离、音乐操控——剪辑如何影响"真实" | [[concepts/documentary-editing]] |

### 全景更新

```
第一轮：流水线主干        第二轮：剪辑技术细节          第三轮：调色/声音/VFX/纪录片
┌──────────────┐       ┌────────────────┐           ┌──────────────────────────────┐
│ 拍摄→代理→   │       │ 转场类型        │           │ ACES/HDR 调色                │
│ 离线→在线→    │   +   │ 多机位剪辑       │     +     │ 声音设计深挖 / Foley          │
│ 调色→VFX→交付 │       │ 绿幕/合成        │           │ VFX 跟踪/AE 动态图形          │
│ 音频流水线    │       │ 效率/Bin 管理    │           │ 纪录片剪辑/伦理               │
│ 交付流水线    │       │ 案例拆解         │           │ 知名调色师/声音设计师          │
└──────────────┘       │ 技术简史         │           └──────────────────────────────┘
                       │ 行业角色         │
                       │ Murch/Schoonmaker│
                       └────────────────┘
```

### 关键人物（第三轮新增）

| 人物 | 核心贡献 | 关联页面 |
|-----|---------|---------|
| Walter Volpatto | 自然主义低饱和度调色、《小丑》视觉、HDR 先行者 | [[entities/colorist-grades]] |
| Jill Bogdanowicz | 画面叙事调色、电视剧电影化、《消失的爱人》 | [[entities/colorist-grades]] |
| Ben Burtt | 星战声音设计之父——光剑/R2-D2/Chewbacca/Vader 呼吸 | [[entities/sound-designer-ben-burtt]] |
| Gary Rydstrom | 7 次奥斯卡——拯救大兵瑞恩战争声景、皮克斯动画声音灵魂 | [[entities/gary-rydstrom]] |

## 第四轮深挖

本轮扩展 5 个新方向：AI 辅助剪辑、协作版本管理、摄影机 RAW 格式、NLE 高手技巧、存储归档策略。

### AI 辅助剪辑与后期

| 方向 | 核心贡献 | 关联页面 |
|-----|---------|---------|
| 转录与自动字幕 | Whisper + Premiere Text-Based Editing 重新定义了对白密集型剪辑工作流 | [[concepts/ai-in-post-production]] |
| AI 粗剪 | 文字即时间线——Text-Based Editing / Descript 直接操作转录稿完成粗剪 | [[concepts/ai-in-post-production]] |
| AI 调色匹配 | 自动色度匹配、参考帧分析、HDR AI 辅助，大幅缩短一级调色时间 | [[concepts/ai-in-post-production]] |
| AI 音频处理 | iZotope RX 频谱编辑、Adobe Podcast Enhance 一键降噪、AI ADR 同步 | [[concepts/ai-in-post-production]] |
| AI 视觉生成 | Runway Gen/Pika/Midjourney 辅助素材生成、对象移除、帧插值 | [[concepts/ai-in-post-production]] |
| 前景展望 | AI 不会取代剪辑师，但会淘汰不使用 AI 的剪辑师——剪辑师从"操作员"变为"策展人" | [[concepts/ai-in-post-production]] |

### 协作与版本管理

| 方向 | 核心贡献 | 关联页面 |
|-----|---------|---------|
| 多人协作方案 | Premiere Productions / Avid bin locking / FCP 共享库——三种迥异的架构 | [[concepts/collaboration-versioning]] |
| 远程工作流 | Frame.io C2C、Hedge Postlab、Evercast 实时审片、LucidLink 云挂载 | [[concepts/collaboration-versioning]] |
| 版本管理 | 命名规范、序列复制归档、Bin 级色彩标记、Git LFS / Perforce 极局限 | [[concepts/collaboration-versioning]] |
| 交换格式 | EDL / AAF / XML / OTIO / CDL——每种格式的适用场景和限制 | [[concepts/collaboration-versioning]] |
| 助理剪辑管线 | Dailies 转码、Bin 组织、序列管理、回套准备、交付导出 | [[concepts/collaboration-versioning]] |

### 摄影机 RAW 格式

| 方向 | 核心贡献 | 关联页面 |
|-----|---------|---------|
| 六大 RAW 格式 | ARRIRAW / REDCODE RAW / BRAW / ProRes RAW / Cinema RAW Light / X-OCN——压缩策略与工作流特性 | [[concepts/camera-raw-formats]] |
| 压缩对比 | 无损 vs 小波 vs 固定质量——解码性能、数据率、比特深度的系统对比 | [[concepts/camera-raw-formats]] |
| 传感器尺寸 | Super 35 / Full Frame / IMAX 对后期数据量、景深、抠像的影响 | [[concepts/camera-raw-formats]] |
| Log 曲线对比 | Log C / S-Log3 / V-Log / BMD Film / C-Log / N-Log——中灰点、动态范围、调色起点差异 | [[concepts/camera-raw-formats]] |
| 选择策略 | RAW vs Log vs Rec.709——根据制作类型决定拍摄格式 | [[concepts/camera-raw-formats]] |

### NLE 高手技巧

| 方向 | 核心贡献 | 关联页面 |
|-----|---------|---------|
| Premiere Pro 技巧 | Dynamic Link 与 AE、代理一键切换、Essential Sound 面板、轨道目标与 Source Patching | [[concepts/nle-power-tips]] |
| DaVinci Resolve | 剪辑到调色传送、Magic Mask 对象跟踪、Fusion 协同、Fairlight 音频清洗 | [[concepts/nle-power-tips]] |
| Final Cut Pro | Magnetic Timeline + 角色分配、后台渲染、复合片段与多机位、色板与效果关联 | [[concepts/nle-power-tips]] |
| 通用技巧 | 快捷键定制哲学、时间线搜索过滤、Marker 颜色编码最佳实践 | [[concepts/nle-power-tips]] |

### 存储、备份与归档

| 方向 | 核心贡献 | 关联页面 |
|-----|---------|---------|
| 三层存储架构 | Hot（现场）→ Warm（工作）→ Cold（归档）——每个层次的介质和策略 | [[concepts/storage-archive-strategy]] |
| RAID 选择 | RAID 0/1/5/6/10 的读写性能、容错能力、适用场景、大盘重建风险 | [[concepts/storage-archive-strategy]] |
| 归档媒介对比 | LTO-8/9 / HDD / SSD / 云 / M-Disc——寿命、成本、速度的全维度对比 | [[concepts/storage-archive-strategy]] |
| 数据完整性 | Checksum 拷贝、3-2-1 法则、ZFS/Btrfs Bit Rot 检测、Verify after Copy | [[concepts/storage-archive-strategy]] |
| 项目归档实践 | 媒体离线、清理无用素材、打包（Collect/Consolidate/Export）、元数据清单 | [[concepts/storage-archive-strategy]] |

### 全景更新

```
第一轮：流水线主干        第二轮：剪辑技术细节          第三轮：调色/声音/VFX/纪录片    第四轮：AI/协作/RAW/NLE/存储
┌──────────────┐       ┌────────────────┐           ┌──────────────────────────┐     ┌──────────────────────────────────┐
│ 拍摄→代理→    │       │ 转场类型        │           │ ACES/HDR 调色              │     │ AI 转录/粗剪/调色/音频/视觉生成     │
│ 离线→在线→    │   +   │ 多机位剪辑       │     +     │ 声音设计深挖 / Foley        │  +  │ 协作/版本/交换格式/远程工作流       │
│ 调色→VFX→交付 │       │ 绿幕/合成        │           │ VFX 跟踪/AE 动态图形        │     │ 六大 RAW 格式/Log 曲线/选择策略     │
│ 音频流水线    │       │ 效率/Bin 管理    │           │ 纪录片剪辑/伦理             │     │ Premiere/Resolve/FCP 高手技巧       │
│ 交付流水线    │       │ 案例拆解         │           │ 知名调色师/声音设计师        │     │ 三层存储/RAID/归档/数据完整性       │
└──────────────┘       │ 技术简史         │           └──────────────────────────┘     └──────────────────────────────────┘
                        │ 行业角色         │
                        │ Murch/Schoonmaker│
                        └────────────────┘
```

四轮深挖已完成。本 synthesis 页面现覆盖了视频后期制作的**流水线主干 → 剪辑技术细节 → 调色/声音/VFX/纪录片/人物 → AI/协作/RAW/NLE/存储归档**的全方位知识图谱。

## 第五轮深挖

本轮扩展 6 个新方向：AE/动态图形进阶、音频修复实战、色彩理论与调色方案、字幕/图形/本地化、视频规格兼容性、剪辑师职业发展。

### AE / 动态图形进阶

| 方向 | 核心贡献 | 关联页面 |
|-----|---------|---------|
| AE 核心架构 | 合成/图层/蒙版/轨道遮罩的层级关系和设计哲学 | [[concepts/advanced-motion-graphics]] |
| 表达式入门 | wiggle/loopOut/time/index/random/linear——最常用 8 个 JavaScript 表达式 | [[concepts/advanced-motion-graphics]] |
| 10 大内置效果 | 从 Curves/Gaussian Blur 到 Turbulent Displace/Radio Waves 的应用场景 | [[concepts/advanced-motion-graphics]] |
| 关键帧辅助 | Easy Ease (F9)、速度图表/值图表编辑、缓动曲线预设 | [[concepts/advanced-motion-graphics]] |
| 第三方插件 | Sapphire / Trapcode Particular / Element 3D / Motion Bro——核心功能对比 | [[concepts/advanced-motion-graphics]] |
| Dynamic Link | Adobe 生态核心优势——Premiere ↔ AE 实时合成回套工作流 | [[concepts/advanced-motion-graphics]] |

### 音频修复实战

| 方向 | 核心贡献 | 关联页面 |
|-----|---------|---------|
| 常见音频问题全表 | 底噪/风声/Click/Hum/混响/削波/齿音/嘶声/ Crackle 的成因和频段定位 | [[concepts/audio-repair-practical]] |
| 降噪策略对比 | 噪声门 vs 频谱降噪——各自的原理/适用场景/限制 | [[concepts/audio-repair-practical]] |
| iZotope RX 核心功能 | Voice De-noise / De-click / De-clip / Mouth De-click / Spectral Repair——工作流顺序 | [[concepts/audio-repair-practical]] |
| 环境音填充 | Room Tone 录制与填充——降噪后的"音频真空"补全策略 | [[concepts/audio-repair-practical]] |
| 电平统一三件套 | Normalize vs Compressor vs Limiter——选择策略和经典链条 | [[concepts/audio-repair-practical]] |
| 免费替代工具 | Audacity / FFmpeg afftdn/anlmdn / OcenAudio / Reaper | [[concepts/audio-repair-practical]] |

### 色彩理论与调色方案

| 方向 | 核心贡献 | 关联页面 |
|-----|---------|---------|
| 色轮基础 | HSL 三维度、色轮/矢量示波器/波形监视器的使用 | [[concepts/color-theory-looks]] |
| 调色方案 | 互补/类似/三角/分裂互补/四角色——各方案的视觉效果和运用场景 | [[concepts/color-theory-looks]] |
| 五大经典电影调色 | Teal & Orange / Bleach Bypass / Monochrome / Warm Saturated / Cool——每种的原理、经典案例、技术实现 | [[concepts/color-theory-looks]] |
| 胶片模拟 | Kodak Vision3 / Fuji Eterna / Tri-X / Portra——胶片的色彩科学数字模拟 | [[concepts/color-theory-looks]] |
| 自定义 Look 流程 | 参考帧 → 波形分析 → 一级匹配 → 二级风格 → LUT 输出 | [[concepts/color-theory-looks]] |
| 色彩校准 | D65 白点/Gamma 2.4/示波器信赖原则/色彩空间匹配 | [[concepts/color-theory-looks]] |

### 字幕、图形与本地化

| 方向 | 核心贡献 | 关联页面 |
|-----|---------|---------|
| 字幕类型 | Hard Burned vs Soft Subtitle——适用场景和平台要求 | [[concepts/titling-localization]] |
| 字幕格式 | SRT/ASS/STL/VTT/SCC/TTML 深入比较 | [[concepts/titling-localization]] |
| 标题设计原则 | 字体选择/位置/持续时间/可读性——4 条核心原则 | [[concepts/titling-localization]] |
| Lower Thirds 设计 | 结构模板/动画节奏/品牌一致性 | [[concepts/titling-localization]] |
| 本地化工作流 | 转录→翻译→时间轴→审校→打包——完整 6 步流程 | [[concepts/titling-localization]] |
| 各 NLE 字幕工具 | Premiere 基本图形 / Resolve Fusion / FCP 字幕发生器 / Avid Marquee | [[concepts/titling-localization]] |

### 视频规格兼容性

| 方向 | 核心贡献 | 关联页面 |
|-----|---------|---------|
| 帧率全表 | 23.976~120 fps 的选择策略、23.976 P 历史由来、帧率转换 judder | [[concepts/video-specs-compatibility]] |
| 分辨率层级 | SD→HD→FHD→2K→4K→6K→8K——每种标准的使用场景 | [[concepts/video-specs-compatibility]] |
| 宽高比 | 16:9/1.85:1/2.39:1/9:16 等 12 种比例——遮幅/转换策略 | [[concepts/video-specs-compatibility]] |
| 逐行 vs 隔行 | Progressive vs Interlaced——去隔行方法、场序确认 | [[concepts/video-specs-compatibility]] |
| Pulldown | 3:2 Pulldown 原理与逆操作、2:2/2:2:2:4 Pulldown 场景 | [[concepts/video-specs-compatibility]] |
| PAR vs DAR | 像素宽高比与显示宽高比的换算——SD 素材/VFX 交接要点 | [[concepts/video-specs-compatibility]] |

### 剪辑师职业发展

| 方向 | 核心贡献 | 关联页面 |
|-----|---------|---------|
| 职业路径 | 二助→一助→Lead AE→剪辑师→主剪辑师→剪辑监督 | [[concepts/editor-career-path]] |
| AE 分级职责 | 二助（Dailies/转码/同步）、一助（Bin 管理/回套/交付）、Lead AE（工作流设计） | [[concepts/editor-career-path]] |
| 市场费率 | 北美/中国年薪和日费率参考——各角色和类型的收入范围 | [[concepts/editor-career-path]] |
| 就业方式对比 | 自由职业 vs 全职入组 vs 远程剪辑——优劣分析 | [[concepts/editor-career-path]] |
| Reel 制作 | 长版/短版/类型特化/叙事 Reel——5 秒第一印象原则 | [[concepts/editor-career-path]] |
| 客户关系 | 初/中/高级三个阶段的人脉和定价策略 | [[concepts/editor-career-path]] |
| 工会体系 | MPEG (IATSE 700) 美国 / BECTU 英国 / 中国现状 | [[concepts/editor-career-path]] |

### 全景更新

```
第一轮：流水线主干        第二轮：剪辑技术细节          第三轮：调色/声音/VFX/纪录片    第四轮：AI/协作/RAW/NLE/存储    第五轮：AE/音频修复/色彩理论/字幕/规格/职业
┌──────────────┐       ┌────────────────┐           ┌──────────────────────────┐     ┌──────────────────────────────────┐    ┌──────────────────────────────────────────┐
│ 拍摄→代理→    │       │ 转场类型        │           │ ACES/HDR 调色              │     │ AI 转录/粗剪/调色/音频/视觉生成     │    │ AE 动态图形进阶/表达式/插件                │
│ 离线→在线→    │   +   │ 多机位剪辑       │     +     │ 声音设计深挖 / Foley        │  +  │ 协作/版本/交换格式/远程工作流       │  + │ 音频修复实战/iZotope RX/免费替代          │
│ 调色→VFX→交付 │       │ 绿幕/合成        │           │ VFX 跟踪/AE 动态图形        │     │ 六大 RAW 格式/Log 曲线/选择策略     │    │ 色彩理论/五大电影调色方案/LUT 制作       │
│ 音频流水线    │       │ 效率/Bin 管理    │           │ 纪录片剪辑/伦理             │     │ Premiere/Resolve/FCP 高手技巧       │    │ 字幕格式/本地化工作流/Lower Thirds        │
│ 交付流水线    │       │ 案例拆解         │           │ 知名调色师/声音设计师        │     │ 三层存储/RAID/归档/数据完整性       │    │ 帧率/分辨率/PAR-DAR/逐行隔行/Pulldown     │
└──────────────┘       │ 技术简史         │           └──────────────────────────┘     └──────────────────────────────────┘    │ 剪辑师职业路径/费率/工会                │
                        │ 行业角色         │                                                                                         └──────────────────────────────────────────┘
                        │ Murch/Schoonmaker│
                        └────────────────┘
```

五轮深挖已完成。本 synthesis 页面现覆盖视频后期制作的 **流水线主干 → 剪辑技术细节 → 调色/声音/VFX/纪录片/人物 → AI/协作/RAW/NLE/存储归档 → AE 动态图形/音频修复/色彩理论/字幕规格/职业发展** 的全方位知识图谱。

## 第六轮深挖

本轮扩展 5 个新方向：视频压缩编码进阶、HDR 制作全流程、插件生态、现场 DIT 数据管理、QC 与交付标准。

### 视频压缩与编码参数进阶

| 方向 | 核心贡献 | 关联页面 |
|-----|---------|---------|
| x264 参数深度 | Preset(ultrafast~placebo)、Profile/Level、CRF vs 2-pass VBR、码率分配 | [[concepts/advanced-video-compression]] |
| H.265/HEVC x265 差异 | CRF 偏移、Main10/Main12、SAO/AQ/deblock/Subme 参数调优 | [[concepts/advanced-video-compression]] |
| AV1 编码现状 | libaom/SVT-AV1/rav1e/NVENC AV1 编码器对比、30% 码率优势、硬件解码生态 | [[concepts/advanced-video-compression]] |
| 按内容编码策略 | 电影(CRF 18-22) vs 动画(CRF 16-20) vs 屏幕录制(CRF 19-24) vs 体育(CRF 22-26) | [[concepts/advanced-video-compression]] |
| 码率分配进阶 | 场景检测编码、GOP 结构(Keyint/B-frame/B-pyramid)、Per-Title Encoding(Netflix 每标题编码) | [[concepts/advanced-video-compression]] |
| 主观视觉优化 | Psychovisual tuning(psy-rd)、AQ(自适应量化)、Deblock、SAO——视觉感知补偿 | [[concepts/advanced-video-compression]] |
| FFmpeg 编码模板 | 存档 H.264 / Netflix 风格 / HEVC 10-bit / AV1 流媒体 / 代理预览命令 | [[concepts/advanced-video-compression]] |

### HDR 制作全流程

| 方向 | 核心贡献 | 关联页面 |
|-----|---------|---------|
| HDR 标准对比 | HDR10(静态)/HDR10+(场景动态)/Dolby Vision(帧动态+RPU)/HLG(SDR 反向兼容) | [[concepts/hdr-production-pipeline]] |
| 色彩空间 | Rec.2020 + PQ(ST 2084)、Color Volume 三维概念、绝对亮度编码 | [[concepts/hdr-production-pipeline]] |
| HDR 拍摄 | 各机型 HDR 模式(Alexa35/Venice/RED/KOMODO/C500/iPhone)、曝光策略 | [[concepts/hdr-production-pipeline]] |
| HDR 调色流程 | Resolve HDR 色轮/Scopes、ACES HDR Output Transform、关键步骤 | [[concepts/hdr-production-pipeline]] |
| SDR->HDR 转换 | AI 辅助(Topaz)/手动重建/生成式 AI、约束(裁切不可恢复/噪点放大) | [[concepts/hdr-production-pipeline]] |
| 交付格式 | Dolby Vision Profile 5/8、HDR10、HDR10+、各平台要求(Netflix/Apple/YouTube) | [[concepts/hdr-production-pipeline]] |
| 监控与 QC | 参考级监视器(Sony/Flanders/Dolby/Apple XDR)、元数据/Luminance/色域检查项 | [[concepts/hdr-production-pipeline]] |

### 后期制作插件生态

| 方向 | 核心贡献 | 关联页面 |
|-----|---------|---------|
| 插件分类 | 调色/特效/修复/转场/字幕/跟踪/粒子——按功能和支持 NLE 的完整分类 | [[concepts/plugin-ecosystem]] |
| Maxon/Red Giant | Magic Bullet(调色)/Universe(100+ 跨平台)/Trapcode(Particular/Form)/VFX Suite | [[concepts/plugin-ecosystem]] |
| Boris FX | Sapphire(270+ 效果, Emmy 获奖)/Continuum/Title Studio/Mocha Pro(平面跟踪标准) | [[concepts/plugin-ecosystem]] |
| Neat Video | 降噪黄金标准——多帧时域+GPU/自动噪声分布/保留纹理质量 | [[concepts/plugin-ecosystem]] |
| FilmConvert/Dehancer | 胶片模拟赛道：Dehancer 60+ 胶片/130+ Camera Profile/Halation/Bloom 深度模拟 | [[concepts/plugin-ecosystem]] |
| Topaz Video AI | AI 放大增强/降噪/帧插值/慢动作/SDR->HDR——Gaia/Theia/Artemis/Chronos 模型 | [[concepts/plugin-ecosystem]] |
| 插件管理 | 永久/订阅/节点锁定/浮动许可策略、版本兼容性检查、渲染性能优化 | [[concepts/plugin-ecosystem]] |

### 现场 DIT 与数据管理

| 方向 | 核心贡献 | 关联页面 |
|-----|---------|---------|
| DIT 角色 | Data Wrangler → Senior DIT → DIT Supervisor 三级职责递增 | [[concepts/dit-workflow]] |
| 现场数据流 | 存储卡 → 2 份备份 + Checksum 校验 → 转码 → 元数据 → 交付剪辑组 | [[concepts/dit-workflow]] |
| DIT 工具对比 | Silverstack(行业标准/元数据解析/Livegrade 集成) vs Hedge(快速拷贝) vs ShotPut Pro(好莱坞传统) | [[concepts/dit-workflow]] |
| Checksum 校验 | MD5(标准)/xxHash(极速)/SHA-256(高安全)算法选择与流程 | [[concepts/dit-workflow]] |
| 现场色彩管理 | CDL + LUT 的"可逆现场调色"——DIT 与调色师的色彩元数据交接 | [[concepts/dit-workflow]] |
| Dailies 生成 | RAW → ProRes Proxy + 时码烧录 + 现场 Look + 场记信息 | [[concepts/dit-workflow]] |
| 片场数据安全 | 3-2-1 现场版本、物理分离、防写保护、加密(AES-256)、运输安全 | [[concepts/dit-workflow]] |

### QC 与交付标准

| 方向 | 核心贡献 | 关联页面 |
|-----|---------|---------|
| QC 三阶段 | 技术QC(自动化格式扫描)→内容QC(人工画面审查)→合规QC(响度/PSE/字幕) | [[concepts/qc-delivery-standards]] |
| Netflix 规范 | ProRes 422 HQ / IMF / -27 LUFS / 色域测试 / Bar Code / Dolby Vision Profile 5 | [[concepts/qc-delivery-standards]] |
| Apple/YouTube 交付 | ProRes 422 HQ / iTT 字幕 / Dolby Vision 打包 (Apple)；H.264/ProRes / PQ/HLG / max 256GB (YouTube) | [[concepts/qc-delivery-standards]] |
| 广播交付 | PSE 闪烁测试(Harding Test)、ITU-R BS.1770 响度标准(-23/-24 LUFS 地区差异)、DVB/CEA 字幕 | [[concepts/qc-delivery-standards]] |
| 影院 DCP | JPEG 2000 / 12-bit XYZ / DCI-P3 / AES-128 加密 / KDM / ISDCF 命名规范 | [[concepts/qc-delivery-standards]] |
| QC 工具链 | Aurora(企业/云)/Interra Baton(IMF+DCP)/Telestream Switch(人工)/Resolve VidChecker(内置免费) | [[concepts/qc-delivery-standards]] |
| 交付清单 | 文件/视频/音频/字幕/合规 五个维度的完整检查项模板 | [[concepts/qc-delivery-standards]] |

### 全景更新

```
第一轮：流水线主干        第二轮：剪辑技术细节          第三轮：调色/声音/VFX/纪录片    第四轮：AI/协作/RAW/NLE/存储    第五轮：AE/音频修复/色彩理论/字幕/规格/职业    第六轮：压缩/HDR/插件/DIT/QC
┌──────────────┐       ┌────────────────┐           ┌──────────────────────────┐     ┌──────────────────────────────────┐    ┌──────────────────────────────────────────┐    ┌────────────────────────────────────────────┐
│ 拍摄→代理→    │       │ 转场类型        │           │ ACES/HDR 调色              │     │ AI 转录/粗剪/调色/音频/视觉生成     │    │ AE 动态图形进阶/表达式/插件                │    │ x264/x265/AV1 编码参数深度/CRF/码率策略    │
│ 离线→在线→    │   +   │ 多机位剪辑       │     +     │ 声音设计深挖 / Foley        │  +  │ 协作/版本/交换格式/远程工作流       │  + │ 音频修复实战/iZotope RX/免费替代          │  + │ HDR10/Dolby Vision/HLG/Rec.2020/PQ 工作流│
│ 调色→VFX→交付 │       │ 绿幕/合成        │           │ VFX 跟踪/AE 动态图形        │     │ 六大 RAW 格式/Log 曲线/选择策略     │    │ 色彩理论/五大电影调色方案/LUT 制作       │    │ Maxon/Boris FX/Neat/Dehancer/Topaz 插件生态│
│ 音频流水线    │       │ 效率/Bin 管理    │           │ 纪录片剪辑/伦理             │     │ Premiere/Resolve/FCP 高手技巧       │    │ 字幕格式/本地化工作流/Lower Thirds        │    │ DIT 数据管理/Silverstack/Hedge/日报/Dailies│
│ 交付流水线    │       │ 案例拆解         │           │ 知名调色师/声音设计师        │     │ 三层存储/RAID/归档/数据完整性       │    │ 帧率/分辨率/PAR-DAR/逐行隔行/Pulldown     │    │ QC 三阶段/Netflix IMF/PSE/响度/DCP/工具链 │
└──────────────┘       │ 技术简史         │           └──────────────────────────┘     └──────────────────────────────────┘    │ 剪辑师职业路径/费率/工会                │    └────────────────────────────────────────────┘
                         │ 行业角色         │                                                                                         └──────────────────────────────────────────┘
                         │ Murch/Schoonmaker│
                         └────────────────┘
```

六轮深挖已完成。本 synthesis 页面现覆盖视频后期制作的 **流水线主干 → 剪辑技术细节 → 调色/声音/VFX/纪录片/人物 → AI/协作/RAW/NLE/存储归档 → AE 动态图形/音频修复/色彩理论/字幕规格/职业发展 → 压缩编码/HDR 制作/插件生态/DIT 数据管理/QC 交付标准 → VFX 进阶/色彩工程/ADR 配音/MV 剪辑/体育剪辑** 的全方位知识图谱。

## 第七轮深挖

本轮扩展 5 个新方向：VFX 进阶（Matchmove/Rotoscoping/合成）、色彩空间与色域工程、ADR 配音与多语言工作流、音乐视频剪辑、体育与快节奏剪辑。

### VFX 进阶：Matchmove / Rotoscoping / 合成

| 方向 | 核心贡献 | 关联页面 |
|-----|---------|---------|
| Rotoscoping 工具 | Mocha Planar Tracking、Resolve Magic Mask、Nuke RotoPaint、AE Roto Brush 2、Silhouette FX——工具选型与工作流 | [[concepts/advanced-vfx-matchmove]] |
| 跟踪技术对比 | 2D 点跟踪 vs Planar Tracking vs 3D Camera Tracking 的原理与适用场景 | [[concepts/advanced-vfx-matchmove]] |
| Matchmove 工作流 | 畸变校正 → Camera Solve → 导出 → 3D 布景 → 合成——完整 VFX 整合流程 | [[concepts/advanced-vfx-matchmove]] |
| 3D 合成基础 | Shadow/Reflection/Depth Pass 的合成叠加技巧 | [[concepts/advanced-vfx-matchmove]] |
| Keying 进阶 | Despill、Edge Blending、Alphabesed 规范 | [[concepts/advanced-vfx-matchmove]] |
| 合成节点结构 | Nuke / AE / Fusion 的典型图层节点结构 | [[concepts/advanced-vfx-matchmove]] |

### 色彩空间与色域工程

| 方向 | 核心贡献 | 关联页面 |
|-----|---------|---------|
| 色域深度对比 | Rec.709/DCI-P3/Rec.2020/ACES AP0-AP1 的色域覆盖与白点 Gamma 差异 | [[concepts/color-science-gamut]] |
| CST 原理 | 色域矩阵乘 + Gamma 转换、CST vs 3D LUT 优势 | [[concepts/color-science-gamut]] |
| ACES 工作流 | IDT → ACEScc → RRT → ODT 架构详解、版本演进 | [[concepts/color-science-gamut]] |
| RCM vs ACES | 适用场景对比——独立剪辑 vs 好莱坞 VFX 流程 | [[concepts/color-science-gamut]] |
| 色域映射 | Clip/Compress/Soft Clip 三种色域外颜色处理策略 | [[concepts/color-science-gamut]] |
| 位深影响 | 8-bit / 10-bit / 12-bit / 16-bit float 的技术意义和视觉差异 | [[concepts/color-science-gamut]] |
| 示波器阅读 | 波形/矢量/直方图/分光示波器的深度解读 | [[concepts/color-science-gamut]] |

### ADR、配音与多语言工作流

| 方向 | 核心贡献 | 关联页面 |
|-----|---------|---------|
| ADR 技术 | 何时需要、录音设置、同步技巧（波形对齐/VocALign/Time Warp/XLI） | [[concepts/adr-dubbing-workflow]] |
| 配音工作流 | 翻译 → 台本调整 → 选声 → 录音 → 同步 → 混音 六步全流程 | [[concepts/adr-dubbing-workflow]] |
| ADR vs 配音 | 目的/演员/语言/预算的全面对比 | [[concepts/adr-dubbing-workflow]] |
| 口型同步技巧 | Pocket 微调、Time Warp 伸缩、XLI 时间码交换、开闭原则 | [[concepts/adr-dubbing-workflow]] |
| 多语言版本管理 | IMF 打包/单母版音频替换、10-30 种语言管理策略 | [[concepts/adr-dubbing-workflow]] |
| 字幕 vs 配音 | 成本/文化/儿童/原声/市场规模的决策矩阵 | [[concepts/adr-dubbing-workflow]] |
| 配音导演方法 | 情绪引导/示范/分析/口型精确四法 | [[concepts/adr-dubbing-workflow]] |

### 音乐视频剪辑

| 方向 | 核心贡献 | 关联页面 |
|-----|---------|---------|
| Beat Sync 核心 | Beat Marking 方法、视觉节奏四层级结构 | [[concepts/music-video-editing]] |
| MV 结构映射 | Intro/Verse/Chorus/Bridge/Outro 对应的视觉节奏策略 | [[concepts/music-video-editing]] |
| 表演 vs 叙事 | 两种镜头的交替编织原则 | [[concepts/music-video-editing]] |
| 风格化技巧 | 时间重映射/Speed Ramp、抽帧/频闪、倒放、闪切 | [[concepts/music-video-editing]] |
| Lip Sync 技巧 | P-Q 原则、辅音优先策略、多重 Take 选择 | [[concepts/music-video-editing]] |
| MV 转场 | Whip Pan/Swish Pan/Flash Frame/Luma Key/Match Cut | [[concepts/music-video-editing]] |
| 知名 MV 导演 | Gondry/Jonze/Cunningham/Romanek/Hype Williams/Akerlund/Wright 风格分析 | [[concepts/music-video-editing]] |

### 体育与快节奏剪辑

| 方向 | 核心贡献 | 关联页面 |
|-----|---------|---------|
| 体育剪辑挑战 | 实时 vs 后期、不可预测性、多机位、无 NG | [[concepts/sports-fast-cut-editing]] |
| EVS 回放系统 | 实时慢动作/多角度回放/Cue Points/Highlight Clip 工作流 | [[concepts/sports-fast-cut-editing]] |
| Highlight 原则 | 高潮前置、节奏递进、数据驱动集锦 | [[concepts/sports-fast-cut-editing]] |
| Opening Sequence | Logo → 空镜 → 球员特写 → 历史集锦的包装结构 | [[concepts/sports-fast-cut-editing]] |
| 动作顺接 | 中轴线原则/球的方向/机位配对——避免观众方向迷失 | [[concepts/sports-fast-cut-editing]] |
| 采访 + B-roll | 五类体育 B-roll 素材与采访交替节奏公式 | [[concepts/sports-fast-cut-editing]] |
| 慢动作时机 | 高帧率/Optical Flow/AI 插值技术对比、过度慢放禁忌 | [[concepts/sports-fast-cut-editing]] |

### 全景更新

```
第一轮：流水线主干        第二轮：剪辑技术细节          第三轮：调色/声音/VFX/纪录片    第四轮：AI/协作/RAW/NLE/存储    第五轮：AE/音频修复/色彩理论/字幕/规格/职业    第六轮：压缩/HDR/插件/DIT/QC    第七轮：VFX 进阶/色彩工程/ADR 配音/MV/体育
┌──────────────┐       ┌────────────────┐           ┌──────────────────────────┐     ┌──────────────────────────────────┐    ┌──────────────────────────────────────────┐    ┌────────────────────────────────────────────┐    ┌────────────────────────────────────────────────┐
│ 拍摄→代理→    │       │ 转场类型        │           │ ACES/HDR 调色              │     │ AI 转录/粗剪/调色/音频/视觉生成     │    │ AE 动态图形进阶/表达式/插件                │    │ x264/x265/AV1 编码参数深度/CRF/码率策略    │    │ Matchmove/Rotoscoping/Planar/3D 跟踪        │
│ 离线→在线→    │   +   │ 多机位剪辑       │     +     │ 声音设计深挖 / Foley        │  +  │ 协作/版本/交换格式/远程工作流       │  + │ 音频修复实战/iZotope RX/免费替代          │  + │ HDR10/Dolby Vision/HLG/Rec.2020/PQ 工作流│  + │ Rec.709/DCI-P3/Rec.2020/ACES 色域深度对比   │
│ 调色→VFX→交付 │       │ 绿幕/合成        │           │ VFX 跟踪/AE 动态图形        │     │ 六大 RAW 格式/Log 曲线/选择策略     │    │ 色彩理论/五大电影调色方案/LUT 制作       │    │ Maxon/Boris FX/Neat/Dehancer/Topaz 插件生态│    │ ADR/VocALign/配音工作流/多语言 IMF 管理       │
│ 音频流水线    │       │ 效率/Bin 管理    │           │ 纪录片剪辑/伦理             │     │ Premiere/Resolve/FCP 高手技巧       │    │ 字幕格式/本地化工作流/Lower Thirds        │    │ DIT 数据管理/Silverstack/Hedge/日报/Dailies│    │ MV Beat Sync/风格化/Lip Sync/导演风格        │
│ 交付流水线    │       │ 案例拆解         │           │ 知名调色师/声音设计师        │     │ 三层存储/RAID/归档/数据完整性       │    │ 帧率/分辨率/PAR-DAR/逐行隔行/Pulldown     │    │ QC 三阶段/Netflix IMF/PSE/响度/DCP/工具链 │    │ EVS 回放/Highlight/Opening/慢动作/体育剪辑   │
└──────────────┘       │ 技术简史         │           └──────────────────────────┘     └──────────────────────────────────┘    │ 剪辑师职业路径/费率/工会                │    └────────────────────────────────────────────┘    └────────────────────────────────────────────────┘
                         │ 行业角色         │                                                                                         └──────────────────────────────────────────┘
                         │ Murch/Schoonmaker│
                         └────────────────┘
```

七轮深挖已完成。本 synthesis 页面现覆盖视频后期制作的 **流水线主干 → 剪辑技术细节 → 调色/声音/VFX/纪录片/人物 → AI/协作/RAW/NLE/存储归档 → AE 动态图形/音频修复/色彩理论/字幕规格/职业发展 → 压缩编码/HDR 制作/插件生态/DIT 数据管理/QC 交付标准 → VFX 进阶/色彩工程/ADR 配音/MV 剪辑/体育剪辑** 的全方位知识图谱。至此共涵盖 40+ 概念页面，10+ 实体页面，6+ 来源页面。
