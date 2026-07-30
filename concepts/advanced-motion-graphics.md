---
title: 动态图形进阶 — After Effects 实践
category: concepts
tags: [video-editing, motion-graphics, after-effects, post-production]
created: 2026-07-30
updated: 2026-07-30
summary: After Effects 动态图形核心技术：合成、表达式、内建效果、关键帧辅助、第三方插件及与 Premiere 的 Dynamic Link 工作流
relationships:
  - target: "[[concepts/vfx-motion-graphics]]"
    type: extends
  - target: "[[entities/adobe-premiere-pro]]"
    type: relates_to
  - target: "[[concepts/titling-localization]]"
    type: relates_to
base_confidence: 0.8
lifecycle: draft
lifecycle_changed: 2026-07-30
---

# 动态图形进阶 — After Effects 实践

## 核心概念

### 合成 (Comp)

合成是 AE 的基本容器，包含时间轴、图层堆栈和渲染设置。每个合成有自己的分辨率、帧率、持续时间和背景色。合成可嵌套，形成层级结构。

- 嵌套合成 = 模块化设计，父合成变化自动传播到子合成
- Pre-compose（Ctrl+Shift+C）：将选中图层打包为新合成，保持原有属性不变
- 合成设置中的"运动模糊"和"快门角度"决定动态模糊的物理真实感

### 图层类型

| 类型 | 用途 |
|------|------|
| 形状图层 | 矢量图形，可无限缩放，支持多个形状在同一图层 |
| 纯色图层 | 填充色块，常用作效果载体或背景 |
| 文本图层 | 文字动画，支持逐字符动画（Text Animator） |
| 空对象 (Null) | 不可见控制层，用作父级绑定或表达式控制器 |
| 调整图层 | 效果应用到其下方所有图层，不影响图层本身 |
| 摄像机图层 | 3D 场景视角，支持景深和焦点动画 |
| 灯光图层 | 3D 场景光源，影响图层的材质选项 |

### 蒙版与轨道遮罩

- **蒙版 (Mask)**：基于路径的透明控制，绘制在图层自身。支持矩形、椭圆、钢笔路径。蒙版羽化（Mask Feather）是核心平滑手段
- **轨道遮罩 (Track Matte)**：利用上方图层的 Alpha 或 Luma 值控制当前图层的透明度。四种模式：
  - Alpha Matte：上方图层透明区域控制下方可见性
  - Alpha Inverted Matte：反向
  - Luma Matte：上方亮度控制下方透明度（亮部可见）
  - Luma Inverted Matte：暗部可见

轨道遮罩是动态图形中最强大的隐藏功能之一，常用于文字逐字出现、过渡遮罩、复杂合成。

## 表达式入门

表达式是基于 JavaScript 的自动化工具，替代手动关键帧。以下是最常用的 10 个：

### wiggle(freq, amp)

最常用的表达式。产生随机抖动。

```
wiggle(2, 30)    // 每秒抖动 2 次，幅度 30 像素
wiggle(5, 10)    // 每秒抖动 5 次，幅度 10 像素
wiggle(1, 100, 3) // 第三个参数 octaves 增加细节抖动
```

### loopOut(type)

自动循环关键帧动画。四种模式：

```
loopOut("cycle")      // 循环播放所有关键帧（默认）
loopOut("pingpong")   // 正反向交替
loopOut("offset")     // 偏移叠加，每轮增量累加
loopOut("continue")   // 保持最后一个关键帧的速度延伸
```

### time

返回当前时间（秒）。用于连续变化：

```
time * 360      // 每秒旋转 360 度
Math.sin(time * 2 * Math.PI) * 50  // 正弦波摆动
```

### index

返回图层在合成中的序号（从 1 开始）。用于批量动画：

```
(index - 1) * 0.2  // 每层延迟 0.2 秒
```

### random(min, max)

伪随机数，种子基于图层索引，保持跨帧一致：

```
random([-100, -100], [100, 100])  // 随机二维位置
random(100, 200)                   // 随机数值范围
```

### 控制表达式常用结构

```
// 用滑块控制参数
effect("Slider Control")("Slider")

// 链接到另一个图层的属性
thisComp.layer("Null 1").transform.position

// 条件判断
if (time > 2) { value + 50 } else { value }

// 线性插值
linear(time, 0, 2, 0, 100)

// 弹性缓动
freq = 3; decay = 5;
amp = 100;
amp * Math.sin(freq * time * 2 * Math.PI) / Math.exp(decay * time)
```

## 10 个常用内置效果

| 效果 | 类别 | 核心用途 |
|------|------|---------|
| Curves | 颜色校正 | 精确控制明暗和色彩曲线，替代 Levels |
| Lumetri Color | 颜色校正 | Premiere 同款调色面板，支持 LUT |
| Gaussian Blur | 模糊 | 简单模糊，轨道遮罩中用做柔化过渡 |
| CC Radial Blur | 模糊 | 径向/缩放模糊模拟相机运动 |
| Transform | 扭曲 | 在一个效果内统一控制缩放/旋转/位置，避免图层变换冲突 |
| Mesh Warp | 扭曲 | 网格变形，局部画面扭曲（如修图级调整） |
| Turbulent Displace | 扭曲 | 流体扭曲，模拟水流、热浪、有机变形 |
| Levels / Levels Individual Controls | 颜色校正 | 输入/输出黑场白场 + Gamma 精确控制 |
| Radio Waves | 生成 | 音波扩散/雷达扫描效果 |
| Fill | 生成 | 替换图层颜色，保持 Alpha |

