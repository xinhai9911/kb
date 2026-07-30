---
title: VFX 与动态图形基础
category: concepts
tags: [vfx, motion-graphics, motion-tracking, compositing, after-effects, animation, keyframe]
created: 2026-07-29
updated: 2026-07-29
summary: 视觉特效与动态图形的核心基础——运动跟踪、画面稳定、混合模式、AE 工作流、标题动画与表达式入门
relationships:
  - target: "[[concepts/chroma-key-compositing]]"
    type: related_to
  - target: "[[entities/adobe-premiere-pro]]"
    type: related_to
  - target: "[[synthesis/video-editing-pipeline]]"
    type: part_of
base_confidence: 0.7
lifecycle: draft
lifecycle_changed: 2026-07-29
sources:
  - "https://en.wikipedia.org/wiki/Motion_graphics"
  - "https://en.wikipedia.org/wiki/Compositing"
  - "https://en.wikipedia.org/wiki/Key_frame"
---

# VFX 与动态图形基础

## 概述

视觉特效（VFX）和动态图形（Motion Graphics）是后期制作中画面流水线的两大核心扩展。[[concepts/chroma-key-compositing|绿幕抠像]]覆盖了合成的一个子集，本篇扩展到运动跟踪、画面稳定、混合模式理论、After Effects 工作流和标题动画。

## 运动跟踪 (Motion Tracking)

### 点跟踪 (Point Tracking)

- **原理**：在画面中选中一个高对比度特征点，跟踪其在帧序列中的位置
- **输出数据**：每帧的 2D 坐标 (X, Y) + 旋转 + 缩放
- **应用**：替换屏幕内容（屏幕跟踪）、添加追焦徽标、面部跟踪叠加
- **限制**：跟踪点在画面中必须保持可见，遮挡会导致跟踪丢失
- **工具**：AE 内建 Tracker、Mocha AE、Boris FX

### 平面跟踪 (Planar Tracking)

- **原理**：跟踪一个平面的透视变换（4 点 + 变形信息）
- **优势**：对部分遮挡更鲁棒，跟踪稳定度远高于点跟踪
- **输出**：4 点定位 + 透视矩阵，可粘贴到 3D 图层
- **经典工具**：Mocha Pro（行业标准）、AE 内置 Planar Tracker（Boris FX 引擎 2019+）
- **应用**：车辆挡风玻璃换屏、墙面广告替换、地面反射合成

### 3D Camera Tracking

- **原理**：从 2D 画面反推摄像机在 3D 空间的运动轨迹
- **输出**：虚拟摄像机在 3D 空间的位置 / 旋转 / 焦距
- **工作流**：一键分析 → 创建空摄像机 + 跟踪点 → 放置 3D 文字/模型到场景
- **关键约束**：分析区域的视差信息越充足，跟踪越精确（纯旋转镜头效果差）
- **工具**：AE 3D Camera Tracker、Nuke CameraTracker、PFTrack、Boujou
- **常见失败原因**：动态模糊过多、画面缺乏深度层次（纯平面背景）

### 面部分离跟踪 (Facial Tracking / Mocap)

- AE 内置 Face Tracker：自动检测面部区域，输出头部旋转/面部表情数据
- 应用：面部替换、数字化妆、虚拟角色驱动
- 高级工具：Reallusion iClone、Faceware、Metahuman Animator

## 画面稳定 (Stabilization)

### 原理

画面稳定不是"消除所有抖动"，而是**在保留镜头原始运动意图的前提下减少不必要的抖动**。

| 类型 | 策略 | 使用场景 |
|------|------|---------|
| 完全锁定 | 将所有帧对齐到第一帧 | 静态机位但意外震动（三脚架拍摄） |
| 平滑 / 滚动快门 | 保留摄像机主运动轨迹，仅过滤高频抖动 | 手持跟拍、斯坦尼康（动态镜头） |
| 局部稳定 | 仅稳定画面中的特定物体 | 动画合成、面部稳定 |

### 工具差异

- AE Warp Stabilizer VFX：一键式，自动分析 + 平滑，可调节平滑度
- Mocha Pro Stabilize Module：平面跟踪基础，更可控的结果
- Resolve DaVinci Resolve Stabilization：使用点跟踪或平面跟踪，适合调色流程
- Premiere Pro Warp Stabilizer：与 AE 相同引擎

### 稳定失败处理

- 图像边缘出现黑边 → 增加缩放（Crop Less / Smooth More）
- 动态模糊导致跟踪点漂移 → 先用 Optical Flow 插帧再稳定
- 前景主体相对于摄像机运动（如人物在画面中走动）→ 使用局部跟踪 + 后台合成

## 混合模式详解 (Blend Modes)

混合模式定义了图层与下层色彩如何进行数学运算。以下是在 VFX 合成中最关键的几个：

### 基础混合

| 模式 | 运算 | 用途 |
|------|------|------|
| Normal | 上层完全覆盖下层 | 默认状态 |
| Dissolve | 随机像素替换 | 噪点 / 像素化效果 |

