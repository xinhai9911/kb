---
title: vLLM 深度解析
tags: [llm, inference-engine, vllm, pagedattention, architecture, deep-dive]
created: 2026-08-18
updated: 2026-08-18
summary: >-
  基于 vLLM 源码（Q:\AI\vllm\vllm）和官方文档，深度解析 vLLM V1 引擎架构、
  PagedAttention、Continuous Batching、Prefix Caching、Disaggregated P/D 等核心技术。
---

# vLLM 深度解析

> 本文基于 vLLM 最新源码（2025-09 分支）和官方博客，从架构设计到源码实现，系统性地解析 vLLM 的核心技术。

## 1. 总体架构

vLLM V1 引擎采用**多进程、分层架构**，将 API 服务与 GPU 执行分离：

```
┌─────────────────────────────────────────────────────────┐
│                    Client API Layer                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │   LLM    │  │ AsyncLLM │  │ OpenAI   │              │
│  │ (Sync)   │  │ (Async)  │  │  Server  │              │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘              │
│       │              │              │                    │
│       └──────────────┼──────────────┘                    │
│                      │ ZMQ IPC                           │
├──────────────────────┼──────────────────────────────────┤
│                Engine Core Layer                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │                 EngineCore                        │   │
│  │  ┌────────────┐  ┌─────────────┐  ┌──────────┐  │   │
│  │  │ Scheduler  │→│  Executor   │→│ Output   │  │   │
│  │  │            │  │ (Workers)   │  │Processor │  │   │
│  │  └──────┬─────┘  └──────┬──────┘  └──────────┘  │   │
│  │         │               │                         │   │
│  │  ┌──────┴─────┐  ┌──────┴──────┐                 │   │
│  │  │ KV Cache   │  │  Model      │                 │   │
│  │  │ Manager    │  │  Runner     │                 │   │
│  │  └────────────┘  └─────────────┘                 │   │
│  └──────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────┤
│                    GPU Execution Layer                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │ Worker 0 │  │ Worker 1 │  │ Worker N │              │
│  │ (GPU 0)  │  │ (GPU 1)  │  │ (GPU N)  │              │
│  └──────────┘  └──────────┘  └──────────┘              │
└─────────────────────────────────────────────────────────┘
```

### V1 vs V0 架构差异

| 维度 | V0 | V1 |
|------|-----|-----|
| **调度器** | Prefill/Decode 分离 | 统一调度（token budget） |
| **KV Cache** | 支持 GPU↔CPU 交换 | 移除交换，简化架构 |
| **Tensor Parallel** | Worker 0 与 Scheduler 共进程 | 对称架构，独立进程 |
| **Prefix Caching** | 默认关闭（CPU 开销大） | 默认开启（近零开销） |
| **Chunked Prefill** | 条件启用 | 默认启用 |

## 2. 源码结构

```
vllm/
├── v1/                          # V1 引擎核心
│   ├── engine/
│   │   ├── core.py              # EngineCore 主循环（调度→执行→输出）
│   │   ├── async_llm.py         # 异步引擎入口（API 服务用）
│   │   └── llm.py               # 同步引擎入口（Python 库用）
│   ├── core/
│   │   ├── sched/
│   │   │   ├── scheduler.py     # 调度器核心（3000+ 行）
│   │   │   └── output.py        # SchedulerOutput 数据结构
│   │   ├── kv_cache_manager.py  # KV Cache 管理器（887 行）
│   │   ├── kv_cache_utils.py    # KVCacheBlock 定义
│   │   └── single_type_kv_cache_manager.py
│   ├── model_executor/          # 模型执行器（Worker 管理）
│   ├── entrypoints/             # API 入口（OpenAI 兼容）
│   └── outputs.py               # 输出数据结构
├── models/                      # 模型实现（Llama, Mistral, Qwen...）
├── kernels/                     # 自定义 CUDA kernel
├── csrc/                        # C++/CUDA 源码
├── lora/                        # LoRA 支持
├── multimodal/                  # 多模态支持
├── distributed/                 # 分布式通信
└── spec_decode/                 # 推测解码
```

### EngineCore 主循环

```python
# vllm/v1/engine/core.py — 简化版
class EngineCore:
    """
    vLLM V1 的核心执行循环。
    在独立进程中运行，通过 ZMQ 与 API 层通信。
    """
    
    def __init__(self, vllm_config):
        # 1. 初始化 Worker（GPU 执行进程）
        self.executor = Executor(vllm_config)
        
        # 2. 性能分析：确定 KV Cache 容量
        self._profile_gpu_memory()
        
        # 3. 初始化调度器
        self.scheduler = Scheduler(vllm_config, ...)
        
        # 4. 结构化输出管理器
        self.structured_output_manager = StructuredOutputManager(...)
    
    def run(self):
        """主循环：schedule → execute → update → repeat"""
        while True:
            # 1. 调度：决定每个请求处理多少 token
            scheduler_output = self.scheduler.schedule()
            
            # 2. 执行：运行模型 forward pass
            executor_output = self.executor.execute_model(scheduler_output)
            
            # 3. 更新：处理输出、释放完成的请求
            self.scheduler.update_from_output(executor_output)
```

