---
title: Agent 记忆与规划
category: concepts
tags: [ai-agent, memory, planning, reasoning]
created: 2026-07-29
updated: 2026-07-29
summary: AI Agent 的记忆机制与规划策略
relationships:
  - target: "[[projects/db-decoder-ironhive/decoder-track]]"
    type: related_to
base_confidence: 0.65
lifecycle: draft
lifecycle_changed: 2026-07-29
sources: []
---

# Agent 记忆与规划

## 记忆机制

### 短期记忆
- 上下文窗口内的历史信息
- 受限于 Token 限制
- 通过滑动窗口或摘要压缩管理

### 长期记忆
- 外部存储（向量数据库、知识图谱）
- RAG 检索增强
- 持久化 Agent 状态

### 情景记忆
- 记录过去的决策和执行结果
- 用于反思和改进
- 支持元学习

## 规划策略

### ReAct 模式
推理（Reasoning）与行动（Acting）交替进行：思考→行动→观察→再思考。

### Plan-and-Execute
先生成完整计划，再逐步执行。适合可预见的多步任务。

### Tree-of-Thought
同时探索多条推理路径，通过评估选择最优分支。
### 反思（Reflection）

执行后评估结果，提取教训，更新策略。

## 实际应用

- 代码开发：分步规划→编码→测试→修复（参见 [[projects/db-decoder-ironhive/decoder-track|解码器开发 Track]] 的编译/验证回环）
- 研究：问题分解→搜索→综合→结论
- 运维：监控→诊断→处理→验证
