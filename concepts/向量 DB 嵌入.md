---
aliases: ["vector-db-embedding"]
title: 向量数据库与 Embedding
tags: [llm, embedding, vector-db, rag, active]
created: 2026-08-07
summary: >-
    向量数据库与 Embedding 全景：Embedding 模型（BGE/E5/GTE/Cohere）、向量数据库架构（Qdrant/Milvus/ChromaDB/Weaviate/Pinecone）、ANN 索引（HNSW/IVF/PQ）、相似度度量、混合检索、RAG 中的向量检索。
category: reference
updated: 2026-08-07
sources: []
base_confidence: 0.83
lifecycle: draft
---

<!-- kb-import-backlink:LLMForEverybody -->

> [!info] 外部资料 · LLMForEverybody
> 中文大模型知识库 [[sources/LLMForEverybody/索引|LLMForEverybody 导航]] 中的相关章节：
> - [[sources/LLMForEverybody/07-第七章-Agent/向量数据库拥抱大模型|向量数据库]]













# 向量数据库与 Embedding

> LLM 无法直接处理外部知识——Embedding 把文本转为向量，向量数据库做高速相似度检索，是 RAG 的基础设施。

## 1. Embedding 模型

### 主流模型对比

| 模型 | 维度 | 语言 | MTEB 排名 | 特点 |
|------|:----:|------|:---------:|------|
| **BGE-M3** | 1024 | 多语言 | ★★★★★ | 多语言+多粒度+多功能（稠密/稀疏/多向量） |
| **bge-small-zh-v1.5** | 512 | 中文 | ★★★★ | 轻量中文，适合本地部署 |
| **E5-Mistral-7B** | 4096 | 多语言 | ★★★★★ | LLM-based Embedding，效果最强 |
| **GTE-Qwen2** | 1536 | 多语言 | ★★★★★ | 通义千问 Embedding |
| **Cohere Embed v3** | 1024 | 多语言 | ★★★★★ | 商用 API |
| **OpenAI text-embedding-3** | 3072 | 多语言 | ★★★★ | 商用 API，支持维度缩减 |

### Embedding 原理

```
文本 → Tokenizer → Transformer → [CLS] 或 Mean Pooling → 归一化 → 向量 (d 维)
```

```python
from sentence_transformers import SentenceTransformer
model = SentenceTransformer("BAAI/bge-m3")
embeddings = model.encode(["什么是向量数据库？", "How does RAG work?"])
# embeddings.shape = (2, 1024)
```

### 选型建议

| 场景 | 推荐 |
|------|------|
| 中文本地部署 | bge-small-zh-v1.5 / bge-m3 |
| 多语言生产 | BGE-M3 / Cohere v3 |
| 极致效果 | E5-Mistral-7B（需 GPU） |
| 低成本快速 | text-embedding-3-small (OpenAI) |

## 2. 向量数据库

### 核心架构

```
写入: 文本 → Embedding 模型 → 向量 → ANN 索引(HNSW/IVF) → 持久化
查询: 查询文本 → Embedding 模型 → 向量 → ANN 搜索 → Top-K 结果
```

### 主流向量数据库对比

| 数据库 | 类型 | 语言 | 特点 | 适用 |
|--------|------|------|------|------|
| **Qdrant** | 独立服务 | Rust | 高性能、过滤强、易用 | 生产首选 |
| **Milvus** | 分布式 | Go/C++ | 大规模、云原生 | 大规模生产 |
| **ChromaDB** | 嵌入式 | Python | 极简、嵌入式 | 原型/小项目 |
| **Weaviate** | 独立服务 | Go | GraphQL API、模块化 | 多模态检索 |
| **Pinecone** | 云托管 | — | 全托管、Serverless | 无运维需求 |
| **pgvector** | PG 扩展 | C | 复用已有 PostgreSQL | 已有 PG 基础设施 |
| **LanceDB** | 嵌入式 | Rust | 列存储、零拷贝 | 分析型场景 |

### ANN 索引算法

| 算法 | 原理 | 内存 | 查询速度 | 精度 |
|------|------|:----:|:--------:|:----:|
| **HNSW** | 分层可导航小世界图 | 高 | ★★★★★ | ★★★★★ |
| **IVF** | 倒排索引 + 聚类 | 中 | ★★★★ | ★★★★ |
| **PQ（乘积量化）** | 向量压缩 | 低 | ★★★ | ★★★ |
| **IVF-PQ** | IVF + PQ 组合 | 低 | ★★★★ | ★★★★ |
| **ScaNN** | Google 优化量化 | 中 | ★★★★★ | ★★★★ |

**选型直觉**：
- 一般场景 → HNSW（默认最优）
- 内存受限 → IVF-PQ
- 十亿级向量 → IVF-PQ + 分片

## 3. 相似度度量

| 度量 | 公式 | 适用 |
|------|------|------|
| **余弦相似度** | cos(a,b) = a·b / (‖a‖·‖b‖) | 文本语义（最常用） |
| **欧氏距离** | ‖a-b‖₂ | 图像特征 |
| **内积（点积）** | a·b | 已归一化向量 |
| **汉明距离** | 二进制位差异 | 二值向量 |

> 文本 Embedding 通常用余弦相似度，归一化后等价于内积。

## 4. RAG 中的向量检索

```
用户查询 → Embedding → 向量 DB 检索 → Top-K 文档块 → LLM 生成回答
```

### 检索优化

| 技术 | 说明 |
|------|------|
| **混合检索** | 向量 + BM25 关键词 → RRF/加权融合 |
| **重排序（Reranker）** | 检索后用交叉编码器精排（如 bge-reranker） |
| **查询改写** | LLM 改写用户查询（HyDE：生成假设文档再检索） |
| **多向量检索** | 每个文档多个向量（摘要+内容），提高召回 |
| **分块策略** | 语义分块 > 固定长度分块 |

详见 [[concepts/AI 智能体 概览|AI Agent 概述]] 和 [[concepts/混合 检索 bm 25 语义 融合|混合检索]]。

## 5. 常见坑

| 现象 | 原因 | 解决 |
|------|------|------|
| 检索结果不相关 | Embedding 模型与领域不匹配 | 微调 Embedding 或换模型 |
| 召回率低 | 分块太大/太小 | 优化分块策略（200~500 token） |
| 向量 DB 内存爆 | HNSW 索引太大 | 用 IVF-PQ 压缩或分片 |
| 实时性差 | 写入未立即可搜索 | 检查索引刷新策略 |

## 延伸

- RAG：[[concepts/RAG 检索 增强 生成|RAG 检索增强生成]]
- 混合检索：[[concepts/混合 检索 bm 25 语义 融合|混合检索]]
- Agent：[[concepts/AI 智能体 概览|AI Agent 概述]]
- LLM 推理：[[concepts/LLM 推理 优化|LLM 推理优化]]