## 3. PagedAttention 深度解析

### 3.1 核心思想

PagedAttention 借鉴 OS 虚拟内存，将 KV Cache 分为固定大小的**块（block）**。

**问题背景**：LLM 推理时，每个 token 的生成都需要用到之前所有 token 的 Key/Value 向量（即 KV Cache）。传统做法是为每个请求预分配最大序列长度的连续显存：

```
假设 max_seq_len = 2048, 一个请求实际只用了 512 tokens：

传统方式：
┌────────────────────────────────────────────────────┐
│ 请求 A 预分配: [████░░░░░░░░░░░░░░░░░░░░░░░░░░░░] │
│                ↑已用    ↑浪费（75%显存）             │
│ 请求 B 预分配: [██████████░░░░░░░░░░░░░░░░░░░░░░] │
│ 请求 C 预分配: [██░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] │
└────────────────────────────────────────────────────┘
问题：
  1. 每个请求浪费 50-80% 预分配的显存
  2. 碎片化严重，无法合并
  3. 批处理大小受限，GPU 利用率低
```

PagedAttention 的解决方案：

```
PagedAttention（分页分配）：
┌────────────────────────────────────────────────────┐
│ Block Pool（物理块池）:                              │
│  [A0][A1][B0][B1][B2][C0]  ← 按需分配，无浪费     │
│                                                     │
│ Block Table（块表 - 逻辑→物理映射）:                │
│  请求 A: 逻辑块 [0, 1] → 物理块 [5, 2]             │
│  请求 B: 逻辑块 [0, 1, 2] → 物理块 [0, 3, 6]      │
│  请求 C: 逻辑块 [0] → 物理块 [1]                   │
│                                                     │
│ 内存浪费：仅最后一个块有浪费 (<4%)                  │
└────────────────────────────────────────────────────┘
```

### 3.2 关键数据结构

**KVCacheBlock**（`vllm/v1/core/kv_cache_utils.py`）：

```python
@dataclass
class KVCacheBlock:
    """一个物理 KV Cache 块，存储固定数量 token 的 Key/Value 向量。"""
    
    block_id: int                    # 物理块的唯一 ID（0 ~ num_gpu_blocks-1）
    ref_count: int = 0               # 引用计数：有多少个请求共享此块
                                     #   0 = 空闲，可被分配
                                     #   1 = 单个请求使用
                                     #   >1 = 多个请求共享（CoW）
    
    block_hash: BlockHash | None = None  # 块内容哈希（用于 Prefix Caching）
                                         #   None = 未缓存/不可缓存
                                         #   有值 = 可被其他请求复用
    
    # 双向链表指针（用于 FreeKVCacheBlockQueue 的 O(1) 删除）
    prev_free_block: 'KVCacheBlock | None' = None
    next_free_block: 'KVCacheBlock | None' = None
```

**FreeKVCacheBlockQueue**（空闲块队列）：

```python
class FreeKVCacheBlockQueue:
    """
    管理空闲 KV Cache 块的双向链表。
    关键优化：支持 O(1) 从任意位置删除（不只是头部/尾部）。
    
    为什么需要 O(1) 任意位置删除？
    - Prefix Caching 需要从空闲队列中"回收"特定的块
    - 如果只能从头部删除，需要 O(n) 遍历找到目标块
    """
    
    def __init__(self):
        self.free_blocks: dict[int, KVCacheBlock] = {}  # block_id → block
        self._head: KVCacheBlock | None = None  # 链表头（最旧的块）
        self._tail: KVCacheBlock | None = None  # 链表尾（最新的块）
    
    def append(self, block: KVCacheBlock):
        """添加空闲块到队列尾部 O(1)"""
        block.next_free_block = None
        block.prev_free_block = self._tail
        if self._tail is not None:
            self._tail.next_free_block = block
        else:
            self._head = block
        self._tail = block
        self.free_blocks[block.block_id] = block
    
    def remove(self, block: KVCacheBlock):
        """从任意位置移除空闲块 O(1)"""
        if block.prev_free_block:
            block.prev_free_block.next_free_block = block.next_free_block
        else:
            self._head = block.next_free_block
        
        if block.next_free_block:
            block.next_free_block.prev_free_block = block.prev_free_block
        else:
            self._tail = block.prev_free_block
        
        del self.free_blocks[block.block_id]
```

