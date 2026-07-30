---
title: 视频规格与兼容性
category: concepts
tags: [video-editing, specs, frame-rate, resolution, codec, compatibility]
created: 2026-07-30
updated: 2026-07-30
summary: 帧率、分辨率、宽高比、逐行/隔行扫描、帧率转换与 pulldown、像素宽高比等视频技术规格详解
relationships:
  - target: "[[concepts/mezzanine-codec]]"
    type: relates_to
  - target: "[[concepts/delivery-codec]]"
    type: relates_to
  - target: "[[concepts/camera-raw-formats]]"
    type: relates_to
  - target: "[[concepts/proxy-workflow]]"
    type: relates_to
  - target: "[[synthesis/video-editing-pipeline]]"
    type: relates_to
base_confidence: 0.8
lifecycle: draft
lifecycle_changed: 2026-07-30
---

# 视频规格与兼容性

## 帧率

### 常见帧率

| 帧率 (fps) | 标准名称 | 用途 |
|-----------|---------|------|
| 23.976 | 23.98p | NTSC 制电视电影（最常用电影帧率） |
| 24 | 24p | 数字电影（DCP 标准） |
| 25 | 25p | PAL/SECAM 制电视电影，欧洲广播 |
| 29.97 | 29.97p | NTSC 制时基校正标准 |
| 30 | 30p | 逐行扫描非广播（网络视频/会议） |
| 50 | 50p | PAL 制广播电视，高帧率内容 |
| 59.94 | 59.94p | NTSC 制广播电视（常见） |
| 60 | 60p | 数字高帧率（HDMI 输入源） |
| 120 | 120p | 慢动作拍摄（5x/4x 慢放） |

### 23.976 的由来

NTSC 彩色电视系统出现时，为避免色度副载波与音频载波干扰，将 30 fps 降低到 30/1.001 = 29.97 fps。24 fps 的电影在 NTSC 电视上播放时也做了同样的比例调整，产生了 23.976 fps。今天几乎所有"24p"的电影制作实际上使用 23.976。

### 帧率选择策略

- **电影感**：23.976 / 24 fps — 运动模糊自然，叙事节奏
- **电视直播**：29.97 (NTSC) / 25 (PAL) — 广播标准
- **体育/动作**：50 / 59.94 / 60 fps — 减少动态模糊，清晰捕捉快动作
- **电子游戏录制**：60 fps — 匹配屏幕刷新率
- **慢动作拍摄**：120 / 240 fps — 后期以 24 fps 输出获得 5x/10x 慢动作
- **网络流媒体**：23.976 (叙事) / 29.97 (直播) — 带宽效率优先

### 帧率转换注意事项

帧率转换会引入 Judder（抖动）或 Motion Blur 伪像：

- **24p → 29.97p**：需 3:2 Pulldown（见下文）
- **25p → 29.97p**：帧混合或光流插值（时间拉伸 4%）
- **29.97p → 23.976p**：需 Reverse Pulldown
- **60p → 24p**：丢弃帧 + 光流插值
- **任何帧率 → 更高帧率**：帧重复（judder）或光流插值（可能产生伪像）

推荐工具：DaVinci Resolve 的 Optical Flow / Premiere Pro 的光流 (Optical Flow) / Twixtor / Flowframes（RIFE AI）。

## 分辨率层级

| 名称 | 像素 (W×H) | 宽高比 | 总像素 | 使用场景 |
|------|-----------|--------|-------|---------|
| SD (PAL) | 720×576 | 4:3 / 16:9 | 0.4 MP | 旧电视/DVD |
| SD (NTSC) | 720×486 | 4:3 / 16:9 | 0.35 MP | 旧电视/DVD |
| HD | 1280×720 | 16:9 | 0.9 MP | 入门高清/720p 广播 |
| Full HD (FHD) | 1920×1080 | 16:9 | 2.1 MP | 主流高清/蓝光/流媒体 |
| 2K | 2048×1080 | 1.90:1 | 2.2 MP | 数字电影发行 |
| QHD | 2560×1440 | 16:9 | 3.7 MP | 显示器/游戏 |
| 4K UHD | 3840×2160 | 16:9 | 8.3 MP | 流媒体 4K / Ultra HD Blu-ray |
| 4K DCI | 4096×2160 | 1.90:1 | 8.8 MP | 数字电影 4K |
| 5K | 5120×2880 | 16:9 | 14.7 MP | RED 摄影机 / 专业显示器 |
| 6K | 6144×3456 | 16:9 | 21.2 MP | RED / ARRI 摄影机 |
| 8K UHD | 7680×4320 | 16:9 | 33.2 MP | 8K 流媒体 / Super Hi-Vision |
| 8K DCI | 8192×4320 | 1.90:1 | 35.4 MP | 数字电影 8K |

