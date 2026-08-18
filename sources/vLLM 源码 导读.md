---
title: vLLM 源码导读（本地 Q:/AI/vllm/vllm）
tags: [vllm, source, inference, index, active]
lifecycle: active
category: sources
base_confidence: 0.9
created: 2026-08-18
updated: 2026-08-18
summary: >-
  本地 vLLM 仓库（Q:/AI/vllm/vllm）的模块地图与回查索引。本文不复制代码，
  只标注关键路径与类，便于跳进源码深挖。当前版本以 V1 架构为默认主线。
---

# vLLM 源码导读（本地 Q:/AI/vllm/vllm）

> **用途**：把 [[entities/vllm|vLLM 推理引擎]] 的概念映射到真实代码路径，方便 `grep`/跳转回查。
> 仓库根即 `Q:/AI/vllm/vllm`，Python 包位于 `vllm/vllm/`（下文路径均相对仓库根，如 `vllm/v1/engine/llm_engine.py`）。

## 版本说明：V1 是默认主线

当前仓库已统一到 **V1 架构**（约 vLLM ≥ 0.8 起逐步成为默认，新版移除/弱化 V0）。
V1 把调度、KV 管理、注意力全部重写到 `vllm/vllm/v1/` 下，追求更低开销与更简洁的请求流转。
（早期 V0 的 `LLMEngine` 仍在 `vllm/engine/`，但不再是默认路径。）

## 请求生命周期（一次 `llm.generate` 的旅程）

```
用户
 │  LLM.generate / OpenAI /v1/completions
 ↓
[入口层]   vllm/entrypoints/llm.py  :  LLM
           vllm/entrypoints/openai/ :  api_server.py (FastAPI)
 │  EngineArgs → VllmConfig
 ↓
[引擎层]   vllm/v1/engine/llm_engine.py :  LLMEngine (主进程, 用户态 API)
           ├─ add_request()   接收请求
           ├─ step()          驱动一步
           └─ 通过 EngineCoreClient 与 EngineCore 通信
 │  ZMQ / 共享内存 (跨进程)
 ↓
[核心层]   vllm/v1/engine/core.py :  EngineCore / EngineCoreProc (独立后台进程)
           ├─ step()          每个迭代：调度→执行→输出
           └─ Scheduler.schedule()  +  Executor.execute_model()
 │
 ├──────────────┐
 ↓              ↓
[调度层]        [执行层]
vllm/v1/core/   vllm/v1/executor/
 ├ sched/       ├ multiproc_executor.py : MultiprocExecutor
 │  scheduler.py: Scheduler  (连续批处理/前缀/抢占)
 │  └ _preempt_request, get_computed_blocks
 ├ kv_cache_manager.py : KVCacheManager (块分配/释放/前缀命中)
 ├ block_pool.py : BlockPool + BlockHashToBlockMap (CoW/前缀缓存)
 └ encoder_cache_manager.py
                ├ ray_executor.py : RayDistributedExecutor (多机)
                └ uniproc_executor.py (单卡调试)
                │
                ↓
            [Worker 层]  vllm/v1/worker/
            ├ gpu_worker.py : Worker (每张 GPU 一个)
            ├ gpu_model_runner.py : GPUModelRunner (前向+采样核心)
            ├ block_table.py : 块表
            └ ubatching.py : 微批 (micro-batch)
                │
                ↓
            [注意力]  vllm/v1/attention/
            ├ backend.py : AttentionBackend (抽象)
            ├ backends/ : flash_attn / flashinfer / triton / flex_attention / mla ...
            └ ops/paged_attn.py : PagedAttention kernel
```

## 模块速查表

### 入口层 `vllm/entrypoints/`

| 路径 | 关键类/文件 | 作用 |
|------|-------------|------|
| `llm.py` | `class LLM` | 离线/进程内 Python API，`generate()`/`chat()` |
| `openai/api_server.py` | — | OpenAI 兼容 HTTP 服务（FastAPI） |
| `openai/engine/` | — | 异步引擎封装 |
| `openai/serving_*` | — | chat/completion/embeddings 等路由 |
| `openai/cli_args.py` | — | `vllm serve` 的命令行参数定义 |
| `openai/responses/`、`chat_completion/` | — | Responses / ChatCompletion 协议实现 |
| `sampler/` | — | 采样参数解析 |

### 引擎层 `vllm/v1/engine/`

| 文件 | 关键类 | 作用 |
|------|--------|------|
| `llm_engine.py` | `LLMEngine` | 主进程里的引擎门面：`add_request` / `step` / `from_engine_args` |
| `core.py` | `EngineCore`、`EngineCoreProc` | 真正跑在后台进程的核心循环（ZMQ 包裹） |
| `core_client.py` | `InprocClient` / `MPClient` / `AsyncMPClient` | 主进程↔核心进程通信（进程内 / 多进程 / 异步） |
| `async_llm.py` | `AsyncLLMEngine` | 异步引擎封装 |
| `detokenizer.py` | `Detokenizer` | 增量 detokenize |
| `output_processor.py` | — | 输出后处理（logprobs、流式） |
| `input_processor.py` | — | 请求输入预处理 |

### 调度与 KV 管理 `vllm/v1/core/`

