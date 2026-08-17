---
title: Agent 评估基准
tags: [ai-agent, evaluation, benchmark, active]
base_confidence: 0.83
lifecycle: draft
category: reference
created: 2026-08-07
updated: 2026-08-07
---

# Agent 评估基准

## 摘要

Agent 评估体系：通用 Agent 基准（GAIA/AgentBench/Tau-bench）、代码 Agent 基准（SWE-bench/HumanEval/MBPP）、Web Agent 基准（WebArena/VisualWebArena/Mind2Web）、评估维度（成功率/效率/安全性/成本）、评估方法（人工/自动/仿真环境）。

## Agent 基准分类

| 类别 | 基准名称 | 评测维度 | 难度 | 最佳模型表现（约） |
|------|----------|----------|------|-------------------|
| **通用 Agent** | GAIA | 多步推理、工具使用、网页浏览 | 高 | GPT-4o: ~35%（Level 3） |
| **通用 Agent** | AgentBench | 8 环境（OS/DB/Web/Lattice 等）综合评测 | 中高 | GPT-4: ~4.5/10 综合分 |
| **通用 Agent** | TAU-bench | 多轮对话 + 工具调用 + 策略约束 | 高 | GPT-4o: ~30-50%（依任务） |
| **通用 Agent** | ToolBench | 16000+ 真实 API 工具调用 | 中 | GPT-4: ~30% pass@1 |
| **代码 Agent** | HumanEval | 函数级代码生成正确性 | 低 | GPT-4o: ~90% pass@1 |
| **代码 Agent** | MBPP | 基础编程问题 | 低 | GPT-4o: ~85% pass@1 |
| **代码 Agent** | SWE-bench | 真实 GitHub Issue 修复 | 高 | 头部 Agent: ~50-60%（verified） |
| **代码 Agent** | LiveCodeBench | 实时竞赛题（防数据泄漏） | 中高 | 持续更新 |
| **Web Agent** | WebArena | 真实网站交互（电商/论坛/GitLab 等） | 高 | GPT-4o: ~14% 任务完成率 |
| **Web Agent** | VisualWebArena | 多模态网页理解与操作 | 极高 | 当前最优: ~20% |
| **Web Agent** | Mind2Web | 跨网站泛化 Web 操作 | 中高 | GPT-4V: ~30% 步骤准确率 |
| **工具使用** | BFCL | 函数调用准确性（多轮/嵌套/并行） | 中 | GPT-4o: ~80% |
| **工具使用** | API-Bank | API 调用链正确性 | 中 | GPT-4: ~75% |
| **工具使用** | T-Eval | 工具选择/参数填充/执行评估 | 中低 | GPT-4: ~70% |

## 评估维度

### 任务成功率

- **最终成功率（SR）**：Agent 是否正确完成目标任务
- **部分完成率**：中间步骤正确但最终未完成的比例
- 按难度分级统计（Easy/Medium/Hard）
- 区分 pass@1（单次）和 pass@k（k 次中最佳）

### 步骤效率

- **平均步数**：完成任务所需的工具调用/交互次数
- **步骤准确率**：每一步操作的正确比例
- **冗余步骤比**：无效操作占总操作的比例
- 效率直接影响 Token 成本和延迟

### 工具调用准确性

- **工具选择准确率**：是否选择了正确的工具/API
- **参数填充准确率**：工具参数是否正确
- **调用链正确性**：多步工具调用的顺序和依赖是否正确
- BFCL、T-Eval 专门评测此维度

### 安全性

- **越权操作率**：Agent 执行了超出授权范围的操作
- **数据泄漏**：敏感信息是否通过工具调用外泄
- **注入攻击抵抗**：prompt injection 下的行为安全性
- 目前评估较少但企业部署的关键需求

### 成本效益

- **Token 消耗**：完成任务的平均 Token 用量
- **延迟**：端到端完成时间
- **性价比**：任务完成率 / Token 成本
- 企业选型的核心考量指标

## 评估方法

### 真实环境

- 在真实网站、真实代码仓库中评估 Agent 行为
- **优点**：最接近实际使用场景，评估结果可信度高
- **缺点**：环境不可控、结果不可复现、可能产生副作用
- **代表**：WebArena（真实网站）、SWE-bench（真实 GitHub 仓库）

### 沙箱仿真

- 在隔离的 Docker 容器或模拟环境中执行 Agent 操作
- **优点**：可复现、可并行、安全可控
- **缺点**：与真实环境有差距，可能遗漏边界情况
- **代表**：SWE-bench（Docker）、AgentBench（多环境沙箱）

### LLM-as-Judge

- 使用 LLM 作为评估者判断 Agent 输出质量
- **优点**：可扩展、成本低、支持主观评价
- **缺点**：存在偏见、可能与人类判断不一致、评估者自身能力限制
- **代表**：MT-Bench（对话质量）、AlpacaEval（指令遵循）

### 人类评估

- 由人类评估者对 Agent 行为和输出进行打分
- **优点**：最接近真实用户体验，可评估主观质量
- **缺点**：成本高、速度慢、难以规模化、评估者间一致性难保证
- **代表**：Chatbot Arena（ELO 排名）、GAIA（人类辅助验证）

## 开放挑战

### 缺乏统一标准

- 不同基准的评估指标、数据格式、评分标准不统一
- 跨基准对比困难，一个基准的高分不代表综合能力强
- 需要标准化的 Agent 能力评估框架

### 环境复现难

- 真实环境随时间变化（网页改版、API 更新、数据漂移）
- Agent 依赖的外部服务可能不可用或行为变化
- 需要环境快照和版本化机制保证评估一致性
- SWE-bench 的时效性问题：部分 Issue 的上下文已过时

### 安全边界评估

- 当前主流基准几乎不评估安全维度
- 越权操作、数据泄漏、注入攻击等风险缺乏系统性评测
- 企业部署需要安全评估标准但目前无成熟方案
- Agent 能力越强，安全评估越紧迫

### 评估能力天花板

- 基准测试的难度跟不上模型能力增长速度
- HumanEval/MBPP 已被多数模型「刷爆」，区分度下降
- 需要持续更新的动态基准（LiveCodeBench 模式）
- 评估本身也需要更高的认知能力来判断 Agent 的深层质量

## 延伸阅读

- [[ai-agent-overview]] - AI Agent 综述，了解 Agent 评估在整体框架中的位置
- [[llm-evaluation-benchmarks]] - LLM 评估基准，对比通用 LLM 评估与 Agent 评估的差异
