---
title: SGLang 源码导读（模块地图与关键路径）
tags: [llm, inference-engine, sglang, source, mla, rust, index]
created: 2026-08-19
updated: 2026-08-19
lifecycle: active
category: sources
base_confidence: 0.78
summary: >-
  SGLang 仓库的模块地图与回查索引：python/sglang/srt/ 各核心模块（Scheduler / RadixCache /
  MemoryPool / ModelRunner / Server）、DeepSeek MLA 融合 kernel 的实现路径、2025 年起的 Rust 组件，
  以及分布式 launch 的命令细节。无本地仓库，基于公开设计与文档整理，clone 后据此回查。
---

# SGLang 源码导读（模块地图与关键路径）

> **用途**：配合 [[sources/推理引擎/SGLang-Deep-Dive|SGLang 深度解析]]，把概念映射到真实代码路径，方便 `grep`/跳转回查。
> ⚠️ 当前环境**无本地 `Q:/AI/sglang` 仓库**，本文基于 SGLang 公开架构设计与文档整理；**路径/类名/旗标随版本演进，clone 后以 `python/sglang/srt/` 实际结构为准**。

## 1. 仓库顶层布局

```
sglang/
├── python/
│   ├── sglang/                 # 前端 DSL（sgl.function / gen / user / assistant / Runtime）
│   └── sglang/srt/             # 后端 Runtime（System for Language Models，本导读重点）
├── benchmark/                  # 内置基准（bench_serving 等）
├── examples/                   # 官方示例
├── test/                       # 单元/集成测试
├── docs/                       # 官方文档（docs.sglang.ai）
├── sgl-kernel/                 # 自研 C++/CUDA kernel（MLA 等，也可独立安装）
└── Cargo 等 (2025+)            # Rust 组件（tokenizer、部分数据结构）随版本增多
```

## 2. 后端核心模块地图（`python/sglang/srt/`）

