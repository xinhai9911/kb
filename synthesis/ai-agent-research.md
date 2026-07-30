---
title: 'Research: AI Agent'
category: synthesis
tags: [ai-agent, research, autonomous]
created: 2026-07-29
updated: 2026-07-29
summary: AI Agent 研究综述：框架、记忆、规划、安全
base_confidence: 0.7
lifecycle: draft
lifecycle_changed: 2026-07-29
sources: []
---

# Research: AI Agent

## 概述

AI Agent 是 LLM 从对话工具向自主行动系统演进的关键范式。本研究报告覆盖 Agent 的核心能力（工具使用、记忆、规划）、主流框架（LangGraph、CrewAI、AutoGen、Dify）、MCP 协议以及 Agent 架构模式。

## 关键发现

- Agent 的核心价值在于将 LLM 从"回答问题"升级为"完成任务"
- 框架选择取决于场景：复杂状态编排选 LangGraph，多角色协作选 CrewAI，对话推理选 AutoGen
- MCP 协议正成为 Agent 工具集成的标准化接口
- 记忆和规划是 Agent 智能水平的决定性因素

## 核心概念

- [[concepts/ai-agent-overview|AI Agent 概述]]
- [[concepts/agent-frameworks|Agent 框架]]
- [[concepts/mcp-protocol|Model Context Protocol]]
- [[concepts/agent-memory-planning|Agent 记忆与规划]]

## 实体与工具

- [[entities/anthropic|Anthropic]]
- [[entities/openai|OpenAI]]
- [[entities/langchain|LangChain]]
- [[entities/crewai|CrewAI]]

## 未解决的问题

- Agent 安全性：自主行动的边界如何定义
- 评估标准：目前缺乏统一的 Agent 能力评测基准
- 成本-性能权衡：多步 Agent 循环的延迟与成本控制
- 人机协作：Agent 自主性与人类控制的平衡点

## 参考来源

- [[sources/anthropic-agent-build|Anthropic Agent 构建指南]]
- [[sources/langchain-intro|LangChain/LangGraph 框架介绍]]
- [[sources/mcp-specification|MCP 规范]]
- [[sources/agent-frameworks-comparison|AI Agent 框架对比]]
