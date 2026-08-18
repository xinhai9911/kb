---
aliases: ["ai-agent-research"]
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

- [[concepts/AI 智能体 概览|AI Agent 概述]]
- [[concepts/智能体 框架|Agent 框架]]
- [[concepts/智能体 编排 模式|Agent 编排模式]]
- [[concepts/智能体 内存 规划|Agent 记忆与规划]]
- [[concepts/智能体 长 期 内存|Agent 长期记忆与反思机制]]
- [[concepts/智能体 工具 使用 MCP|Agent 工具使用与 MCP 协议]]
- [[concepts/MCP 协议|Model Context Protocol]]

## 协作与应用

- [[concepts/多 智能体 协作|多 Agent 协作架构]]
- [[concepts/智能体 编程|Agentic Coding 智能编程]]
- [[concepts/浏览器 智能体|Browser Agent 浏览器自动化]]

## 评测

- [[concepts/智能体 评估 基准|Agent 评估基准]]

## 实体与工具

- [[entities/Anthropic|Anthropic]]
- [[entities/OpenAI|OpenAI]]
- [[entities/LangChain|LangChain]]
- [[entities/CrewAI|CrewAI]]

## 未解决的问题

- Agent 安全性：自主行动的边界如何定义
- 评估标准：目前缺乏统一的 Agent 能力评测基准
- 成本-性能权衡：多步 Agent 循环的延迟与成本控制
- 人机协作：Agent 自主性与人类控制的平衡点

## 参考来源

- [[sources/Anthropic 智能体 构建|Anthropic Agent 构建指南]]
- [[sources/LangChain 入门|LangChain/LangGraph 框架介绍]]
- [[sources/MCP 规范|MCP 规范]]
- [[sources/智能体 框架 对比|AI Agent 框架对比]]
