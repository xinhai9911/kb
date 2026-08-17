---
aliases: ["dit-workflow"]
title: 现场 DIT 与数据管理
category: concepts
tags: [video-editing, dit, on-set, data-management, dailies, backup, post-production]
created: 2026-07-30
updated: 2026-07-30
summary: 数字影像工程师（DIT）的现场数据管理流程——从存储卡到剪辑组的完整数据管线、校验策略、日报生成与现场色彩
lifecycle: draft
base_confidence: 0.8
---

# 现场 DIT 与数据管理

## 概述

DIT（Digital Imaging Technician，数字影像工程师）是当代影视制作中不可或缺的桥梁角色。DIT 工作在拍摄现场（On-Set），核心职责：**保证数据安全到达剪辑组**——管理原始素材的拷贝、校验、转码、元数据和现场色彩。

DIT 不是"搬运工"。在专业制作中，DIT 直接影响后期效率和质量。

## DIT 角色定位

| 角色分级 | 职责范围 | 典型任用项目 |
|---------|---------|-------------|
| **DIT / Data Wrangler** | 现场数据备份、校验、组织 | 中小型广告/短片/纪录片 |
| **Senior DIT** | 数据管理 + 现场调色 + Dailies 制作 | 长片/高端剧集 |
| **DIT Supervisor** | 多机位数据流设计 + 色彩管理 + 全流程监控 | 大制作院线/VFX 重片 |

### DIT 核心技能

- **硬件**：RAID/SSD 阵列、校验拷贝系统、HDR 监视器
- **软件**：Silverstack / Hedge / ShotPut Pro / Resolve
- **色彩**：LUT 加载、Log → Rec.709 转换、一级匹配
- **编解码**：RAW 封装理解、Mezzanine 编码、代理生成
- **沟通**：与 DP、剪辑师、调色师之间的色彩和技术沟通

## 现场数据流

### 标准 5 步数据流

```
存储卡 → 备份 1 (Primary) → 备份 2 (Mirror) → 校验 → 转码 → 交付剪辑组
```

### Step-by-Step

1. **卡接收**（Receive）
   - 从摄影助理接收已拍摄的存储卡
   - 检查卡是否物理完好、是否有写入错误

2. **备份 1（主硬盘）**
   - 使用 DIT 工具将卡内容拷贝到主 RAID 或 SSD 阵列
   - 保持文件夹结构与原卡一致

3. **备份 2（冗余硬盘）**
   - 同步拷贝到独立硬盘（物理分离——不同硬盘盒/电脑）  
   - 这是 3-2-1 策略的**现场最小化版本**：1 份素材 + 2 份备份

4. **校验**（Verification）
   - **Checksum 校对**：MD5 / xxHash / SHA-256 逐文件校验
   - 验证拷贝到两处备份的 Checksum 完全匹配
   - 校验不通过 → 重新拷贝 + 标记异常文件

5. **转码 / 日报生成**
   - RAW → 代理文件（ProRes Proxy / DNxHD LB）
   - 套 LUT（Log → Rec.709 / 现场调色 Look）
   - 加场记信息（Slate / Take / TC 烧录）

6. **交付剪辑组**
   - 通知剪辑组数据已就绪
   - 通过硬盘快递 / 云同步（Masv / Aspera）传输
   - 提供元数据日志（拷贝报告、校验报告、素材清单）

### 数据安全原则

- **永远不要写回存储卡**
- **格式化前确认备份完全校验通过**
- **备份介质物理分离**（车中保留一份、片场保留一份）
- **拷贝过程中不关机、不待机**
- **清晰的硬盘标签系统**：`Project_Date_Backup#`

## 常用 DIT 工具

### Silverstack

Pomfort 出品的行业标准 DIT 工具套件，欧洲主流。

| 版本 | 售价 | 核心功能 |
|------|------|---------|
| **Silverstack** | $139/年 | 拷贝、校验、元数据管理、LUT 应用 |
| **Silverstack Lab** | $699/年 | 以上 + Dailies 转码、调色、报告 |
| **Silverstack XT** | $1,399/年 | 完整版 + RAW 转码、多用户、Cloud |

核心功能：
- Offload Wizard：可视化拖放拷贝工作流
- 实时校验：拷贝同时计算 Checksum
- ARRIRAW / RED / BRAW 元数据深度解析
- 自定义报告（Apple Notes / PDF / HTML）
- 现场调色：加载 CDL / LUT，创建 Look
- 集成 Livegrade（现场调色系统）

### Hedge

快速、简洁、可靠的拷贝程序（macOS/Windows）。

