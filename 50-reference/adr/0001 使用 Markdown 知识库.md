---
aliases: ["0001-use-markdown-for-kb"]
title: 知识库使用 Markdown + Git
tags: [adr, kb, kb-stack]
status: accepted
summary: >-
    accepted
category: reference
updated: 2026-07-29
created: 2026-06-10
sources: []
base_confidence: 0.8
lifecycle: reviewed
---

# ADR 0001: 知识库使用 Markdown + Git

## 状态

accepted

## 背景

需要一个个人/工作知识库，记录协议分析、项目笔记、命令片段。备选方案包括 Notion、Obsidian（云同步）、GitHub Wiki、纯本地 Markdown。

## 决策

采用 **纯 Markdown 文件 + Git 仓库 + GitHub 远端** 的方案。本地路径 `Q:\AI\kb\`，远端为 GitHub 私有仓库。

## 原因

- **可读性**：Markdown 是纯文本，任何编辑器都能打开
- **可版本化**：Git 天然适合追踪笔记变更
- **可被 AI 读取**：Claude、Cursor 等工具能直接吃 .md 作为上下文
- **可移植**：不绑定任何专有工具
- **免费**：GitHub 私有仓库免费

## 后果

- 优点：
  - 零成本启动，零依赖运行
  - 跨设备同步：git clone/pull
  - 全文搜索：grep / GitHub 搜索框
  - 可被 Claude 直接读取（避免信息孤岛）
- 缺点 / 妥协：
  - GitHub 不原生支持双链跳转，需 Obsidian 或插件
  - 没有原生标签筛选，靠全文搜索
  - 图片/二进制需 Git LFS（先避免）

## 备选方案

- **Notion**：功能强但锁定生态，纯文本导出困难
- **Obsidian 云同步**：每月 $4，双链体验好但被绑死在 Obsidian
- **GitHub Wiki**：与代码仓库耦合，移动/迁移不便
- **纯本地**：无版本控制，无跨设备同步

## 备注

- 不在范围内：RAG、Pages、Memory 同步（见 spec 第 2 节"非目标"）
- 后续可叠加：mkdocs 静态站、Claude Memory 同步