### 3.3 Block Table 映射（内存布局）

```
GPU 显存中的物理块（Physical Blocks）：
┌──────┬──────┬──────┬──────┬──────┬──────┬──────┐
│  0   │  1   │  2   │  3   │  4   │  5   │  6   │
├──────┼──────┼──────┼──────┼──────┼──────┼──────┤
│  B0  │  C0  │  A1  │  B1  │  空  │  A0  │  B2  │
│(4tok)│(1tok)│(4tok)│(4tok)│      │(4tok)│(2tok)│
└──────┴──────┴──────┴──────┴──────┴──────┴──────┘

请求 A: "What is machine learning?" (6 tokens)
  逻辑块 0 → 物理块 5 (前4个token的KV)
  逻辑块 1 → 物理块 2 (后2个token的KV)
  Block Table: [5, 2]

请求 B: "Explain deep neural networks in detail" (10 tokens)
  逻辑块 0 → 物理块 0 (前4个token)
  逻辑块 1 → 物理块 3 (第5-8个token)
  逻辑块 2 → 物理块 6 (最后2个token)
  Block Table: [0, 3, 6]

请求 C: "Hi" (1 token)
  逻辑块 0 → 物理块 1 (仅1个token)
  Block Table: [1]
  → 浪费 3 个 slot（块大小=4，只用了1个）
```

### 3.4 Copy-on-Write (CoW) 机制

Beam Search 和并行采样时，多个序列共享公共前缀的 KV Cache：

```
场景：Beam Search，beam_width=2
初始 prompt: "The capital of France is"

Step 1: 共享前缀
  Seq A: [Block 0] [Block 1]  ← 共享（ref_count=2）
  Seq B: [Block 0] [Block 1]  ← 共享（ref_count=2）

Step 2: 分叉（生成不同 token）
  Seq A: [Block 0] [Block 1] [Block 2-A]  ← 新块（ref_count=1）
  Seq B: [Block 0] [Block 1] [Block 2-B]  ← 新块（ref_count=1）
  
  Block 0, Block 1: ref_count 从 2 降到 1（不再是共享）

Step 3: 继续分叉
  Seq A: [Block 0] [Block 1] [Block 2-A] [Block 3-A]
  Seq B: [Block 0] [Block 1] [Block 2-B] [Block 3-B]

内存节省：
  传统方式：2 序列 × 4 块 = 8 块
  CoW：2 + 2 + 2 + 2 = 最多共享前 2 块 = 6 块（节省 25%）
  
  实际场景中，共享前缀越长，节省越多：
  - 1000 token 的 system prompt + 2 beam → 节省约 50% 显存
```

**CoW 触发流程**：

```
1. 请求 A 和 B 共享 Block X（ref_count=2）
2. 请求 A 需要修改 Block X（生成新 token，写入新 KV）
3. 触发 CoW：
   a. 从空闲队列分配新块 Block Y
   b. 将 Block X 的内容复制到 Block Y
   c. Block X 的 ref_count 减 1（变为 1）
   d. 请求 A 的块表更新：Block X → Block Y
4. 此后 A 使用 Block Y，B 继续使用 Block X
```

## 4. Continuous Batching 调度器

### 4.1 静态批处理 vs 连续批处理

**静态批处理（传统方式）**：

```
时间线：
  t0: [Req1, Req2, Req3] → 开始处理
  t1: Req1 完成，但必须等 Req2, Req3 → GPU 空闲等待
  t2: Req2 完成，等 Req3
  t3: 全部完成 → 才能处理新请求 [Req4, Req5, Req6]

问题：短请求等长请求，GPU 利用率低
```

**连续批处理（vLLM）**：

```
时间线：
  t0: [Req1(100tok), Req2(50tok), Req3(200tok)] → 开始
  t1: Req2 完成 → 立即加入 Req4 → [Req1, Req3, Req4]
  t2: Req1 完成 → 立即加入 Req5 → [Req3, Req4, Req5]
  t3: Req4 完成 → 立即加入 Req6 → [Req3, Req5, Req6]
  ...

效果：GPU 始终保持高利用率，平均延迟更低
```

### 4.2 V1 调度器设计

V1 调度器的**核心创新**：统一处理 prefill 和 decode，用简单的 token budget 分配。

