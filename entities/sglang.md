---
title: SGLang 推理引擎
tags: [llm, inference-engine, sglang, radixattention, structured-generation, active]
lifecycle: active
category: entity
base_confidence: 0.82
created: 2026-08-17
updated: 2026-08-17
summary: >-
  SGLang：高性能 LLM 推理引擎，核心创新 RadixAttention 实现高效前缀复用，
  原生支持结构化生成（JSON/正则约束解码）、多模态推理、分裂式 prefill-decode 架构。
---

# SGLang 推理引擎

> **一句话**：SGLang = RadixAttention（前缀树 KV Cache）+ 结构化生成 + 分裂式架构，追求编程友好和极致效率。

## 定位

| 维度 | 说明 |
|------|------|
| **定位** | 高性能 LLM 推理 + 结构化生成引擎 |
| **核心创新** | RadixAttention（基数树注意力） |
| **语言** | Python + C++/CUDA |
| **许可证** | Apache 2.0 |
| **GitHub** | github.com/sgl-project/sglang |

## 核心架构

```
┌──────────────────────────────────────────┐
│           SGLang Runtime                  │
├──────────────────────────────────────────┤
│  Frontend: SGLang 前端语言                │
│  ┌──────────────────────────────────┐    │
│  │  Python DSL + 程序结构化生成       │    │
│  │  JSON Schema / Regex 约束         │    │
│  └──────────────────────────────────┘    │
├──────────────────────────────────────────┤
│  Backend: 推理引擎                       │
│  ┌──────────────┐  ┌──────────────────┐  │
│  │ RadixAttention│  │ Continuous Batching│ │
│  │ (基数树 KV)   │  │ (连续批处理)       │  │
│  └──────────────┘  └──────────────────┘  │
├──────────────────────────────────────────┤
│  分裂式架构 (Disaggregated)               │
│  ┌──────────┐      ┌──────────────┐      │
│  │ Prefill  │ ───→ │    Decode     │      │
│  │ Instance │      │   Instance    │      │
│  └──────────┘      └──────────────┘      │
├──────────────────────────────────────────┤
│  CUDA / NCCL / NVLink                    │
└──────────────────────────────────────────┘
```

## 核心特性

### 1. RadixAttention（基数树注意力）

SGLang 的核心创新。将所有请求的 KV Cache 组织为一棵**基数树（Radix Tree）**，自动共享公共前缀：

```
Radix Tree 结构：

Root
├── [System Prompt] (1000 tokens)
│   ├── [User: What is AI?] → KV Cache A
│   ├── [User: What is ML?] → KV Cache B
│   └── [User: What is NLP?] → KV Cache C
├── [Other Prompt] (500 tokens)
│   └── [User: Hello] → KV Cache D
```

| 维度 | vLLM Prefix Caching | SGLang RadixAttention |
|------|---------------------|----------------------|
| 数据结构 | 线性缓存 | 基数树 |
| 前缀匹配 | 精确匹配 | LRU 淘汰 + 树匹配 |
| 共享粒度 | 块级别 | Token 级别 |
| 适用场景 | 简单前缀复用 | 复杂多轮对话、Agent |

### 2. 结构化生成（Guided Decoding）

SGLang 内置强大的结构化生成支持：

```python
import sglang as sgl

@sgl.function
def chat_with_schema(s, question):
    s += sgl.system("You are a helpful assistant")
    s += sgl.user(question)
    s += sgl.assistant(
        sgl.gen(
            "answer",
            max_tokens=256,
            # JSON Schema 约束
            regex=r'\{"name": "[^"]+", "age": \d+, "skills": \["[^"]+", ...\]\}'
        )
    )

# 或使用 Pydantic 模型
from pydantic import BaseModel

class PersonInfo(BaseModel):
    name: str
    age: int
    skills: list[str]

@sgl.function
def extract_info(s, text):
    s += sgl.user(f"Extract person info from: {text}")
    s += sgl.assistant(
        sgl.gen(
            "info",
            max_tokens=256,
            json_schema=PersonInfo
        )
    )
```

### 3. SGLang 前端语言

提供 Python DSL 编排复杂推理流程：

```python
import sglang as sgl

@sgl.function
def multi_turn_qa(s, question, context):
    # 多轮对话
    s += sgl.system("You are a helpful assistant")
    s += sgl.system(f"Context: {context}")
    
    # 第一轮
    s += sgl.user(question)
    s += sgl.assistant(sgl.gen("answer1", max_tokens=256))
    
    # 基于第一轮结果的追问
    s += sgl.user(f"Tell me more about: {s['answer1']}")
    s += sgl.assistant(sgl.gen("answer2", max_tokens=256))

# 并行执行多个请求
states = multi_turn_qa.run_batch([
    {"question": "What is AI?", "context": "..."},
    {"question": "What is ML?", "context": "..."},
])
```

