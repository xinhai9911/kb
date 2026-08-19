---
title: SGLang 深度解析
tags: [llm, inference-engine, sglang, radixattention, scheduling, gpu, api, deep-dive]
created: 2026-08-19
updated: 2026-08-19
lifecycle: active
category: sources
base_confidence: 0.82
summary: >-
  从架构到源码逻辑深度解析 SGLang：前后端分层、Scheduler 连续批处理与 cache-aware 调度、
  RadixAttention 基数树 KV 缓存、页式 MemoryPool、flashinfer/MLA/CUDA Graph 等 GPU 侧实现、
  分离式 Prefill/Decode，以及 OpenAI 兼容与 /generate 等对外接口。
---

# SGLang 深度解析

> **一句话**：SGLang = 「结构化生成语言（DSL）+ RadixAttention 基数树前缀复用 + 分裂式 Prefill/Decode」，把 LLM 推理当"程序调度"来做，追求编程友好与极致效率。
> 本文基于 SGLang 公开架构设计与源码模块（`python/sglang/srt/`）整理，面向 [[entities/sglang|SGLang 实体页]] 的深度展开。

## 1. 定位与总体架构

### 1.1 定位

| 维度 | 说明 |
|------|------|
| **项目** | `sgl-project/sglang`（Apache 2.0） |
| **核心思想** | 把一次 LLM 请求（甚至一个 Agent/多轮/分支流程）看作**结构化程序**，在引擎内做前缀复用与统一调度 |
| **核心创新** | RadixAttention（基数树前缀缓存）、结构化生成（JSON/正则约束解码）、分裂式 Prefill/Decode |
| **语言** | Python（控制面）+ C++/CUDA（数据面 kernel） |
| **最佳场景** | 高前缀复用工作负载（system prompt 很长 / 多轮对话 / Agent / 树搜索）、DeepSeek V3/R1（官方推荐栈） |

### 1.2 前后端分层

SGLang 把 "SGLang 后端（System for Language Models，`srt`）" 单列为一个工程 `python/sglang/srt/`，与面向用户的 DSL 前端（`sglang` 包）解耦：

```
┌───────────────────────────────────────────────────────────────┐
│  Frontend（DSL 前端，面向开发者）                                │
│  sgl.function 装饰器 / sgl.gen / sgl.user / sgl.assistant      │
│  JSON Schema / regex / grammar 约束 + 分支（LlamaIndex 集成）    │
└───────────────────────────┬───────────────────────────────────┘
                            │ Http / 进程内调用
┌───────────────────────────┴───────────────────────────────────┐
│  Runtime（python/sglang/srt/）                                  │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────────┐  │
│  │ Tokenizer     │  │  Scheduler    │  │  Detokenizer      │  │
│  │ Manager       │→ │  (连续批处理+  │  │  Manager          │  │
│  │ (多请求 token  │  │   RadixCache) │  │  (批量增量解码)    │  │
│  │ 化)           │  └──────┬────────┘  └───────────────────┘  │
│  └───────────────┘         │ schedule / forward 调用           │
│                     ┌──────┴────────┐                          │
│                     │ ModelRunner   │  ┌─────────────┐         │
│                     │ (GPU 前向+采样) │→│ ModelTpCaLayer│→ kernel│
│                     │ MemoryPool    │  └─────────────┘         │
│                     │ (页式 KV 池)   │  flashinfer / FA / MLA   │
│                     └───────────────┘                          │
└───────────────────────────────────────────────────────────────┘
```

### 1.3 一次请求的完整流转

