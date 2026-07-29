---
title: LLM 推理优化
category: concepts
tags: [llm, inference, optimization, quantization]
created: 2026-07-29
updated: 2026-07-29
summary: LLM 推理优化技术全景：量化、KV Cache、推测解码
base_confidence: 0.65
lifecycle: draft
lifecycle_changed: 2026-07-29
sources: []
---
# LLM 推理优化

## 问题定义

Transformer 的自回归特性导致推理存在两个核心瓶颈：

1. **计算瓶颈**: 每步生成都需要完整前向传播
2. **内存瓶颈**: KV Cache 随序列长度 O(n) 增长，存储所有历史 K/V 向量

## 优化技术全景

### 1. IO-Aware 计算优化

| 技术 | 原理 | 加速比 | 适用阶段 |
|------|------|--------|----------|
| FlashAttention | 分块计算，利用 SRAM 减少 HBM 读写 | 2-4x | 训练+推理 |
| FlashAttention-2 | 减少非矩阵操作，并行化 | 2-3x over FA1 | 训练+推理 |
| FlashAttention-3 | FP8 Tensor Core 利用 | 1.5-2x over FA2 | H100+ |

### 2. KV Cache 优化

- **PagedAttention (vLLM)**: 分页管理，消除碎片，类似 OS 虚拟内存
- **GQA/MQA**: 减少 KV Head 数量（[[concepts/transformer-architecture|Transformer 架构]]变体）
- **KV Cache 量化**: 对 K/V 做 INT8/FP8 量化存储
- **Window Attention**: 只保留最近 N 步的 KV
- **Cache 共享**: Prefix Caching、RadixAttention

### 3. 模型量化

```
FP16/BF16 (基准, 100%)
  ├── FP8 (推理主流, 50% 内存, 几乎无损)
  ├── INT4 (小损, 25% 内存, GPTQ/AWQ)
  ├── INT2/NF4 (显存极致, 12.5%, GGML)
  └── 混合精度 (不同层不同精度, 最灵活)
```

### 4. 推测解码 (Speculative Decoding)

- 草稿模型（如 7B）快速生成候选序列
- 目标模型（如 70B）以并行方式验证
- 无损加速 **2-3x**

### 5. 系统级优化

- **Continuous Batching**: 动态管理请求进出，而非静态 batch
- **张量/流水线并行**: 多 GPU 分载
- **请求调度**: 优先级队列、请求合并、前缀缓存

## 主流推理引擎对比

| 引擎 | 开源 | 关键特性 | 最佳场景 |
|------|------|----------|----------|
| [[sources/huggingface-ecosystem|vLLM]] | 是 | PagedAttention, 极致显存利用 | 通用生产部署 |
| llama.cpp | 是 | CPU 友好, GGUF 格式, 跨平台 | 本地/边缘/个人 |
| TensorRT-LLM | 是 | NVIDIA 深度优化, 图融合 | 企业批量推理 |
| TGI | 是 | Hugging Face 集成, 易用性 | 快速上线 |
| SGLang | 是 | 结构化生成, 前沿实验特性 | 需要复杂控制 |

## 推理成本趋势

- API 定价持续下降（DeepSeek: $0.14/M tokens vs GPT-4: ~$10/M tokens）
- 长上下文推理（128K+）的成本仍是瓶颈
- Speculative Decoding + 量化 的组合约可降低 5-10x 总成本

## 开放挑战

- 长序列推理（1M+ tokens）的 KV Cache 管理
- 稀疏化加速（Sparse Attention）的生产级落地
- 硬件异构（GPU + CPU + NPU）的混合推理调度
- 隐私推理（TEE/SGX 环境下的推理性能）
