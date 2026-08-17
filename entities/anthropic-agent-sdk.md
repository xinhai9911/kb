---
title: Anthropic Agent SDK
tags: [ai-agent, framework, anthropic, sdk, harness, active]
lifecycle: draft
category: entity
base_confidence: 0.7
created: 2026-08-17
updated: 2026-08-17
summary: >-
  Anthropic 官方 Agent 开发 SDK（Python/TypeScript），提供"薄 harness"：
  Agent 运行循环、Tool Use、sub-agents 并行、内置 tracing。是 Claude Code 等产品的底层运行时原型。
---

# Anthropic Agent SDK

Anthropic 提供的官方 Agent 开发 SDK（Python / TypeScript），定位是**给开发者自己的"薄 harness"**——把 [[agent-tool-use-mcp|工具调用]]、循环、上下文管理与可观测打包成可复用库，让你在应用里直接跑 Claude Agent，而不必从 `while` 循环手写（见 [[llm-agent-harness]] D 类）。

## 核心能力

- **Agent / 运行循环**：封装"模型调用 → 工具执行 → 结果回注"的 ReAct 循环。
- **Tool Use**：用函数 + 类型定义声明工具，SDK 负责序列化与调度（协议层见 [[mcp-protocol]]）。
- **Sub-agents**：把大任务拆给子 Agent 并行处理再汇总，对应 [[agent-orchestration-patterns]] 的扇出。
- **Tracing**：内置 trace，记录每轮模型输入输出、工具调用、token——即 [[llm-agent-harness]] 强调的"可观测"层。
- **Computer Use / 文件**：可接入操作文件、终端、浏览器的工具，构成编程 Agent 的 harness。

## 与设计指南的关系

- [[sources/anthropic-agent-build|Anthropic Agent 构建指南]] 讲"怎么设计 Agent"（原则 / 模式）；本 SDK 是这些原则的**代码化落地**。
- 与 Claude Code 等成品应用的关系：Claude Code 是"自带 harness 的成品"，Agent SDK 是"让你自己搭 harness 的零件"。

## 延伸

- → [[llm-agent-harness]] — harness 总论（为什么需要 harness）
- → [[agent-tool-use-mcp]] — 工具调用与 MCP
- → [[agent-frameworks]] — 与 LangGraph / CrewAI / AutoGen 的对比
- → [[sources/anthropic-agent-build]] — Anthropic 官方构建指南