```
client (curl / openai sdk) 
   │  POST /generate 或 /v1/chat/completions
   ▼
SGLang Runtime 主进程（服务器）
   1. 前端 HTTP 路由 → 构造 GenerationReq
   2. TokenizerManager.process_request_async：
        对每个请求异步 tokenize，落成 input_token_ids
   3. scheduler.add_request：请求进入 PriorityQueue（二级优先级队列）
   │
   ▼ 主调度循环（后台 while-Task，每 ~几 ms 一次）
   Scheduler.schedule()：
     ├─ decode 阶段：继续推进 running 队列中每个请求（每步 1 token / 或 spec token）
     ├─ 若 token 预算有空闲：从 waiting 队列按优先级/缓存命中取 prefill（可分块）
     └─ 产出本轮 ForwardBatch
   ▼
   ModelRunner.forward(fwd_batch)：
     ├─ 复用/重填 CUDA Graph 捕获的输入张量（decode），或执行 prefill 前向
     ├─ 注意：先算 attention（FlashInfer/FA/MLA kernel），再采样
     └─ 每个请求得到 >=1 个新 token，写入 KV cache（页式 MemoryPool + RadixCache 登记）
   ▼
   scheduler 记录输出 token、检查停止/stream 条件
   DetokenizerManager.process_batch_result：批量增量 detokenize（可流式发回前端）
   ▼
   HTTP 流式/一次性响应返回 client
```

> 关键点：**调度与解 token 化都在"批"层面做**——多个请求的 tokenize/detokenize 合并成 batch 调用，避免每请求 Python 循环开销。

## 2. 核心组件详解

### 2.1 Scheduler（调度器）

`python/sglang/srt/managers/scheduler.py`。职责：维护所有存活请求的状态机、做**统一 forward 决策**（每轮 forward 该跑哪些请求、每个请求处理多少 token）、生成 `ScheduleBatch`。

**与 vLLM V1 的"无阶段调度"理念一致**：SGLang 的调度器也不区分显式 prefill / decode 阶段，而是把请求分成几类 forward：

| 类别 | 含义 | 每轮做的计算 |
|------|------|--------------|
| **decode forward** | running 中的请求继续自回归 | 每请求生成 1 个 token（或 spec 多条） |
| **prefill（extend）forward** | 新请求首次计算 prompt | 一次处理整个 prompt；过长时分块（`chunked_prefill_size`） |
| **idle / fill** | 本轮无实际计算，仅"填坑" | 给 CUDA Graph 的固定 shape 填充 padding |
| **杀/拦状态** | 完成后清理 | 释放 KV、归还 tokenizer 状态 |

关键计数与预算：

- `token_budget`：本轮最多喂给 GPU 多少 token，受 `--max-running-requests`（并发上限）、batch 与显存预算共同约束（SGLang 没有 vLLM 那种单一 `max_num_batched_tokens` 旗标，而是用"running 请求数 + prefill chunk"间接控制）。
- 每轮先跑 **decode forward**（running 请求），token_budget 有余量再 **prefill waiting 中的请求**。这样 decode 延迟不会一直被长 prefill 挤掉（类似 vLLM 的 chunked prefill 效果）。
- 超过预算时，新请求继续留在 waiting，下一轮再进。

**排序与优先级**：waiting 队列用 **PriorityQueue**（可启动 `--schedule-policy lpm`（least prompt 优先/最短 prompt 优先）等策略；默认按到达顺序）。长 prompt 的大请求不会无限挤占短请求的 TTFT。

**cache-aware 调度**：RadixAttention 的价值体现在调度器——等待请求在**命中前缀缓存**时，前缀部分**不重新计算**，只需为剩余 prompt 做增量 prefill。SGLang 会优先调度缓存命中率高的请求（提高整体有效吞吐）；这是与 vLLM 前缀缓存调度混排的重要差异点。

### 2.2 RadixAttention / RadixCache（基数树前缀缓存）

#### 设计动机

vLLM 的 Prefix Caching 是"**块级哈希精确匹配**"；SGLang 更进一步，把**所有请求的 KV 片段组织成一棵前缀树（基数树，Radix Tree）**，节点按 token 序列共享前缀，天然支持：

- **最长公共前缀命中**（一个请求的前缀命中了多个历史请求拼出的公共前缀）；
- **LRU 淘汰**（内存不够时从树上剪掉最不常用的**叶子分支**）；
- **Copy-on-Write**（树搜索/并行采样时多个序列共享同一段前缀，只在分叉点写入）。

#### 数据结构

```
                        ┌──── root ────┐
   共用 system prompt   │   "你是助手"  │ (len=1000, 被 2 个 child 共享)
                        │   ┌──────┴──────────┐
                        │   │                 │
                 "什么是AI?"            "什么是ML?"
                   (len=40)              (len=40)
                        │                 │
                     KV 片段可被后续请求直接复用(Cache Hit)
```

