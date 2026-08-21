## 淘汰策略、分块（chunk）与页面（page）对齐

本文覆盖 `radix_cache.py` 的淘汰实现、`evict_policy.py` 的七种淘汰策略、以及 chunk 化 prefill 如何与 radix 树在 page 粒度上协同，最后说明 radix 禁用时替代的 `ChunkCache` 族。配套文件：`base_swa_memory_pool.py`、`index_key_cache.py`。

### evict 淘汰流程（radix_cache.py:593）

```python
leaves = list(self.evictable_leaves)                      # 候选池：可淘汰叶子
eviction_heap = [(strategy.get_priority(node), node) for node in leaves]
heapq.heapify(eviction_heap)
while num_evicted < num_tokens and len(eviction_heap):
    _, x = heapq.heappop(eviction_heap)
    self.token_to_kv_pool_allocator.free_segment(x.value, start_pos=0)  # 归还 GPU KV
    num_evicted += len(x.value)
    self._delete_leaf(x)                                  # 从树中摘除
    if len(x.parent.children) == 0 and x.parent.lock_ref == 0:
        heapq.heappush(eviction_heap, (strategy.get_priority(x.parent), x.parent))
```

要点：

- **只从叶子淘汰**：`evictable_leaves` 由 `_update_leaf_status` 维护；叶子被删后若父节点变成无子节点的「新叶子」，父节点补入堆，从而把整棵子树逐层向上收缩。
- **只淘汰缺口**：调度侧 `evict_from_tree_cache`（`common.py:114`）先查 `allocator.available_size()`，不够才调 `tree_cache.evict(EvictParams(num_tokens=缺口))`，不整批清理。
- 每次淘汰都 `kv_events.record_remove(x)` 发布 `BlockRemoved` 事件（若启用）。

### 淘汰策略（evict_policy.py）

`EvictionStrategy` 抽象出 `get_priority(node)`，值越小越先被淘汰；`radix_cache.py:329` 通过 `get_eviction_strategy(policy)`（`utils.py:67`）工厂创建，`CacheInitParams.eviction_policy` 默认 `"lru"`：

| 策略 | priority | 说明 |
|---|---|---|
| `LRUStrategy` | `last_access_time` | 最久未访问先淘汰（默认） |
| `LFUStrategy` | `(hit_count, last_access_time)` | 命中次数少者优先，同频比时间 |
| `FIFOStrategy` | `creation_time` | 先创建先淘汰 |
| `MRUStrategy` | `-last_access_time` | 最近使用先淘汰 |
| `FILOStrategy` | `-creation_time` | 后创建先淘汰 |
| `PriorityStrategy` | `(priority, last_access_time)` | 显式优先级，低优先先淘汰，同级按 LRU |
| `SLRUStrategy` | `(is_protected, last_access_time)` | 两段式：`hit_count < protected_threshold(=2)` 为 Probationary 段，否则 Protected 段；段 0 先于段 1 淘汰 |

`_insert_helper`/`match_prefix` 中 `node.priority = max(node.priority, priority)`：优先级沿路径向上传播（`radix_cache.py:752`），新插入段以请求优先级为初始值。

### chunk 化与 radix 的结合（page 对齐 / cache_protected_len）

- `page_size > 1`（paged allocator）时，`RadixCache` 只缓存**页对齐前缀**：`match_prefix`/`insert` 先 `key.page_aligned(page_size)`；`RadixKey.match` 的结果也向下取整到页。尾部的**未对齐残页**不入树。
- `Req.cache_protected_len`（`radix_cache.py:569`）记录本次请求**真正入树**的长度（= `len(new_indices)`），与 `req.prefix_indices` 可能不同：`prefix_indices` 还带上残页的 KV 索引供 prefill 使用，残页会在下一次 `cache_unfinished_req` 或 `cache_finished_req` 中被 `free_segment(..., start_pos=key_len)` 释放，避免内存泄漏。
- chunked prefill：每个 chunk 算完后 `cache_unfinished_req(req, chunked=True)` 把已覆盖前缀插入树（`scheduler.py:2975` 的 `maybe_cache_unfinished_req`）；`chunked=True` 抑制 `hit_count` 自增，防止分块请求在「自己刚建的节点」上虚增命中。
- `RadixKey.limit` 结合 `Req._compute_max_prefix_len(input_len)`（`schedule_batch.py:1411`）：匹配最多到 `input_len - 1`（留 1 个 token 保证 logprob 可算），`return_logprob` 时再被 `logprob_start_len` 截断。
- Eagle bigram 模式下，树缓存 `len-1` 个二元组单元，`values` 同步截断（`radix_cache.py:156`）。

### ChunkCache 族（radix_cache 禁用时的分块缓存）

| 类 | 文件 | 语义 |
|---|---|---|
| `ChunkCache` | `chunk_cache.py:35` | radix 禁用 + 标准 chunked-prefill：`match_prefix` 恒 miss（`disable` 恒 True），`insert` 为 no-op；请求 KV 跟随请求生命周期，完成即整体 `free` |
| `SWAChunkCache` | `chunk_cache.py:115` | 支持 sliding window 的 ChunkCache，要求 allocator 是 `SWATokenToKVPoolAllocator`（或其 HiSparse 子类） |
| `PureSWAChunkCache` | `chunk_cache.py:142` | 全 SWA 模型：请求完成时跳过 decode 阶段已被 `_evict_swa` 释放的窗口区间，防止双重 free |

`base_swa_memory_pool.py` 的 `BaseSWAKVPool`（ABC）定义 SWA 子池契约：`register_mapping(full_to_swa_index_mapping)`、`translate_loc_from_full_to_swa`、`get_state_buf_infos`，供 `SWATokenToKVPoolAllocator` 与 PD 分离路径把 full/SWA 状态分开管理。

### index_key_cache.py（DSA indexer 旁路缓存）

`IndexKeyCache`（`index_key_cache.py:14`）服务于 DSA（DeepSeek 稀疏注意力）的量化 index-K 缓冲：按层维护 `(num_pages, page_size*(index_head_dim + index_head_dim//quant_block_size*4))` 的 GPU buffer，提供 `move`/`get_k_continuous`/`store_quantized`/`cpu_copy`/`load_cpu_copy`。`skip_topk_layers` 层复用上一层 top-k、不写 index-K，分配 0 行占位。它不是前缀树，而是随 KV 页一起迁移的索引数据。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
