---
title: Model Context Protocol 规范
category: reference
tags: [ai, agent, mcp]
sources:
  - "https://modelcontextprotocol.io/"
source_url: "https://modelcontextprotocol.io/"
created: 2026-07-29
updated: 2026-07-29
summary: >-
  MCP 协议规范概览：为 LLM 提供上下文感知能力的标准化接口。
provenance:
  extracted: 0.75
  inferred: 0.15
  ambiguous: 0.1
base_confidence: 0.7
lifecycle: draft
lifecycle_changed: 2026-07-29
---

# Model Context Protocol 规范

## 概述

MCP（Model Context Protocol）是 Anthropic 提出的开放协议，为 LLM 提供标准化的上下文获取接口。类似于 AI 应用的 USB-C 标准。

## 架构

- **Host**：宿主应用（如 Claude Desktop、IDE 插件）
- **Client**：与 MCP Server 建立一对一连接的客户端
- **Server**：提供上下文、工具和资源的服务端

## 核心原语

- **Resources**：模型可读取的结构化数据（文件、数据库记录、API 响应）
- **Tools**：模型可调用的函数（搜索、计算、外部 API）
- **Prompts**：预定义的提示词模板

## 传输层

- stdio：本地进程间通信
- SSE：远程服务端推送
- Streamable HTTP：基于 HTTP 的流式传输

## 安全考虑

- 服务器需显式声明能力
- 工具执行在宿主环境中受控
- 支持用户确认拦截

## 生态

- 官方 SDK：Python、TypeScript
- 社区集成：VS Code、JetBrains、Obsidian
- 预构建服务器：文件系统、数据库、GitHub、Slack