```python
@dataclass
class SchedulerOutput:
    """
    V1 的调度输出非常简洁：
    只需告诉每个请求"这一步处理多少个 token"。
    
    prefill 和 decode 的区别仅在于 num_tokens 的大小：
    - prefill: num_tokens = 整个 prompt 长度（或 chunk 大小）
    - decode: num_tokens = 1（生成一个新 token）
    """
    scheduled_reqs: dict[str, int]  # {request_id: num_tokens_to_process}
    
    # 示例：
    # {
    #   "req_1": 2048,   # prefill：处理 2048 个 prompt tokens
    #   "req_2": 1,      # decode：生成 1 个新 token
    #   "req_3": 1,      # decode：生成 1 个新 token
    #   "req_4": 512,    # prefill：分块处理 512 个 tokens（chunked prefill）
    # }
```

### 4.3 调度流程详解

```
┌─────────────────────────────────────────────────────────────┐
│              Scheduler.schedule() — 每步执行一次             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  阶段 1：处理 Running 队列（正在生成的请求）                  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ for req in running:                                   │  │
│  │   num_tokens = 1  # decode 每次只处理 1 个 token      │  │
│  │   if 需要 speculative decode:                         │  │
│  │     num_tokens += num_spec_tokens                     │  │
│  │                                                       │  │
│  │   # 尝试分配 KV Cache 块                               │  │
│  │   blocks = kv_cache_manager.allocate(req, num_tokens) │  │
│  │   if 分配失败:                                        │  │
│  │     抢占低优先级请求 → 释放其 KV Cache → 重试          │  │
│  │                                                       │  │
│  │   # 更新 token budget                                 │  │
│  │   token_budget -= num_tokens                          │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  阶段 2：处理 Waiting 队列（等待处理的新请求）                │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ while waiting 非空 and token_budget > 0:              │  │
│  │   req = waiting.peek()                                │  │
│  │                                                       │  │
│  │   # 1. 检查 Prefix Cache 命中                         │  │
│  │   computed_blocks, num_computed =                     │  │
│  │     kv_cache_manager.get_computed_blocks(req)         │  │
│  │                                                       │  │
│  │   # 2. 计算需要处理的 token 数                         │  │
│  │   num_new_tokens = req.num_tokens - num_computed      │  │
│  │                                                       │  │
│  │   # 3. Chunked Prefill：限制单步 token 数             │  │
│  │   if num_new_tokens > long_prefill_token_threshold:   │  │
│  │     num_new_tokens = long_prefill_token_threshold     │  │
│  │                                                       │  │
│  │   # 4. 检查资源是否足够                                │  │
│  │   if token_budget >= num_new_tokens and               │  │
│  │      kv_cache 有足够空间:                              │  │
│  │     blocks = allocate(num_new_tokens)                 │  │
│  │     running.append(req)                               │  │
│  │     token_budget -= num_new_tokens                    │  │
│  │   else:                                               │  │
│  │     break  # 资源不足，等待下一轮                      │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  阶段 3：输出 SchedulerOutput                                │
│  返回 {req_id: num_tokens} 给 EngineCore 执行 forward pass  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 4.4 完整请求生命周期

```
用户请求到达
    │
    ▼
┌──────────┐
│ API层    │  Tokenize prompt
│          │  创建 Request 对象
└────┬─────┘
     │
     ▼
┌──────────┐
│ Waiting  │  请求进入等待队列
│ Queue    │
└────┬─────┘
     │  schedule() 选中此请求
     ▼
┌──────────┐
│ Running  │  1. 检查 Prefix Cache
│          │  2. 分配 KV Cache 块
│          │  3. 执行 forward pass (prefill)
│          │  4. 采样第一个 token
└────┬─────┘
     │  每步 decode 生成 1 个 token
     │  直到遇到 EOS 或达到 max_tokens
     ▼
┌──────────┐
│ Finished │  1. 释放 KV Cache 块（归还空闲队列）
│          │  2. Detokenize 输出
│          │  3. 返回给用户
└──────────┘
```

### 4.5 抢占机制

当 KV Cache 不足时，调度器需要抢占低优先级请求：

```python
# 抢占策略（V1 简化版）
def preempt(self, request):
    """
    V1 不再支持 GPU↔CPU 交换（V0 有）。
    直接释放 KV Cache，请求重新计算。
    
    为什么这样设计？
    1. 简化架构，减少 CPU↔GPU 数据搬运开销
    2. Prefix Caching 可以快速恢复已计算的前缀
    3. 短序列重新计算的代价很低
    """
    # 1. 释放此请求的所有 KV Cache 块
    self.kv_cache_manager.free(request)
    
    # 2. 重置计算进度
    request.num_computed_tokens = 0
    
    # 3. 移回 Waiting 队列
    request.status = RequestStatus.PREEMPTED
    self.waiting.prepend_request(request)