- 每个节点：一段 token 序列（或 page key 哈希）、被引用的计数 `ref_cnt`、children、`last_access_time`（LRU）。
- 命中时沿树走到最深匹配节点，把该节点下缀的 KV 块"接入"请求的块表，命中部分 `ref_cnt+=1`（类似 vLLM 的共享块）；未命中部分分配新页、算完 KV 后挂到树上。
- 淘汰：全局维护 **LRU 驱逐器**；当需要新 KV 页而池已满，按 `last_access_time` 从**叶子**逐出（仅 `ref_cnt==0` 的节点可驱逐）。
- 实现上既有"token 序列匹配"的原始版本，也有**按页哈希（page/key hash）匹配**、可并行/增量插入的现代版本——后者让前缀匹配更快、并天然支持跨多请求共享。

#### 与 vLLM Prefix Caching 的对比

| 维度 | SGLang RadixAttention | vLLM Prefix Caching |
|------|----------------------|---------------------|
| 组织方式 | 基数树（树） | 哈希表 + LRU（表） |
| 匹配粒度 | token / 页级任意前缀 | 块级（block_size=16 token） |
| 淘汰 | 叶子优先 + LRU | 全块 LRU |
| 共享 | 树路径天然共享（含多分支） | CoW 块共享 |
| 适用 | 多轮/Agent/树长尾前缀 | 固定长 system prompt |
| 实现代价 | 树维护略复杂 | 简单、工程成熟 |

### 2.3 MemoryPool（页式 KV 池）

SGLang 的 KV Cache 按**页（page/block）**管理（`python/sglang/srt/mem_cache/memory_pool.py`），类似 OS 分页：

- 每个页装固定数量 token 的 Key/Value（页大小可配置，常见为 16 量级的 token/页；不同后端/模型默认不同）。
- 页池预分配在 GPU 显存（H100/H200 也可为 KV cache 单独用 FP8 存储，见 §5）。
- 每个序列维护一张页表；RadixCache 的"前缀命中"本质是把命中部分的**已存在页**直接接到请求页表之后。
- 页分配失败 → 触发 RadixCache 驱逐释放内存 → 不够则本轮不调度新请求。

### 2.4 TokenizerManager / DetokenizerManager

- **TokenizerManager**：把「多个前端可能同时请求 tokenize」的并发请求**批量** tokenize（进程池 / 异步），并缓存分词结果（`input_token_ids`），避免每个请求各自开一次分词。
- **DetokenizerManager**：把「每轮 decode 产生的所有输出 token」**批量增量 detokenize**——只翻译新增 token 的文本片段，支持流式（每轮把新增的 delta 文本推给 HTTP 流），避免把整个输出反复重译。

### 2.5 ModelRunner / ModelTpCaLayer

- `ModelRunner`（`python/sglang/srt/model_executor/model_runner.py`）：组装 ForwardBatch → 调模型前向 → 采样。管理 CUDA Graph 捕获、多 stream、dtype/量化。
- `ModelTpCaLayer`：Tensor Parallel 下的模型层封装。分布式场景下用 `DistributedModelRunner`：多进程多卡，每个 rank 持有切片后的模型 + 全局调度器只在 master rank 跑。
- 采样：支持 `temperature / top_p / top_k / min_p`、`repetition_penalty`、`frequency_presence_penalty`、`stop` 词、logprobs、beam search（并行分支共享前缀）。

### 2.6 结构化输出后端

SGLang 原生把"程序生成"做成第一公民：`sgl.gen(..., regex=...) / json_schema=... / grammar=...` 或 OpenAI 请求体里带 `structured_outputs`。运行时经 **约束解码后端**（先后有 `outlines`、自研 `svGrammar`/`xgrammar`——现代版本默认 **XGrammar**）为当前已生成前缀构造**合法字符集合掩码**，在采样时抑制非法 token：
- 并行采样同一步中，把掩码应用成 `logits_mask`（logits 足够大时 1.5%-3% 性能损失；掩码计算有缓存，命中率高时开销近零）。

## 3. 内部调度详解（重点）

### 3.1 统一 forward 决策

每轮 `Scheduler.schedule()` 的核心伪代码：

