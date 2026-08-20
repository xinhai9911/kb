## KV 缓存管理：PagedAttention 块池与协调器

### 块模型概述

PagedAttention 将 KV 缓存按固定大小块（block/page）管理，每块含 `block_size` 个 token 的 KV 张量。KV 缓存在物理上是一个统一 GPU 块池，请求持有「块表」（block table）按需追加；相邻请求可共享相同前缀的块（前缀缓存）。`kv_cache_utils.py` 中 `BlockHash = NewType("BlockHash", bytes)` 表示链式前缀哈希。

块粒度数据：

| 术语 | 定义 |
|------|------|
| `hash_block_size` | 计算 block hash 的粒度；单组模型下等于调度块大小，多组为各块大小 GCD（可用 `prefix_match_unit` 覆盖） |
| `scheduler_block_size` | 调度对齐粒度，为各 cache group 有效块大小的 LCM |
| `block_size` | 各 cache group 的实际块大小，须为 `hash_block_size` 整数倍 |

### `KVCacheBlock` 与 `FreeKVCacheBlockQueue`

`KVCacheBlock`（`kv_cache_utils.py`）是块元数据，不持有 GPU 张量：`block_id`、`ref_cnt`（引用计数）、`_block_hash`/`_block_hash_num_tokens`（整块缓存哈希及覆盖 token 数）、`is_null`（占位空块，永不被缓存）、`prev_free_block`/`next_free_block`（空闲双向链表指针）。

`FreeKVCacheBlockQueue` 以双向链表组织空闲块，实现 O(1) 中段删除、O(1) 取头/增尾；使用哨兵假头尾减少分支，不额外分配对象：`popleft_n`（批量分配）、`prepend_n`（头插，无缓存块 LIFO 复用）、`append_n`（尾插，缓存块 FIFO 复用）。

### `BlockPool` 块池（`block_pool.py`）

构造时创建 `num_gpu_blocks` 个 `KVCacheBlock` 并按序链接，`null_block` 固定取 `block_id=0`（`is_null=True`，ref 计数不维护）。关键操作：

| 方法 | 行为 |
|------|------|
| `get_new_blocks` | 从空闲队列头取块；`enable_caching` 时先 `_maybe_evict_cached_block`（清哈希、发 `BlockRemoved` 事件），`ref_cnt=1` |
| `touch` | 前缀命中：ref_cnt 0→1 时移出空闲队列，`ref_cnt += 1`（命中块被复用） |
| `free_blocks` | 逆序归还；无哈希块头插（LIFO 保 GPU 局部性），有哈希块尾插（LRU 淘汰顺序） |
| `evict_blocks` | 按 block_id 仅从前缀缓存哈希表驱逐（不改变池内占用） |
| `reset_prefix_cache` | 清空哈希表与块哈希；仅当所有块空闲（除 null 块）时成功 |

前缀缓存以 `cached_block_hash_to_block: BlockHashToBlockMap` 维护 `{block_hash(+group_id): block}` 映射；同一哈希可对应多个块（存 `dict[int, KVCacheBlock]`）。`cache_full_blocks` 在块写满时登记哈希（阻塞时以 `block_mask` 跳过 SWA/Mamba 稀疏组），`cache_partial_block` 支持块内 `hash_block_size` 边界的部分条目。

### `KVCacheManager`（`kv_cache_manager.py`）

对外以 `KVCacheBlocks`（按 `kv_cache_group` 分组的块序列元组）暴露分配结果，隐藏内部结构。核心 `allocate_slots(request, num_new_tokens, ...)` 布局：

```
| <comp> | <new_comp> | <ext_comp> | <new> | <lookahead> |
| Prefix 缓存命中(本地/外部 connector) | 待计算 |
```

分为三个阶段：(1) 释放 `comp` 段多余块并检查空闲量；(2) 处理前缀 token（滑动窗口外释放、为外部命中分配块）；(3) 为待计算 token+lookahead 分配新块。

其他职责：
- `watermark`：为 WAITING/PREEMPTED 请求预留的最小空闲块比例，避免频繁抢占。
- `remove_skipped_blocks`：释放注意力窗口外不再需要的块并以 null 占位。
- `get_computed_blocks`：最长前缀命中（上限 `num_tokens-1`）；`shared_prefix_boundary` 标记稀疏组未覆盖的共享前缀交点。
- `take_new_block_ids`/`record_blocks_for_zeroing`：需 KV 零化时把新块 ID 交给 worker 事前清零。
- `take_kv_cache_block_copies`：取出 partial-hit CoW 复制对（`KVCacheBlockCopy(src, dst)`）。
- `take_events`：透传块池事件并补注 `kv_cache_spec` 元数据。

