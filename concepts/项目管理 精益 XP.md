---
aliases: ["pm-lean-xp"]
summary: Lean Software Development 与 Extreme Programming（XP）深入——精益原则（消除浪费/内建质量/延迟决策）和 XP 工程实践（TDD / 结对编程 / CI / 重构 / 简单设计）。
category: concept
title: Lean 与 XP 深入
tags: [pm, concept, lean, xp]
lifecycle: draft
created: 2026-07-30
updated: 2026-07-30
base_confidence: 0.85
---

# Lean 与 XP 深入

## 概述

Lean 和 XP 是敏捷运动的两大思想源头。**Lean 提供管理哲学**（消除浪费、加速流动），**XP 提供工程保障**（技术实践确保代码质量不拖累速度）。

## Lean Software Development

由 Mary Poppendieck 将丰田生产系统应用于软件，提出 **7 大原则**：

### 7 大精益原则

1. **消除浪费** — 识别七种浪费：不必要功能、等待、任务切换、缺陷、过度处理、库存（半成品）、管理活动
2. **内建质量** — 缺陷在产生时就被捕获，不流入下游
3. **创造知识** — 重视经验、文档化与学习
4. **延迟决策** — 保留选项，在最后责任时刻做出决策
5. **快速交付** — 缩短周期时间，快速获取反馈
6. **尊重人** — 团队自组织，管理层赋能而非控制
7. **整体优化** — 不局部优化，关注端到端价值流

### 价值流映射（Value Stream Mapping）

可视化端到端流程（从需求提出到部署上线），标注每个步骤的**处理时间**和**等待时间**，找到瓶颈和浪费。

## Extreme Programming（XP）

由 Kent Beck 创建，以**工程实践**著称。核心实践分为四象限：

### 四个象限

#### 技术实践
- **Test-Driven Development（TDD）** — 先写测试再写实现，红-绿-重构
- **持续集成（CI）** — 每日多次集成，自动构建+测试
- **重构** — 持续改进代码结构，不改变外部行为
- **简单设计** — 仅实现当前需求的足够设计
- **结对编程** — 两人一台机器，持续代码审查
- **集体代码所有权** — 所有人都可修改任何代码

#### 沟通实践
- **故事卡片（User Story）** — 简短的需求描述
- **现场客户（On-site Customer）** — 客户代表在团队中
- **编码规范（Coding Standard）** — 统一代码风格

#### 管理实践
- **计划游戏（Planning Game）** — 开发和业务共同排优先级
- **小型发布（Small Releases）** — 频繁上线
- **可持续节奏** — 每周 40 小时，不加班
- **开放工作空间**

#### 反馈实践
- **测试** — TDD 保证代码安全性
- **Pair Feedback** — 结对中即时反馈
- **CI 反馈** — 提交即验证

## XP 在现代的继承

XP 的工程实践已被广泛吸收：
- TDD → 现代测试文化
- CI → DevOps 基石
- 重构 → 模式语言
- 结对 → 现代 Pair/Mob Programming

## 相关页面

- [[concepts/项目管理 敏捷 方法论]]
- [[concepts/项目管理 质量 管理]]
- [[synthesis/软件项目管理全景综述]]
