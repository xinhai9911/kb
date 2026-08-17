---
title: Transformer 架构
category: concepts
tags: [transformer, self-attention, architecture, attention-mechanism]
created: 2026-07-29
updated: 2026-07-29
summary: Transformer 架构原理、变体与演化路线
base_confidence: 0.65
lifecycle: draft
lifecycle_changed: 2026-07-29
sources: []
---

<!-- kb-import-backlink:LLMForEverybody -->

> [!info] 外部资料 · LLMForEverybody
> 中文大模型知识库 [[sources/LLMForEverybody/index|LLMForEverybody 导航]] 中的相关章节：
> - [[sources/LLMForEverybody/01-第一章-预训练/什么是大模型的位置编码Position-Encoding|位置编码 Position-Encoding]]
> - [[sources/LLMForEverybody/01-第一章-预训练/从欧拉公式的美到旋转位置编码RoPE|RoPE 旋转位置编码]]
> - [[sources/LLMForEverybody/01-第一章-预训练/10分钟搞清楚为什么Transformer中使用LayerNorm而不是BatchNorm|Transformer 中的 LayerNorm]]












# Transformer 架构

## 定义

Transformer 是一种完全基于注意力机制的神经网络架构，2017 年由 Vaswani 等人提出（[来源](sources/vaswani2017-attention)）。它是所有现代大语言模型（GPT、Claude、LLaMA、DeepSeek、Qwen 等）的底层架构。

## 核心组件

### Scaled Dot-Product Attention

$$Attention(Q, K, V) = softmax(\frac{QK^T}{\sqrt{d_k}}) V$$

- **Q (Query)**: 当前 token 的查询向量
- **K (Key)**: 所有 token 的键向量，决定 Q 关注哪些位置
- **V (Value)**: 所有 token 的值向量，被关注的加权内容
- 缩放因子 $\sqrt{d_k}$ 防止内积过大导致 softmax 进入梯度饱和区

### Multi-Head Attention

- 将 Q/K/V 投影到 h 个不同的子空间，并行计算注意力
- 拼接所有头的输出后再次投影
- 多头让每个头关注不同类型的关系（语法、语义、词法...）

### 位置编码

- 原始 Transformer 使用正弦/余弦函数
- 现代变体多使用 **RoPE**（旋转位置编码，Rotary Position Embedding），如 LLaMA、Mistral、Qwen
- **ALiBi**（注意力线性偏置）在压测中表现出更好的外推能力

### 前馈网络（FFN）

- 两层 MLP：$FFN(x) = W_2 \cdot GELU(W_1 x + b_1) + b_2$
- 在现代模型中通常占 2/3 参数量
- MoE 变体将 FFN 替换为多个"专家"网络

## 架构变体

### Decoder-Only（当代主流）
- GPT、LLaMA、Claude、DeepSeek
- 因果注意力（Causal Attention）：每个 token 只能看前面的 token
- 自回归生成

### Encoder-Only
- BERT、RoBERTa
- 双向注意力
- 用于理解/分类/嵌入

### Encoder-Decoder
- T5、BART
- 原始 Transformer 架构
- 序列到序列任务

## 架构演化路线

```
Transformer (2017)
  ├── GPT (Decoder-only)
  │    ├── GPT-2 → GPT-3 → InstructGPT → GPT-4 → GPT-4o
  │    ├── LLaMA → LLaMA-2 → LLaMA-3
  │    ├── Mistral → Mixtral (MoE)
  │    └── DeepSeek → DeepSeek V4 (MoE + MTP)
  ├── BERT (Encoder-only)
  │    └── RoBERTa → ALBERT → DistilBERT
  └── T5 (Encoder-Decoder)
       └── Text-to-Text Transfer Transformer
```

## 关键改进方向

- **GQA (Grouped Query Attention)**: 减少 KV Head 数量，降低 KV Cache（LLaMA-2 70B+）
- **MQA (Multi-Query Attention)**: 所有查询共享同一组 K/V，进一步减少缓存
- **MoE (Mixture of Experts)**: 稀疏激活，扩展参数规模但保持推理成本（[[sources/deepseek-v4-technical|DeepSeek V4]]、Mixtral）
- **FlashAttention**: IO-Aware 的精确注意力计算（[[sources/llm-inference-optimization|推理优化]]）
- **RoPE/ALiBi**: 更优的位置编码方案
- **MTP (Multi-Token Prediction)**: 同时预测多个未来 token

## 局限性

- **二次复杂度**: 标准 Attention 的计算和内存随序列长度 O(n²) 增长
- **位置编码**: 外推能力在不同长度下存在衰减
- **幻觉**: 注意力机制可能学到虚假的相关性，导致错误知识输出
