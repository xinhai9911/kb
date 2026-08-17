---
title: Agent 编排模式
lifecycle: draft
category: reference
tags: [ai-agent, orchestration, workflow, active]
created: 2026-08-07
updated: 2026-08-07
base_confidence: 0.83
summary: Agent 编排模式详解：顺序链/并行扇出/条件路由/DAG/状态机/事件驱动/Actor 模型。含代码示例、框架支持、选型决策树。
---

<!-- kb-import-backlink:LLMForEverybody -->

> [!info] 外部资料 · LLMForEverybody
> 中文大模型知识库 [[sources/LLMForEverybody/index|LLMForEverybody 导航]] 中的相关章节：
> - [[sources/LLMForEverybody/07-第七章-Agent/Agent设计范式与常见框架|Agent 设计范式]]













# Agent 编排模式

## 七种编排模式

| 模式 | 原理 | 复杂度 | 适用场景 | 框架支持 |
|------|------|--------|---------|---------|
| **顺序链** | 任务按线性顺序依次执行 | 低 | 管道处理、固定流程 | LangChain, LangGraph |
| **并行扇出** | 多个子任务同时执行，结果合并 | 中 | 独立子任务加速、多视角分析 | LangGraph, CrewAI |
| **条件路由** | 根据运行时条件动态选择路径 | 中 | 分类决策、异常处理分支 | LangGraph, Dify |
| **DAG** | 有向无环图定义任务依赖关系 | 高 | 复杂依赖编排、数据管道 | LangGraph, Airflow |
| **状态机** | 显式状态 + 转移规则驱动 | 高 | 多轮对话、工作流审批 | LangGraph, Temporal |
| **事件驱动** | 异步事件触发响应，松耦合 | 高 | 实时响应、微服务编排 | Temporal, Custom |
| **Actor 模型** | 独立 Actor 通过消息通信协作 | 高 | 大规模并发、弹性伸缩 | AutoGen, MAS |

## 代码示例

### 顺序链

```python
# LangChain Sequential Chain
chain = LLMChain(llm=llm, prompt=prompt_a) | LLMChain(llm=llm, prompt=prompt_b) | LLMChain(llm=llm, prompt=prompt_c)
result = chain.invoke({"input": "原始数据"})
```

### 并行扇出

```python
# LangGraph Parallel Fan-out
from langgraph.graph import StateGraph

graph = StateGraph(State)
graph.add_node("analyze", analyze_task)
graph.add_node("summarize", summarize_task)
graph.add_node("merge", merge_results)
graph.add_edge("analyze", "merge")
graph.add_edge("summarize", "merge")
# analyze 与 summarize 并行执行
```

### 条件路由

```python
# LangGraph Conditional Routing
def route_classify(state):
    if state["category"] == "technical":
        return "tech_agent"
    elif state["category"] == "general":
        return "general_agent"
    return "default_agent"

graph.add_conditional_edges("classifier", route_classify)
```

### 状态机

```python
# LangGraph State Machine
graph.add_node("draft", create_draft)
graph.add_node("review", review_draft)
graph.add_node("revise", revise_draft)
graph.add_node("publish", publish_final)

graph.add_edge("draft", "review")
graph.add_conditional_edges("review", lambda s: "revise" if s["needs_revision"] else "publish")
graph.add_edge("revise", "review")  # 循环：修改后重新审核
```

### 事件驱动

```python
# Temporal Workflow (伪代码)
@workflow.defn
class MyWorkflow:
    @workflow.run
    async def run(self, input):
        result = await workflow.execute_activity(analyze, input)
        signal = await workflow.wait_condition(lambda: self.has_signal)
        await workflow.execute_activity(respond, result, signal)
```

## 选型决策树

```
需要编排多步任务？
├─ 步骤固定、顺序明确？ ──────────▶ 顺序链
├─ 步骤可并行？ ──────────────────▶ 并行扇出
├─ 需根据条件分支？ ────────────▶ 条件路由
├─ 步骤间有复杂依赖关系？ ────▶ DAG
├─ 需显式状态管理/多轮循环？ ──▶ 状态机
├─ 异步事件驱动？ ─────────────▶ 事件驱动
└─ 大规模并发 Agent 协作？ ────▶ Actor 模型
```

## 框架编排能力对比

| 框架 | 顺序链 | 并行 | 条件路由 | DAG | 状态机 | 事件驱动 | 多 Agent |
|------|--------|------|---------|-----|--------|---------|---------|
| **LangGraph** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **CrewAI** | ✅ | ✅ | ✅ | ⚠️ | ❌ | ❌ | ✅ |
| **AutoGen** | ✅ | ✅ | ✅ | ⚠️ | ❌ | ✅ | ✅ |
| **Dify** | ✅ | ⚠️ | ✅ | ⚠️ | ❌ | ❌ | ⚠️ |
| **Temporal** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ |

> ✅ = 原生支持  ⚠️ = 部分/间接支持  ❌ = 不支持

## 延伸阅读

- [[agent-frameworks]]
- [[multi-agent-collaboration]]
- [[agent-tool-use-mcp]]
- [[llm-agent-harness]] — 包裹模型的运行时 / 控制循环（编排跑在 harness 之上）
