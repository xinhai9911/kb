---
title: 调色进阶
category: concepts
tags: [color-grading, aces, hdr, dolby-vision, lut, color-science, stylized-look, film-emulation]
created: 2026-07-29
updated: 2026-07-29
summary: 超越一级调色的高级色彩管理技术——ACES 管线、HDR 调色、风格化流派、以及颜色在叙事中的节奏作用
relationships:
  - target: "[[concepts/color-grading-workflow]]"
    type: extends
  - target: "[[concepts/narrative-psychology-editing]]"
    type: related_to
  - target: "[[entities/davinci-resolve]]"
    type: uses
  - target: "[[entities/colorist-grades]]"
    type: references
  - target: "[[synthesis/video-editing-pipeline]]"
    type: part_of
base_confidence: 0.75
lifecycle: draft
lifecycle_changed: 2026-07-29
sources:
  - "https://en.wikipedia.org/wiki/Color_grading"
  - "https://en.wikipedia.org/wiki/ACES_(color_space)"
  - "https://en.wikipedia.org/wiki/Dolby_Vision"
  - "https://en.wikipedia.org/wiki/Teal_and_orange"
---

# 调色进阶

## 概述

[[concepts/color-grading-workflow|色彩管理管线]]覆盖了一级/二级调色的基础知识。本篇向上延伸，深入 ACES 标准、HDR 工作流、风格化调色流派、以及调色在叙事层面的心理作用。

## ACES 色彩管理管线

### 什么是 ACES

**ACES (Academy Color Encoding System)** 是美国电影艺术与科学学院开发的开源色彩管理标准，旨在提供一个**设备无关**的色彩管线，使不同摄像机的素材能在统一的色彩空间中匹配和调色。

### ACES 核心架构

```
拍摄素材 (BRAW / ARRIRAW / S-Log / RED)
    │
    ▼ IDT (Input Device Transform)
    │  将各厂家的 Log 转换到 ACES 统一空间
    ▼
ACES2065-1 — 学院色彩编码空间（AP0 色域 / 线性光）
    │
    ▼ ACEScc / ACEScct — 调色工作空间（对数伽马，适合调色师操作）
    │  在此空间内完成一级和二级调色
    ▼
    RRT (Reference Rendering Transform)
    ▼
    ODT (Output Device Transform) — Rec.709 / Rec.2020 / P3-D65
```

| 组件 | 功能 |
|-----|------|
| AP0 色域 | 全可见光谱数学定义（超过任何显示设备），作为操作参考空间 |
| AP1 色域 | 调色师实际工作的窄色域，与 P3/Rec.2020 接近 |
| IDT | 摄像机厂家提供的色彩转换，将 RAW/Log 映射到 ACES |
| ACEScc | 对数编码调色空间，色轮操作与传统方式兼容 |
| RRT + ODT | 统称为"输出变换"，将场景参考映射到显示参考 |

### ACES 的优势

- **精确匹配**：多机型素材在同一部影片中色彩匹配度极高
- **未来存档**：ACES2065-1 存档格式不绑定任何显示标准，未来显示技术升级时可重新渲染
- **标准化协作**：不同工作室之间通过 ACES 交换调色元数据
- **免费开源**：不需要许可费用

### ACES 的局限

- 学习曲线陡峭
- 某些创意 LUT 在 ACES 空间中表现不如传统 Log 空间
- 对较旧的 SDR 素材可能有过度处理的风险

## Log → LUT → Grade 工作流深挖

### 三种工作流对比

| 工作流 | 复杂度 | 灵活性 | 适用场景 |
|-------|-------|-------|---------|
| **LUT-Only** | 低 | 低 | 快节奏项目、新闻、预告片初剪 |
| **Manual CST** | 中 | 高 | 独立电影、广告片 |
| **ACES / RCM** | 高 | 极高 | 长片、Netflix/院线项目 |

### LUT 链的构建

专业调色不是用一个 LUT 搞定一切，而是构建 LUT 链：

1. **Input LUT**：Camera Log → Log C (统一中间格式)
2. **Technical LUT**：Log C → Rec.709 (参考转换)
3. **Look LUT**：风格化变换（叠加在 Technical 之上）
4. **Output LUT**：最终调色通过监视器 LUT 预览

关键要点：调色师通常在**查色后的画面上再做手调**，LUT 提供起点而非终点。

## 风格化调色流派

### Teal / Orange（青橙冷暖对比）

这是当代好莱坞最普遍的调色策略之一。

- 原理：人类肤色倾向于橙色色谱；互补色青色/蓝色在色环对面。将肤色保留橙色，环境阴影推向青蓝，产生自然的人景分离。
- 代表作：《变形金刚》系列、《速度与激情》系列、《加勒比海盗》
- 实现：在色轮中将 Midtones 向橙色偏移，Shadows 向蓝色偏移，或使用 Hue vs Hue / Hue vs Sat 曲线
- 批评：过度使用导致同质化

### Bleach Bypass（漂白效果 / 银保留）