```
schedule():
  1) token_budget = 本步上限（受并发 running 数、batch 与显存预算约束）
  2) running = [r for r in running]
  3) #—— decode 优先 ——
     for req in running:
        if token_budget <= 0: break
        req.new_token_ids = predict(req)   # 1 token，若 spec decode 则 k 个草稿
        token_budget -= spec_len 或 1
        if req 到达停止条件: 移入 finished 列表
  4) #—— prefill 填空隙 ——
     while waiting 非空 and token_budget > 0:
        req = pop_next(waiting)            # 按优先级队列
        hit_len = radix_cache.prefix_match(req)      # 前缀命中长度
        if 剩余 tokens > chunk_prefill_size: req 只算一个 chunk
        if 预算够: 调度该 chunk；否则放回 waiting
  5) 产出一个 ForwardBatch：
     - input_ids, positions, seq_lens, req_pool_indices, ...
  6) 让模型跑一次 forward（见 §4）
```

- **decode 与 prefill 混排**：长 decode batch 中插入短 prefill chunk，避免 TTFT 被 decode 完全阻塞；反过来 decode 请求的延迟也被持续保证。
- **停止/流式**：`update_outputs` 检查 EOS / stop 串 / max_new_tokens → 完成态 → 释放 KV → 通知 Detokenizer 输出。

### 3.2 Cache-aware 调度与抢占

- SGLang 对 prefetch/缓存命中做了调度层面的优化：优先把能命中 RadixCache 前缀的请求排进本轮（命中部分零计算）。
- 显存吃紧时**抢占（preemption）**：vLLM V1 为"直接释放 KV、重新计算"；SGLang 更灵活——由于 RadixCache 中保留已算 KV 块并带引用计数，被抢占请求的前缀 KV 通常仍可复用，重新 prefill 只需算新的一部分。实际实现上简单粗暴地把整请求返回 waiting、清理其 KV 引用（但若前缀被其他请求共享则 `ref_cnt>0` 不真释放）。

> 经验：SGLang 在**高前缀复用**（长 system prompt + 多用户并发）+ **长上下文**场景下优势明显；在零复用、短 prompt、超高并发通用负载上与 vLLM 差距很小。RadixCache 默认开启，可用 `--disable-radix-cache` 关闭做对比（对应 vLLM 的 `--enable-prefix-caching` 开关语义）。

### 3.3 Speculative Decoding（推测解码）

SGLang 内置推测解码，且与 RadixCache 协同：
- **自举/单模型**：EAGLE（自回归草稿头）、Medusa（并行头）、NPC、Lookahead/n-gram、TyD（"你拥有的草稿"）。
- 调度层：dump 草稿 token 到广播前缀匹配；验证时一次性前向已验证 token，可接受多个草稿 → **每步产出多 token**（显著提 decode 步速度）。
- 关键指标：`spec stable acceptance rate`、`spec working accept rate`（监控日志里可见）。

### 3.4 Tree-of-Thought / 并行分支

DSL 支持 `sgl.gen(name, n=分支数)` 或 `fork`：多个分支共享同一前缀 KV（树上并行走），用 CoW 避免复制；展开/合并逻辑由 engine 统一调度，把"一个流程"当一棵树跑，分支间前缀在树上天然共享。这是面向 Agent 与推理-time 计算（如 beam search、ToT）的关键能力。

## 4. 内存管理详解（重点）

### 4.1 KV Cache 页式分配 与 容量规划

- 显存预算：`可用显存 = gpu_memory_utilization × 单卡总显存 × tp_size`（SGLang 以 `--mem-fraction-static` 表达，"静态"指权重+KV 的固定份额，默认约 0.88，随版本浮动）；分给权重（含激活）、KV Cache 页池、CUDA Graph 捕获缓存（`--cuda-graph-max-bs`）、推理临时 buffer 与采样 buffer。
- KV Cache 页池大小 = 静态份额 − 权重 − 激活余量，超出后由 RadixCache 驱逐调度兜底。
- FP8 KV Cache：`--kv-cache-dtype fp8` 直接把 KV 存成 FP8（half 精度减半），DeepSeek 系列配合 W8A8 权重获得显著容量提升。

### 4.2 RadixCache 的引用计数、驱逐与重算

