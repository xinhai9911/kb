---
aliases: ["pm-metrics-kpi"]
summary: 软件项目度量与 KPI 涵盖过程度量、产品度量和项目度量，包括 Velocity、Cycle Time、缺陷密度、CPI/SPI 等关键指标。
category: concept
title: 项目度量与 KPI
tags: [pm, concept, metrics, kpi]
lifecycle: draft
created: 2026-07-30
updated: 2026-07-30
base_confidence: 0.85
---

# 项目度量与 KPI

## 概述

**度量不是为了控制，而是为了洞察。** 好的度量指标帮助团队预测问题、发现瓶颈、持续改进。

## GQM 方法（Goal-Question-Metric）

由 Basili 提出的度量框架：
- **Goal** — 你想达成什么目标？
- **Question** — 如何判断目标是否达成？
- **Metric** — 用什么数据回答问题？

示例：
- Goal：提高交付可预测性
- Question：我们每次 Sprint 是否按计划完成？
- Metric：Sprint 完成率（Planned vs Actual）

## 常用软件项目指标

### 进度类

| 指标 | 公式/含义 | 适用 |
|------|----------|------|
| **Velocity** | 每个 Sprint 完成的故事点 | Scrum |
| **Cycle Time** | 需求从开始到完成的时间 | Kanban |
| **Lead Time** | 需求从提出到交付的时间 | 端到端 |
| **SPI**（进度绩效） | EV / PV | EVM |

### 质量类

| 指标 | 含义 |
|------|------|
| **缺陷密度** | Bug 数 / 千行代码（KLoC） |
| **逃逸缺陷率** | 生产发现的 Bug / 总 Bug |
| **测试覆盖率** | 代码行/分支被测试覆盖的比例 |
| **MTBF / MTTR** | 平均故障间隔 / 平均修复时间 |

### 成本类

| 指标 | 含义 |
|------|------|
| **CPI**（成本绩效） | EV / AC，>1 好 |
| **ROI** | (收益 − 成本) / 成本 |

### 交付健康类

| 指标 | 含义 |
|------|------|
| **Sprint 完成率** | 完成点数 / 计划点数 |
| **缺陷创建速率** | 每 Sprint 新缺陷数 |
| **技术债比率** | 修复技术债耗时 / 新功能耗时 |
| **员工满意度** | 定期匿名调查分数 |

## 度量的坏实践

- 用 Velocity 比较不同团队（相对单位不可比）
- 用代码行数衡量生产力（鼓励反模式）
- 仅收集数据不回顾分析
- Goodhart 定律：当指标成为目标，它就不再是好指标

## 相关页面

- [[concepts/项目管理 进度 成本 管理|EVM 深入]]
- [[concepts/项目管理 质量 管理]]
- [[concepts/项目管理 Scrum|Velocity / Burn-down]]
- [[concepts/项目管理 看板|Cycle Time / CFD]]
