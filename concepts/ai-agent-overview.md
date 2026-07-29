---
title: AI Agent 概述
category: concepts
tags: [ai-agent, overview, autonomous]
created: 2026-07-29
updated: 2026-07-29
summary: AI Agent 定义、核心能力与发展历史
base_confidence: 0.65
lifecycle: draft
lifecycle_changed: 2026-07-29
sources: []
---

# AI Agent 概述

## 定义

AI Agent 是能够感知环境、自主决策并采取行动以实现目标的智能系统。区别于传统 Chatbot，Agent 具有**主动性**和**工具使用**能力。

## 类型

- **Reactive Agent**：基于当前感知直接响应，无内部状态
- **Proactive Agent**：具有目标和规划能力，主动采取行动
- **Hybrid Agent**：结合反应式和主动式策略
- **Multi-Agent System**：多个 Agent 协作完成复杂任务

## 核心架构

- **感知（Perception）**：接收用户输入、环境信号、工具返回
- **推理（Reasoning）**：LLM 作为推理引擎，理解目标、规划步骤
- **行动（Action）**：执行工具调用、生成输出、更新状态
- **记忆（Memory）**：短期（上下文窗口）、长期（外部存储）
- **反馈（Feedback）**：从执行结果中学习与调整

## 演化路线

Chatbot → Tool-Enhanced LLM → Agent（单步）→ Agent（多步循环）→ Multi-Agent System → Autonomous Agent

## 参考来源

- [[sources/anthropic-agent-build|Anthropic Agent 构建指南]]
- [[sources/agent-frameworks-comparison|AI Agent 框架对比]]
- [[concepts/agent-frameworks|Agent 框架]]
- [[concepts/mcp-protocol|Model Context Protocol]]