### 减暗类 (上层暗于下层时生效)

| 模式 | 运算 | 用途 |
|------|------|------|
| Multiply | 上层 × 下层（每次 ≤1） | 去除亮部 / 叠加纹理 / 产生阴影 |
| Darken | 逐像素取暗值 | 减去亮部 |
| Color Burn | 增加对比度后变暗 | 增强阴影深度 |

### 提亮类 (上层亮于下层时生效)

| 模式 | 运算 | 用途 |
|------|------|------|
| Screen | 互补乘法（亮度累加） | 光晕 / 镜头耀斑 / 火焰叠加 |
| Add | 上层 + 下层（亮度累加） | 粒子效果、闪光、高光增强 |
| Lighten | 逐像素取亮值 | 保留高光 |

### 对比类

| 模式 | 运算 | 用途 |
|------|------|------|
| Overlay | Multiply + Screen 混合（中性灰不作用） | 纹理叠加 / 胶片颗粒 / 锐化 |
| Soft Light | 类似 Overlay 但更柔和 | 微妙的照明调整 |
| Hard Light | 结合 Multiply + Screen 更强烈 | 光照 / 投影 |

### 色彩类

| 模式 | 运算 | 用途 |
|------|------|------|
| Color | 下层亮度 + 上层颜色 | 调色 / 着色 |
| Luminosity | 下层颜色 + 上层亮度 | 亮度调整不影响颜色 |
| Hue / Saturation | 仅使用上层的色相/饱和度 | 局部颜色替换 |

## After Effects 工作流

### 核心结构

```
Project Panel (素材入口)
    │
    ▼
Composition (Comp) — 时间线容器
    ├── Layer Stack (下→上: 背景 → 素材 → 调色/效果 → 文字/图形)
    ├── Timeline — 每层的寿命 + 关键帧
    ├── Effect Controls — 图层的属性修改
    └── Render Queue → Media Encoder → 交付
```

### 关键概念

- **Pre-compose**：将多个图层打包为一个合成，是复杂项目的基础组织单元
- **Null Object**：不可见的控制层，常作为跟踪数据的容器或父子连接的根
- **Adjustment Layer**：效果应用于该层，影响其下方的所有层（类似调整图层的概念）
- **Parenting**：子层继承父层的变换属性（位置/旋转/缩放）
- **Expressions**：基于 JavaScript 的属性自动化语言

### 表达式入门

```
// 抖动表达式
wiggle(freq, amp)  // wiggle(5, 20) = 每秒抖动 5 次，振幅 20 像素

// 循环表达式
loopOut()  // 在关键帧之间循环
loopIn()   // 从图层起点循环到第一个关键帧

// 时间表达式
time * 360 / 2  // = 每秒 180 度旋转

// 父子链接属性引用
thisComp.layer("Null").transform.position

// 音频驱动的动画
value + amplitude * thisComp.layer("Audio").transform.audioLevels[0]
```

### 渲染管线

- **预览 (RAM Preview)**：实时播放，取决于缓存帧数
- **Render Queue**：基于流程图的逐帧处理（非实时）
- **Adobe Media Encoder (AME)**：后台编码，适合交付格式输出
- **重要设置**：最好渲染为 ProRes 4444 或 PNG Sequence（保留 alpha），再转码到交付格式

## 标题与字幕动画

### 类型

| 类型 | 定义 | 工具 |
|------|------|------|
| Lower Third | 屏幕下方的人名/身份条 | AE Templates / Premiere Essential Graphics |
| 全屏标题 | 章节标题、演职员表 | AE / Apple Motion |
| 滚屏字幕 | 结尾演职员表 | AE / Captivate |
| 动态字幕（Kinetic Typography） | 单词/字母动画 | AE |

### 标题设计原则

1. **可读性优于花哨**：动画是手段，信息传递是目的
2. **留白（Safe Margins）**：文字保持在 Title Safe Zone（90% 画面宽度）
3. **动画时间**：保持 3-5 秒显示时间，过渡 200-400ms
4. **对比度**：文字与背景之间有至少 50% 亮度差
5. **品牌一致性**：字体/颜色/风格与品牌指南一致

### AE 标题动画常见技术

- **Text Animator**：使用 Range Selector 控制逐个字符的动画（位置/透明度/旋转/模糊）
- **Typewriter**：Mask Reveal + 光标闪烁
- **3D Text**：使用 Geometry Options 启用 Z 轴上的厚度
- **响应式布局**：使用 Essential Graphics Panel 向 Premiere 导出可编辑模板（MOGRTs）
- **表达式驱动的自动排版**：基于文字长度自动调整字号

## 关联页面

- [[concepts/chroma-key-compositing]] — 绿幕/蓝幕抠像（VFX 合成的基础）
- [[entities/adobe-premiere-pro]] — 与 AE 动态链接的 NLE
- [[concepts/editing-transitions]] — 转场与动画的中间地带
- [[synthesis/video-editing-pipeline]] — 全景流水线
