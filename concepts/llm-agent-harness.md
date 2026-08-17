---
title: LLM Agent Harness（智能体运行时 / 控制循环）
tags: [llm, agent, harness, runtime, active]
lifecycle: active
category: concept
base_confidence: 0.82
created: 2026-08-17
updated: 2026-08-17
summary: >-
  LLM Agent Harness（智能体运行时）：包裹 LLM 的控制层，把"只预测下一个 token 的模型"
  变成"能感知上下文、调工具、保持状态、循环决策"的可用 Agent。解释为什么需要 harness，
  以及它的典型组成（prompt 组装/推理循环/工具运行时/上下文管理/编排/安全/可观测）。
---

<!-- kb-import-backlink:LLMForEverybody -->

> [!info] 外部资料 · LLMForEverybody
> 中文大模型知识库 [[sources/LLMForEverybody/index|LLMForEverybody 导航]] 中的相关章节：
> - [[sources/LLMForEverybody/07-第七章-Agent/如何设计智能体架构：参考OpenAI还是Anthropic|Agent 架构设计]]













# LLM Agent Harness（智能体运行时 / 控制循环）

## 什么是 Harness

在 AI Agent 语境里，**harness（本义"马具 / 挽具"，引申为"套在模型外面的控制层"）** 是包裹 LLM 的**运行时（runtime）**：它把"只会预测下一个 token 的模型"变成一个"能感知上下文、调用工具、维持状态、循环决策"的可用 Agent。

模型本身只做一件事：给定一段输入文本，输出下一段文本。其余一切让 Agent 真正"能干活"的 plumbing——拼装提示词、跑工具、管理记忆、循环推理、处理错误、做安全护栏、记录 trace——都由 harness 承担。

> 一句话：**模型负责"想"，harness 负责"把想法变成行动并跑起来"。**

## 为什么需要 Harness

裸调 LLM API 做不到 Agent，原因有五层：

### 1. 模型是无状态的，而 Agent 需要"持续对话 + 累积状态"
一次 API 调用是无记忆的。要让模型在多轮里保持上下文、记住工具结果、基于前文决策，必须有人（harness）在每轮重新拼装 `system + history + tools + new observation` 再发起调用。没有 harness，你每次都得手写这套拼装。

### 2. 工具调用需要一个"执行 + 回注"的闭环
ReAct / Function Calling（见 [[agent-tool-use-mcp]]）不是模型自己完成的——模型只产出一段"我想调 get_weather"的 JSON，真正的**执行工具、把结果塞回上下文、再让模型继续**是 harness 的循环（Thought → Action → Observation → …）。没有 harness 这个环，工具调用只是一句空话。

### 3. 上下文窗口有限，需要"管理"而非"塞满"
长任务会撑爆 context。harness 负责：截断 / 压缩历史、摘要、按需注入相关记忆与资源（RAG）、auto-compact（自动压缩窗口）。这是 [[agent-memory-planning]] 与长期记忆的落地点。

### 4. 生产级运行需要工程保障
真实使用要：重试与退避、超时、错误分类与降级、并发 / 并行扇出（见 [[agent-orchestration-patterns]]）、流式输出、权限与沙箱（[[agent-tool-use-mcp]] §安全考量）、限流与成本控制。这些是 harness 的"运维层"，缺了 Agent 一碰异常就崩。

### 5. 不可观测就无法调试与改进
Agent 出错时，你需要知道：模型哪一轮说了什么、调了哪个工具、传了什么参数、返回了什么、为什么跑偏。harness 的 **trace / 日志层** 提供全链路可观测性。平台侧的"Harness trace 接入"（如 [[projects/db-decoder-ironhive|db-decoder-ironhive]] 的平台部 Harness trace）就是这个能力的工程落地 ^[inferred]。

## Harness 的典型组成

