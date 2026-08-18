---
aliases: ["llm-inference-optimization"]
kind: source
title: "LLM 推理优化技术综述"
alias: ["Inference Optimization", "推理加速"]
year: 2026
url: https://zylos.ai/llm-inference-optimization
related:
  - concepts/llm-inference-optimization
  - concepts/transformer-architecture
  - entities/hugging-face
tags:
  - inference
  - quantization
  - vllm
  - flash-attention
  - speculative-decoding
category: reference
updated: 2026-07-29
summary: LLM 推理优化技术与引擎对比
created: 2026-07-29
lifecycle: draft
sources: []
base_confidence: 0.6
---
# LLM 推理优化技术综述

## 核心挑战

LLM 推理的自回归特性（逐 token 生成）导致两个瓶颈：
1. **计算瓶颈**: 每步需计算整个 transformer 层的前向传播
2. **内存瓶颈**: KV Cache 随序列长度线性增长，对长上下文场景影响巨大

## 关键优化技术

### FlashAttention (2022-2025)

- **IO-Aware**: 将注意力计算拆分为 tiles，利用 SRAM 避免 HBM 读写
- **FlashAttention-2**: 减少非矩阵乘法操作，并行化 attention 计算
- **FlashAttention-3 (FP8)**: 利用 Hopper GPU 的 Tensor Core FP8 支持
- 效果: 2-4x 训练/推理加速

### PagedAttention (vLLM, 2023)

- 将 KV Cache 分页管理，类似操作系统的虚拟内存
- 消除 KV Cache 碎片，实现近乎 100% 显存利用率
- 支持 Copy-on-Write，对 Sampling 并行生成友好
- vLLM 是目前部署最广的开源推理引擎

### 量化 (Quantization)

| 精度 | 内存节省 | 质量损失 | 典型方法 |
|------|----------|----------|----------|
| FP16/BF16 | 0x | 无 | 基准 |
| FP8 | 2x | 极小 | DeepSeek V4, H100 |
| INT4 | 4x | 轻微 | GPTQ, AWQ |
| INT2/NF4 | 8x | 可见 | GGML, QLoRA |

### 推测解码 (Speculative Decoding)

- 草稿模型快速生成候选 Token 序列
- 主模型并行验证，接受通过率高的前缀
- 无损加速 2-3x
- 适用于批量推理 > 实时场景

## 主流推理引擎

| 引擎           | 适用场景            | 关键特性                                |
| ------------ | --------------- | ----------------------------------- |
| vLLM         | 通用生产部署          | PagedAttention, Continuous Batching |
| llama.cpp    | CPU/边缘/本地       | GGUF 量化格式, 跨平台                      |
| TensorRT-LLM | NVIDIA 最优       | 图优化, 融合核, FP8                       |
| TGI          | Hugging Face 生态 | 与 Transformers 库深度集成                |

## 参考文献

Zylos AI. (2026). LLM Inference Optimization: A Comprehensive Guide.

## 🔗 关联

- [[concepts/LLM 推理 优化|LLM 推理优化]] — 概念笔记
- [[sources/LLMForEverybody/索引|LLMForEverybody 导航]] — 第二章「部署与推理」
