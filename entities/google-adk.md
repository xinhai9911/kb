---
title: Google ADK（Agent Development Kit）
tags: [ai-agent, framework, google, sdk, harness, active]
lifecycle: draft
category: entity
base_confidence: 0.7
created: 2026-08-17
updated: 2026-08-17
summary: >-
  Google 开源的 Agent 开发套件（Python/JS）：Tools、Agents（LLM/Workflow/Custom）、
  Sessions/Memory、可部署到 Vertex AI / Cloud Run，深度绑定 Gemini。
---

# Google ADK（Agent Development Kit）

Google 开源的 Agent 开发套件（Python / JS），提供从单 Agent 到多 Agent 的**官方 harness 运行时**，并深度绑定 Gemini 与 Google Cloud。

## 核心抽象

- **Tools**：函数工具、Google API 工具、第三方 / 长尾工具（MCP 兼容思路，见 [[mcp-protocol]]）。
- **Agents**：LLM Agent（自主循环）、Workflow Agent（顺序 / 并行 / 循环等确定性编排，对应 [[agent-orchestration-patterns]]）、Custom Agent（自定义逻辑）。
- **Sessions / Memory / State**：管理多轮对话状态与长期记忆（见 [[agent-memory-planning]]）。
- **Eval / Deploy**：内置评估与一键部署到 Vertex AI / Cloud Run。

## 定位

- 全栈式 SDK：比 OpenAI / Anthropic 的"薄 harness"更重，自带编排、记忆、部署闭环（见 [[llm-agent-harness]] B/C 之间）。
- 适合已在 GCP 生态、用 Gemini 的团队。

## 延伸

- → [[llm-agent-harness]] — harness 总论
- → [[agent-orchestration-patterns]] — Workflow Agent 的编排模式
- → [[agent-memory-planning]] — Sessions / Memory
- → [[mcp-protocol]] — 工具接入标准
