---
title: 声音设计深挖
category: concepts
tags: [sound-design, foley, ambience, audio-psychology, sound-effects, post-production]
created: 2026-07-29
updated: 2026-07-29
summary: 声音设计的理论、实践与心理学——从 Foley 艺术到沉浸声场，从低频恐惧到寂静的力量
relationships:
  - target: "[[concepts/audio-post-production-pipeline]]"
    type: extends
  - target: "[[entities/avid-pro-tools]]"
    type: uses
  - target: "[[entities/walter-murch]]"
    type: references
  - target: "[[concepts/narrative-psychology-editing]]"
    type: related_to
  - target: "[[synthesis/video-editing-pipeline]]"
    type: part_of
base_confidence: 0.75
lifecycle: draft
lifecycle_changed: 2026-07-29
sources:
  - "https://en.wikipedia.org/wiki/Sound_design"
  - "https://en.wikipedia.org/wiki/Foley_(filmmaking)"
  - "https://en.wikipedia.org/wiki/Ben_Burtt"
  - "https://en.wikipedia.org/wiki/Gary_Rydstrom"
---

# 声音设计深挖

## 概述

[[concepts/audio-post-production-pipeline|音频后期制作管线]]覆盖了音频的工程化流程。本篇深入到声音设计的艺术层面——声音的层次结构、Foley 艺术的技术细节、环境音的构建策略、以及声音对人类心理的作用机制。

## 声音设计的三个层次

### 1. 对白 (Dialogue)

- **优先级最高**：观众对声音内容的理解始终以对白为锚点
- **编辑要点**：去除口水声、唇齿噪声；电平统一（-12 dBFS 平均）；呼吸管理
- **ADR (Automated Dialogue Replacement)**：棚内补录，需要与原场景声学环境匹配
- **ADR 技巧**：使用与拍摄现场相同的麦克风类型、距离和环境混响

### 2. 环境音 (Ambience / Atmos)

- 定义：场景中持续的"底噪"——房间底噪、风声、交通、机械嗡鸣
- 功能：建立空间感、连接镜头之间的"声音桥"
- **关键原则**：环境音**不应被观众注意到**——它的成功在于它的不可见性
- 构建层次：背景层（持续）+ 前景层（间歇性的环境事件：鸟鸣、远处汽车）

### 3. 效果音 (Sound Effects / SFX)

- **硬效果 (Hard FX)**：画面中可见声源的门声、脚步声、碰撞——需要与画面精确同步
- **设计效果 (Designer FX)**：现实中不存在的声音——机器人、能量武器、科幻舰船
- **背景效果 (Background FX)**：背景中的可识别事件——远处的警笛、邻桌的谈话

## Foley 艺术

### 历史

Foley 得名于**Jack Foley**，1920 年代环球影业的音效先驱。在同期录音时代，Jack 开发了在混音棚中实时为画面表演声音的工作方法。这种方法持续至今，被称为 Foley Stage。

### Foley 的三个核心类别

| 类别 | 内容 | 关键技巧 |
|------|------|---------|
| **Footsteps (脚步声)** | 不同地面材质、鞋型、步伐速度 | 每只脚各用一个声道；使用与原片相同的地面材质；同步到画面步行 |
| **Props (道具)** | 衣物摩擦、物体移动、工具使用 | 道具与原物不符时调整 EQ；多层叠加（如纸质 = 基础层 + 细节层） |
| **Cloth (衣物)** | 人物动作产生的布料摩擦 | 在演员动作的每一帧精确跟随；多层次（内衣→外套） |

### 常见 Foley 道具技术

| 想要的声音 | 使用的道具 |
|-----------|-----------|
| 雨声 | 在热板上煎盐或大米 |
| 马蹄声 | 半个椰子壳敲击泥土 |
| 断骨声 | 折断芹菜或树枝 |
| 火焰声 | 揉捏赛璐珞（Celluloid） |
| 脚步声（雪地） | 揉捏玉米淀粉/面粉 |
| 拳击声 | 用湿毛巾拍打生肉 |
| 枪上膛 | 金属扣组合（实际上是多段录制） |
| 扇耳光 | 用手掌拍另一手掌（不同角度的多种变化） |
| 刀入肉 | 用刀切入胡萝卜或西瓜 |
| 骨骼折断 | 意大利面条折断 |

### Foley 录制流程

