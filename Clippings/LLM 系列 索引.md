---
title: "LLM 系列（索引）"
source: "https://cloud.tencent.com/developer/article/2530467"
author: "磊叔的技术博客"
created: 2026-08-19
description: "公众号《磊叔的技术博客》（glmapper_2018）在腾讯云开发者社区的《LLM 系列》文章导航索引（第 2~20 篇，共 19 篇），从基础概念、模型训练/推理、数学基础、RAG、上下文工程到注意力/FFN 原理拆解，再到 DeepSeek-V4 前沿分析。"
tags:
  - "clippings"
  - "LLM 系列"
  - "MOC"
---

# LLM 系列（索引）

> 作者：[[Clippings/LLM 系列（二）：基础概念篇-腾讯云开发者社区-腾讯云|磊叔的技术博客]] ｜ 同步自微信公众号 **glmapper_2018**，发布于腾讯云开发者社区。
> 本页是这个系列的入口：按篇目顺序汇总全部 19 篇剪藏，并回链库内相关笔记。

## 篇目一览（二~二十）

| 篇目 | 主题 | 原始发表 | 腾讯云原文 | 本库笔记 |
| --- | --- | --- | --- | --- |
| 二 | 基础概念篇 | 2025-06-10 | [原文](https://cloud.tencent.com/developer/article/2530467) | [[LLM 系列（二）：基础概念篇-腾讯云开发者社区-腾讯云|笔记]] |
| 三 | 核心技术之架构模式 | 2025-06-16 | [原文](https://cloud.tencent.com/developer/article/2532151) | [[LLM 系列（三）：核心技术之架构模式-腾讯云开发者社区-腾讯云|笔记]] |
| 四 | 神奇的魔法数 27 | 2025-06-20 | [原文](https://cloud.tencent.com/developer/article/2533264) | [[LLM 系列(四)：神奇的魔法数 27-腾讯云开发者社区-腾讯云|笔记]] |
| 五 | 模型训练篇 | 2025-07-01 | [原文](https://cloud.tencent.com/developer/article/2536981) | [[LLM 系列（五）：模型训练篇-腾讯云开发者社区-腾讯云|笔记]] |
| 六 | 模型推理篇 | 2025-07-07 | [原文](https://cloud.tencent.com/developer/article/2551256) | [[LLM 系列（六）：模型推理篇-腾讯云开发者社区-腾讯云|笔记]] |
| 七 | 数学概念篇 | 2025-07-13 | [原文](https://cloud.tencent.com/developer/article/2540456) | [[LLM 系列（七）：数学概念篇-腾讯云开发者社区-腾讯云|笔记]] |
| 八 | RAG 篇 | 2025-07-20 | [原文](https://cloud.tencent.com/developer/article/2544765) | [[LLM 系列（八）：RAG 篇-腾讯云开发者社区-腾讯云|笔记]] |
| 九 | RAG 番外篇-从文档到向量 | 2025-08-03 | [原文](https://cloud.tencent.com/developer/article/2552398) | [[LLM 系列（九）：RAG 番外篇-从文档到向量-腾讯云开发者社区-腾讯云|笔记]] |
| 十 | RAG 番外篇-向量检索 | 2025-08-26 | [原文](https://cloud.tencent.com/developer/article/2563637) | [[LLM 系列（十）：RAG 番外篇-向量检索-腾讯云开发者社区-腾讯云|笔记]] |
| 十一 | 从 DeepSeek UE8M0 来回顾精度革命 | 2025-08-28 | [原文](https://cloud.tencent.com/developer/article/2563638) | [[LLM 系列（十一）：从 DeepSeek UE8M0 来回顾精度革命-腾讯云开发者社区-腾讯云|笔记]] |
| 十二 | 解读 Function Calling | 2025-09-09 | [原文](https://cloud.tencent.com/developer/article/2583842) | [[LLM 系列（十二）：解读 Function Calling-腾讯云开发者社区-腾讯云|笔记]] |
| 十三 | 解读 Context Engineering | 2025-09-20 | [原文](https://cloud.tencent.com/developer/article/2583843) | [[LLM 系列（十三）：解读 Context Engineering-腾讯云开发者社区-腾讯云|笔记]] |
| 十四 | 解读 Deep Research | 2025-10-10 | [原文](https://cloud.tencent.com/developer/article/2583844) | [[LLM 系列（十四）：解读 Deep Research-腾讯云开发者社区-腾讯云|笔记]] |
| 十五 | Positional Encoding | 2025-11-11 | [原文](https://cloud.tencent.com/developer/article/2592796) | [[LLM 系列（十五）：Positional Encoding-腾讯云开发者社区-腾讯云|笔记]] |
| 十六 | 输出采样 | 2025-11-14 | [原文](https://cloud.tencent.com/developer/article/2592793) | [[LLM 系列（十六）：输出采样-腾讯云开发者社区-腾讯云|笔记]] |
| 十七 | 残差连接 Residual Connection | 2025-12-04 | [原文](https://cloud.tencent.com/developer/article/2607782) | [[LLM 系列（十七）：残差连接 Residual Connection-腾讯云开发者社区-腾讯云|笔记]] |
| 十八 | 注意力机制 Attention | 2025-12-19 | [原文](https://cloud.tencent.com/developer/article/2609606) | [[LLM 系列（十八）：注意力机制 Attention-腾讯云开发者社区-腾讯云|笔记]] |
| 十九 | 前馈神经网络 FFN | 2026-01-30 | [原文](https://cloud.tencent.com/developer/article/2627429) | [[LLM 系列（十九）：前馈神经网络 FFN-腾讯云开发者社区-腾讯云|笔记]] |
| 二十 | 解读 DeepSeek-V4 | 2026-04-26 | [原文](https://cloud.tencent.com/developer/article/2661157) | [[LLM 系列（二十）：解读 DeepSeek-V4-腾讯云开发者社区-腾讯云|笔记]] |

## 系列脉络

- **基础与训练**：二 基础概念篇 · 三 核心技术之架构模式 · 四 神奇的魔法数 27 · 五 模型训练篇 · 六 模型推理篇 · 七 数学概念篇
- **RAG 专题**：八 RAG 篇 · 九 RAG 番外篇-从文档到向量 · 十 RAG 番外篇-向量检索
- **工程与应用**：十一 从 DeepSeek UE8M0 来回顾精度革命 · 十二 解读 Function Calling · 十三 解读 Context Engineering · 十四 解读 Deep Research
- **原理拆解**：十五 Positional Encoding · 十六 输出采样 · 十七 残差连接 Residual Connection · 十八 注意力机制 Attention · 十九 前馈神经网络 FFN
- **前沿追踪**：二十 解读 DeepSeek-V4

## 关联知识库笔记

[[concepts/Transformer 架构|Transformer 架构]] · [[concepts/分词器 LLM|分词器]] · [[sources/推理引擎/PagedAttention|PagedAttention]] · [[concepts/RAG 检索 增强 生成|RAG 检索增强生成]] · [[concepts/LLM 训练 流水线|LLM 训练流水线]] · [[sources/推理引擎/LLM 推理 优化|LLM 推理优化]] · [[sources/Vaswani 2017 Attention|Attention Is All You Need]] · [[sources/LLMForEverybody/索引|LLMForEverybody]] · [[sources/中文 LLM 全景|中文 LLM 全景]] · [[sources/推理引擎/vllm|vLLM]] · [[sources/推理引擎/tensorrt-llm|TensorRT-LLM]]

## 备注

- 系列编号从「二」开始；《LLM 系列（一）》未在本站点检索到（可能为公众号独发篇目或编号随之调整）。
- 全部 19 篇均为公众号同步转载，原始出处：磊叔的技术博客（glmapper_2018）；腾讯云体系外亦可见于其公众号。