- 不解析元数据，只做拷贝 + 校验
- 速度比 Silverstack 更快（纯拷贝，不加载元数据）
- 价格更亲民（$129 终身）
- 适合较小制作或 Data Wrangler 快速备份
- 整合 **Postlab**（远程协作平台）

### ShotPut Pro

老牌 DIT 工具（macOS/Windows），在好莱坞广泛使用。

- 规则引擎：自动重命名、分区、添加元数据
- 双重校验（验证文件大小 + Checksum）
- 复杂的报告模板
- 单次 $199 / Pro 版 $399

### DaVinci Resolve

很多小型制作的 DIT 直接用 Resolve：

- Clone Tool：拖放拷贝，Resolve 内置
- 可直接 Proxy 到 DNxHR / ProRes
- 作为 Dailies 生成工具：色彩空间转换 + LUT + 烧录

### Livegrade (Pomfort/Living Shadows)

**现场调色标准工具**。DIT 使用 Livegrade 为拍摄现场实时调色：
- 连接摄影机 SDI 信号
- 应用 CDL + LUT
- 同时预览 Log + Rec.709 + HDR 版本
- 保存调色元数据传递到后期

## Checksum 校验

校验是 DIT 工作的核心质量保证手段。

| 算法 | 速度 | 碰撞概率 | 推荐 |
|------|------|---------|------|
| **MD5** | 中 | 极低 | **行业标准** |
| **xxHash** | **极快** | 极低 | 大文件首选 |
| SHA-1 | 慢 | 极低 | 旧系统兼容 |
| SHA-256 | 慢 | 理论上接近于零 | 高安全场景 |

**校验流程**：
```
计算源文件 Checksum →
拷贝到目标位置 →
计算目标文件 Checksum →
比较 Source == Target →
如果不匹配 → 重新拷贝
```

Silverstack 默认使用 xxHash（速度优势）+ MD5（兼容性）。

## 现场色彩管理

DIT 的"调色"是现场色彩处理，注意区分：

| 活动 | DIT 现场色彩 | 调色师后期调色 |
|------|-------------|--------------|
| 目的 | 技术正确、监看一致 | 创意风格 |
| 工具 | LUT + CDL only | 色轮 + 窗口 + 跟踪 |
| 可逆性 | **完全可逆**（仅元数据） | 可能破坏原始数据 |
| 输出 | 套 LUT 代理 + 元数据 | 最终母版 |

**标准流程**：
1. DP 在开拍前确定 Look（使用 Livegrade + 参考帧）
2. DIT 将 Look 保存为 CDL（ASC Color Decision List）
3. DIT 将 CDL + LUT 应用到日报拷贝
4. 后期调色师收到原始 RAW + CDL 元数据
5. 调色师以 CDL 为"一级起始点"继续精修

## 日报 (Dailies) 生成

日报是每天拍摄完成后交付给剪辑组的关键产出。

**日报标准内容**：
- 代理文件（ProRes 422 Proxy / DNxHR LB）
- 时码烧录（Timecode Burn-in）含磁带名/场景/镜头/Take
- 套现场 Look（Log → 709 / 预设 LUT / CDL）
- 场记信息嵌入（key/meta data sidecar XML）
- 可按需输出 H.264 远程审阅版本

**日报工作流**：
```
RAW Read → CST to Rec.709 → Apply LUT/CDL → Proxy Encode → Burn TC → Metadata Injection
```

## 片场数据安全策略

| 策略 | 实现方式 |
|------|---------|
| 3-2-1 法则 | 3 副本、2 介质、1 异地 |
| 物理分离 | 两张备份硬盘不在同一位置 |
| 防写保护 | 源卡在验证通过前只读 |
| 安全运输 | 防震箱 + GPS 跟踪（高端项目） |
| 加密 | AES-256 BitLocker / FileVault |
| 物理销毁 | 拍摄完成后的旧硬盘物理销毁或重置 |
| 保险 | 数据保险 + 设备保险（Lloyd's / Fireman's Fund） |

## 关键链接

- [[concepts/存储 归档 策略|存储与归档策略]] — 3-2-1 法则详细说明
- [[concepts/代理 工作流|代理工作流]] — 日报生成相关
- [[concepts/摄影机 RAW 格式|摄影机 RAW 格式]] — DIT 最常处理的格式
- [[concepts/夹层 编解码器|中间件编码]] — 代理编码选择
- [[concepts/交付 编解码器|交付 Codec 选择]]
- [[concepts/调色 调色 工作流|调色工作流]] — CDL → 后期调色衔接