1. **观看画面**（Spotting Session）— 与导演、剪辑师确定需要 Foley 的镜头
2. **准备阶段** — 收集道具、铺设地面材质（砂石/木板/雪面）
3. **录制（多遍法）** — Foley 艺术家边看画面边"表演"声音，通常需要 3-6 遍
4. **编辑** — 去掉噪音、对齐波形、电平统一
5. **混音集成** — 混入环境音和音乐中，使三者平衡

## 环境音构建：从单声道到沉浸式声场

### 声场层次（从近到远）

```
前景效果        — 画面内事件（精确定位）
     ↓
中场环境        — 画面中的背景动作
     ↓
背景环境（Room Tone）— 持续底噪，建立空间感
     ↓
氛围层（低频嗡鸣） — 几乎不可察觉的空间"音色"
```

### 沉浸式格式的工作流差异

| 格式 | 声道数 | 环境音策略 | 交付标准 |
|------|-------|-----------|---------|
| 立体声 (Stereo) | 2 | 左右声道全景 | -14 LUFS |
| 5.1 Surround | 6 | 前后左右 + LFE | -27 LUFS |
| 7.1 Surround | 8 | 扩展侧后环绕 | -27 LUFS |
| Dolby Atmos | 128+ 对象 | 对象基音床 + 元数据定位 | -18 LUFS |
| Ambisonics | 4 (B-Format) | 球面声场可旋转 | VR / 360 视频 |

### Dolby Atmos 声音设计要点

- **音床 (Bed)**：固定的环绕声道（5.1/7.1）作为基础
- **对象 (Object)**：独立空间定位的声源（最多 118 个对象）
- **Height Channel**：头顶扬声器提供垂直空间感
- 设计原则：不是把所有声音都扔到 3D 空间中——Atmos 的策略是**保留前方声场完整性，用环境/音效扩展空间感**
- 参考影片：《疯狂的麦克斯：狂暴之路》、《1917》、《银翼杀手 2049》

## 声音的心理学

### 低频恐惧

- **机制**：人类听觉对 20-80 Hz 低频的本能警觉——这些频率在自然界中对应大型掠食者移动或地震前兆
- **电影应用**：在恐怖/紧张场景中叠加不可察觉的低频持续嗡鸣，触发观众的生理焦虑反应（心率上升）
- **经典案例**：《黑暗骑士》中 Joker 主题的 30 Hz 低频、《星际穿越》的管风琴低频

### 高频紧张

- **机制**：2-8 kHz 高频对应人类尖叫和婴儿啼哭——触发杏仁核的警觉反应
- **电影应用**：在攻击场景前几秒加入微妙的高频音层
- **经典案例**：《精神病患者》淋浴场景的弦乐高音撕裂、《闪灵》的 dissonant 弦乐

### 寂静的力量

- **原理**：在持续的声景中突然抽掉声音，观众的注意力被瞬间拉入画面
- **应用**：在爆炸前的绝对静音、噩梦惊醒后的消声、死寂空间的营造
- **最佳实践**：沉默不是绝对无声——减去环境音但保留一点点"空气声"（Mic Noise Floor），否则观众会以为是回放设备故障
- **Murch 理论**：Walter Murch 认为剪辑师对沉默的理解决定其剪辑水平的上限

### 声音蒙太奇

- **重叠过渡**：将下一场景的声音提前在当前场景出现——J-Cut 的声音版
- **声音闪回**：当前画面切出特定声音触发回忆（如《教父 II》中 Michael 回想初遇 Kay 的场景）
- **声画对位**：画面内容是灾难，声音是轻松的音乐（如《发条橙》中的 Singin in the Rain）

## 知名声音设计师

- [[entities/walter-murch]] —《现代启示录》音效设计 + 混音，《英语病人》剪辑 + 混音
- [[entities/sound-designer-ben-burtt]] — 星战声音设计之父（光剑、R2-D2、Wookiee）
- [[entities/gary-rydstrom]] —《拯救大兵瑞恩》、《玩具总动员》、《侏罗纪公园》

## 关联页面

- [[concepts/audio-post-production-pipeline]] — 音频后期工程化流程（本页的基础）
- [[entities/avid-pro-tools]] — 行业标准 DAW
- [[entities/walter-murch]] — 声音先行剪辑思想家
- [[entities/sound-designer-ben-burtt]] — 星战声音设计之父
- [[entities/gary-rydstrom]] — 皮克斯 / 战争片音效大师
- [[concepts/narrative-psychology-editing]] — 剪辑叙事心理学（声音是人脑加工的核心输入之一）
- [[synthesis/video-editing-pipeline]] — 全景流水线