模拟胶片处理中跳过漂白步骤的化学效果。

- 视觉特征：高对比度、低饱和度、暗部密实、亮部过曝
- 经典作品：《拯救大兵瑞恩》、《兄弟连》、《疯狂的麦克斯：狂暴之路》
- 实现：降低饱和度 + 拉 S-Curve（抬暗部对比），在 Log 空间中叠加分色（RGB 曲线差异化）

### Desaturated Look（褪色 / 低饱和）

- 类型 A：暗部褪色（Crushed Blacks + 低饱和）—《七宗罪》、《蝙蝠侠：黑暗骑士》
- 类型 B：亮部褪色（高亮褪色）—《银翼杀手 2049》
- 实现：将 Sat 曲线在 Shadows/Highlights 区域拉低，或通过 LGG 中的 Sat vs Lum 曲线

### Film Emulation（胶片模拟）

胶片模拟的核心是复现胶片的**特征性瑕疵**：

| 特征 | 机制 | 实现方式 |
|------|------|---------|
| S-Curve（肩趾曲线） | 暗部压缩 + 高光柔化 | Log 空间中调整对比度曲线 |
| 色偏偏移 | 每个胶片品牌独特的色调倾向 | Power Grade / Film LUT |
| 颗粒感 | 感光乳剂的随机晶体 | Film Grain 插件 |
| Halation | 高光边缘的光晕扩散 | OFX 特效插件 |
| Gate Weave | 胶片门不稳的微抖动 | 稳定器反向缓动 |
| 闪光效果 | 胶片露光的色罩偏移 | 调色版叠加 |

知名胶片模拟工具：Filmbox、Dehancer、CineMatch、FilmConvert

## HDR 调色

### 核心标准

| 标准 | 峰值亮度 | 色域 | EOTF |
|------|---------|------|------|
| **HDR10** | 1,000 nits | Rec.2020 | PQ (ST.2084) |
| **HDR10+** | 4,000 nits | Rec.2020 | PQ + 动态元数据 |
| **Dolby Vision** | 10,000 nits | P3-D65 (mastering) | PQ + 12-bit + 动态元数据 |
| **HLG (Hybrid Log-Gamma)** | 1,000 nits | Rec.2020 | HLG (BBC/NHK) |

### Dolby Vision 工作流

1. **分级母版**：调色师在 Dolby Vision 监视器（峰值 ~4,000 nits）上完成调色
2. **Trim Passes**：针对不同亮度等级（1,000 / 600 / 400 / 100 nits）做微调
3. **动态元数据**：逐场景或逐帧记录色彩调整信息
4. **CMv4 (Color Metadata v4)**：Dolby Vision 最近一代色彩管理规范

### HDR vs SDR 工作流差异

- 一级调色工具在 HDR 中增加 HDR wheel（高光/阴影/亮部/暗部独立控制）
- 二级调色在 HDR 中更多使用 HDR Grade（限定器 + 增益）
- HDR 调色需要支持 PQ 的监视器和 LUT Box（如 FSI / Sony BVM / Dolby Pulsar）
- 最终质量要求：色条必须覆盖 P3-D65，峰值亮度目标按发行渠道定义

### SDR → HDR 上变换

当代有很多 SDR 影片被重新制成 HDR 版本。常见技术：
- **AI 辅助 HDR Retiming**：使用机器学习从 SDR 推断亮度范围
- **手动重建**：调色师重新做 HDR 调色，找到原始 RAW 或 Log 板
- **HDR Histogram**：在 PQ 空间中查看亮度分布，将亮部重新映射到 HDR 范围

## 颜色在时间线中的叙事节奏

颜色的转变本身就是一种剪辑语言：

| 叙事功能 | 颜色策略 | 示例 |
|---------|---------|------|
| 时空区分 | 闪回降低饱和 + 暖色偏 |《黑暗骑士》闪回片段 |
| 角色成长 | 随角色变化从青冷转向暖黄 |《绝命毒师》Walter White |
| 情绪预警 | 场景中逐渐注入青色 — 危机感 |《囚徒》 |
| 平行剪辑 | 两条故事线不同色调，最终汇合 |《教父 II》双线 |
| 场景过渡 | 用主导色连接不同场景的切点 |《布达佩斯大饭店》 |
| 时代感 | 仿胶片 + 高颗粒表示过去 |《第一归正会》 |

调色师的终极能力不在于操作色轮，而在于**理解颜色在何时、为何、如何推动叙事**——这是调色从"修图"通向"艺术"的分水岭。

## 知名调色师

见 [[entities/colorist-grades]] 合集页。

## 关联页面

- [[concepts/color-grading-workflow]] — 色彩管理基础（本页的向上延伸基础）
- [[concepts/narrative-psychology-editing]] — 剪辑叙事心理学
- [[entities/davinci-resolve]] — 行业标准调色工具
- [[entities/colorist-grades]] — 知名调色师合集
- [[synthesis/video-editing-pipeline]] — 全景流水线
