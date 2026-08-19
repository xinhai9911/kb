---
title: llama.cpp
tags: [llm, inference-engine, llama-cpp, gguf, cpu-inference, cross-platform, active]
lifecycle: active
category: entity
base_confidence: 0.85
created: 2026-08-18
updated: 2026-08-18
summary: >-
  llama.cpp：纯CPU/跨平台 LLM 推理先驱，定义了GGUF量化格式，
  支持CUDA/Metal/Vulkan等多后端加速，零GPU依赖运行大模型。
---

# llama.cpp

> **一句话**：llama.cpp = CPU-first 推理 + GGUF 量化 + 全平台支持，让每个人都能在本地跑大模型。

## 定位

| 维度 | 说明 |
|------|------|
| **定位** | CPU-first / 跨平台 LLM 推理引擎 |
| **核心创新** | GGUF 量化格式、CPU优化推理 |
| **语言** | C/C++ |
| **许可证** | MIT |
| **GitHub** | github.com/ggerganov/llama.cpp |

## 核心特性

### 1. GGUF 量化格式

llama.cpp 定义的模型格式，取代了早期的 GGML：

| 量化类型 | 位宽 | 7B 模型大小 | 质量 | 速度 |
|---------|------|-----------|------|------|
| F16 | 16-bit | ~14GB | 原始 | 慢 |
| Q8_0 | 8-bit | ~7.5GB | 优 | 中 |
| Q6_K | 6-bit | ~5.5GB | 良 | 快 |
| Q4_K_M | 4-bit | ~4GB | 可用 | 快 |
| Q2_K | 2-bit | ~2.5GB | 差 | 最快 |

### 2. 多后端加速

```
┌─────────────────────────────────────────┐
│              llama.cpp                  │
├─────────────────────────────────────────┤
│  CPU (默认) → 所有平台                   │
│  CUDA       → NVIDIA GPU                │
│  Metal      → Apple Silicon M1/M2/M3/M4 │
│  Vulkan     → 跨平台 GPU                │
│  SYCL       → Intel GPU                 │
│  CANN       → 华为昇腾                   │
└─────────────────────────────────────────┘
```

### 3. 内存映射（mmap）+ 页式 KV Cache

- **mmap**：模型文件直接映射到虚拟内存，按需加载，支持超大模型在有限内存上运行；`--no-mmap`/`--mlock` 可改为整体载入防换出。
- **KV Cache**：按 `--ctx-size` 为全量并发请求分配；现代版本用**页式 KV Cache + defrag**（`llama_kv_cache` 分页、删段、碎片整理），配合 `--parallel` 槽位共享。
- **内存公式**：权重（量化后）+ KV cache + 计算缓冲 ≈ 4B(Q4)~35GB(70B Q4)；用 `--batch-size`/`--ubatch-size` 控制激活峰值。

### 4. GPU 后端与内部调度

- **多后端**：CUDA / Vulkan / Metal / SYCL / CANN / RPC 统一走 `ggml_backend`；`-ngl` 控制层卸载量，`--split-mode layer|row(tensor)` + `--tensor-split` 做多卡切分，支持 MoE expert offload。
- **调度**：prefill（整体/分 micro-batch）与 decode（逐 token）由 `llama_decode(batch)` 驱动；服务端用 `--parallel` 槽位 + `--cont-batching`（默认开）把多请求拼成一个 batch 每轮前向、等待队列排队，近似连续批处理。

### 5. 服务与结构化输出

- 内置 **llama-server**：OpenAI 兼容（`/v1/chat/completions` 等）+ 原生 `/completion`、`/infill`、`/embedding`、`/tokenize`、`/health`、`/metrics`、`/slots`。
- **GBNF 语法**约束结构化输出（`grammars/` 含 json.gbnf），支持原地限约束解码。

## 与 vLLM / Ollama 对比

| 维度 | llama.cpp | vLLM | Ollama |
|------|-----------|------|--------|
| **运行环境** | CPU/GPU | GPU | CPU/GPU |
| **量化格式** | GGUF | 多种 | GGUF (底层llama.cpp) |
| **跨平台** | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
| **CPU推理** | ⭐⭐⭐⭐⭐ | ❌ | ⭐⭐⭐⭐ |
| **GPU吞吐量** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **最佳场景** | 本地/边缘/离线 | 生产服务 | 个人助手 |

## 生态

- **Ollama** — 基于 llama.cpp 的简化封装
- **LM Studio** — GUI 界面，底层 llama.cpp
- **llama-cpp-python** — Python 绑定
- **Open WebUI** — 兼容 OpenAI API 的 Web 界面

## 延伸

- → [[sources/推理引擎/llama.cpp-Deep-Dive|llama.cpp 深度解析]] — GGUF/量化/mmap/GPU 后端/调度/接口 全展开
- → [[sources/推理引擎/vllm|vLLM]] — GPU 生产部署首选
- → [[sources/推理引擎/sglang|SGLang]] — RadixAttention 推理引擎
- → [[sources/推理引擎/推理 引擎 选择]] — 推理引擎选型对比
- → [[sources/推理引擎/LLM 推理 优化]] — 推理优化技术总论

---

**参考来源**：
- [llama.cpp GitHub](https://github.com/ggerganov/llama.cpp)
- [llama.cpp Wiki](https://github.com/ggerganov/llama.cpp/wiki)
- [GGUF 格式规范](https://github.com/ggerganov/llama.cpp/blob/master/docs/gguf.md)

**最后更新**：2026-08-18
**维护者**：Claudian
**状态**：活跃维护中

---

## 📖 来源参考

- **深度解析**：[[sources/推理引擎/llama.cpp-Deep-Dive|llama.cpp 深度解析]] — GGUF/量化/内存/GPU/调度/接口 架构详解
- **LLMForEverybody**：[[sources/LLMForEverybody/02-第二章-部署与推理/大模型推理框架（七）llama.cpp|大模型推理框架（七）llama.cpp]] — 专题介绍文章
- **导航**：[[sources/LLMForEverybody/索引#部署与推理|部署与推理（第02章）]]
> 来自 [luhengshiwo/LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody) 外部知识库导入
