---
aliases: ["mcp-protocol"]
title: MCP 协议
category: concepts
tags: [mcp, protocol, tool-use, integration]
created: 2026-07-29
updated: 2026-07-29
summary: Model Context Protocol (MCP) 协议设计与实现
relationships:
  - target: "[[20-protocols/HBase 2]]"
    type: related_to
  - target: "[[20-protocols/Elasticsearch 2]]"
    type: related_to
base_confidence: 0.65
lifecycle: draft
lifecycle_changed: 2026-07-29
sources: []
---

# Model Context Protocol

## 设计动机

LLM 应用面临的核心问题是**上下文孤岛**：模型无法直接访问文件、数据库、API 等外部数据源。MCP 通过标准化接口解决这个问题。

## 架构层级

- **Host**（宿主）：Claude Desktop、IDE、Web App
- **Client**（客户端）：每个 Server 对应一个 Client 连接
- **Server**（服务端）：提供能力的具体实现

## 与原语

- **Resources**：可读取的数据（文件内容、查询结果）
- **Tools**：可执行的函数（搜索、计算、发送消息）
- **Prompts**：可复用的提示词模板

## MCP vs Function Calling

MCP 是协议层标准化，Function Calling 是模型层能力。MCP 可封装任意 Function Calling 实现。

## 应用场景

- IDE 代码补全与上下文
- 数据库查询与分析（如 [[20-protocols/HBase 2|HBase]]、[[20-protocols/Elasticsearch 2|Elasticsearch]] 协议）
- DevOps 自动化
- 个人知识管理

## 参考来源

- [[sources/MCP 规范|MCP 规范]]
- [[entities/Anthropic 2|Anthropic]]
