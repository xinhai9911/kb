---
title: >-
  VFX 进阶：Matchmove / Rotoscoping / 合成
category: concepts
tags: [vfx, compositing, tracking, post-production]
created: 2026-07-30
updated: 2026-07-30
summary: >-
  VFX 核心技术详解：Rotoscoping 工具方法、2D/Planar/3D 跟踪技术、Matchmove 工作流、Keying 进阶与合成节点结构
relationships:
  - target: "[[concepts/chroma-key-compositing]]"
    type: extends
  - target: "[[concepts/vfx-motion-graphics]]"
    type: extends
  - target: "[[concepts/camera-raw-formats]]"
    type: relates
base_confidence: 0.85
lifecycle: draft
lifecycle_changed: 2026-07-30
---

# VFX 进阶：Matchmove / Rotoscoping / 合成

## Rotoscoping 工具与方法

Rotoscoping（动态遮罩描摹）是将影片中的对象逐帧或半自动分离的技术，是合成的基础前提。

| 工具 | 类型 | 核心特点 |
|------|------|---------|
| Mocha Pro | Planar Tracking + Roto | 基于平面跟踪的贝塞尔曲线自动跟随，B-spline 手动微调 |
| Resolve Magic Mask | AI 语义分割 | DaVinci Neural Engine 驱动，一键分离人物/物体，精度依赖素材 |
| Nuke RotoPaint | 节点化 Roto | 每个 Roto 独立节点，支持 RotoShape + Paint 结合，可串联 Spline 动画 |
| After Effects Roto Brush 2 | AI 逐帧 | Segmentation Edge 自动识别边界，适合快速粗 Roto |
| Silhouette FX | 专业 Roto 套装 | 基于 Mocha 跟踪 + 专用 Roto 面板、Spline 编辑工具、Stereo Roto |

工作流要点：
- **Roto 分层**：前景主体 + 细节（头发/半透明） + 运动模糊 分层独立处理
- **Roto 顺序**：先粗后细，先跟踪后微调，每帧检查边缘
- **边缘羽化**：Feather 随运动模糊变化，避免生硬裁剪
- **头发处理**：Roto 无法处理头发半透明，需结合 Keylight + Despill 或 Refine Edge

## 2D Tracking vs Planar Tracking vs 3D Camera Tracking

| 方法 | 原理 | 适用场景 | 代表工具 |
|------|------|---------|---------|
| 2D 点跟踪 | 逐帧跟踪单一像素区域 | 屏幕插入、对象锁定、简单稳定 | AE Tracker, Resolve Tracker |
| Planar Tracking | 跟踪四边形平面的纹理变形 | 屏幕替换、Roto 辅助、透视匹配 | Mocha Pro |
| 3D Camera Tracking | 从 2D 视频反向解算摄像机三维运动 | 3D 合成、CG 场景匹配、虚拟置景 | AE 3D Camera Tracker, Nuke CameraTracker, PFTrack |

**2D 点跟踪**：跟踪一个 2D 像素块（Track Point），输出位置/旋转/缩放。局限：面对透视变形、遮挡、模糊时容易丢失。

**Planar Tracking（平面跟踪）**：跟踪一个平面区域（而非单点），利用该平面内的纹理分布计算仿射/透视变换矩阵。Mocha 的核心算法。优势：
- 可以忽略遮挡物（只跟踪可见纹理区域）
- 输出可驱动 Roto 曲线自动跟随
- 支持 Lens Distortion 预处理

**3D Camera Tracking（3D 摄影机解算）**：从画面中的特征点运动反算摄影机的三维坐标、旋转、焦距。流程：
1. 自动提取 2D 特征点（Harris/SIFT/ORB）
2. Bundle Adjustment 解算 3D 点云 + Camera Pose
3. 手动设定地面平面、坐标系原点、缩放
4. 导出到 3D 软件（Maya/Blender/C4D）

## Matchmove 工作流

Matchmove（匹配移动）是将 CG 元素无缝融入实拍镜头的核心技术，典型工作流如下：

```
实拍素材 → Lens Distortion Removal → 2D Tracking/3D Camera Solve
   → 导出到 3D 软件 → 布置 CG 场景/灯光 → 渲染
   → 合成中叠加 → Lens Distortion Re-apply
```

### 步骤详解：