| 模块路径 | 关键类/文件 | 作用 |
|----------|-------------|------|
| `managers/scheduler.py` | `Scheduler` | 每轮做统一 forward 决策、维护所有请求状态机、产出 `ScheduleBatch`（[[sources/推理引擎/SGLang-Deep-Dive#3|调度详解]]） |
| `managers/tokenizer_manager.py` | `TokenizerManager` | 多请求异步批量 tokenize、缓存 `input_token_ids` |
| `managers/detokenizer_manager.py` | `DetokenizerManager` | 每轮批-增量 detokenize、驱动流式输出 |
| `managers/io_struct.py` | `GenerationReq / EmbeddingReq` 等 | HTTP 请求体 → 内部请求对象 |
| `mem_cache/memory_pool.py` | `MemoryPool` | KV 页池：allocate/free（页粒度） |
| `mem_cache/radix_cache.py` | `RadixCache` | 基数树前缀缓存：match / insert / evict（LRU 叶子淘汰） |
| `model_executor/model_runner.py` | `ModelRunner` | 组装 ForwardBatch → 前向 → 采样；管理 CUDA Graph |
| `model_executor/controller.py` | `Controller` | 分布式控制（worker 管理、启停、deadlock 检测） |
| `model_executor/cuda_graph_runner.py` | `CUDAGraphRunner` | batch 固定 + 图捕获/重放 |
| `server.py` / `entrypoints/` | — | HTTP server 与路由注册 |
| `layers/attention/` | `flashinfer` / `flashattn` / `triton` 后端 | 注意力 kernel 封装（MLA 走专用路径） |
| `layers/sampling.py` | `Sampler` | 采样（temperature/top_p/stop/beam） |
| `layers/quantization/` | 各量化器 | fp8 / w8a8 等 |
| `constraints/` | `ConstraintType` 系列 | 结构化生成约束（regex / json_schema / grammar） |
| `speculative/` | `SpecInfo` 系列 | EAGLE / Medusa / Lookahead / NGram 等 |
| `models/` | `deepseek_v2.py`、`llama.py`、`qwen*`… | 各模型实现（含 MLA 特殊 attention） |
| `kernels/` | 自研 kernel (部分在 `sgl-kernel`) | fused 算子：rms_norm、FP8、MLA 等 |

## 3. 一次请求的最短代码路径

```
HTTP → server.py 路由
   └─> TokenizerManager.process_request_async   (tokenize 落在 input_token_ids)
        └─> Scheduler.add_request                (请求进 priority 队列)
             └─> Scheduler.schedule()             (每轮：decode running + 缝隙 prefill)
                  └─> 生成 ScheduleBatch
                       └─> ModelRunner.forward(fwd_batch)
                            ├─> CUDAGraphRunner 复用/重放（decode）或普通 prefill
                            ├─> 模型前向：layers/attention 取 KV → 写回 MemoryPool 页
                            ├─> RadixCache.insert（登记新前缀）
                            └─> Sampler → 新 token
             └─> Scheduler.update_outputs          (停止/流式检查)
                  └─> DetokenizerManager.process_batch_result → HTTP 流/一次返回
```

## 4. DeepSeek MLA（Multi-head Latent Attention）的实现路径（重点）

MLA 是 SGLang 对 DeepSeek V2/V3/R1 优化最深的部分，也是 DeepSeek 官方推荐 SGLang 的核心原因。

### 4.1 MLA 原理（为什么省内存）

传统 MHA 每个 token 缓存 `num_kv_heads × head_dim` 的 K/V；MLA 把 K/V 从**低秩潜在向量 `c_KV`** 上投影得到，KV Cache 只存 `c_KV`（+ 少量 RoPE 分量 `k_R`），同样也压缩 Q（`c_Q`）：

```
传统 MHA:   K/V cache = [num_kv_heads × head_dim] per token（如 2×128）
MLA:        KV cache ≈ [c_KV dim（如 512/576 量级） + k_R] per token（一个潜在向量）
            decode 时才上投影：c_KV → W_UK → K； c_KV → W_UV → V
```

- KV cache 大幅缩小 → 同显存下更长上下文 / 更大并发 / 更省 KV 传输（PD 部署）。
- 代价：decode 时投影有一次性矩阵乘开销，必须用融合 kernel 压住。

### 4.2 代码与 kernel 路径

- **模型实现**：`python/sglang/srt/models/deepseek_v2.py` 等的 MLA Attention（`DeepseekV2Attention` 类，`forward_absorb` / `forward_normal` 两种路径）。
- **融合 kernel**：主要在 **`sgl-kernel`**（自研仓库）的 MLA 实现，把「潜在向量上投影 → 分页注意力 → 采样」里的算子尽量合并；支持：
  - FP8(W8A8) 权重；
  - **FP8 KV Cache**（保存 c_KV 为 FP8）；
  - `--kv-lora-rank` 调潜在向量维度；
  - `forward_absorb`（把 Q 吸收进 W_UK/W_UV 以省一次乘）等优化变体。
- **注意力后端**：MLA 不依赖通用 flashattn 路径，走独立的 MLA kernel（后端 `mla`）；通用模型才用 flashinfer/flashattn/triton 后端。
- **验证**：`run_batch`/`bench_serving` 里 DeepSeek 系列基准即走这条路径。

### 4.3 为什么 DeepSeek V3/R1 官方推荐 SGLang

SGLang 团队与 DeepSeek 协同：MLA 融合、FP8 全链路（权重+KV）、CUDA Graph、`torch.compile`（`--enable-torch-compile`）、分离式 P/D 的 KV 传输（MLA 可用 0.5×/低分辨率传输）都做了专门优化——即 [[sources/推理引擎/大模型 推理引擎 对照|模型↔引擎对照]] 里说的"官方强绑定"。

## 5. Rust 组件（2025+）

SGLang 从 2025 年起把高频/内存敏感的部件用 Rust 重写，方向包括（**以仓库实际为准**）：

| 方向 | 现状/趋势 |
|------|-----------|
| **Tokenizer** | Rust tokenizer（BPE/Unigram）替代 Python 逐请求 tokenize，降低 CPU 侧开销 |
| **Radix Cache / 数据结构** | 部分缓存/索引结构尝试 Rust 实现，减少 Python 对象开销（类似 vLLM 的 block 结构底层化） |
| **采样/小算子** | 部分采样与数值小件下沉 Rust/C++ |

- 定位：这是 "拆 Python 热径" 的延续——调度决策仍在 Python（灵活），但**每 token 必经的高频路径**（tokenize、前缀匹配、采样）逐步 Rust 化。
- 对本知识库的意义：提到 SGLang 性能持续增长的机制时，可归因于「Python 控制面 + Rust/H 高频数据面」混合架构演进（与 vLLM 的 Rust 前端路线相映）。

> 因为本地无仓库，上述 Rust 模块名/边界不展开精确路径，避免误导；追踪方法见 §7。

## 6. 分布式 launch 命令细节

### 6.1 单机多卡（TP）

```bash
python -m sglang.launch_server \
  --model-path deepseek-ai/DeepSeek-V3 \
  --tp-size 8 \
  --host 0.0.0.0 --port 30000 \
  --kv-cache-dtype fp8 --quantization fp8
```

### 6.2 多机多卡（TP 跨机）

```bash
# 主节点
python -m sglang.launch_server \
  --model-path deepseek-ai/DeepSeek-V3 \
  --tp-size 16 --nnodes 2 \
  --dist-init-addr 10.0.0.1:20000 \
  --host 0.0.0.0 --port 30000

# 从节点（同一 dist-init-addr）
python -m sglang.launch_server \
  --model-path deepseek-ai/DeepSeek-V3 \
  --tp-size 16 --nnodes 2 \
  --dist-init-addr 10.0.0.1:20000 \
  --host 0.0.0.0 --port 30001
```

> 跨机 TP 每轮前向走 NCCL allreduce，跨节点带宽是瓶颈；超大模型优先用「PP 层间流水 + 节点内 TP」而非纯 TP 跨机。

### 6.3 分离式 Prefill/Decode（PD，DeepSeek 官方形态）

```bash
# Prefill 实例
python -m sglang.launch_server --model deepseek-ai/DeepSeek-V3 \
  --tp 8 --host 0.0.0.0 --port 31000 \
  --is-prefill --kv-cache-dtype fp8 --quantization fp8

# Decode 实例
python -m sglang.launch_server --model deepseek-ai/DeepSeek-V3 \
  --tp 8 --host 0.0.0.0 --port 32000 \
  --is-decode --kv-cache-dtype fp8 --quantization fp8
```
- 两者通过 KV 传输层（ZeroScatter / NCCL / TCP）交换预填充好的 KV Cache；MLA 下可传低分辨率（0.5×）潜在向量进一步省带宽。
- 环境变量/开关族：`SGLANG_PD_SERVER_MODE`、`--disaggregation-*`、`--enable-connector-*` 等（随版本演进）。

### 6.4 Data Parallel（DP，多调度器分摊 QPS）

```bash
python -m sglang.launch_server \
  --model-path meta-llama/Llama-3-8B \
  --tp-size 2 --data-parallel-size 2 \
  --host 0.0.0.0 --port 30000
# 效果：2 份 scheduler（各挂 TP2 worker），请求被 router 分发；RadixCache 每份独立
```

## 7. 快速回查技巧（clone 之后）

```bash
git clone https://github.com/sgl-project/sglang Q:/AI/sglang
# 若想与既有 vLLM 本地仓库同级：Q:/AI/sglang
cd Q:/AI/sglang/python/sglang/srt

# 找调度决策
grep -rn "def schedule" managers/scheduler.py

# 找前缀缓存
grep -rn "def match\|def insert\|evict" mem_cache/radix_cache.py

# 找 MLA kernel
grep -rn "mla\|MLA" model_executor models/deepseek_v2.py ../../sgl-kernel

# 找采样
grep -rn "class Sampler" layers/sampling.py

# 找 CUDA Graph
grep -rn "class CUDAGraphRunner" model_executor/cuda_graph_runner.py
```

## 参考

- [SGLang GitHub](https://github.com/sgl-project/sglang)
- [SGLang 文档](https://docs.sglang.ai/)
- [DeepSeek-V2 论文：MLA (arXiv 2405.04434)](https://arxiv.org/abs/2405.04434)

---

## 📚 相关笔记

- [[sources/推理引擎/SGLang-Deep-Dive|SGLang 深度解析]] — 架构/调度/内存/GPU/接口 详解（本导读的配套）
- [[sources/推理引擎/sglang|SGLang 实体页]] — 概览
- [[sources/推理引擎/vLLM 源码 导读|vLLM 源码导读]] — 同类「源码地图」笔记（vLLM 有本地仓库 `Q:/AI/vllm/vllm`）
- [[sources/推理引擎/大模型 推理引擎 对照]] — DeepSeek↔SGLang 官方绑定
- [[sources/推理引擎/PagedAttention|PagedAttention]] — 分页 KV 思想对比 MLA 潜在向量