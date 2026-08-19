---
title: PagedAttention（分页注意力）
tags: [llm, inference, pagedattention, kv-cache, vllm, active]
lifecycle: active
category: concepts
base_confidence: 0.86
created: 2026-08-18
updated: 2026-08-18
summary: >-
  PagedAttention 是 vLLM 的核心创新：借鉴操作系统虚拟内存的分页思想，将 KV Cache
  切成固定大小的块（block）按需分配，用块表（block table）做逻辑→物理映射，
  把碎片从 40-80% 降到 <4%，并支持前缀缓存的 Copy-on-Write 共享。
---

# PagedAttention（分页注意力）

> **一句话**：用「虚拟内存分页」的方式管理 KV Cache——不预分配连续大块，而是按固定块按需分配、用块表映射，从而消灭碎片、共享前缀。

## 问题：传统 KV Cache 为何浪费

自回归解码时，每个 token 都要缓存其 Key/Value 张量（KV Cache）。朴素实现在请求开始时为**整个序列最大长度**预分配一块**连续显存**：

| 浪费来源 | 说明 |
|----------|------|
| 预留浪费 | 实际长度远小于 `max_model_len`，未用部分空占 |
| 内部碎片 | 不同请求长度不一，连续块无法复用 |
| 外部碎片 | 长短请求交替，连续空闲块被割裂 |
| 无法共享 | system prompt 等公共前缀在每个请求里各算一份 |

论文与工程实测：**40%–80% 的显存被白白浪费**。这正是 vLLM 之前 LLM 服务吞吐受限的根因。

## 核心思想：把 KV Cache 当成「虚拟内存」

PagedAttention 借鉴 OS 的分页（paging）机制：

```
传统（连续分配）               PagedAttention（分页分配）
┌────────────────────┐        ┌─────────┐ ┌─────────┐ ┌─────────┐
│ 连续 KV 块(预留满) │        │ Block 0 │ │ Block 1 │ │ Block 2 │
│ [已用][空占][空占] │   →    └────┬────┘ └────┬────┘ └────┬────┘
│                    │            物理不连续，逻辑上连续
└────────────────────┘

请求视角（逻辑块）：  Block 0 → Block 1 → Block 2 → Block 3
实际显存（物理块）：  Phys #17   Phys #3    Phys #42   Phys #8   ← 由块表映射
```

- **块（block）**：固定大小，默认 `block_size=16` 个 token 的 KV。
- **块表（block table）**：每个请求维护一张「逻辑块号 → 物理块号」的映射表（vLLM V1 实现见 `vllm/v1/worker/block_table.py`）。
- **按需分配（alloc-on-demand）**：遇到第 N 个 token 才分配第 ⌈N/16⌉ 个块，不再预留整段。
- **碎片仅剩末尾块**：最多浪费不到一个块（<4%），不再有预留与外部碎片。

## 两大关键能力

### 1. 前缀共享（Prefix Caching）+ 写时复制（Copy-on-Write）

多个请求共享同一段前缀（如相同 system prompt）时，它们的块表可以**指向同一批物理块**，Decode 阶段互不修改则一直共享；当某请求要写入已被共享的块时，才触发 **Copy-on-Write** 复制出新块。

vLLM 源码中这块由 `BlockPool` + `BlockHashToBlockMap`（`vllm/v1/core/block_pool.py`）实现：

- `BlockHashToBlockMap`：以「块内容的哈希 + group id」为键，把已算好的块缓存起来。
- `get_cached_block()` / `cache_full_blocks()`：前缀命中的块直接复用，无需重算 KV。
- CoW 通过引用计数（`KVCacheBlock.ref_cnt`）管理，写时复制、引用归零才真正释放。

`KVCacheManager`（`vllm/v1/core/kv_cache_manager.py`）负责上层编排：`get_computed_blocks()` 做前缀命中查询，`allocate_slots()` 按需分配，`free()` 回收。

### 2. 注意力计算时的「 Gather 」

因为物理块不连续，注意力 kernel 不能像连续张量那样直接寻址。PagedAttention 在每次 step 前，根据块表把分散的物理块**收集（gather）**成注意力所需的布局，再做分块注意力（paged attention）。

