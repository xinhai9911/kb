---
aliases: ["mindformers-models-r1.8.0"]
title: "MindSpore Transformers 模型库（官方文档 r1.8.0）"
tags: [mindspore, ascend, llm, models, official-docs, active]
lifecycle: active
category: reference
base_confidence: 0.85
created: 2026-08-17
updated: 2026-08-17
summary: >-
  MindSpore Transformers r1.8.0 官方模型库：支持 50+ 模型，涵盖 LLaMA/Qwen/DeepSeek/GLM/Baichuan 等
  稠密/稀疏 LLM 及 CogVLM/Whisper/Qwen-VL 等多模态模型，区分 Mcore/Legacy 架构。
source: https://www.mindspore.cn/mindformers/docs/zh-CN/r1.8.0/introduction/models.html
---

# MindSpore Transformers 模型库（官方文档 r1.8.0）

> 📄 本文档抓取自 MindSpore Transformers v1.8.0 官方文档，作为参考归档。

## 模型总览

当前 MindSpore Transformers 支持 **50+ 模型**，按类型分为稠密 LLM、稀疏 LLM（MoE）和多模态（MM）。

### 最新 Mcore 架构模型（r1.8.0）

| 模型 | 规格 | 类型 | 架构 | 版本 |
|------|------|------|------|------|
| **Qwen3** | 0.6B/1.7B/4B/8B/14B/32B | 稠密 LLM | Mcore | 1.8.0 |
| **Qwen3-MoE** | 30B-A3B/235B-A22B | 稀疏 LLM | Mcore | 1.8.0 |
| **DeepSeek-V3** | 671B | 稀疏 LLM | Mcore/Legacy | 1.8.0 |
| **GLM4.5** | 106B-A12B/355B-A32B | 稀疏 LLM | Mcore | 1.8.0 |
| **GLM4** | 9B | 稠密 LLM | Mcore/Legacy | 1.8.0 |
| **TeleChat2** | 7B/35B/115B | 稠密 LLM | Mcore | 1.8.0 |

### Legacy 架构模型（r1.5.0 及更早）

| 模型 | 规格 | 类型 | 版本 |
|------|------|------|------|
| **Qwen2.5** | 0.5B~72B | 稠密 LLM | 1.8.0 |
| **Llama3.1** | 8B/70B | 稠密 LLM | 1.7.0 |
| **Mixtral** | 8x7B | 稀疏 LLM | 1.7.0 |
| **CodeLlama** | 34B | 稠密 LLM | 1.5.0 |
| **CogVLM2-Image** | 19B | 多模态 | 1.5.0 |
| **CogVLM2-Video** | 13B | 多模态 | 1.5.0 |
| **DeepSeek-V2** | 236B | 稀疏 LLM | 1.5.0 |
| **DeepSeek-Coder-V1.5** | 7B | 稠密 LLM | 1.5.0 |
| **DeepSeek-Coder** | 33B | 稠密 LLM | 1.5.0 |
| **GLM3-32K** | 6B | 稠密 LLM | 1.5.0 |
| **GLM3** | 6B | 稠密 LLM | 1.5.0 |
| **InternLM2** | 7B/20B | 稠密 LLM | 1.5.0 |
| **Llama3.2** | 3B | 稠密 LLM | 1.5.0 |
| **Llama3.2-Vision** | 11B | 多模态 | 1.5.0 |
| **Llama3** | 8B/70B | 稠密 LLM | 1.5.0 |
| **Qwen2** | 0.5B~72B | 稠密/稀疏 | 1.5.0 |
| **Qwen1.5** | 7B/14B/72B | 稠密 LLM | 1.5.0 |
| **Qwen-VL** | 9.6B | 多模态 | 1.5.0 |
| **TeleChat** | 7B/12B/52B | 稠密 LLM | 1.5.0 |
| **Whisper** | 1.5B | 多模态 | 1.5.0 |
| **Yi** | 6B/34B | 稠密 LLM | 1.5.0 |
| **YiZhao** | 12B | 稠密 LLM | 1.5.0 |

### 早期模型（r1.3.2 及更早）

| 模型 | 规格 | 类型 | 版本 |
|------|------|------|------|
| **Llama2** | 7B/13B/70B | 稠密 LLM | 1.3.2 |
| **Baichuan2** | 7B/13B | 稠密 LLM | 1.3.2 |
| **GLM2** | 6B | 稠密 LLM | 1.3.2 |
| **GPT2** | 124M/13B | 稠密 LLM | 1.3.2 |
| **InternLM** | 7B/20B | 稠密 LLM | 1.3.2 |
| **Qwen** | 7B/14B | 稠密 LLM | 1.3.2 |

### 基础模型（r1.0 及更早）

| 模型 | 规格 | 类型 | 版本 |
|------|------|------|------|
| **Baichuan** | 7B/13B | 稠密 LLM | 1.0 |
| **Blip2** | 8.1B | 多模态 | 1.0 |
| **Bloom** | 560M~176B | 稠密 LLM | 1.0 |
| **Clip** | 149M/428M | 多模态 | 1.0 |
| **CodeGeex** | 13B | 稠密 LLM | 1.0 |
| **GLM** | 6B | 稠密 LLM | 1.0 |
| **Llama** | 7B/13B | 稠密 LLM | 1.0 |
| **MAE** | 86M | 多模态 | 1.0 |
| **Mengzi3** | 13B | 稠密 LLM | 1.0 |
| **PanguAlpha** | 2.6B/13B | 稠密 LLM | 1.0 |
| **SAM** | 91M~636M | 多模态 | 1.0 |
| **Skywork** | 13B | 稠密 LLM | 1.0 |
| **Swin** | 88M | 多模态 | 1.0 |
| **T5** | 14M/60M | 稠密 LLM | 1.0 |
| **VisualGLM** | 6B | 多模态 | 1.0 |
| **Ziya** | 13B | 稠密 LLM | 1.0 |
| **Bert** | 4M/110M | 稠密 LLM | 0.8 |

## 架构分布统计

| 架构 | 模型数量 | 说明 |
|------|----------|------|
| **Mcore** | 6+ | 新架构，模块化，性能优化 |
| **Legacy** | 40+ | 旧架构，各模型独立实现 |

## 模型类型分布

| 类型 | 数量 | 代表模型 |
|------|------|----------|
| **稠密 LLM** | 35+ | LLaMA, Qwen, GLM, Baichuan, Bloom |
| **稀疏 LLM (MoE)** | 5+ | DeepSeek-V2/V3, Qwen3-MoE, GLM4.5, Mixtral |
| **多模态 (MM)** | 10+ | CogVLM2, Qwen-VL, Whisper, LLaVA, SAM, CLIP |

## 知识关联

- → [[entities/mindspore Transformer]] — MindFormers 套件详解
- → [[50-reference/sources/mindspore/mindformers 概览 r 1 8 0|整体架构]] — 架构与能力
- → [[50-reference/sources/mindspore/mindformers-installation-r1.8.0|安装指南]] — 版本配套与安装

---

**抓取时间**：2026-08-17
**文档版本**：r1.8.0
**维护者**：Claudian