```

## 5. Prefix Caching

### 5.1 为什么需要 Prefix Caching

```
场景：客服系统，每个请求都带 2000 token 的 system prompt

无 Prefix Caching：
  请求 1: 计算 [2000 tok prompt + 50 tok user] = 2050 tokens
  请求 2: 计算 [2000 tok prompt + 30 tok user] = 2030 tokens
  请求 3: 计算 [2000 tok prompt + 80 tok user] = 2080 tokens
  → 2000 token 的 prompt 被重复计算 3 次 = 6000 tokens 浪费

有 Prefix Caching：
  请求 1: 计算 [2000 tok prompt + 50 tok user] = 2050 tokens
  请求 2: 复用 prompt 的 KV Cache，只计算 30 tok user = 30 tokens
  请求 3: 复用 prompt 的 KV Cache，只计算 80 tok user = 80 tokens
  → 总计算量：2050 + 30 + 80 = 2160 tokens（节省 70%+）
```

### 5.2 基于哈希的缓存实现

```python
# Block Hash 计算（简化版）
def compute_block_hash(token_ids: list[int], context_hash: int) -> int:
    """
    每个块的哈希 = f(块内 token IDs, 前驱块的哈希)
    
    这样设计的好处：
    - 相同前缀 + 相同内容 → 相同哈希
    - 可以快速判断两个块是否内容一致
    - 支持任意位置的前缀匹配
    """
    return hash((tuple(token_ids), context_hash))

# 缓存查找流程
def find_longest_cache_hit(block_hashes: list[int], max_length: int):
    """
    从左到右，找到最长的连续缓存命中。
    
    示例：
    请求的 block_hashes = [hash_A, hash_B, hash_C, hash_D]
    
    缓存中已有：[hash_A, hash_B, hash_C]  ← 命中前 3 个块
    
    结果：
    - computed_blocks = [Block 0, Block 1, Block 2]
    - num_computed_tokens = 3 * block_size = 48 tokens
    - 剩余需要计算：1 个块（hash_D）
    """
```

### 5.3 V1 的关键优化

V1 对 Prefix Caching 做了重要优化，解决了 V0 的性能问题：

```python
# V0 的问题：Prefix Caching 有 CPU 开销
# 当缓存命中率低时，性能反而下降（因为哈希计算、LRU 淘汰的开销）
# 所以 V0 默认关闭 Prefix Caching

# V1 的优化：
# 1. O(1) 缓存淘汰：使用常数时间数据结构替代线性扫描
# 2. 最小化 Python 对象创建：减少 GC 压力
# 3. 结果：即使缓存命中率 0%，性能也几乎无损

# 源码中的优化点（kv_cache_coordinator.py）：
class HybridKVCacheCoordinator:
    def find_longest_cache_hit(self, block_hashes, max_length):
        """
        V1 优化：
        - 使用 dict 存储 block_hash → block 的映射（O(1) 查找）
        - LRU 淘汰使用 collections.OrderedDict（O(1) 移动/删除）
        - 避免创建临时对象
        """
        # 1. 按 block_hash 查找（O(1)）
        for i, block_hash in enumerate(block_hashes):
            if block_hash not in self.cached_blocks:
                break
            # 2. 检查块是否仍然有效（未被淘汰）
            block = self.cached_blocks[block_hash]
            if not self._is_block_valid(block):
                break
            # 3. LRU 更新（O(1)）
            self._touch_block(block)
            computed_blocks.append(block)
        
        return computed_blocks, num_computed_tokens
```

### 5.4 多模态 Prefix Caching

V1 扩展了 Prefix Caching 支持多模态输入（如图像）：

```python
# 对于图像输入，哈希计算包含图像特征的哈希
block_hash = hash((
    token_ids,           # 文本 token
    context_hash,        # 前驱块哈希
    image_hash,          # 图像特征哈希（如果有）
))

# 场景：多轮对话中重复使用同一张图片
# 请求 1: [Image_A] + "描述这张图片"
# 请求 2: [Image_A] + "图片中有什么动物？"
# → Image_A 的 KV Cache 可以被复用
```

## 6. Chunked Prefill

### 6.1 问题

长 prompt 的 prefill 是计算密集型操作，会阻塞 decode 请求的处理：

```
传统方式：
  Prefill [10000 tokens] → Decode 被阻塞 ~100ms
                             ↑
                     用户感知到延迟尖峰
```

### 6.2 解决方案

将长 prefill 分成多个 chunk，与 decode 交替执行：

```
Chunked Prefill：
  Step 1: Prefill chunk [0-2048] + Decode req_1, req_2
  Step 2: Prefill chunk [2048-4096] + Decode req_1, req_2
  Step 3: Prefill chunk [4096-6144] + Decode req_1, req_2
  ...
