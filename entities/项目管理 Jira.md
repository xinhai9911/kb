---
aliases: ["pm-jira"]
summary: Jira 是 Atlassian 旗下最流行的项目跟踪与问题管理工具，支持 Scrum、Kanban 和混合流程，被广泛用于软件团队的 Sprint 管理与 Bug 跟踪。
category: entity
title: Jira — 项目跟踪工具
tags: [pm, entity, tool, jira]
lifecycle: draft
created: 2026-07-30
updated: 2026-07-30
base_confidence: 0.85
---

# Jira — 项目跟踪工具

## 概述

Jira 由澳大利亚公司 Atlassian 开发，最初面向 Bug 跟踪，现已演变为企业级项目管理平台。

## 核心功能

- **Issue 类型** — Epic / Story / Task / Sub-task / Bug
- **工作流** — 可视化流程（To Do → In Progress → Done），可自定义
- **Scrum Board** — Sprint 规划、Backlog 管理、Velocity Chart
- **Kanban Board** — WIP 限制、Cycle Time、CFD 累积流图
- **Roadmap** — 多团队、多项目路线图规划（Advanced Roadmaps）
- **权限与角色** — 项目角色、方案权限控制
- **Automation** — 规则引擎减少重复操作（P0 Bug 自动 @ 负责人）
- **Marketplace** — 丰富的插件生态（Tempo Timesheets、eazyBI、Zephyr）

## 常用配置

| 配置项 | 推荐做法 |
|--------|----------|
| Issue Type Scheme | 统一团队类型定义 |
| Workflow Scheme | 尽量简化，避免过多状态 |
| Screen Scheme | 不同 Issue 类型不同字段布局 |
| Notification Scheme | 按角色配置通知，避免骚扰 |
| Permission Scheme | 开发/测试/PO 分层权限 |

## 替代工具

- [[entities/项目管理 常见 工具|项目管理工具对比]]

## 相关页面

- [[concepts/项目管理 Scrum]]
- [[concepts/项目管理 看板]]
- [[concepts/项目管理 需求 管理]]
