---
aliases: ["anthropic-agent-build"]
title: Anthropic Agent 构建指南
category: reference
tags: [ai, agent, anthropic]
sources:
  - "https://docs.anthropic.com/en/docs/agents-and-tools"
source_url: "https://docs.anthropic.com/en/docs/agents-and-tools"
created: 2026-07-29
updated: 2026-07-29
summary: >-
  Anthropic 官方 Agent 构建指南，涵盖工具使用、系统提示词与 Agent 设计模式。
provenance:
  extracted: 0.7
  inferred: 0.2
  ambiguous: 0.1
base_confidence: 0.65
lifecycle: draft
lifecycle_changed: 2026-07-29
---

# Anthropic Agent 构建指南

## 概述

Anthropic 提供了构建 AI Agent 的官方指导，聚焦于 Claude 模型的工具使用（Tool Use）能力。

## 核心设计原则

- **保持简单**：尽可能在单个 API 调用内完成，只在需要时引入 Agent 循环
- **工具定义**：用清晰、具体的 JSON Schema 定义工具，减少歧义
- **系统提示词**：为 Agent 设定明确的角色、约束与输出格式
- **迭代改进**：从简单的提示词开始，逐步增加工具和逻辑

## Agent 架构模式

- **Workflow 模式**：预定义的代码路径，按固定顺序编排模型调用
- **Agent 模式**：模型自主决策流程、工具使用和输出，适合开放性问题
- **混合模式**：在确定性流程中嵌入 Agent 节点

## 关键能力

- Function Calling / Tool Use
- 多步推理（Chain of Thought）
- 结构化输出
- 视觉理解（Vision）

## 已知限制

- 长上下文下的延迟和成本
- 工具调用错误处理
- 安全护栏与滥用防护