```

V1 默认启用 chunked prefill，通过 `long_prefill_token_threshold` 控制 chunk 大小。

## 7. Disaggregated P/D（分离式 Prefill-Decode）

### 7.1 设计动机

Prefill 和 Decode 有完全不同的性能特征：

| 维度 | Prefill | Decode |
|------|---------|--------|
| **计算特性** | 计算密集型 | 内存带宽密集型 |
| **GPU 利用率** | 高 | 低 |
| **延迟敏感度** | TTFT（首 Token） | ITL（Token 间） |

### 7.2 架构

```
┌─────────────────────────────────────────┐
│         Disaggregated P/D              │
├─────────────────────────────────────────┤
│  N 个 Prefill 实例                      │
│  ┌──────────┐  ┌──────────┐            │
│  │ Prefill  │  │ Prefill  │            │
│  │ Worker 0 │  │ Worker 1 │            │
│  └────┬─────┘  └────┬─────┘            │
│       │              │                  │
│       └──────┬───────┘                  │
│              ↓                          │
│     KV Cache Transfer (NIXL)            │
│              ↓                          │
│  M 个 Decode 实例                       │
│  ┌──────────┐  ┌──────────┐            │
│  │ Decode   │  │ Decode   │            │
│  │ Worker 0 │  │ Worker 1 │            │
│  └──────────┘  └──────────┘            │
└─────────────────────────────────────────┘
```

- Prefill 实例专注处理输入 tokens
- Decode 实例专注生成输出 tokens
- 通过 NIXL（NVIDIA Interconnect eXchange Library）传输 KV Cache

## 8. 推测解码（Speculative Decoding）

### 8.1 原理

使用小模型（Draft Model）快速生成多个候选 token，大模型一次性验证：

```
Draft Model:  快速生成 [t1, t2, t3, t4, t5]  (5 tokens, 10ms)
Target Model: 一次性验证 [t1, t2, t3, t4, t5] → 接受 [t1, t2, t3], 拒绝 [t4, t5]
              ↑
              等效于 3 次 decode，但只用了 1 次 forward pass
```

### 8.2 vLLM 支持的推测解码方式

| 方式 | 说明 | 特点 |
|------|------|------|
| **N-gram** | 基于输入 n-gram 预测 | 无需额外模型 |
| **EAGLE** | 自回归 draft model | 高接受率 |
| **DFlash** | Flash Attention 优化 | 低开销 |

## 9. 量化支持

### 9.1 支持的量化格式

| 格式 | 类型 | 适用硬件 | 说明 |
|------|------|----------|------|
| **FP8** | W8A8 | Hopper+ (H100/H200) | 原生支持，KV Cache 也可量化 |
| **NVFP4** | W4A8 | Blackwell (B100/B200) | 最新 4-bit 量化 |
| **AWQ** | W4A16 | 通用 | 激活感知权重量化 |
| **GPTQ** | W4A16 | 通用 | 基于 Hessian 的量化 |
| **GGUF** | 多种 | 通用 | llama.cpp 格式 |
| **BitsAndBytes** | W4/W8 | 通用 | 动态量化 |
| **TorchAO** | 多种 | 通用 | PyTorch 原生 |

### 9.2 FP8 KV Cache

FP8 KV Cache 将 KV Cache 精度从 FP16 降至 FP8，显存减半：

```bash
# 启用 FP8 KV Cache
vllm serve meta-llama/Llama-3-8B-Instruct \
    --kv-cache-dtype fp8 \
    --quantization fp8
```

## 10. 多 GPU 并行

### 10.1 并行策略

| 策略 | 说明 | 适用场景 |
|------|------|----------|
| **张量并行 (TP)** | 模型层切分到多 GPU | 单模型跨多 GPU |
| **流水线并行 (PP)** | 模型层分配到不同 GPU | 超大模型 |
| **专家并行 (EP)** | MoE 专家分布在不同 GPU | DeepSeek 等 MoE 模型 |
| **上下文并行 (DCP)** | KV Cache 按序列维度切分 | 长上下文 Agent 场景 |

### 10.2 对称架构

V1 引入对称 Tensor Parallel 架构：

```
V0（非对称）：
  Scheduler + Worker 0 共进程 → 复杂，Worker 0 特殊处理

V1（对称）：
  Scheduler（独立进程）→ 所有 Worker 相同处理
                    ↓
  Worker 0 / Worker 1 / ... / Worker N
