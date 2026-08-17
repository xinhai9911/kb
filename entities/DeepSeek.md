---
aliases: ["deepseek", "DeepSeek 2"]
title: DeepSeek
category: entities
tags: [ai, llm, deepseek, open-source]
created: 2026-07-29
updated: 2026-07-29
summary: DeepSeek 开源 MoE 大模型与定价策略
base_confidence: 0.65
lifecycle: draft
lifecycle_changed: 2026-07-29
sources: []
---

<!-- kb-import-backlink:LLMForEverybody -->

> [!info] 外部资料 · LLMForEverybody
> 中文大模型知识库 [[sources/LLMForEverybody/索引|LLMForEverybody 导航]] 中的相关章节：
> - [[sources/LLMForEverybody/01-第一章-预训练/一文了解Deepseek系列中的MLA技术|DeepSeek MLA]]












# DeepSeek

## 概览

DeepSeek（深度求索）是中国幻方量化（High-Flyer）旗下的大模型公司，总部杭州。以 **MoE 架构 + 极致开源** 策略在全球 AI 社区引起巨大关注。其 API 定价仅为 GPT-4 的 1/70，极大推动了推理成本下行。

## 发展历程

| 时间 | 事件 |
|------|------|
| 2023 | DeepSeek 公司成立，发布首个模型 |
| 2024 | DeepSeek V2 发布，MoE 架构，推理效率突出 |
| 2024 | DeepSeek-Coder 在编程基准上表现亮眼 |
| 2025 | DeepSeek V4 发布，MTP + GRPO + FP8 训练 |
| 2025 | 全模型系列开源（MIT/Apache 2.0） |

## 技术策略

### 架构
- **MoE (Mixture of Experts)**: 总参数 671B，每次推理仅激活 37B
- **MTP (Multi-Token Prediction)**: 一次预测多个未来 token
- **GRPO**: 自研对齐方法，无需 Critic 模型
- **FP8 训练**: 全程 FP8 混合精度

### 开源承诺
- 所有模型权重和推理代码全量开源
- 训练技术报告详细公开（架构、数据、超参数）
- 社区可自由下载、推理、微调

## 产品矩阵

| 模型 | 规模 | 特点 |
|------|------|------|
| DeepSeek V4 | 671B MoE | 旗舰模型，对标 GPT-4/Claude |
| DeepSeek-Coder | 多尺寸 | 编程专项模型 |
| DeepSeek-VL | 多模态 | 图文理解 |
| DeepSeek-Math | 专项 | 数学推理 |

## 影响力

- 推动全球 API 定价下降 10x+
- "开源模型能否追平闭源"讨论的核心证据
- 国产芯片适配标杆（昇腾 910B/910C）
- NVIDIA GPU 出口管制背景下，用受限硬件做出世界级模型

## 挑战

- **数据来源合规性**: 训练数据的版权和法律风险
- **价值观对齐**: 中文互联网内容的审查和价值观校准
- **出口管制不确定性**: 随中美关系波动的供应链风险
- **盈利压力**: 极低定价策略的长期可持续性