- 每个 KV 页都有引用计数；`ref_cnt==0` 的页才是"可驱逐候选"。
- LRU 驱逐只剪**叶子**节点（避免破坏共享前缀），剪掉后用 `chunk` 记录（token 仍以 `input_token_ids` 保留在请求侧），未来若再命中，是重新计算 KV 而非恢复——即**缓存淘汰后丢失的是 KV，不丢失 prompt**。
- 由于是树，跨请求的"部分共享"（两个请求共享前 2000 token、后面不同）天然高效；这也让多轮对话、Agent 的 tool-use 流水线极省算力。

### 4.3 激活与临时内存

- decode 阶段激活量小（逐 token），prefill 阶段激活量随 `max_new_token / seq_len` 增长；SGLang 用 chunked prefill 控制 peak activation（`--chunked-prefill-size`）。
- 长上下文（如推理时 100K+ token 的 prefill）使用 `--max-prefill-tokens` / `--long-prefill-chunk-size` 分裂式 chunk，防止单次 forward 激活 OOM。

### 4.4 多模态内存

- vision 等模态的 encoder 输出作为隐藏层 token 并入序列，参与 RadixCache 前缀匹配（图像 token 序列也按 token 匹配），实现"同一张图的多轮追问只算一遍 vision encoder"。

## 5. GPU 层详解（重点）

### 5.1 注意力 kernel & 后端

- SGLang 深度绑定 **FlashInfer**（早期）+ 自研 **sgl-kernel** / FlashAttention：两者都覆盖 paged KV cache、任意前缀、变长序列。
- **MLA（Multi-head Latent Attention）**：为 DeepSeek-V2/V3/R1 专门写了融合 kernel（`sgl-kernel` 的 mla 实现），把 MLA 的潜向量绑定、KV 下采样做进单 kernel；FP8(W8A8) 或 FP8 KV 都有专门路径，是开源引擎里对 DeepSeek 优化最深的（DeepSeek 官方因此推荐 SGLang）。
- 结构化输出掩码计算、`fused_add_rms_norm/rotary` 等算子也在同仓库 kernel 层提供。

### 5.2 CUDA Graph 捕获与重填（关键优化）

- SGLang 与 vLLM 一样用 **CUDA Graph** 把"模型前向"这一整串 kernel 固定在几个静态内存地址上，避免每次 launch 的 Python/CPU 开销（decode 吞吐可提升 1.5-3 倍）。
- 关键技巧：**graph 复用** —— SGLang 为常用 batch size 预捕获一组图；运行中 batch 变化时，把新请求"填入"现有图的固定 tensor（`ForwardBatch` 复用 input 槽位），而不是重放整套图。这是它与朴素 CUDA Graph 实现的差异点，也是"为什么 SGLang decode 的 shape 变化开销低"的原因。
- 可由 `--disable-cuda-graph` 关闭（用于调参对比）；`--cuda-graph-max-bs` 决定捕获的 batch 档位上限。

### 5.3 分布式并行

| 并行类型 | 作用 | SGLang 相关参数 |
|----------|------|------------------|
| **Tensor Parallel (TP)** | 单模型切层多卡 | `--tp-size` |
| **Expert Parallel (EP)** | MoE 专家分散多卡 | `--ep-size` |
| **Data Parallel (DP)** | 多调度器副本分摊请求 | `--data-parallel-size` |
| **分离式 Prefill/Decode (PD)** | prefill 与 decode 各占一台/组 | `--is-prefill` / `--is-decode`（及 `SGLANG_PD_SERVER_MODE` 环境变量） |

- **DP**：请求被 router 按哈希/轮询分到不同 scheduler（每 scheduler 独占自己的 RadixCache）→ QPS 高时避免单调度器成为瓶颈；代价是跨副本前缀不复用。
- **分离式 P/D**（DeepSeek 官方建议的部署形态）：prefill 实例专门吃 prompt、产出 KV，把 **KV Cache（含 MLA）通过高速互联/网络**（如 ZeroScatter/NCCL 或 TCP）传给 decode 实例，decode 实例只做自回归。好处：TTFT 稳、decode 吞吐高、两类工作负载互不干扰；代价：KV 传输带宽、跨机调度复杂度。

