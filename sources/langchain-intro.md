---
title: LangChain/LangGraph 框架介绍
category: reference
tags: [ai, agent, langchain]
sources:
  - "https://www.langchain.com/"
source_url: "https://www.langchain.com/"
created: 2026-07-29
updated: 2026-07-29
summary: >-
  LangChain 和 LangGraph 框架概览：LLM 应用开发的生态系统。
provenance:
  extracted: 0.7
  inferred: 0.2
  ambiguous: 0.1
base_confidence: 0.65
lifecycle: draft
lifecycle_changed: 2026-07-29
---

# LangChain/LangGraph 框架介绍

## 概述

LangChain 是构建 LLM 应用最广泛的开源框架之一，LangGraph 是其图化 Agent 运行时。

## 核心组件

- **LangChain Core**：基础抽象（LLM、Chat Model、Embedding、Vector Store）
- **LangChain Community**：第三方集成（模型提供商、工具、向量库）
- **LangGraph**：有状态 Agent 运行时，支持循环、分支、并行
- **LangSmith**：可观测性与调试平台

## LangGraph Agent 架构

- **StateGraph**：基于状态迁移的工作流定义
- **Node**：每个处理步骤（模型调用、工具执行）
- **Edge**：节点间的条件或无条件连接
- **Persistence**：内置检查点机制，支持断点续传
- **Human-in-the-Loop**：支持人工审批中断点

## 关键特性

- 有状态图化编排
- 流式输出支持
- 并行节点执行
- 时间旅行调试

## 与 Anthropic Agent 对比

LangGraph 更适合需要复杂状态管理和多步编排的场景，而 Anthropic 的 Agent 方案更简洁、更适合单模型场景。