```

## 11. 生产部署配置

### 11.1 关键参数

| 参数 | 默认值 | 推荐值 | 说明 |
|------|--------|--------|------|
| `--gpu-memory-utilization` | 0.9 | 0.92-0.95 | GPU 内存利用率 |
| `--max-num-seqs` | 256 | 256-512 | 最大并发序列数 |
| `--max-num-batched-tokens` | auto | 8192-16384 | 每步 token 预算 |
| `--enable-prefix-caching` | V1: on | on | 共享 prompt 时 30%+ 提升 |
| `--enable-chunked-prefill` | V1: on | on | 平滑 P99 延迟 |
| `--swap-space` | 4 GiB | 16-32 GiB | 抢占时 CPU 缓冲 |
| `--tensor-parallel-size` | 1 | 按需 | 张量并行 GPU 数 |
| `--kv-cache-dtype` | auto | fp8 (Hopper+) | KV Cache 量化 |

### 11.2 性能基准（Llama 3.1 8B, A100 80GB）

| 配置 | 吞吐量 (tok/s) | 成本 ($/1M tok) |
|------|:--------------:|:---------------:|
| vLLM 默认 | 4,200 | $0.27 |
| vLLM 调优 | 6,200 | $0.18 |
| vLLM + FP8 KV | 7,100 | $0.16 |
| SGLang | 6,800 | $0.17 |

### 11.3 部署模式

```bash
# 1. 单 GPU 直接部署
vllm serve meta-llama/Llama-3-8B-Instruct --port 8000

# 2. 多 GPU 张量并行
vllm serve meta-llama/Llama-3-70B-Instruct \
    --tensor-parallel-size 4 \
    --max-model-len 4096

# 3. Docker 部署
docker run --gpus all -p 8000:8000 \
    vllm/vllm-openai:latest \
    --model meta-llama/Llama-3-8B-Instruct

# 4. Ray Serve 分布式部署（生产推荐）
# 多副本 + 自动扩缩容
```

## 12. 与其他引擎对比

| 维度 | vLLM | SGLang | TensorRT-LLM | llama.cpp |
|------|------|--------|---------------|-----------|
| **核心创新** | PagedAttention | RadixAttention | 图融合+量化 | GGUF+CPU |
| **Prefill/Decode** | 统一调度 | 统一调度 | 混合 | 混合 |
| **前缀缓存** | 哈希+LRU | 基数树 | 支持 | ❌ |
| **结构化输出** | Guided Decoding | 原生 DSL | 有限 | ❌ |
| **分裂式 P/D** | ✅ (NIXL) | ✅ (原生) | ✅ | ❌ |
| **模型支持** | 最广 | 广 | 中等 | 广 |
| **安装难度** | 简单 | 简单 | 困难 | 简单 |
| **生产成熟度** | 高 | 高 | 很高 | 中 |
| **最佳场景** | 通用生产 | Agent/结构化 | NVIDIA 极致优化 | 本地/边缘 |

## 13. 已知限制与改进方向

| 限制 | 说明 | 状态 |
|------|------|------|
| 长上下文抢占 | 100K token prefill 会阻塞集群 | Chunked Prefill 缓解 |
| 结构化输出开销 | JSON schema 约束降低 15-30% 吞吐 | 持续优化中 |
| Multi-LoRA 调度 | Round-robin，非公平感知 | 改进中 |
| GPU↔CPU 交换 | V1 已移除 | 直接重新计算 |

## 14. 端到端示例：一个请求的完整旅程

通过一个具体例子，串联所有核心组件：

```
用户请求：POST /v1/chat/completions
{
  "model": "Llama-3-8B-Instruct",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "What is 2+2?"}
  ],
  "max_tokens": 100
}
```

### Step 1: API 层处理

```
OpenAI Compatible Server (vllm/v1/entrypoints/)
    │
    ├─ 1. 接收 HTTP 请求
    ├─ 2. 验证请求格式
    ├─ 3. InputProcessor 处理：
    │     ├─ Tokenize prompt → [token_1, token_2, ..., token_N]
    │     ├─ 处理多模态输入（如果有图像）
    │     └─ 创建 EngineCoreRequest 对象
    └─ 4. 通过 ZMQ 发送给 EngineCore