### 5.4 多机与组网

- 启动：`python -m sglang.launch_server --host 0.0.0.0 --port 30000 --tp-size 8 --nnodes 2 --dist-init-addr <主节点ip:port>`。
- 通信：master 调度进程 + 每 rank worker 进程；sample 回报/NCCL allreduce 用于采样一致、TP/EP 通信走 NCCL/RCCL、KV 传输可走共享内存/ZeroMQ/NCCL。
- 环境变量族：`SGLANG_*`（如 `SGLANG_ENABLE_*`）控制开启项；`--log-level` 控制可见性。

## 6. 对外接口（重点）

### 6.1 启动与两种入口

```bash
# 服务器（OpenAI 兼容 + 原生接口）
python -m sglang.launch_server \
    --model-path deepseek-ai/DeepSeek-V3 \
    --tp-size 8 --port 30000 \
    --kv-cache-dtype fp8 --quantization fp8

# 离线/程序化运行（无需起服务）
python -m sglang.run_batch --model-path meta-llama/Llama-3-8B \
    --data-path ./requests.jsonl --tp-size 1
# 或 DSL：
from sglang import function, gen, user, assistant, Runtime
```

### 6.2 OpenAI 兼容端点

| 端点 | 作用 |
|------|------|
| `POST /v1/chat/completions` | 对话补全（`messages` + `max_tokens`，`stream=True` 支持 SSE） |
| `POST /v1/completions` | 文本补全 |
| `POST /v1/models` | 列出已加载模型 |
| `GET /health` | 存活探针 |
| `GET /metrics` | Prometheus 指标 |

支持请求体内的采样/约束：`temperature / top_p / top_k / min_p / stop / logprobs / max_tokens / n`、`json_schema`、`regex`、`grammar`。客户端可直接用 `openai` SDK 或任意 OpenAI 兼容客户端。

### 6.3 原生扩展接口（SGLang 特色）

| 端点 | 说明 |
|------|------|
| `POST /generate` | 通用生成（`input_ids` / `prompt` + 采样参数 + `return_logprob`） |
| `POST /classify` | 文本分类（`logits` 向量打分） |
| `POST /encode` | 词向量生成（`dense_embed`） |
| `/v1/embeddings` | Embedding（OpenAI 风格） |
| `POST /rerank` | 重排（`query` + `documents` → 相关性分数） |
| `POST /v1/score` | 打分（新派生的任务接口） |
| `/v1/loas` 系列 | LoRA 适配器管理（若启用 `--lora-paths`） |
| `POST /tokenize` / `/detokenize` | 分词往返 |

> 注意：端点集合随版本演进（派生/分类/打分任务逐步统一到 `tasks` 路由），以版本文档为准；上面的 `/generate`、`/classify`、`/encode` 是 SGLang 早期就有的长稳接口。

### 6.4 流式（Streaming）

```bash
curl http://localhost:30000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"m","messages":[{"role":"user","content":"讲个笑话"}],
       "stream":true,"max_tokens":64}'
```
- 返回 `data:` SSE 帧，每帧一个 delta chunk（由 DetokenizerManager 批-增量生成）。
- 可用 `--log-level info` 观察 scheduler 日志：每步打印 `token: pref? decode` 进度。

### 6.5 DSL 前端（sgl 语言）示例

```python
import sglang as sgl

@sgl.function
def multi_tool_agent(s, query):
    s += sgl.system("你是助手，会使用工具。")
    s += sgl.user(query)
    # 第一次生成：结构化 JSON 动作（约束解码保证合法 JSON）
    s += sgl.assistant(
        sgl.gen("action",
                json_schema={
                    "type": "object",
                    "properties": {"tool": {"type": "string"},
                                   "args": {"type": "object"}},
                    "required": ["tool", "args"]}))
    # 用第一次结果追问第二轮：前缀会被 RadixCache 复用
    s += sgl.user("基于动作结果继续回答。" + s["action"])
    s += sgl.assistant(sgl.gen("final", max_tokens=128))

# 离线跑
runtime = sgl.Runtime(model_path="meta-llama/Llama-3-8B-Instruct")
sgl.set_default_backend(runtime)
state = multi_tool_agent.run(query="上海明天天气？")
print(state["action"], state["final"])
```

