---
title: Agent 工具使用与 MCP 协议
tags: [llm, agent, tool-use, mcp, active]
lifecycle: draft
category: reference
base_confidence: 0.82
created: 2026-08-07
updated: 2026-08-07
summary: LLM Agent 工具使用机制：Function Calling、ReAct 框式、MCP 协议架构（Host/Client/Server/Transport）、工具发现与注册、多工具编排、安全考量。
---

<!-- kb-import-backlink:LLMForEverybody -->

> [!info] 外部资料 · LLMForEverybody
> 中文大模型知识库 [[sources/LLMForEverybody/index|LLMForEverybody 导航]] 中的相关章节：
> - [[sources/LLMForEverybody/07-第七章-Agent/MCP：基础概念、快速应用和背后原理|MCP 原理]]













# Agent 工具使用与 MCP 协议

## Function Calling 流程

```
用户请求 → LLM 推理 → 生成工具调用 JSON → 执行工具 → 返回结果 → LLM 继续推理 → 最终响应
```

### 核心要素

| 组件 | 描述 | 示例 |
|------|------|------|
| 工具定义 | JSON Schema 格式描述函数签名 | `name`, `parameters`, `description` |
| 调用生成 | 模型输出结构化的函数调用 | `{"name": "get_weather", "arguments": {"city": "Beijing"}}` |
| 结果注入 | 工具返回值回注到对话上下文 | `{"temperature": 25, "condition": "sunny"}` |
| 多轮编排 | 支持顺序/并行/条件调用 | 一次响应中调用多个工具 |

### 实现模式
- **OpenAI 格式**: `tools` + `tool_choice` 参数
- **Anthropic 格式**: `tools` 字段 + `tool_use` content block
- **Google 格式**: `function_declarations` in `tools`
- **通用兼容**: OpenAI 兼容 API 成为事实标准

## ReAct 框式

```
Thought: 用户需要查询北京天气，我应该调用天气API
Action: get_weather(city="Beijing")
Observation: {"temp": 25, "condition": "sunny"}
Thought: 已获取天气信息，可以组织回答
Answer: 北京今天晴天，气温25°C
```

### 循环机制

| 阶段 | LLM 职责 | 输出 |
|------|---------|------|
| Thought | 分析当前状态，规划下一步 | 推理文本 |
| Action | 选择并调用工具 | 工具调用 |
| Observation | 接收工具执行结果 | 外部数据 |
| 循环终止 | 判断是否完成任务 | 最终答案或继续循环 |

### 变体与优化
- **ReAct + CoT**: 结合链式推理提升规划质量
- **Plan-and-Execute**: 先制定完整计划再逐步执行
- **Reflexion**: 执行后自我反思，修正错误
- **Tool-augmented CoT**: 在推理过程中按需调用工具

## MCP 协议架构

Model Context Protocol (MCP) — Anthropic 提出的开放标准，统一 LLM 与外部工具/数据源的连接方式。

### 架构层次

```
┌─────────────────────────────────────┐
│            Host (应用层)             │
│  Claude Desktop / IDE / 自定义应用   │
├─────────────────────────────────────┤
│          Client (MCP 客户端)         │
│    协议协商 · 能力发现 · 消息路由     │
├─────────────────────────────────────┤
│          Server (MCP 服务端)         │
│    工具注册 · 资源暴露 · 提示模板     │
├─────────────────────────────────────┤
│          Transport (传输层)          │
│   stdio / SSE / Streamable HTTP     │
└─────────────────────────────────────┘
```

### 核心概念

| 概念 | 描述 | 用途 |
|------|------|------|
| Tools | 服务端暴露的可调用函数 | 执行操作（读写文件、调API） |
| Resources | 服务端提供的数据源 | 上下文增强（文件内容、数据库） |
| Prompts | 服务端定义的提示模板 | 预定义交互模式 |
| Sampling | Host 代理的 LLM 推理 | 服务端请求模型生成 |

### 传输方式

| 传输 | 模式 | 适用场景 |
|------|------|---------|
| stdio | 进程间通信 | 本地工具、CLI 集成 |
| SSE (Server-Sent Events) | HTTP 长连接 | 远程服务、Web 集成 |
| Streamable HTTP | HTTP + 流式 | 云服务、高并发 |

## 工具发现与注册

### 工具描述规范
```json
{
  "name": "database_query",
  "description": "执行只读 SQL 查询",
  "inputSchema": {
    "type": "object",
    "properties": {
      "sql": { "type": "string", "description": "SQL 查询语句" },
      "database": { "type": "string", "enum": ["main", "analytics"] }
    },
    "required": ["sql"]
  }
}
```

### 动态发现流程
1. Client 连接到 Server
2. 发送 `initialize` 握手，交换能力
3. Client 请求 `tools/list` 获取工具列表
4. LLM 根据工具描述决定何时调用
5. Client 转发调用到 Server，返回结果

## 多工具编排

### 编排模式

| 模式 | 描述 | 复杂度 |
|------|------|--------|
| 串行链 | 工具 B 的输入依赖工具 A 的输出 | 低 |
| 并行扇出 | 多个独立工具同时调用 | 中 |
| 条件路由 | 根据中间结果选择下一步工具 | 中 |
| DAG 编排 | 有向无环图定义复杂依赖 | 高 |
| 自主规划 | Agent 动态生成执行计划 | 高 |

### 失败处理
- **重试策略**: 指数退避 + 最大重试次数
- **降级方案**: 工具不可用时切换替代工具
- **错误传播**: 将错误信息反馈给 LLM 重新规划
- **超时控制**: 工具执行超时自动终止

## 安全考量

### 权限控制
- **最小权限原则**: 工具仅获取完成任务所需的最小权限
- **用户确认**: 高风险操作（写入/删除）需用户显式确认
- **作用域限制**: 工具可访问的资源范围明确界定
- **OAuth 集成**: MCP 支持 OAuth 2.1 授权流程

### 沙箱执行
- 工具在隔离环境中运行，限制文件系统/网络访问
- 资源消耗限制（CPU、内存、时间）
- 输入验证防止注入攻击（SQL 注入、命令注入）

### 数据保护
- 敏感数据标记与过滤
- 工具间数据传递加密
- 审计日志记录所有工具调用

## 延伸

- → [[mcp-protocol]] — MCP 协议规范深入解析
- → [[agent-frameworks]] — Agent 框架对比（LangChain、CrewAI、AutoGen）
- → [[llm-agent-harness]] — 包裹模型的运行时 / 控制循环（为什么需要 harness）
- → [[ai-safety-alignment]] — 工具使用场景的安全风险与防御
- → [[function-calling-deep-dive]] — Function Calling 底层机制