```

### Step 2: 调度器决策

```
Scheduler.schedule()（vllm/v1/core/sched/scheduler.py）
    │
    ├─ 1. 检查 Waiting 队列 → 发现新请求
    │
    ├─ 2. Prefix Cache 查找：
    │     ├─ 计算 block_hashes = [hash_0, hash_1, ..., hash_M]
    │     ├─ find_longest_cache_hit() → 假设命中前 2 个块
    │     └─ num_computed_tokens = 2 * block_size = 32 tokens
    │
    ├─ 3. 计算需要处理的 token 数：
    │     num_new_tokens = prompt_length - num_computed_tokens
    │                    = 50 - 32 = 18 tokens
    │
    ├─ 4. Chunked Prefill 检查：
    │     18 tokens < long_prefill_token_threshold → 无需分块
    │
    ├─ 5. KV Cache 块分配：
    │     ├─ kv_cache_manager.allocate(req, 18)
    │     ├─ 从 FreeBlockQueue 分配 2 个新物理块
    │     └─ 更新 Block Table
    │
    ├─ 6. 资源检查：
    │     ├─ token_budget 剩余足够
    │     ├─ KV Cache 使用率 < 阈值
    │     └─ 通过 → 加入 Running 队列
    │
    └─ 7. 输出 SchedulerOutput：
          {"req_1": 18}  # 这一步处理 18 个 token
```

### Step 3: 模型执行

```
Executor.execute_model()（vllm/v1/model_executor/）
    │
    ├─ 1. 准备输入：
    │     ├─ 从 SchedulerOutput 获取 token 列表
    │     ├─ 构建 attention metadata（block_table、position_ids）
    │     └─ CPU → GPU 数据传输
    │
    ├─ 2. Forward Pass：
    │     ├─ Embedding 层：token → hidden_states
    │     ├─ N × Transformer Layer：
    │     │     ├─ Self-Attention（使用 PagedAttention kernel）
    │     │     │   ├─ Query = hidden_states @ W_q
    │     │     │   ├─ Key/Value 从 KV Cache 块中读取
    │     │     │   ├─ Attention = softmax(Q @ K^T / sqrt(d)) @ V
    │     │     │   └─ 将新的 K/V 写入分配的物理块
    │     │     ├─ FFN（MLP）
    │     │     └─ LayerNorm
    │     └─ LM Head：hidden_states → logits
    │
    ├─ 3. 采样：
    │     ├─ logits = output_logits[-1]  # 最后一个 token 的 logits
    │     ├─ 应用 temperature、top_p、top_k
    │     ├─ 采样得到 token_id = 42
    │     └─ 如果是结构化输出，应用 guided decoding
    │
    └─ 4. 输出 ExecutorOutput：
          {req_1: [token_42]}
```

### Step 4: 后处理与循环

```
update_from_output()（vllm/v1/core/sched/scheduler.py）
    │
    ├─ 1. 将 token_42 追加到 Request 的 output_token_ids
    │
    ├─ 2. 检查停止条件：
    │     ├─ token_42 == EOS? → 否
    │     ├─ len(output) >= max_tokens? → 否
    │     └─ 继续生成
    │
    ├─ 3. 下一轮调度：
    │     Request 仍在 Running 队列
    │     SchedulerOutput = {"req_1": 1}  # decode 1 token
    │
    └─ 4. 重复 Step 3-4 直到完成
```

### Step 5: 完成与返回

```
Request 完成（遇到 EOS 或达到 max_tokens）
    │
    ├─ 1. 释放 KV Cache 块：
    │     kv_cache_manager.free(req)
    │     → 块的 ref_count 减 1
    │     → ref_count=0 的块归还 FreeBlockQueue
    │
    ├─ 2. Detokenize：
    │     token_ids → 文本字符串
    │
    ├─ 3. 构建 ChatCompletionResponse
    │
    └─ 4. 通过 ZMQ 返回给 API 层 → HTTP 响应
```

## 参考

- [vLLM 官方文档](https://docs.vllm.ai/)
- [vLLM GitHub](https://github.com/vllm-project/vllm)
- [PagedAttention 论文 (SOSP 2023)](https://arxiv.org/abs/2309.06180)
- [Anatomy of a High-Throughput LLM Inference System](https://vllm.ai/blog/2025-09-05-anatomy-of-vllm)
- [vLLM V1 架构博客](https://vllm.ai/blog/2025-01-27-v1-alpha-release)
- [vLLM Continuous Batching Deep Dive](https://www.swfte.com/blog/vllm-continuous-batching-deep-dive)

---

## 📚 相关笔记

- [[entities/vllm|vLLM 实体笔记]] — 概览与快速参考
- [[sources/LLMForEverybody/02-第二章-部署与推理/大模型推理框架（二）vLLM|大模型推理框架（二）vLLM]] — LLMForEverybody 系列文章
- [[entities/sglang|SGLang]] — 对比：RadixAttention 推理引擎
- [[entities/tensorrt-llm|TensorRT-LLM]] — 对比：NVIDIA 官方推理引擎
- [[entities/llama.cpp|llama.cpp]] — 对比：CPU-first 推理引擎
- [[concepts/LLM 推理 优化|LLM 推理 优化]] — 推理优化技术总论
- [[concepts/推理 引擎 选择|推理引擎选型]] — 推理引擎选型对比
