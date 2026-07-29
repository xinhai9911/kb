---
title: 'Research: AI 大模型'
category: synthesis
tags: [ai, llm, research]
created: 2026-07-29
updated: 2026-07-29
summary: AI 大模型全景综述：架构、训练、推理、生态
base_confidence: 0.7
lifecycle: draft
lifecycle_changed: 2026-07-29
sources: []
---
# AI 大模型全景综述

## 知识图谱

```
Transformer 架构 [concepts/transformer-architecture]
  ├── 来源于: [sources/vaswani2017-attention]
  ├── 改进: [concepts/llm-inference-optimization]
  │
  ├── 代表实体:
  │   ├── [entities/openai] → GPT 系列 (闭源)
  │   ├── [entities/deepseek] → DeepSeek V4 (开源, 中国)
  │   └── [entities/hugging-face] → 开源生态枢纽
  │
  └── 训练方法: [concepts/llm-training-pipeline]
      └── 详细指南: [sources/llm-training-pipeline-guide]
```

## 核心结论

### 1. Transformer 仍是最优基础架构

自 2017 年提出以来，Transformer 的 Decoder-only 变体主导了大模型领域。所有改进（GQA、RoPE、MoE、MTP、FlashAttention）均在此框架内优化，而非颠覆。

### 2. "预训练 → SFT → 对齐"三阶段范式确立

当前几乎所有主流模型遵循此管线。分歧在于第三阶段的选择：
- [[entities/openai|OpenAI]] / Anthropic 坚持 RLHF
- Meta (LLaMA-3) 、Mistral 使用 DPO
- [[entities/deepseek|DeepSeek]] 使用 GRPO（最简方案）

### 3. 开源与闭源差距急剧缩小

DeepSeek V4 和 LLaMA-3 405B 证明开源模型在多数基准上可与 GPT-4 级闭源模型匹敌。关键差距转移到了：
- 安全对齐质量
- 推理效率（工程优化）
- 多模态能力

### 4. 推理优化成为核心竞争点

推理成本直接影响产品可行性。FlashAttention、PagedAttention、量化、推测解码等技术组合可降低 10x+ 推理成本。[[entities/deepseek|DeepSeek]] 以 $0.14/M tokens 的定价将竞争推向白热化。

### 5. 中国大模型生态双轨并行

中国形成**开源（DeepSeek/Qwen）vs 闭源（百度/字节/腾讯）**的双轨格局。国产芯片（昇腾 910C）适配和监管合规是两个关键壁垒。中文场景表现本土模型占优。

## 开放问题

| 问题 | 涉及 |
|------|------|
| Scaling Law 是否持续有效？ | 预训练数据可能于 2026-2028 年耗尽 |
| RLHF vs DPO vs GRPO 哪个更优？ | 依赖场景和评测维度 |
| 开源模型能否追赶多模态能力？ | 多模态对齐难度远高于文本 |
| 国产芯片能否支撑万亿参数训练？ | 昇腾 vs NVIDIA 的差距 |
| 大模型的盈利模式是什么？ | 定价战 vs 应用层价值 |

## 闭包检查（provenance coverage）

- ✅ Transformer 架构 → [sources/vaswani2017-attention] (extracted)
- ✅ MoE + MTP + GRPO → [sources/deepseek-v4-technical] (extracted)
- ✅ 三阶段训练管线 → [sources/llm-training-pipeline-guide] (extracted)
- ✅ 推理优化技术 → [sources/llm-inference-optimization] (extracted)
- ✅ 中国大模型格局 → [sources/chinese-llm-landscape] (extracted)
- ✅ Hugging Face 生态 → [sources/huggingface-ecosystem] (extracted)
- ✅ 开放式问题标记 → 已在各 source 页的 ambiguous 字段记录
