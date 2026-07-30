---
title: 音频修复实战
category: concepts
tags: [video-editing, audio, post-production, sound-design, audio-repair]
created: 2026-07-30
updated: 2026-07-30
summary: 后期制作中常见音频问题及其修复策略，含 iZotope RX 工作流、降噪策略、电平统一、免费替代工具
relationships:
  - target: "[[concepts/audio-post-production-pipeline]]"
    type: extends
  - target: "[[concepts/sound-design-deep-dive]]"
    type: relates_to
  - target: "[[entities/avid-pro-tools]]"
    type: relates_to
base_confidence: 0.8
lifecycle: draft
lifecycle_changed: 2026-07-30
---

# 音频修复实战

## 常见音频问题及成因

| 问题 | 频率区域 | 典型成因 |
|------|---------|---------|
| 底噪 (Noise Floor) | 全频段 | 增益不足、环境噪声、摄像机前置放大器本底噪声 |
| 风声 (Wind) | 低频（< 200 Hz） | 户外拍摄未使用防风罩/死猫 |
| 咔嗒声 (Click/Pop) | 随机脉冲 | 数字时钟错误、编辑切口不齐、灰尘干扰 |
| 嗡嗡声 (Hum) | 50/60 Hz + 谐波 | 电源接地回路、荧光灯镇流器 |
| 混响 (Reverb) | 中高频 | 小房间反射、多面硬表面 |
| 削波 (Clipping) | 全频段 | 录音电平过高、限幅器不当 |
| 齿音 (Sibilance) | 5-8 kHz | 话筒拾音过近、配音演员发音特点 |
| 嘶声 (Hiss) | 高频（> 8 kHz） | 模拟磁带底噪、无线话筒接收噪声 |
| 咔咔 (Crackle) | 中高频散粒 | 线缆接触不良、电子元件老化 |

## 降噪策略：噪声门 vs 降噪插件

### 噪声门 (Noise Gate)

原理：低于阈值时静音，高于阈值时通过。

```
输入信号 → 电平检测器 → 比较器 → VCA → 输出
                 ↓
            阈值/Attack/Release/ Hold
```

适用场景：
- 说话间隙的背景恒定噪声
- 两句话之间的话筒漏音
- 不需要保留环境音的采访

限制：
- 无法区分噪声和信号的频率差异
- Attack/Release 设置不当会产生"啵啵声"（gate chatter）
- 无法解决与信号重叠的噪声

### 频谱降噪 (Spectral Denoise)

原理：分析噪声样本的频谱特征（噪声指纹），在信号中精确移除匹配频率。

核心参数：
| 参数 | 作用 |
|------|------|
| Noise Floor | 噪声基准线，设置降噪强度 |
| Reduction | 降噪量（dB），通常 6-18 dB |
| Attack/Release | 降噪的响应速度 |
| Frequency Smoothing | 频域平滑度，越高越少"音乐噪声" |
| Algorithm | Spectral（好但慢）vs Spectral Multiband（快）|

痛点：过量降噪会产生"水声"（musical noise/artifacts），尤其是 Reduction > 18 dB 时。

### 选择决策

| 场景 | 推荐方案 |
|------|---------|
| 恒定底噪（空调/风扇） | Spectral Denoise，学习噪声指纹后移除 |
| 说话间隙噪声 | Noise Gate（轻） + Spectral Denoise（重）叠加 |
| 高频嘶声 | De-esser 或 Spectral Denoise 高频限幅 |
| 低频嗡声 | EQ 切除 + Spectral Denoise 针对谐波 |
| 风声 | High-pass filter（80-120 Hz）+ Spectral Denoise |

## 对白修复：iZotope RX 核心功能

iZotope RX 是目前对白修复的行业标准工具，集成在 Pro Tools 生态中。以下是按优先级排列的核心模块。

### Voice De-noise

用途：移除对白中的底噪声。

工作流：
1. Learn（学习噪声指纹）— 选中一段纯噪声区域
2. 调整 Reduction 滑块（默认 12 dB）
3. 用 Threshold 微调保留细节
4. 勾选 Music Mode 处理有背景音乐的对白

核心技巧：RX Advanced 的 Dialogue Contour 模块还可修复不自然的语调变化。

### De-click

用途：移除数字咔嗒声、电子噪声、编辑切口声。

参数：
- Sensitivity：检测灵敏度，越高检出越多
- Click Widening：影响范围，窄=单独点击，宽=连击（如黑胶爆豆）
- Artifact Control：残留伪像控制
- Presets：Default / Moderate / Heavy

策略：先做 De-click，再做其他降噪处理，顺序很重要。

### De-clip

用途：修复削波（波形平顶失真）。

内置算法使用 AI 重建削波部分的波形曲线：
- 轻度削波（3-6 dB）：几乎完美重建
- 重度削波（> 6 dB）：可明显改善但不会完美
- 先用 De-clip 检测削波区域，再选择重建范围

经验规则：如果对白一个词的音节完全削平，De-clip 无法重建——它需要参考相邻周期的波形模式。

### Mouth De-click

用途：移除口水声、嘴唇湿润声、牙齿碰击声——这些是采访/对白最常见的微小噪声。

RX Advanced 独有模块。工作原理：
- AI 模型专门训练识别口腔噪声（不同于普通 De-click）
- Sensitivity 调到 4-6（默认 5）效果最自然
- 处理过重会产生"电子唇"感（mouth dryness artifact）