| 文件 | 关键类/方法 | 作用 |
|------|-------------|------|
| `sched/scheduler.py` | `Scheduler.schedule()` | 统一调度（无显式 prefill/decode 阶段，靠 `num_computed_tokens` vs `num_tokens_with_spec`）；含 chunked prefill、前缀缓存、推测解码、抢占 |
| `kv_cache_manager.py` | `KVCacheManager` | `get_computed_blocks`(前缀命中)、`allocate_slots`、`free`、`evict_blocks` |
| `block_pool.py` | `BlockPool`、`BlockHashToBlockMap` | 物理块池 + 哈希查前缀 + 引用计数实现 CoW |
| `kv_cache_coordinator.py` | — | 多 KV Cache 组（如 Mamba/注意力混合）协调 |
| `kv_cache_utils.py` | — | block 大小、对齐等工具 |
| `encoder_cache_manager.py` | — | 多模态 encoder 的 KV 缓存 |

### 执行器 `vllm/v1/executor/`

| 文件 | 关键类 | 作用 |
|------|--------|------|
| `abstract.py` | `Executor` | 执行器抽象 |
| `multiproc_executor.py` | `MultiprocExecutor`、`WorkerProc` | 单机多卡：每卡一个 Worker 进程 |
| `ray_executor.py` | `RayDistributedExecutor` | 多机分布式（Ray） |
| `uniproc_executor.py` | — | 单进程（调试用） |

### Worker 与模型执行 `vllm/v1/worker/`

| 文件 | 关键类 | 作用 |
|------|--------|------|
| `gpu_worker.py` | `Worker` | 单 GPU worker，持有模型、KV、注意力 |
| `gpu_model_runner.py` | `GPUModelRunner` | **核心**：把 batch 喂给模型、构建注意力元数据、采样 |
| `block_table.py` | — | 逻辑块→物理块映射（PagedAttention 的块表） |
| `gpu_input_batch.py` | — | 当前步的输入批 |
| `ubatching.py` | — | micro-batching（细粒度批处理） |
| `cpu_worker.py` / `xpu_worker.py` / `tpu_*` | — | 其他硬件后端 |

### 注意力 `vllm/v1/attention/`

| 文件 | 关键类 | 作用 |
|------|--------|------|
| `backend.py` | `AttentionBackend` | 后端抽象：`get_name`/`get_kv_cache_shape`/`supports_block_size` 等 |
| `selector.py` | — | 按硬件/参数选择后端 |
| `backends/` | `flash_attn.py`、`flashinfer.py`、`triton_attn.py`、`flex_attention.py`、`mla/` … | 具体 kernel 后端 |
| `ops/paged_attn.py` | `PagedAttention` | PagedAttention 核心 kernel（split/write KV cache） |
| `ops/chunked_prefill_paged_decode.py` | — | 分块 prefill + paged decode 融合 kernel |

### 配置 `vllm/config/`（已拆分多文件）

| 文件 | 关键类 | 作用 |
|------|--------|------|
| `vllm.py` | `VllmConfig` | 总配置聚合体 |
| `model.py` | `ModelConfig` | 模型路径、dtype、max_model_len |
| `cache.py` | `CacheConfig` | `gpu_memory_utilization`、`block_size`、`enable_prefix_caching`、`kv_cache_dtype` |
| `parallel.py` | `ParallelConfig` | `tensor_parallel_size`、`pipeline_parallel_size`、`distributed_executor_backend` |
| `scheduler.py` | `SchedulerConfig` | `max_num_seqs`、`max_num_batched_tokens`、`enable_chunked_prefill` |
| `speculative.py` | `SpeculativeConfig` | 推测解码（`num_speculative_tokens`、draft 模型） |
| `quantization.py` | `QuantizationConfig` | 量化方法 |
| `lora.py` | `LoRAConfig` | LoRA 适配 |

### 特性模块

| 能力 | 路径 |
|------|------|
| 推测解码 | `vllm/v1/spec_decode/`（eagle / medusa / ngram / draft_model / dynamic/） |
| 结构化输出（约束解码） | `vllm/v1/structured_output/`（xgrammar / outlines / lm_format_enforcer 后端） |
| 量化 | `vllm/model_executor/layers/quantization/`（fp8 / awq / gptq(auto_gptq) / fbgemm_fp8 / mxfp4 / torchao / kv_cache / …） |
| LoRA | `vllm/lora/` |
| 多模态 | `vllm/multimodal/`、worker 的 encoder 缓存 |
| 分布式 | `vllm/distributed/`（通信原语、并行组） |
| 模型定义 | `vllm/model_executor/models/`（各 HuggingFace 模型的实现） |
| 平台抽象 | `vllm/platforms/`（`current_platform`，CUDA/XPU/CPU/TPU/ROCm） |

## 快速回查技巧

```bash
# 仓库根
cd Q:/AI/vllm/vllm

# 找类定义
grep -rnE "^class Scheduler" vllm/v1/core/sched/scheduler.py

# 找 PagedAttention kernel
grep -rn "class PagedAttention" vllm/v1/attention/

# 找某配置项默认值
grep -n "enable_chunked_prefill" vllm/config/scheduler.py

# 找 spec decode 支持的方法
ls vllm/v1/spec_decode/
```

## 延伸

- → [[entities/vllm|vLLM 推理引擎]] — 概念总览与 V1 架构
- → [[concepts/PagedAttention|PagedAttention]] — KV 分页的核心算法与实现
- → [[concepts/LLM 推理 优化]] — 推理优化总论
- → [[concepts/分布式推理]] — TP/PP/EP 并行

---

**参考来源**：本地仓库 `Q:/AI/vllm/vllm`（已 checkout，含 `vllm/vllm/v1/` V1 架构）
**最后更新**：2026-08-18
**维护者**：CodeBuddy
**状态**：活跃维护中
