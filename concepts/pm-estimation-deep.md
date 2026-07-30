---
summary: 软件项目估算深度技术，涵盖 Wideband Delphi、Planning Poker、COCOMO II、功能点分析（FPA）等方法的原理与适用场景。
category: concept
title: 软件估算技术深入
tags: [pm, concept, estimation, planning]
lifecycle: draft
created: 2026-07-30
updated: 2026-07-30
base_confidence: 0.85
---

# 软件估算技术深入

## 概述

软件估算不可能完全精确（"人月神话"），但优秀的估算方法能**缩小误差区间、暴露假设、促进共识**。

## 估算的"漏斗"模型

不同阶段的估算精度要求不同：

| 阶段 | 精度 | 常用方法 |
|------|------|---------|
| 概念阶段 | −50% ~ +100% | T-Shirt Sizing、类比估算 |
| 计划阶段 | −25% ~ +75% | 功能点、Wideband Delphi |
| 设计完成 | −10% ~ +25% | 自下而上、参数模型 |
| 迭代中 | ±5% | 基于 Velocity 的短期预测 |

## 核心方法详解

### 1. Wideband Delphi（宽德尔菲法）

由 Barry Boehm 提出，结合专家判断与匿名投票：

1. 协调者介绍需求，专家独立给出三值（乐观/最可能/悲观）
2. 汇总结果，展示分布（匿名）
3. 偏差大的专家陈述理由
4. 重复 1–3 直到收敛

### 2. Planning Poker（规划扑克）

Scrum 采用的估算技术：
- 每个开发者用扑克牌同时出分（Fibonacci 序列：1,2,3,5,8,13,21）
- 最大最小出分者分别解释理由
- 重新投票直到趋于一致

### 3. COCOMO II（Constructive Cost Model）

Boehm 的参数化模型：

```
Effort = A × (Size)^B × EM
```

- **A** = 常数（2.94）
- **Size** = KSLOC（千行代码）
- **B** = 缩放因子（5 个驱动因子）
- **EM** = 17 个成本乘数（产品/平台/人员/项目维度）

### 4. 功能点分析（FPA）

IFPUG 标准，从功能角度估算规模：
- 五种功能类型：EI / EO / EQ / ILF / EIF
- 加权计算未调整功能点（UFP）
- × 调整因子（VAF）= 调整功能点（AFP）

## 常见陷阱

- 协商式估算 — 为了满足上级数字强行压缩
- 安全裕度过大 — 团队隐瞒，PERT 三值可缓解
- 忽略非编码活动 — 会议、设计、评审、部署
- 虚幻精度 — 用小时给出三位数精度

## 相关页面

- [[concepts/pm-schedule-cost-management]]
- [[concepts/pm-scrum]]
- [[concepts/pm-metrics-kpi]]
