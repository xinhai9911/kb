---
title: AI Agent 框架对比
category: concepts
tags: [ai-agent, framework, langchain, crewai]
created: 2026-07-29
updated: 2026-07-29
summary: LangChain、CrewAI、AutoGPT 等主流 AI Agent 框架的架构对比
base_confidence: 0.65
lifecycle: draft
lifecycle_changed: 2026-07-29
sources: []
---

# Agent 框架

## 框架选型维度

- **状态管理**：是否有状态、持久化能力
- **编排模式**：顺序、图化、对话
- **工具集成**：API 调用、代码执行、外部搜索
- **可观测性**：日志、追踪、调试
- **部署复杂度**：依赖、配置、扩展性

## LangGraph

基于状态图的有状态编排，适合复杂工作流。节点定义处理步骤，边控制流转。[[sources/langchain-intro|详见介绍]]

## CrewAI

以角色为中心的协作框架。Agent 拥有角色、目标、背景故事。通过任务委派和层级管理实现协作。[[sources/agent-frameworks-comparison|详见对比]]

## AutoGen

微软的对话式多 Agent 框架。Agent 之间通过消息传递协作，支持代码生成与执行沙箱。

## 趋势

- 从无状态向有状态演进
- 从单 Agent 向多 Agent 协作演进
- 框架正趋向标准化（MCP、Function Calling）

## 官方 Agent SDK（薄 harness）

除上述"重编排"框架外，模型厂商也提供官方 SDK，定位更轻、更贴近 harness 本身（见 [[llm-agent-harness]] B 类）：

- [[anthropic-agent-sdk|Anthropic Agent SDK]] — tool-use loop + sub-agents + trace
- [[openai-agents-sdk|OpenAI Agents SDK]] — handoffs + guardrails + tracing
- [[google-adk|Google ADK]] — 全栈式（编排 + 记忆 + 部署），绑定 Gemini

更轻量的库见 [[lightweight-agent-frameworks]]（Pydantic AI / smolagents / Agno / LlamaIndex）。