1. **镜头畸变校正（Lens Distortion）**：用网格板/Solve 算出镜头畸变参数，先移除再跟踪。不校正畸变会导致 CG 在画面边缘飘移
2. **跟踪/解算**：根据镜头类型选择方法（静态镜头用 2D Track，运动镜头用 3D Camera Solve）
3. **导出**：FBX（Maya/Blender）/ Alembic / Nuke Script 导出 Camera 数据
4. **3D 场景布置**：导入跟踪数据后，匹配真实场景的物体位置（地面、墙面等）
5. **阴影/反射**：在 3D 中生成 Matte Shadow / Reflection Pass，合成时叠加到实拍
6. **畸变还原**：合成完成后重新加上 Lens Distortion，匹配原始镜头

### 常用软件

| 软件 | 用途 | 特点 |
|------|------|------|
| PFTrack | Matchmove 专用 | 强大的 Camera Solver + Object Tracking，好莱坞标准之一 |
| 3DEqualizer | VFX Matchmove | 工业级 Camera Solve，支持多 Camera Rig |
| Nuke CameraTracker | 节点化 | 集成在 Nuke 合成环境内，无需导出导入 |
| Blender + fSpy | 独立/小项目 | 单帧透视匹配 + 手动跟踪，适合低预算 |
| After Effects 3D Camera Tracker | 简单场景 | 一键解算 + 创建地面/文本/点云，精度不足用于复杂 VFX |

## 简单 3D 合成核心概念

### Shadow（阴影合成）
- **Drop Shadow**：简单平面阴影，适合文本/Logo
- **Matte Shadow**：在 3D 软件中渲染阴影通道（Shadow Pass），合成时 Multiply 叠加到背景
- **Contact Shadow**：接触面阴影，通过 Gaussian Blur + Levels 模拟

### Reflection（反射合成）
- **Screen Reflection**：降低透明度 + 渐变遮罩，模拟地面/水面反射
- **Environment Reflection**：用球面环境贴图模拟高光反射，适合汽车/玻璃
- **Pass 合成**：Diffuse / Specular / Reflection 独立 Render Pass 叠加

### Depth（景深合成）
- **Z-Depth Pass**：从 3D 软件渲染深度通道，在合成中控制前景/背景虚化
- **Fog/Atmosphere**：深度驱动的雾效叠加，增加空间层次
- **DoF 伪造**：基于深度图的 Lens Blur，模拟大光圈浅景深

## Keying 进阶

Chroma Key（色度抠像）进阶技术超越简单的颜色范围抠图：

### Despill（去溢色）
绿幕/蓝幕的光线会反射到前景主体边缘（Spill），常见去溢色方法：
- **Despill Bias**：从绿色/蓝色方向扣除溢色，保持肤色
- **Core Matte / Edge Matte**：分离主体核心与边缘，分别处理溢色
- **Nuke Spill Suppressor**：将溢色映射为互补色（绿→品红）
- **Delta Keyer Despill**：对前后景做色差计算，只扣除前景上的溢色成分

### Edge Blending（边缘混合）
抠像后边缘处理决定合成真实度：
- **Edge Grow/Shrink**：膨胀/收缩边缘遮罩
- **Edge Blur**：对遮罩边缘高斯模糊，匹配实拍边缘柔和度
- **Motion Blur Edge**：在运动方向上拉伸边缘遮罩，模拟运动模糊

### Alphabesed（遮罩命名/规范）
在 Nuke 等节点化合成软件中，Alpha/B 通道独立管理不同遮罩：
- **Alpha**：主前景遮罩
- **B-Channel**：额外遮罩（头发、半透明区域）
- **AlphaBypass**：传递未修改的原始 Alpha 通道

## 常用合成节点/图层结构

### Nuke 节点结构（典型）

```
Read（实拍素材）─┬─ Roto ── Keyer ── Merge(over) ─┬─ Grade ── Write
                 │                                 │
                 ├── CameraTracker ── Scene ────────┘
                 │        │
                 └── Read（CG 渲染）─── Multiply ────
```

### After Effects 图层结构
- 最底层：背景层（实拍或纯色）
- 中间层：CG Render（带 Alpha），混合模式 Multiply/Screen
- 上层：Adjustment Layer 统一调色
- 最顶层：Lens Distortion + Grain 匹配

### Resolve Fusion 节点
- 类 Nuke 节点化架构
- MediaIn → Merge → MediaOut
- Delta Keyer / Planar Tracker / Magic Mask 节点

## 关键思想

VFX 合成的最高法则是 **"匹配原始摄影"**：所有跟踪、Roto、Keying、阴影、反射的目的都是让观众无法区分 CG 与实拍的界限。这需要从畸变校正到颗粒匹配的每个环节都不跳跃。
