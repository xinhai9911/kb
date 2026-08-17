---
title: LLM 训练管线
category: concepts
tags: [llm, training, pretraining, sft, rlhf]
created: 2026-07-29
updated: 2026-07-29
summary: LLM 预训练、SFT、对齐三阶段训练管线详解
base_confidence: 0.65
lifecycle: draft
lifecycle_changed: 2026-07-29
sources: []
---

<!-- kb-import-backlink:LLMForEverybody -->

> [!info] 外部资料 · LLMForEverybody
> 中文大模型知识库 [[sources/LLMForEverybody/index|LLMForEverybody 导航]] 中的相关章节：
> - [[sources/LLMForEverybody/01-第一章-预训练/大模型训练框架（一）综述|训练框架综述]]
> - [[sources/LLMForEverybody/01-第一章-预训练/大模型分布式训练并行技术（一）概述|分布式训练并行概述]]












# LLM 训练管线

## 三阶段框架

训练一个大语言模型通常需要经过三个主要阶段：

### 第一阶段：预训练（Pre-training）

在互联网规模的文本数据上进行因果语言建模训练。

- **目标**: 最大化似然 $L = \sum_{t} \log P(x_t | x_{<t})$
- **数据**: 数万亿 tokens，从 Common Crawl、Reddit、StackOverflow、Wikipedia 等来源清洗
- **规模**: 从 7B（$~$100K GPU-hours）到 405B（$~$30M GPU-hours）
- **挑战**: 数据去重、质量过滤、毒性过滤、合规审查
- **输出**: Base Model——纯语言模型，不遵循指令

### 第二阶段：监督微调（SFT, Supervised Fine-Tuning）

使用人工标注的（指令, 回答）对让模型学会遵循指令。

- **数据**: 数万到数十万条高质量对话（OpenAssistant、ShareGPT、自标注）
- **格式**: chat template 定义对话的结构化格式
- **策略**: 多轮对话一致性、拒绝回答边界（什么能答什么不能答）
- **输出**: Instruction Model——能进行对话的助手

### 第三阶段：人类偏好对齐（Alignment）

| 方法 | 核心思想 | 需奖励模型 | 代表作 |
|------|----------|-----------|--------|
| RLHF (PPO) | 奖励模型 + 策略优化 | 是 | GPT-4, Claude |
| DPO | 直接从偏好对更新策略 | 否 | LLaMA-3, Mistral |
| GRPO | 组内相对分数优化 | 否 | [[sources/deepseek-v4-technical|DeepSeek V4]] |
| Constitutional AI | 原则驱动的自对弈 | 否 | Claude (Anthropic) |

## 基础设施

### 并行策略
- **数据并行 (DP)**: 每个 GPU 一份完整模型副本
- **张量并行 (TP)**: 单层内切分矩阵乘法
- **流水线并行 (PP)**: 不同 GPU 加载不同层
- **序列并行 (SP)**: 长序列在多个设备间切分

### 训练框架
- **PyTorch + DeepSpeed**: 最广泛的开源方案
- **Megatron-LM**: NVIDIA 官方方案，高性能但灵活性低
- **JAX**: Google 和部分开源社区使用（如 LLaMA 训练也有 JAX 版本）
- **自研框架**: [[entities/openai|OpenAI]]（自研）、[[entities/deepseek|DeepSeek]]（HAI-LLM）、Google（Pathways）

## 数据质量要点

1. **预训练数据**: 必须多样性 + 高质量，去重是关键
2. **SFT 数据**: 多样性 > 数量，需要专家标注
3. **偏好数据**: 成对比较（chosen/rejected），维度包括 helpfulness + harmlessness + honesty
4. **合成数据**: 2025年后，使用强模型生成 -> 弱模型蒸馏的 pipeline 渐成主流

## 训练成本趋势

| 模型 | 参数量 | 训练数据 | 估算成本 |
|------|--------|----------|----------|
| GPT-3 | 175B | 300B tokens | $4.6M |
| LLaMA-3 70B | 70B | 2T tokens | ~$20M |
| LLaMA-3 405B | 405B | 15.6T tokens | ~$100M+ |
| DeepSeek V4 | 671B MoE | 14.8T tokens | 未公开 |

## 当前未解决的问题

- **灾难性遗忘**: 对齐阶段削弱预训练能力
- **评测污染**: 数据集交叉污染严重，建立干净评测越来越难
- **多模态训练**: 文本 + 图像 + 音频 + 视频的统一训练尚未成熟
- **持续学习**: 在不 OOM/遗忘的前提下持续增量训练