| 层 | 职责 | 对应 vault 概念 |
|----|------|----------------|
| Prompt 组装 | system / 角色 / 工具描述 / 上下文拼接 | [[agent-tool-use-mcp]] |
| 推理循环 | 模型调用、输出解析、终止判断 | ReAct / Plan-and-Execute |
| 工具运行时 | 工具注册、发现、执行、结果回注 | [[mcp-protocol]]、[[agent-tool-use-mcp]] |
| 上下文管理 | 窗口压缩、记忆检索、RAG 注入 | [[agent-memory-planning]]、[[agent-long-term-memory]] |
| 编排 | 串行 / 并行 / DAG / 自主规划 | [[agent-orchestration-patterns]] |
| 安全 | 权限、沙箱、确认、审计 | [[agent-tool-use-mcp]] §安全 |
| 可观测 | trace、日志、评估 | [[agent-evaluation-benchmarks]]、Harness trace |
| 调度 / 流式 | 并发、token 预算、SSE | — |

## Harness vs 框架 vs 编排

- **Harness**：单个 Agent 的"运行内核"（循环 + 工具 + 上下文 + 安全 + trace）。
- **编排（Orchestration）**：多个步骤 / 多个 Agent 如何串联（见 [[agent-orchestration-patterns]]）。
- **框架（Framework）**：LangChain / LangGraph / CrewAI / AutoGen 等把"harness 能力 + 编排能力"打包成可复用库（见 [[agent-frameworks]]）。Claude Code、CodeBuddy 这类产品则是"自带 harness 的应用"。

> 类比：模型是发动机，harness 是底盘 + 变速箱 + 仪表盘，框架是把整套动力总成做成可量产的车，编排是车队调度。

## 业界常用 Harness（按形态分类）

"Harness" 一词偏口语，下面这些 SDK / 框架 / 产品都在不同程度上提供 harness 能力（运行循环 + 工具 + 上下文 + 安全 + 可观测）。按定位分四类：

### A. 产品型（开箱即用，自带 harness 的 Agent 应用）
- **Claude Code / CodeBuddy**：终端 / IDE 编程 Agent，本地跑 harness，接文件、shell、MCP。
- **Cursor / Cline / Aider / OpenCode**：编程 Agent，harness 内嵌在编辑器或 CLI 中。
- **Operator / 浏览器 Agent 类**：以"操作电脑 / 网页"为工具的 harness（见 [[concepts/browser-agent]]）。

### B. SDK / 库型（官方给的"薄 harness"，自己搭 Agent）
- **[[anthropic-agent-sdk|Anthropic Agent SDK]]**（原 Claude Agent SDK）：tool-use loop、sub-agents、trace。
- **[[openai-agents-sdk|OpenAI Agents SDK]]**：handoffs（交接）、guardrails、内置 tracing。
- **[[google-adk|Google ADK（Agent Development Kit）]]**：多工具 / 多 Agent 的官方运行时。

### C. 框架型（loop + 编排 + 生态打包）
- **LangGraph**（LangChain 系，图化有状态 harness）— 见 [[agent-frameworks]] / [[entities/langchain]]
- **AutoGen**（微软，对话式多 Agent harness）— 见 [[agent-frameworks]]
- **CrewAI**（角色制多 Agent harness）— 见 [[entities/crewai]] / [[agent-frameworks]]
- **Pydantic AI / smolagents / Agno / LlamaIndex** — 见 [[lightweight-agent-frameworks]]（轻量 harness 库横向对比）

### D. 自研 harness
- 直接用 `while` 循环 + 模型 SDK 手写最薄一层（适合理解原理 / 轻量场景）。

> 选型直觉：要"马上用"选 A；要"可控地搭"选 B/C；要"完全掌控"或教学选 D。框架与 SDK 的差异见 [[agent-frameworks]] 与 [[agent-orchestration-patterns]]。

## 延伸

- → [[harness-deep-dive]] — 为什么需要 harness 的深度解析（技术/商业/用户体验/安全多角度）
- → [[harness-framework-comparison]] — harness 框架对比与选型指南
- → [[harness-evolution-future]] — harness 演进历史与未来趋势
- → [[agent-tool-use-mcp]] — 工具调用与 MCP，harness 的"手"
- → [[agent-orchestration-patterns]] — 多步 / 多 Agent 编排，harness 之上的调度
- → [[agent-memory-planning]] — 上下文与记忆管理，harness 的"脑"
- → [[agent-frameworks]] — 把 harness 能力产品化的框架
- → [[agentic-coding]] — 编程 Agent 即运行在 harness 中的典型应用
- → [[projects/db-decoder-ironhive]] — 平台部 Harness trace 接入示例（harness 可观测性的工程落地）
