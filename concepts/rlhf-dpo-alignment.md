---
lifecycle: draft
base_confidence: 0.83
category: reference
tags:
  - llm
  - rlhf
  - dpo
  - grpo
  - alignment
  - active
aliases:
  - RLHF
  - DPO
  - GRPO
  - 对齐
---

# RLHF/DPO/GRPO 对齐技术

## 概述

对齐（Alignment）是确保大语言模型的行为符合人类意图和价值观的关键技术。从 RLHF 到 DPO 再到 GRPO，对齐方法在不断演进，追求更高效、更稳定的训练流程。

---

## RLHF 完整流程

### 三阶段训练

```
阶段1: SFT (Supervised Fine-Tuning)
  -> 监督微调基础模型

阶段2: 奖励模型训练 (Reward Model)
  -> 人类标注偏好对 -> 训练奖励模型

阶段3: PPO 优化 (Proximal Policy Optimization)
  -> 使用奖励模型信号 -> 强化学习优化策略
```

### PPO 训练细节

- 目标函数: max E[reward] - beta * KL(policy || reference)
- 使用 KL 散度惩罚防止策略偏离过远
- 需要同时维护 4 个模型: actor, critic, reference, reward
- 计算成本极高，显存需求大

### RLHF 的问题

- 奖励模型可能被 hack（reward hacking）
- 训练不稳定，超参敏感
- 人类标注成本高，质量参差不齐

---

## DPO 直接偏好优化

### 核心思想

DPO (Direct Preference Optimization) 通过数学推导，将奖励模型隐式地嵌入策略优化中，直接从偏好对更新策略。

### 数学推导

传统 RLHF 目标:

```
max E[reward(x,y)] - beta * KL(policy || ref)
```

DPO 的关键洞察: 最优策略与奖励函数的闭式关系:

```
r*(x,y) = beta * log(pi*(y|x) / ref(y|x))
```

DPO 损失函数:

```
L_DPO = -E[log sigma(beta * (log(pi(y_w|x)/ref(y_w|x)) - log(pi(y_l|x)/ref(y_l|x))))]
```

其中 y_w 是偏好（winning），y_l 是非偏好（losing）。

### DPO 优势

- 无需训练奖励模型
- 无需在线采样，训练更稳定
- 显存需求大幅降低（只需 2 个模型）
- 效果与 RLHF 相当甚至更好

---

## GRPO 组相对策略优化

### DeepSeek 方案

GRPO (Group Relative Policy Optimization) 是 DeepSeek 提出的无奖励模型方案。

### 核心机制

1. 对每个 prompt 采样一组响应 (group)
2. 用规则化奖励函数计算组内相对分数
3. 组内归一化后作为优势估计

```
advantage_i = (reward_i - mean(group_rewards)) / std(group_rewards)
```

### 优势

- 完全不需要奖励模型
- 组内相对排名消除了绝对分数的偏差
- 特别适合有明确规则的任务（代码、数学）

---

## Constitutional AI

### Anthropic 方案

- 定义一组宪法原则（如：不帮助暴力、不泄露隐私）
- AI 自我批评并修正回答
- 用修正后的数据做 RLHF

### 流程

```
1. AI 生成初始回答
2. AI 根据宪法原则自我批评
3. AI 修正回答
4. 修正后的 (original, revised) 构成偏好对
5. 用偏好对训练
```

---

## 对齐税 (Alignment Tax)

### 概念

对齐后模型在某些能力上可能下降:

- 创造力下降（过度保守）
- 拒绝合理请求（过度安全）
- 某些专业领域知识减少
- 长文本生成能力下降

### 缓解策略

- 分层对齐: 不同场景使用不同对齐强度
- 可调参数: 在推理时控制对齐程度
- 红队测试: 持续评估对齐效果

---

## 对齐数据构建

### 偏好对格式

```json
{
  "prompt": "如何学习编程？",
  "chosen": "推荐从Python开始...",
  "rejected": "我不知道..."
}
```

### 数据来源

- 人类标注员直接比较
- AI 辅助标注（RLAIF）
- 规则化生成（如代码正确性）
- 用户反馈（点赞/踩）

### 数据质量要求

- 每对差异要明显
- 覆盖多样化场景
- 避免标注者偏见
- 建议每对标注多次取众数

---

## 方法对比表

| 方法 | 是否需奖励模型 | 在线采样 | 计算成本 | 训练稳定性 | 效果 |
|------|--------------|---------|---------|-----------|------|
| RLHF (PPO) | 是 | 是 | 极高 | 低 | 好 |
| DPO | 否 | 否 | 低 | 高 | 好 |
| GRPO | 否 | 是 | 中 | 中 | 好 |
| Constitutional AI | 是 | 是 | 高 | 中 | 好 |
| KTO | 否 | 否 | 低 | 高 | 中上 |

---

## 延伸阅读

- [[llm-training-pipeline]] - 完整训练流程中的对齐阶段
- [[transformer-architecture]] - 基础架构对对齐方法的影响
- InstructGPT 论文: https://arxiv.org/abs/2203.02155
- DPO 论文: https://arxiv.org/abs/2305.18290
- GRPO: DeepSeek 技术报告
