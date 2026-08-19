---
aliases: ["rag-retrieval-augmented-generation"]
title: RAG 检索增强生成
tags: [llm, rag, retrieval, generation, active]
created: 2026-08-07
summary: >-
    RAG（Retrieval-Augmented Generation）架构：基础 RAG 流程、高级 RAG（查询改写/多步检索/自适应检索）、Naive RAG vs Advanced RAG vs Modular RAG、RAG 评估（RAGAS/TruLens）、RAG vs 长上下文 vs 微调选型。
category: reference
updated: 2026-08-07
sources: []
base_confidence: 0.83
lifecycle: draft
---

<!-- kb-import-backlink:LLMForEverybody -->

> [!info] 外部资料 · LLMForEverybody
> 中文大模型知识库 [[sources/LLMForEverybody/索引|LLMForEverybody 导航]] 中的相关章节：
> - [[sources/LLMForEverybody/07-第七章-Agent/搭配Knowledge-Graph的RAG架构|KG+RAG 架构]]
> - [[sources/LLMForEverybody/07-第七章-Agent/干货-落地企业级RAG的实践指南|企业级 RAG 实践]]
> - [[sources/LLMForEverybody/07-第七章-Agent/10分钟了解如何进行多模态RAG|多模态 RAG]]





# RAG 检索增强生成

> RAG 让 LLM 在回答时**先检索相关文档**，再基于检索结果生成，解决幻觉和知识过时问题。

## 1. RAG 核心流程

```
用户查询 ──► 查询理解/改写 ──► 检索(Vector+BM25) ──► 重排序(Reranker)
                                                            │
用户回答 ◄── LLM 生成 ◄── 上下文组装 ◄── Top-K 文档块 ◄──┘
```

### Naive RAG vs Advanced RAG vs Modular RAG

| 范式 | 特点 | 适用 |
|------|------|------|
| **Naive RAG** | 简单检索+生成，无优化 | 原型/MVP |
| **Advanced RAG** | 查询改写/重排序/多步检索 | 生产系统 |
| **Modular RAG** | 组件化（路由/评估/自纠正） | 复杂场景 |

## 2. 高级 RAG 技术

### 查询侧优化

| 技术 | 说明 |
|------|------|
| **查询改写** | LLM 重写用户查询（多角度/Step-Back） |
| **HyDE** | 生成假设性文档，用假设文档做检索 |
| **查询路由** | 根据查询类型选择检索策略 |
| **多查询** | 将一个查询扩展为多个子查询 |

### 检索侧优化

| 技术 | 说明 |
|------|------|
| **混合检索** | 向量 + BM25 + RRF 融合 |
| **重排序** | Cross-Encoder 精排（bge-reranker） |
| **父子检索** | 小块检索+大块上下文返回 |
| **多向量索引** | 文档摘要+内容分别索引 |

### 生成侧优化

| 技术 | 说明 |
|------|------|
| **引用追溯** | 标注答案来源（哪个文档的哪段） |
| **置信度评分** | 检索结果相关性评分，低于阈值拒绝回答 |
| **自纠正** | 生成后自评，不满足则重新检索 |
| **流式输出** | 检索+生成流水线化，减少延迟 |

## 3. RAG 评估

### 评估指标

| 指标 | 评估维度 | 工具 |
|------|---------|------|
| **Faithfulness** | 答案是否忠于检索结果 | RAGAS |
| **Answer Relevancy** | 答案是否与问题相关 | RAGAS |
| **Context Precision** | 检索结果中相关文档的排名 | RAGAS |
| **Context Recall** | 参考答案中的信息是否被检索到 | RAGAS |

### 评估框架

| 框架 | 特点 |
|------|------|
| **RAGAS** | 标准 RAG 评估，LLM-as-Judge |
| **TruLens** | 可观测性+评估 |
| **LangSmith** | LangChain 生态的追踪与评估 |

## 4. RAG vs 长上下文 vs 微调

| 维度 | RAG | 长上下文 (128K+) | 微调 |
|------|-----|-----------------|------|
| 知识更新 | 实时更新 | 需重传文档 | 需重训练 |
| 成本 | 检索基础设施 | 长序列推理贵 | 训练贵 |
| 精确性 | 取决于检索质量 | 上下文内精确 | 知识内化 |
| 幻觉控制 | 好（有引用） | 中 | 差 |
| 适用 | 企业知识库 | 一次性分析 | 领域专精 |

## 5. 典型 RAG 架构

### LangChain RAG

```python
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.chains import RetrievalQA

# 1. 向量化文档
vectorstore = Chroma.from_documents(docs, OpenAIEmbeddings())

# 2. 构建检索链
qa_chain = RetrievalQA.from_chain_type(
    llm=ChatOpenAI(model="gpt-4"),
    retriever=vectorstore.as_retriever(search_kwargs={"k": 5}),
    return_source_documents=True
)

# 3. 查询
result = qa_chain.invoke({"query": "什么是 RAG？"})
```

### 生产级 RAG 架构

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ 文档解析  │───►│ 分块策略  │───►│ Embedding │───►│ 向量 DB  │
│(PDF/HTML) │    │(语义分块) │    │(BGE-M3)   │    │(Qdrant)  │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
                                                      │
┌──────────┐    ┌──────────┐    ┌──────────┐         │
│ 用户查询  │───►│ 查询改写  │───►│ 混合检索  │◄────────┘
│           │    │(HyDE)    │    │(向量+BM25)│
└──────────┘    └──────────┘    └────┬─────┘
                                     │
┌──────────┐    ┌──────────┐         │
│ 答案生成  │◄───│ 重排序    │◄────────┘
│ (LLM)    │    │(Reranker)│
└──────────┘    └──────────┘
```

## 6. 常见坑

| 现象 | 原因 | 解决 |
|------|------|------|
| 答案幻觉 | 检索结果无关 | 提升检索质量（混合检索+重排序） |
| 答案不完整 | 分块切断关键信息 | 语义分块+父子检索 |
| 延迟高 | 检索+LLM 串行 | 异步检索、缓存热门查询 |
| 成本高 | 长上下文+大模型 | 小模型+精确检索 |

## 延伸

- 向量 DB：[[concepts/向量 DB 嵌入|向量数据库与 Embedding]]
- 混合检索：[[concepts/混合 检索 bm 25 语义 融合|混合检索]]
- Agent：[[concepts/AI 智能体 概览|AI Agent 概述]]
- LLM 推理：[[sources/推理引擎/LLM 推理 优化|LLM 推理优化]]


