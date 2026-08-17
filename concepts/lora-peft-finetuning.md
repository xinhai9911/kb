---
lifecycle: draft
base_confidence: 0.85
category: reference
tags:
  - llm
  - lora
  - peft
  - finetuning
  - active
aliases:
  - LoRA
  - PEFT
  - 微调
  - QLoRA
---

# LoRA/PEFT 参数高效微调

## 概述

参数高效微调 (PEFT, Parameter-Efficient Fine-Tuning) 是在保持预训练模型大部分参数冻结的情况下，仅更新少量参数来适应下游任务的技术。LoRA 是其中最主流的方法。

---

## PEFT 技术分类表

| 方法 | 核心思想 | 可训练参数量 | 推理延迟 | 适用场景 |
|------|---------|------------|---------|---------|
| **LoRA** | 低秩矩阵分解注入 | ~0.1%-1% | 无额外 | 通用微调首选 |
| **QLoRA** | 4bit 量化 + LoRA | ~0.1%-1% | 量化推理 | 显存受限 |
| **Prefix Tuning** | 在每层添加可学习前缀向量 | ~0.1% | 略增 | 生成任务 |
| **P-Tuning v2** | 每层插入可学习 prompt token | ~0.1% | 略增 | NLU 任务 |
| **Adapter** | 在 FFN 层间插入小型瓶颈层 | ~1%-5% | 增加延迟 | 多任务切换 |
| **IA3** | 缩放层内激活值 | ~0.01% | 无额外 | 极少参数场景 |
| **DoRA** | LoRA + 分解方向和幅度 | ~0.1%-1% | 无额外 | 追求更高质量 |

---

## LoRA 原理

### 低秩分解

```
W' = W + delta_W = W + B * A

其中:
- W: 原始权重矩阵 (d x d)
- B: 低秩矩阵 (d x r)
- A: 低秩矩阵 (r x d)
- r: 秩 (rank)，通常 r = 8, 16, 32, 64
```

### 参数量对比

- 全量微调: d x d 个参数
- LoRA: d x r + r x d = 2dr 个参数
- 当 d=4096, r=16 时: LoRA 仅需 0.78% 参数

### 关键超参

- **rank (r)**: 秩，越大表达能力越强但参数越多
- **alpha**: 缩放因子，通常 alpha = 2 * r
- **target_modules**: 注入层选择，通常 q_proj, v_proj, k_proj, o_proj
- **dropout**: LoRA 层的 dropout，通常 0.05-0.1

---

## QLoRA 量化微调

### 核心技术

1. **4bit NormalFloat (NF4)**: 基于正态分布的 4bit 量化
2. **双重量化**: 对量化常数再量化
3. **分页优化器**: 避免显存 OOM

### 显存估算

| 精度 | 7B 模型微调 | 70B 模型微调 |
|------|-----------|-------------|
| FP32 全量微调 | ~120GB | ~1.2TB |
| FP16 全量微调 | ~60GB | ~600GB |
| LoRA (FP16) | ~20GB | ~200GB |
| QLoRA (4bit) | ~6GB | ~36GB |

### 适用性

- 单卡微调 70B 模型成为可能
- 推理时可合并回原始权重，无额外延迟

---

## 微调实战步骤

### 1. 数据格式准备

**Alpaca 格式:**
```json
{
  "instruction": "翻译以下文本",
  "input": "Hello, how are you?",
  "output": "你好，你怎么样？"
}
```

**ShareGPT 格式:**
```json
{
  "conversations": [
    {"from": "human", "value": "你好"},
    {"from": "assistant", "value": "你好！有什么可以帮你的？"}
  ]
}
```

### 2. 训练配置

```yaml
# 典型 LoRA 配置
model_name: Qwen/Qwen2.5-7B-Instruct
lora_rank: 16
lora_alpha: 32
lora_dropout: 0.05
target_modules: all-linear
learning_rate: 1e-4
batch_size: 4
gradient_accumulation: 8
epochs: 3
max_seq_length: 2048
```

### 3. DeepSpeed 配置

```json
{
  "bf16": {"enabled": true},
  "zero_optimization": {
    "stage": 2,
    "offload_optimizer": {"device": "cpu"}
  }
}
```

---

## 选型决策树

```
需要微调吗？
  |-- 能通过提示工程解决？ -> 提示工程
  |-- 需要特定领域知识？ -> RAG
  |-- 需要改变模型行为/风格？ -> 微调

微调方式选择？
  |-- 显存充足(>24GB) -> LoRA (FP16)
  |-- 显存不足(<24GB) -> QLoRA (4bit)
  |-- 需要极致性能 -> 全量微调
  |-- 多任务快速切换 -> Adapter
```

### 微调 vs RAG vs 提示工程

| 维度 | 微调 | RAG | 提示工程 |
|------|------|-----|---------|
| 知识注入 | 内化到参数 | 外部检索 | 上下文注入 |
| 成本 | 中-高 | 低 | 低 |
| 更新频率 | 需重训 | 实时更新 | N/A |
| 适用场景 | 风格/行为改变 | 知识密集型 | 简单任务 |

---

## 常见坑

### 1. 过拟合

- 症状: 训练损失很低但验证损失上升
- 原因: 数据量太少或训练轮数太多
- 解决: 减少 epochs, 增加数据, 增大 dropout

### 2. 灾难性遗忘

- 症状: 微调后通用能力大幅下降
- 原因: 学习率过高或数据分布偏移太大
- 解决: 降低学习率, 混合通用数据, 减少训练轮数

### 3. 数据质量

- 垃圾数据导致垃圾输出
- 标注不一致影响模型学习
- 建议: 人工审核数据质量, 去重, 清洗

### 4. 收益递减

- 数据量超过一定阈值后，LoRA 收益递减
- 通常 1K-10K 高质量数据即可获得显著效果
- 追求极致性能时考虑全量微调

---

## 延伸阅读

- [[llm-training-pipeline]] - 完整训练流程中微调阶段的定位
- [[transformer-architecture]] - LoRA 在 Transformer 各层的注入位置
- LoRA 原始论文: https://arxiv.org/abs/2106.09685
- QLoRA 论文: https://arxiv.org/abs/2305.14314
- PEFT 库: https://github.com/huggingface/peft
- LLaMA-Factory: https://github.com/hiyouga/LLaMA-Factory
