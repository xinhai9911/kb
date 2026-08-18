---
aliases: ["vaswani2017-attention"]
kind: source
title: "Attention Is All You Need"
alias: ["Transformer 原始论文"]
creators: [Vaswani et al.]
year: 2017
url: https://arxiv.org/abs/1706.03762
related:
  - concepts/transformer-architecture
  - entities/openai
  - concepts/llm-inference-optimization
tags:
  - transformer
  - self-attention
  - architecture
category: reference
updated: 2026-07-29
summary: Attention Is All You Need 论文核心内容与影响
created: 2026-07-29
lifecycle: draft
sources: []
base_confidence: 0.6
---
# Attention Is All You Need

## 核心贡献

2017 年 Google 团队的 Vaswani 等人提出了 Transformer 架构，完全基于注意力机制、摒弃循环神经网络（RNN）和卷积神经网络（CNN）。该论文是今天 [[concepts/Transformer 架构|大语言模型]] 的奠基性工作。

## 创新点

- **Scaled Dot-Product Attention**: $Attention(Q, K, V) = softmax(QK^T / \sqrt{d_k}) V$。缩放因子 $\sqrt{d_k}$ 防止 softmax 梯度消失。
- **Multi-Head Attention**: 将 Q/K/V 投影到 h=8 个子空间进行并行注意力计算，拼接后再次投影。
- **Positional Encoding**: 使用正弦/余弦函数为序列位置编码，使无递归的注意力机制能感知顺序。
- **残差连接 + LayerNorm**: 每个子层（Attention/FFN）后均使用残差连接和层归一化。
- **标签平滑**: 训练中使用 $\epsilon_{ls}=0.1$ 的正则化。

## 训练细节

- 英法双语翻译任务，WMT 2014 数据集
- Adam 优化器（$\beta_1=0.9, \beta_2=0.98, \epsilon=10^{-9}$）
- 学习率预热（warmup_steps=4000）后按 $\frac{1}{\sqrt{d_{model}}}$ 衰减
- 正则化：Dropout $P_{drop}=0.1$，标签平滑
- Batch size：~25000 token 对

## 当时记录

- BLEU 41.8（英法），BLEU 28.4（英德）
- 训练耗时 3.5 天（8 张 NVIDIA P100 GPU）
- 首次证明纯注意力机制在主流翻译任务上全面超越 RNN/LSTM

## 后续影响

- 几乎所有 [[entities/OpenAI|OpenAI]] GPT 系列模型均基于 Decoder-only Transformer
- [[concepts/LLM 推理 优化|推理优化]] 领域的 FlashAttention、PagedAttention 解决其 O(n²) 瓶颈
- 架构迭代方向包括：GQA（分组查询注意力）、MQA（多查询注意力）、RoPE（旋转位置编码）、ALiBi（线性偏置位置编码）、MoE（混合专家）

## 参考文献

Vaswani, A., Shazeer, N., Parmar, N., Uszkoreit, J., Jones, L., Gomez, A. N., Kaiser, L., & Polosukhin, I. (2017). Attention Is All You Need. *NeurIPS 2017*.


---

## 📖 来源参考

- **LLMForEverybody**：[[sources/LLMForEverybody/索引#AGI之路|AGI之路（第00章）]] / [[sources/LLMForEverybody/索引#预训练|预训练（第01章）]]
> 来自 [luhengshiwo/LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody) 外部知识库导入