### `KVCacheCoordinator` 全局协调器（`kv_cache_coordinator.py`）

单例，通过工厂 `get_kv_cache_coordinator` 按模型选择：

| 协调器 | 适用场景 |
|--------|---------|
| `KVCacheCoordinatorNoPrefixCache` | 关闭前缀缓存 / 注意力无关模型（支持 0..n 个组） |
| `UnitaryKVCacheCoordinator` | 仅一个 KV cache group（单一注意力类型）；block 大小 × DCP |
| `HybridKVCacheCoordinator` | 混合模型多个组；`find_longest_cache_hit` 用迭代固定点算法收敛各注意力类型的前缀命中；`attention_groups` 按 spec 分组、full attention 优先提供初始上界 |

所有协调器共享同一 `BlockPool`，内部按 `kv_cache_config.kv_cache_groups` 为每种注意力类型创建一个 `SingleTypeKVCacheManager`；请求块表由各管理器 `req_to_blocks` 分散持有。协调器统一做两阶段分配（先 touch 各组本地命中块，再分配外部块，避免相互驱逐）与释放。

### single_type 特化（`single_type_kv_cache_manager.py`）

`get_manager_for_kv_cache_spec` 通过 `KVCacheSpecRegistry` 注册表按 spec 类型选管理器：

| 管理器 | 对应 spec | 特化行为 |
|--------|----------|---------|
| `FullAttentionManager` | `FullAttentionSpec`/`ChunkedLocalAttentionSpec`，也接管 `MLAAttentionSpec`/`HiddenStateCacheSpec` | 完整注意权重；支持细粒度部分命中（`supports_fine_grained_hash_lookup=True`）、EAGLE 末块回退、`_cache_partial_tail_block` |
| `RSWAManager` | `RSWASpec` | 释放 prefill 尾与解码窗口之间的空隙块，KV 内存 O(prefix+window) |
| `SlidingWindowManager` | `SlidingWindowSpec`/`SlidingWindowMLASpec` | 从右向左寻找足够连续块形成滑窗命中；`get_num_skipped_tokens` 释放窗口外块 |
| `ChunkedLocalAttentionManager` | `ChunkedLocalAttentionSpec` | 按 chunk 边界跳过窗口外块 |
| `MambaManager` | `MambaSpec` | 只保留最后 token 状态；`align` 模式按块对齐 SSM 状态、用 CoW 部分命中 |
| `CrossAttentionManager` | `CrossAttentionSpec` | 编码器-解码器交叉注意力，不做前缀缓存 |
| `SinkFullAttentionManager` | `SinkFullAttentionSpec` | 预留 sink 块 |

### 缓存指标与事件

- `KVCacheMetricsCollector`（`kv_cache_metrics.py`）：以 `sample_rate`（默认 0.01）采样块驻留生命周期指标：`lifetime_seconds`、`idle_seconds`、`reuse_gaps_seconds`（最近 4 次访问间隙），驱逐时产出 `KVCacheEvictionEvent`。
- `BlockPool.get_usage()`：`1 - free/null_adj`，即 `kv_cache_manager.usage`，随 `SchedulerStats.kv_cache_usage` 上报。
- `PrefixCacheStats`：记录 prefix 查询 token/命中/preempted（`record_prefix_cache_stats`）。
- KV cache 事件（`vllm/distributed/kv_events.py`）：`BlockStored`/`BlockRemoved`/`AllBlocksCleared` 入队后由 `EventPublisherFactory` 创建的 `kv_event_publisher` 以 `KVEventBatch` 发布（用于 KV connector、gateway 等外部消费者）。

### Encoder 缓存（`encoder_cache_manager.py`）

`EncoderCacheManager` 以多模态 `mm_hash` 为键缓存 encoder 输出（按 embedding 数计容量）：
- `check_and_update_cache` 命中则登记引用；`can_allocate` 空间不足时按 FIFO 驱逐 `freeable` 中已无引用的最旧条目（`freed` 记录，经 `get_freed_mm_hashes` 通知 worker 释放）。
- `EncoderDecoderCacheManager` 为 encoder-decoder 模型的过渡实现：不缓存，仅做调度记账。
- 预算由 `compute_mm_encoder_budget` 计算：`max(max_num_encoder_input_tokens, 单条 mm 最大 token)`。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)