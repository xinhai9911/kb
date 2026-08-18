---
aliases: ["llm-training-pipeline-guide"]
kind: source
title: "LLM 训练管线全面指南"
alias: ["Training Pipeline Guide", "预训练-SFT-RLHF"]
year: 2026
url: https://datascience.ocean/llm-training-pipeline
related:
  - concepts/llm-training-pipeline
  - concepts/transformer-architecture
  - entities/openai
  - entities/hugging-face
tags:
  - training
  - pre-training
  - sft
  - rlhf
  - dpo
  - alignment
category: reference
updated: 2026-07-29
summary: LLM 训练管线全流程指南
created: 2026-07-29
lifecycle: draft
sources: []
base_confidence: 0.6
---
# LLM 训练管线全面指南

## 三个阶段

### Phase 1: 预训练（Pre-training）

- **任务**: Causal Language Modeling（因果语言建模/Next Token Prediction）
- **数据**: 数万亿 tokens，涵盖互联网文本、书籍、学术论文、代码
- **规模**: GPT-3 175B 约 $4.6M，LLaMA-3 405B 估计超 $100M
- **架构**: Decoder-only Transformer，通常使用 GQA/RoPE 等优化
- **损失**: Cross-Entropy Loss，仅计算预测 token 位置的损失
- **输出**: 基础模型（Base Model），未对齐，不具备指令跟随能力

### Phase 2: 监督微调（SFT）

- **任务**: Instruction Following
- **数据**: 人工标注的 (指令, 回答) 对
- **格式**: 使用特殊 token（如 `<|im_start|>`）标记对话轮次
- **规模**: 数万到数十万条高质量对话
- **技巧**: 通常仅对回答部分计算损失，指令部分 mask
- **输出**: 指令模型（Instruction Model），具备基本的对话能力

### Phase 3: 对齐（Alignment）

| 方法 | 原理 | 代表模型 | 训练开销 |
|------|------|----------|----------|
| RLHF (PPO) | SFT + 奖励模型 + PPO | GPT-4, Claude | 高 |
| DPO | 直接偏好优化，无奖励模型 | LLaMA-3, Mistral | 中 |
| GRPO | 组相对策略优化，无 Critic | DeepSeek V4 | 低 |
| Constitutional AI | AI 自我对弈 | Claude | 中 |

## 训练基础设施

- **框架**: PyTorch + DeepSpeed/FSDP/Megatron-LM
- **并行策略**: 数据并行 + 张量并行 + 流水线并行 + 序列并行
- **混合精度**: FP16/BF16 为主，FP8 渐成主流（[[sources/DeepSeek 4 技术|DeepSeek V4]]）
- **硬件**: NVIDIA H100/H800/B200，万卡集群

## 关键挑战

- **灾难性遗忘**: 对齐阶段可能损害预训练学到的通用知识
- **数据污染**: 评测集数据可能混入训练数据
- **奖励破解**: 奖励模型可能学到虚假关联而非真实偏好
- **扩展定律**: Scaling Law 在数据量级趋近互联网总量时是否持续有效

## 参考文献

DataSci Ocean. (2026). LLM Training Pipeline Guide. Zhipu AI Technical Blog.


---

## 📖 来源参考

- **LLMForEverybody**：[[sources/LLMForEverybody/索引#预训练|预训练（第01章）]]
> 来自 [luhengshiwo/LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody) 外部知识库导入
