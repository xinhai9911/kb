---
aliases: ["openai-agents-sdk"]
title: OpenAI Agents SDK
tags: [ai-agent, framework, openai, sdk, harness, active]
lifecycle: draft
category: entity
base_confidence: 0.7
created: 2026-08-17
updated: 2026-08-17
summary: >-
  OpenAI 官方轻量 Agent SDK（Python），核心抽象：Agent（LLM+指令+工具）、
  handoffs（Agent 间交接）、guardrails（输入/输出护栏）、tracing（内置可观测）。
---

# OpenAI Agents SDK

OpenAI 官方的轻量 Agent 开发 SDK（Python，由实验项目 Swarm 演化而来），定位同样是**薄 harness**：用极少抽象把"运行循环 + 工具 + 交接 + 护栏 + 追踪"交给你。

## 核心抽象

- **Agent**：LLM + 指令 + 工具 + 交接目标的组合体（即一个 harness 内的"角色"）。
- **Handoffs（交接）**：一个 Agent 把控制权交给另一个 Agent，对应 [[智能体 编排 模式]] 的条件路由 / 多 Agent 协作（见 [[多 智能体 协作]]）。
- **Guardrails（护栏）**：在 Agent 运行前后做输入 / 输出校验与拦截，对应 [[LLM 智能体 测试框架]] 的"安全层"。
- **Tracing（追踪）**：内置 trace，可发到 OpenAI 平台或自定义 sink，即 harness 的"可观测层"（呼应 [[智能体 评估 基准]] 的评测闭环）。
- **模型无关倾向**：默认走 OpenAI 模型，但工具与 loop 与具体模型解耦。

## 定位

- 轻量、"少封装"——适合要可控地搭 Agent 的团队（见 [[LLM 智能体 测试框架]] B 类）。
- 在 [[sources/智能体 框架 对比|AI Agent 框架对比]] 中被列为"轻量 Agent、交接、护栏"的代表。

## 延伸

- → [[LLM 智能体 测试框架]] — harness 总论
- → [[智能体 框架]] — 与 LangGraph / CrewAI / AutoGen 对比
- → [[多 智能体 协作]] — 多 Agent 交接与协作
- → [[sources/智能体 框架 对比]] — 框架横向对比