### 分辨率选择策略

- **最终交付**：按平台规范选择（YouTube 最高 8K / 电视剧 1080p-4K / 影院 4K DCI）
- **拍摄**：高于交付分辨率 2x 以上（4K 交付时拍 6K/8K 留 reframe 空间）
- **代理剪辑**：720p 或 1080p 低码率代理
- **VFX**：通常需要原生最高分辨率，避免缩放损失细节

### 上采样 vs 下采样

- **下采样**（如 4K→1080p）：品质无损失，甚至因超采样提升锐度
- **上采样**（如 1080p→4K）：需 AI 算法，Topaz Video AI 是行业标准，RISR（Resolve）次之
- **上采样风险**：过度锐化产生 ringing，细节不足产生软焦感

## 宽高比

| 宽高比 | 名称 | 使用场景 |
|--------|------|---------|
| 4:3 (1.33:1) | Academy / 传统电视 | 旧电视/VHS/CRT 时代标准 |
| 16:9 (1.78:1) | 宽屏电视 | 现代电视/YouTube/流媒体默认 |
| 1.85:1 | 学院宽银幕 | 美国主流电影标准（无变形镜头，摄影机原生遮幅） |
| 2.35:1 / 2.39:1 | 变形宽银幕 | 史诗/大片/宽银幕电影 |
| 2.55:1 | CinemaScope | 早期宽银幕（现已少用） |
| 1:1 | 方形 | Instagram 等社交平台 |
| 4:5 | 人像 | Instagram Feed 图片 |
| 9:16 | 竖屏 | TikTok/Reels/Shorts/手机全屏 |
| 2:1 | Univisium | Netflix 原创剧集常见（如《怪奇物语》） |

### 遮幅 (Letterbox / Pillarbox)

- **Letterbox**：宽画面嵌入窄屏幕，上下加黑条
- **Pillarbox**：高画面嵌入宽屏幕，左右加黑条
- **Windowbox**：四周都有黑条，应避免
- 母版制作时**不应**烧录遮幅黑条，应保留原生宽高比，由播放平台动态添加

### 宽高比转换

- 16:9 → 9:16（竖屏）：裁剪中央区域（损失构图）或上下加模糊背景（更自然）
- 16:9 → 2.39:1：上下添加黑条或裁剪倍率 zoom
- 4:3 → 16:9：左右裁剪或拉伸变形（不可接受）

## 逐行 vs 隔行扫描

| 特征 | 逐行 (Progressive) | 隔行 (Interlaced) |
|------|-------------------|-------------------|
| 扫描方式 | 每帧完整扫描所有行 | 分奇偶场扫描（上半 + 下半场） |
| 标记 | p（如 1080p） | i（如 1080i） |
| 帧/场 | 完整帧 | 每个时间点只有半帧信息 |
| 动态 | 清晰 | 快速运动产生梳状伪像 (Combing) |
| 带宽效率 | 低 | 同等带宽下场频翻倍 |
| 现代使用 | 全部流媒体/电影/数字制作 | 仅存于老旧广播系统 |

### 隔行源的处理

如果收到隔行素材：

1. 在 NLE 中设置为 "Upper Field First" 或 "Lower Field First"
2. 应用去隔行 (Deinterlace) 滤镜
3. 推荐品质：Motion Adaptive Deinterlace > Blend Deinterlace > Bob Deinterlace
4. Resolve 中可自动检测并去隔行

**不要**将隔行素材直接输出为逐行而不去隔行——梳状伪像无法后期逆转。

### 场序 (Field Dominance)

| 标准 | 场序 | 使用区域 |
|------|------|---------|
| PAL | Upper Field First (UFF) | 欧洲/中国 |
| NTSC | Lower Field First (LFF) | 北美/日本 |

错误场序会产生抖动或撕裂效果。确认方式：隔行片段在时间线上移动一帧，如果运动不连续则场序设置错误。

## 帧率转换与 Pulldown

### 3:2 Pulldown（Telecine）

将 24p 电影转换为 29.97p 的过程：