核心 kernel 实现：`vllm/v1/attention/ops/paged_attn.py` 的 `class PagedAttention`：

- `split_kv_cache()`：把 `[2, num_blocks, ...]` 形态的 KV 缓存拆成 key/value 两路，并按 head 维 reshape。
- `write_to_paged_cache()`：把新算出的 K/V 按 `slot_mapping`（来自块表）写入对应物理块槽位。
- 配合 `slot_mapping` / `block_table` 张量，CUDA kernel 在解码时定位每个 query 应 attend 的 KV 物理块。

## 注意力后端（Attention Backends）

PagedAttention 是「块表 + 分页 kernel」的抽象，具体的注意力计算由可插拔后端完成（V1 在 `vllm/v1/attention/backends/`）：

| 后端文件 | 说明 |
|----------|------|
| `flash_attn.py` | FlashAttention-2/3（CUDA，默认高性能路径） |
| `flashinfer.py` | FlashInfer（Triton/CTA 优化，常作备选） |
| `triton_attn.py` | 纯 Triton 实现，便于定制 |
| `flex_attention.py` | PyTorch `flex_attention` |
| `flash_attn_diffkv.py` / `triton_attn_diffkv.py` | DiffKV 变体 |
| `mla/` | 多头潜在注意力（DeepSeek MLA）专用 |
| `cpu_attn.py` / `rocm_attn.py` / `rocm_aiter_*` | CPU / ROCm 平台后端 |

后端接口由 `vllm/v1/attention/backend.py` 的 `AttentionBackend` 抽象类定义：`get_name()`、`get_kv_cache_shape()`、`get_supported_kernel_block_sizes()`、`supports_block_size()` 等，决定该后端支持哪些 block size / head size / dtype。

## 为什么它对吞吐至关重要

- **更高并发**：相同显存下能放下更多请求的 KV Cache → 并发序列数（`max_num_seqs`）显著提升。
- **连续批处理的基础**：配合 [[sources/推理引擎/LLM 推理 优化#连续批处理 Continuous Batching|连续批处理]]，新请求到来时只需分配新块，已完成请求释放块即可被他人复用。
- **前缀缓存落地的载体**：共享前缀的 KV 以「块」为粒度缓存，命中即跳过 prefill 计算。

## 源码导读（本地 `Q:/AI/vllm/vllm`）

| 关注点 | 文件 |
|--------|------|
| PagedAttention kernel | `vllm/v1/attention/ops/paged_attn.py` |
| 分块 prefill + paged decode kernel | `vllm/v1/attention/ops/chunked_prefill_paged_decode.py` |
| 块表（逻辑→物理映射） | `vllm/v1/worker/block_table.py` |
| KV 块分配/释放/前缀命中 | `vllm/v1/core/kv_cache_manager.py` |
| 块池 + 前缀哈希缓存 + CoW | `vllm/v1/core/block_pool.py` |
| 注意力后端抽象与选择 | `vllm/v1/attention/backend.py`、`selector.py`、`backends/` |
| 整体引擎中的调用点 | `vllm/v1/worker/gpu_model_runner.py`（`_build_attention_metadata`、`_prepare_inputs`） |

详见 [[sources/推理引擎/vLLM 源码 导读|vLLM 源码导读]] 与实体页 [[sources/推理引擎/vllm|vLLM 推理引擎]]。

## 延伸

- → [[sources/推理引擎/vllm|vLLM 推理引擎]] — PagedAttention 的承载引擎与 V1 架构
- → [[sources/推理引擎/LLM 推理 优化]] — 推理优化总论（KV Cache、批处理、量化）
- → [[sources/推理引擎/分布式推理]] — 多 GPU 下 KV Cache 的并行与传输
- → [[sources/推理引擎/推测解码]] — 草稿 token 与块表的协同

---

**参考来源**：
- [PagedAttention 论文 (vLLM, arXiv 2309.06180)](https://arxiv.org/abs/2309.06180)
- [vLLM 官方文档：PagedAttention](https://docs.vllm.ai/)
- 本地源码 `Q:/AI/vllm/vllm/vllm/v1/attention/ops/paged_attn.py`、`vllm/v1/core/block_pool.py`

**最后更新**：2026-08-18
**维护者**：CodeBuddy
**状态**：活跃维护中