### 4. 分裂式架构（Disaggregated Prefill-Decode）

将 Prefill（预填充）和 Decode（解码）分离到不同 GPU：

```
传统架构：
  GPU 0: [Prefill + Decode 混合] → 互相干扰

分裂式架构：
  GPU 0 (Prefill):  [快速处理输入 tokens] → KV Cache 传输
  GPU 1 (Decode):   [专注生成输出 tokens] → 高吞吐
```

| 维度 | 混合架构 | 分裂式架构 |
|------|----------|------------|
| GPU 利用率 | Prefill 和 Decode 争抢资源 | 各自专注，利用率高 |
| TTFT | 受 Decode 干扰 | 更低（Prefill 专用 GPU） |
| 吞吐量 | 一般 | 更高 |
| 复杂度 | 低 | 高（需 KV 传输） |

### 5. 多 GPU 并行

```bash
# 张量并行
python -m sglang.launch_server \
    --model-path meta-llama/Llama-3-8B-Instruct \
    --tp-size 2 \
    --port 30000

# 分裂式部署
python -m sglang.launch_server \
    --model-path meta-llama/Llama-3-8B-Instruct \
    --disaggregation-mla-chunk-prefill-size 32 \
    --port 30000
```

### 6. 内存、GPU 与对外接口速览

| 视角 | 要点 |
|------|------|
| **内存** | 页式 MemoryPool（KV 按页分配）；RadixCache 用引用计数 + LRU 叶子淘汰实现前缀共享；FP8 KV Cache（`--kv-cache-dtype fp8`）减半 KV 显存；chunked prefill 控制激活峰值 |
| **GPU** | 深度绑定 FlashInfer + 自研 sgl-kernel；DeepSeek MLA 有专用融合 kernel；CUDA Graph 按 batch 档位捕获 + 填坑复用；TP/EP/DP/分离式 P/D 全支持 |
| **接口** | OpenAI 兼容（`/v1/chat/completions`、`/v1/completions`）+ 原生 `/generate`、`/classify`、`/encode`、`/embedding`、`/tokenize`、`/health`、`/metrics`；DSL `sgl.function` 离线/在线两用；结构化输出（XGrammar/正则/JSON Schema）常见兜底接口 |

> 深度展开见 [[sources/SGLang-Deep-Dive|SGLang 深度解析]]。

## 与 vLLM 对比

| 维度 | SGLang | vLLM |
|------|--------|------|
| **前缀复用** | ⭐⭐⭐⭐⭐ (RadixAttention) | ⭐⭐⭐⭐ (Prefix Caching) |
| **结构化生成** | ⭐⭐⭐⭐⭐ (原生支持) | ⭐⭐⭐⭐ (Guided Decoding) |
| **易用性** | ⭐⭐⭐⭐ (SGLang DSL) | ⭐⭐⭐⭐⭐ (OpenAI API) |
| **模型支持** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **分裂式架构** | ⭐⭐⭐⭐⭐ (原生) | ⭐⭐ (开发中) |
| **社区活跃度** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **最佳场景** | Agent/多轮对话/结构化 | 通用服务化部署 |

## 延伸

- → [[sources/SGLang-Deep-Dive|SGLang 深度解析]] — 架构/调度/内存/GPU/接口 全展开
- → [[entities/vllm|vLLM]] — 对比：最流行推理引擎
- → [[entities/llama.cpp|llama.cpp]] — 对比：CPU/边缘推理
- → [[推理 引擎 选择]] — 推理引擎选型对比
- → [[LLM 推理 优化]] — 推理优化技术总论

---

**参考来源**：
- [SGLang 官方文档](https://sgl-project.github.io/)
- [SGLang GitHub](https://github.com/sgl-project/sglang)
- [RadixAttention 论文](https://arxiv.org/abs/2312.07104)

**最后更新**：2026-08-17
**维护者**：Claudian
**状态**：活跃维护中

---

## 📖 来源参考

- **深度解析**：[[sources/SGLang-Deep-Dive|SGLang 深度解析]] — 基于架构与源码逻辑的详解
- **LLMForEverybody**：[[sources/LLMForEverybody/02-第二章-部署与推理/大模型推理框架（六）SGLang|大模型推理框架（六）SGLang]] — 专题介绍文章
- **导航**：[[sources/LLMForEverybody/索引#部署与推理|部署与推理（第02章）]]
> 来自 [luhengshiwo/LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody) 外部知识库导入