```
24p 帧:    A    B    C    D
         A1 A2 B1 B2 B3 C1 C2 D1 D2 D3
29.97p 场: A1 A2 B1 B2 | B3 C1 C2 D1 | D2 D3 A1 | ...
           └─ 完整帧 ─┘ └─ 3 场帧 ─┘ └─ 混合 ─┘
```

每个 24p 帧被拆分为 2 或 3 场，10 个 24p 帧变为 10×2.5 = 25 个 29.97p 帧。
结果是 4 个 24p 帧 → 5 个 29.97 场，形成规则的 3:2 模式。

### 逆 3:2 Pulldown（Reverse Telecine）

将 29.97p 还原为 23.976p。关键步骤：

1. 检测 pulldown 模式
2. 丢弃重复场
3. 重组原始 24p 帧
4. 调整时间码为 23.976

几乎所有现代 NLE 可自动完成此操作。Resolve 中在 Media Pool 右键片段选择 "Detect Pulldown"。

### 其他 Pulldown

| 类型 | 源 | 目标 | 说明 |
|------|-----|------|------|
| 2:2 Pulldown | 25p | 50i | PAL 制中 25p→50i，每帧拆 2 场 |
| 2:2:2:4 Pulldown | 24p | 25p | 速度调整（4% 加速），欧洲电视电影 |
| 2:3:3:2 Pulldown | 24p | 29.97p | 少用，特定 DV 格式 |

## 像素宽高比 vs 显示宽高比

### PAR (Pixel Aspect Ratio) vs DAR (Display Aspect Ratio)

- **PAR**：单个像素的宽度与高度之比
- **DAR**：整个画面的显示宽高比
- **SAR**（Sample Aspect Ratio）：等同于 PAR

两者关系：

```
DAR = (水平像素数 × PAR) / 垂直像素数
```

### 常见 PAR 值

| 格式 | 水平像素 | 垂直像素 | PAR | DAR | 说明 |
|------|---------|---------|-----|-----|------|
| Square Pixel | 任意 | 任意 | 1:1 | 由分辨率决定 | 现代标准 |
| PAL 4:3 | 720 | 576 | 12:11 | 4:3 | SD 电视 |
| PAL 16:9 | 720 | 576 | 16:11 | 16:9 | 宽屏 SD |
| NTSC 4:3 | 720 | 486 | 10:11 | 4:3 | SD 电视 |
| NTSC 16:9 | 720 | 486 | 40:33 | 16:9 | 宽屏 SD |
| DV NTSC | 720 | 480 | 32:27 (16:9) | 可变 | DV 摄像机 |
| HD | 1920 | 1080 | 1:1 | 16:9 | 现代 HD |
| Anamorphic 2x | 1920 | 1080 | 2:1 | 32:9 | 变形镜头拍摄，后期需要解算 |

### PAR 常见问题

- **错误 PAR**：SD 素材在 HD 时间线中未设置 PAR 会显示为"压扁"或"拉长"的人脸
- **检查 PAR**：Resolve 中 Clip Attributes > Pixel Aspect Ratio
- **转换**：始终在导入阶段将非 1:1 PAR 转换为 Square Pixel，不在导出阶段处理
- **VFX 交接**：确认 AE/Photoshop 导入时未自动改变 PAR

### 为什么 PAR 仍然重要

即使全行业已转向 Square Pixel（1:1 PAR），在以下场合仍需关注：

1. **SD 素材归档重制**：大量历史 DV/DVCAM 素材为 720×480/576，PAR 非 1:1
2. **变形镜头拍摄**：2x squeeze 的素材，需要正确 PAR 才能在时间线正确显示
3. **广播交接**：部分广播规范仍使用 PAL/NTSC PAR
4. **DVD 制作**：必须正确设置 PAR

## 与编解码器选择的关系

视频规格直接影响 [[concepts/mezzanine-codec|Mezzanine 编解码器]] 和 [[concepts/delivery-codec|交付编解码器]] 的选择：

- **高帧率**（60p+）需要更高码率来维持同等画质
- **高分辨率**（4K+）推荐硬件加速编码（NVENC/QuickSync）
- **隔行素材**必须选择支持交错编码的编解码器（ProRes、DNxHR 均支持）
- **PAR 非 1:1** 的素材在转码时需确保正确解算

[[concepts/camera-raw-formats|摄影机 RAW 格式]] 的最佳实践是在拍摄时确定基本规格（帧率/分辨率），后期尽量不转换。
