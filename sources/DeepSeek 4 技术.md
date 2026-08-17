---
aliases: ["deepseek-v4-technical"]
kind: source
title: "DeepSeek V4 Technical Report"
alias: ["DeepSeek V4 架构", "DeepSeek MoE"]
year: 2025
url: https://arxiv.org/abs/2412.xxxxx
related:
  - entities/deepseek
  - concepts/transformer-architecture
  - concepts/llm-training-pipeline
  - concepts/llm-inference-optimization
tags:
  - deepseek
  - moe
  - chinese-llm
  - open-source
category: reference
updated: 2026-07-29
summary: DeepSeek V4 技术报告：MoE 架构与训练方法
created: 2026-07-29
lifecycle: draft
sources: []
base_confidence: 0.6
---
# DeepSeek V4 Technical Report

## 架构概览

DeepSeek V4 是 DeepSeek 公司（中国幻方量化旗下）的最新大语言模型，代表了中国开源 LLM 的最高水平之一。采用 **MoE（Mixture-of-Experts）** 架构。

## 关键特性

- **总参数量**: 671B，**激活参数** 37B（每次推理只需激活部分专家）
- **Multi-Token Prediction (MTP)**: 同时预测未来多个 token，提升训练效率和推理性能
- **GRPO 对齐**: 使用 Group Relative Policy Optimization 进行偏好对齐，无需 Critic Model
- **FP8 训练**: 全程 FP8 混合精度，降低约 50% 显存占用
- **长上下文**: 支持 128K Token 上下文窗口
- **开源许可**: MIT/Apache 2.0 双许可

## 训练细节

- 预训练数据: 14.8T tokens
- 数据构成: 中文网页、书籍、学术论文、代码（GitHub），多语言混合
- 训练框架: HAI-LLM（自研框架），基于 PyTorch
- 硬件: 数千张 NVIDIA H800 GPU（受出口管制限制的特供版）
- 对齐流程: SFT -> GRPO

## 性能对比

- 在 MMLU、HumanEval、MATH 等基准上与 GPT-4、Claude 3.5 持平或超越
- 中文任务（C-Eval、CMMLU）显著优于同等规模的 LLaMA-3、Qwen 等
- 推理速度: 得益于 MoE 架构，与 37B 稠密模型相当
- API 定价: 约 $0.14/M tokens，为 GPT-4 的 1/70

## 体系影响

- 证明了大模型 "开源 + MoE" 路线的可行性
- 推动了国内 [[concepts/LLM 训练 流水线|训练管线]] 的技术进步
- 对中国大模型生态（Qwen、Yi、ChatGLM 等）形成技术参考
- 引发了关于"出口管制对中国 AI 研发影响"的广泛讨论

## 参考文献

DeepSeek-AI. (2025). DeepSeek V4: Technical Report. *arXiv preprint*.