## 关键帧辅助

### 缓入缓出 (Easy Ease)

- F9：应用 Easy Ease（自动计算缓入缓出）
- Shift+F9：Easy Ease In（仅缓入）
- Ctrl+Shift+F9：Easy Ease Out（仅缓出）

### 速度图表与值图表

AE 提供两种图表编辑模式：

- **速度图表**：横轴时间，纵轴速度。水平线=匀速，峰=加速到减速拐点
- **值图表**：横轴时间，纵轴属性值。S 曲线=平滑变化，直线=线性变化

核心技巧：
- 速度图表中拖动手柄控制加减速斜率
- 值图表中拉直曲线可消除缓入缓出中的"回弹感"
- 同时选中多个关键帧按 F9 后微调速度手柄，实现自定义缓动

### 缓动曲线预设

通过 Graph Editor 右击关键帧选择"Keyframe Assistant > Easy Ease"，或安装 EaseCopy 等第三方工具批量处理。

## 常用第三方插件

| 插件 | 开发商 | 用途 |
|------|--------|------|
| Sapphire (Boris FX) | Boris FX | 超过 270 种效果（光晕/辉光/风格化/转场），行业 VFX 标准 |
| Trapcode Particular | Maxon/Red Giant | 粒子系统，模拟火焰/烟雾/星空/魔法 |
| Element 3D | Video Copilot | 3D 模型导入/渲染，无需独立 3D 软件 |
| Motion Bro | Motion Bro | MOGRT 模板管理器，提供文字动画/转场/标题预设库 |
| Red Giant Universe | Maxon | 大量 GPU 加速效果（发光/纹理/转场），性价比高 |
| Optical Glow | Video Copilot | 高质量辉光效果，比原生 Glow 更平滑 |
| Deep Glow | aescripts | 32 位浮点辉光，色彩溢出更自然 |
| Plexus | aescripts | 点线连接网络特效（密集粒子 + 线条） |
| Mocha AE | Boris FX | 平面跟踪与遮罩，集成在 AE 中 |
| Animation Composer | Mister Horse | 免费缓动预设和文字动画助手 |
| EaseCopy | Ian Haigh | 复制粘贴缓动曲线 |

### Sapphire 核心效果

Sapphire 是插件之王，常用效果：

- **S_Glow**：可定制辉光，支持色散
- **S_Shine**：定向光束，3D 文字常用
- **S_LensFlare**：物理级镜头光晕
- **S_WarpBubble**：流体变形转场
- **S_EdgeRays**：边缘光射出效果

### Trapcode Particular

粒子系统的行业标准。核心概念：

- **Emitter**：粒子发射器类型（点/盒子/球形/灯光）
- **Particle**：粒子外观（sprite/texture/sphere）
- **Physics**：物理模拟（重力/空气阻力/湍流/撞墙）
- **Aux System**：二次粒子（火花→烟雾）
- **OBJ Model**：粒子沿 3D 模型分布

Typical 工作流：点发射器 → 调整气流湍流模拟烟雾 → 辅助系统从主粒子分裂 → 辉光叠加层完成。

## AE 与 Premiere 的 Dynamic Link 工作流

Dynamic Link 是 Adobe 生态的核心优势，让 AE 合成直接在 Premiere 时间线中实时渲染。

### 操作流程

1. 在 Premiere 时间线上选中片段 → 右键 → Replace With After Effects Composition
2. Premiere 自动创建 AE 合成并打开 AE
3. 在 AE 中编辑动画/特效，保存后 Premiere 自动更新
4. 或使用 File > Adobe Dynamic Link > New After Effects Composition

### 注意事项

- **不切断动态链接**：导入 AE 前不要先渲染输出；让时间线直接引用 AE 合成
- **渲染性能**：动态链接在播放时实时渲染 AE 帧，复杂合成会降帧。解决方案：
  - 在 AE 中预览渲染（RAM Preview）后 Premiere 播放缓存的帧
  - 使用 "Render and Replace" 将动态链接替换为渲染视频
- **分辨率匹配**：AE 合成设置应与 Premiere 序列匹配，避免缩放不一致
- **音频安全**：AE 不擅长多轨音频，复杂音频应在 Premiere 处理
- **回套替代**：对调色/VFX 复杂的场景，也可输出 ProRes 4444 回套到 Premiere，比 Dynamic Link 更稳定

### 替代方案

- **回套工作流**：AE 渲染 ProRes 4444 + Alpha → Premiere 导入替换 → 更稳定但迭代慢
- **After Codecs**：AE 输出中间格式后 Premiere 导入

## 与进阶 VFX 的关系

[[concepts/vfx-motion-graphics]] 覆盖了运动跟踪、画面稳定、混合模式等基础 VFX 概念。AE 动态图形是在这些基础上叠加的视觉增强层——文字动画、UI 动效、Logo 演绎、数据可视化、标题序列等。

[[concepts/titling-localization]] 中的 Lower Third 标题设计通常直接在 AE 中完成。