建议：口齿声可以用 Mouth De-click 处理 80%，剩余 20% 手动用 Spectral Repair 点状修复。

### Spectral Repair

用途：在频谱图上精确修复。

三种修复模式：
| 模式 | 原理 | 适用 |
|------|------|------|
| Attenuate | 衰减选中频率区域 | 远处汽车喇叭、手机铃声 |
| Replace | 用周围频谱填充选中区域 | 咳嗽、翻纸声——对白修复最常用 |
| Fill Single | 替换单帧异常 | 数字咔嗒、瞬态爆点 |

操作：选中频谱图中的问题区域 → 选择模式 → 预览 → 微调参数。

AudioSuite 版本（Pro Tools）和 Standalone 版本均可使用。

## 环境音填充技巧

移除噪声后会产生"音频真空"——死寂比噪声更让人不舒服。

### Room Tone 填充

拍摄现场录制 30-60 秒的房间环境音（无对白）。后期处理中：

1. 用 De-noised 对白后的间隙铺 Room Tone
2. 音量比对白低 20-25 dB
3. 循环时用 Crossfade 避免循环接缝（推荐 50ms）
4. 如果无 Room Tone，从对白间隙中抽取噪声指纹生成环境垫底

### Ambience 匹配

- 同一场景保持同一环境音文件
- 室内 vs 室外环境音差异明显时不可混合
- 使用 Match EQ 或 RX EQ Match 匹配不同镜头的环境音差异

## 电平统一

### Normalize（归一化）

将最高峰值提升到目标电平（如 -3 dBFS 或 -23 LUFS）。

```
gain = target_peak / current_peak
```

- True Peak Normalize 考虑 intersample peaks
- Loudness Normalize 以 LUFS 为标准（ITU-R BS.1770）

### Compressor（压缩器）

降低高电平，提升低电平，缩小动态范围。

| 参数 | 作用 |
|------|------|
| Threshold | 开始压缩的电平阈值 |
| Ratio | 压缩比（超过阈值部分，4:1=每 4 dB 输出 1 dB） |
| Attack | 压缩触发速度（对白典型 10-30ms） |
| Release | 压缩释放速度（对白典型 50-100ms） |
| Knee | 软拐点 vs 硬拐点 |

对白推荐设置：Ratio 2:1-3:1, Attack 10ms, Release 50ms, Threshold -20 dBFS。

### Limiter（限幅器）

高比率压缩器（通常 Ratio > 10:1），只阻止信号超过阈值。

- 用于最终保护输出不削波
- True Peak Limiter 考虑 intersample peaks
- 设置 -1 dBTP 或 -2 dBTP 作为安全余量

### 选择策略

| 目标 | 方案 |
|------|------|
| 所有对白平均电平一致 | Normalize to -23 LUFS (broadcast) 或 -16 LUFS (web) |
| 缩小动态范围 | Compressor 2:1-4:1 |
| 保护输出不削波 | Limiter -1 dBTP |
| 说话音量忽大忽小 | Leveler (RX Leveler) → Vocal Rider → 手动 Clip Gain |
| 综合 | Leveler → Compressor → Limiter（经典链条） |

## 免费替代工具

### Audacity

- 免费开源，跨平台
- 降噪：Effect > Noise Reduction（两步：Noise Profile → Apply）
- 频谱分析：Spectrogram view
- 压缩器：Effect > Compressor（简单够用）
- 格式支持有限（无 AAF/OMF 导入，需中间文件手动对齐）

### FFmpeg 音频滤镜

脚本级降噪方案，适合批处理：

```
ffmpeg -i input.wav -af afftdn=nf=-25 output.wav
ffmpeg -i input.wav -af highpass=f=80,lowpass=f=8000 output.wav
ffmpeg -i input.wav -af volume=6dB output.wav
ffmpeg -i input.wav -af dynaudnorm output.wav
```

参数说明：
- `afftdn`：自适应 FFT 降噪，`nf` 设置噪声底
- `highpass/lowpass`：频段滤波器
- `anlmdn`：非局部均值降噪（更现代）
- `dynaudnorm`：动态音频归一化（替代压缩）
- `loudnorm`：ITU-R BS.1770 响度归一化

限噪：FFmpeg 降噪效果远不如 iZotope RX，适合不需要高质量的前期粗剪或素材预处理。

### 其他免费工具

- **OcenAudio**：轻量级，频谱编辑能力比 Audacity 更精细
- **SoX (Sound eXchange)**：命令行音频处理瑞士军刀
- **Reaper**：商业但 60 天全功能试用，脚本生态媲美 Pro Tools
- **Datomic E3**：免费谱谱编辑插件（VST）
- **Waves WLM Plus**：免费 LUFS 表

## 修复流程建议

```
原始音轨
  │
  ├── 1. De-click (移除数字咔嗒)
  ├── 2. Mouth De-click (移除口齿声)
  ├── 3. Spectral Repair (点状移除咳嗽/翻纸)
  ├── 4. Voice De-noise / Spectral Denoise (降底噪)
  ├── 5. EQ (修音色平衡)
  ├── 6. De-esser (控齿音)
  ├── 7. Leveler / Compressor (统一电平)
  ├── 8. Room Tone 填充间隙
  └── 9. Limiter (保护输出)
```

顺序不可随意调换：噪声移除（1-4）必须在动态处理（7-9）之前，否则压缩器会放大噪声。

对白编辑与混合的完整流程参见 [[concepts/audio-post-production-pipeline]]。声音设计深挖参见 [[concepts/sound-design-deep-dive]]。