## 7. 性能特征与典型配置

| 主要调参项 | 作用 | 建议 |
|-----------|------|------|
| `--tp-size` / `--tp` | 张量并行 | 模型卡内存不够/inference 调大 |
| `--mem-fraction-static` | 静态显存用于权重+KV 比例 | 默认 ~0.88；调到 0.9+ 需防 OOM |
| `--kv-cache-dtype fp8` | KV 减半 | H100/H200、DeepSeek 系列强烈推荐 |
| `--cuda-graph-max-bs` | CUDA Graph 捕获 batch 档位上限 | 对齐并发期望值（如 256） |
| `--chunked-prefill-size` | 长 prompt 分块 | 长上下文/RAG 大 influx 时调小 |
| `--schedule-policy` | waiting 队列排序 | 短请求优先（lpm）降 TTFT |
| `--disable-cuda-graph` | 关图 | 仅调试/对比用 |

DeepSeek V3/R1 参考（官方推荐路径）：

```bash
python -m sglang.launch_server \
  --model deepseek-ai/DeepSeek-V3 \
  --tp 8 --trust-remote-code \
  --kv-cache-dtype fp8 --quantization fp8 \
  --attention-backend flashattn \
  --cuda-graph-max-bs 256 --enable-torch-compile
```

## 8. 与 vLLM 深度对比

| 维度 | SGLang | vLLM |
|------|--------|------|
| 前缀复用 | Radix Tree（任意前缀/树/LRU 叶子淘汰） | Block 哈希 + LRU（块粒度精确匹配） |
| 调度模型 | decode 优先 + 缝隙 prefill，PriorityQueue | V1 统一 token budget，Running/Waiting |
| CUDA Graph | 固定 batch 图 + 填坑复用 | V1 多档图 + 复用 |
| 结构化输出 | 第一公民（XGrammar，DSL/OpenAI 均支持） | Guided Decoding（xgrammar/outlines/LMFE） |
| 分离式 P/D | 原生（prefill/decode 分置 + KV 传输） | 支持（NIXL 等，较新） |
| DeepSeek 支持 | 官方推荐、MLA 融合 kernel、FP8 全链路 | 支持良好但非官方首选 |
| 模型覆盖面 | 广 | 最广 |
| 生态/工程 | 较新、演进快 | 最成熟、部署最广 |
| 最佳场景 | Agent/多轮/树搜索/DeepSeek/长上下文 | 通用生产服务、超高并发 |

## 9. 已知权衡与注意事项

- RadixCache 的树维护有 CPU 开销；**前缀复用率极低**时不如简单哈希（这正是 vLLM 默认关闭 prefix caching 的历史原因）。评估负载时可用 `--disable-radix-cache` 做 A/B。
- DP 扩容时每副本各自独立缓存，前缀复用在副本间失效；用哈希路由可让同一发送方落同一副本。
- 版本演进快，参数名（`--tp-size` vs `--tp`、`--kv-cache-dtype` vs `--quantization`）与端点集合请以对应版本文档为准。
- Web/文档访问在本环境不可用：本文架构性结论依据 SGLang 稳定公开设计；特定版本号/参数请自核 `sglang --help`。

## 参考

- [SGLang 官方文档](https://docs.sglang.ai/)
- [SGLang GitHub](https://github.com/sgl-project/sglang)（`python/sglang/srt/`）
- [SGLang: Efficient Execution of Structured Language Model Programs, arXiv 2312.07104](https://arxiv.org/abs/2312.07104)

---

## 📚 相关笔记

- [[entities/sglang|SGLang 实体页]] — 概览与快速参考
- [[entities/vllm|vLLM]]、[[sources/vLLM-Deep-Dive|vLLM 深度解析]] — 对比引擎
- [[sources/LLMForEverybody/02-第二章-部署与推理/大模型推理框架（六）SGLang|大模型推理框架（六）SGLang]] — 外文转载
- [[concepts/PagedAttention|PagedAttention]] — 分页 KV 思想（对比 RadixAttention）
- [[concepts/分布式推理]] — TP/PP/EP/DP 并行
- [[concepts/LLM 推理 优化]] — 推理优化总论（前缀缓存/批处理/量化）