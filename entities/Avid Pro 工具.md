---
aliases: ["avid-pro-tools"]
title: Avid Pro Tools
category: entities
tags: [audio, daw, pro-tools, avid, mixing, sound-design]
created: 2026-07-29
updated: 2026-07-29
summary: Avid 出品的数字音频工作站——音频后期制作行业标准，从录制到混音到母版的全流程平台
relationships:
  - target: "[[concepts/音频 后期 制作 流水线]]"
    type: implements
  - target: "[[entities/Avid 媒体 合成器]]"
    type: related_to
base_confidence: 0.75
lifecycle: draft
lifecycle_changed: 2026-07-29
sources:
  - "[[sources/音频 后期 强项 AI]]"
---

# Avid Pro Tools

## 概述

Avid Pro Tools 是音频后期制作领域的**黄金标准**。从好莱坞大片的最终混音到 Billboard 热门唱片的录音，Pro Tools 在专业音频制作中占据统治地位。与 Avid Media Composer 的深度集成使其在影视后期流程中不可替代。

## 核心特性

- **非破坏性编辑**（Non-Destructive Editing）：原始音频文件不受影响
- **AAF/OMF 支持**：与 NLE 之间的无缝项目交接
- **Elastic Audio**：实时时间伸缩与变调
- **Clip Gain 系统**：每个音频片段独立的增益控制
- **高级路由**：任意轨到任意输出的灵活性（总线 / 发送 / 插入）
- **HDX / Native**：DSP 加速（HDX 硬件卡）vs 原生 CPU 处理

## 产品层级

| 版本 | 价格 | 音轨数 | 定位 |
|------|------|--------|------|
| Pro Tools Artist | $9.99/月 | 32 | 个人创作入门 |
| Pro Tools Studio | $39.99/月 | 512 | 专业音频后期 |
| Pro Tools Ultimate | $99.99/月 | 2048+ | 大型后期 / 环绕声 / Atmos |
| 永久授权（仅 Ultimate） | $2,499 买断 | 2048+ | 教育 / 机构 |

## 在影视流程中的角色

1. **交接**：从 Avid Media Composer 或任意 NLE 通过 AAF 导入时间线
2. **对白编辑**：降噪（iZotope RX 集成）、电平统一
3. **ADR**：棚录 + Beep Track + 口型同步
4. **Foley**：视频参考轨 + 拟音录制
5. **混音**：Stem 混音 + Dolby Atmos 渲染
6. **Layback**：混音回填到 NLE 或独立母版

## 与 Fairlight 的对比

- **Fairlight**：内建在 DaVinci Resolve 中，功能低于 Pro Tools
- **Pro Tools**：行业标准，生态系统（插件 / 硬件 / 录音棚）更成熟
- **中型项目**：Fairlight + Resolve 一体化流程成本更低
- **大型项目**：Pro Tools 仍是唯一选择

## 相关页面

- [[concepts/音频 后期 制作 流水线]]：音频后期流程
- [[concepts/离线 在线 工作流]]：Layback 回填阶段
