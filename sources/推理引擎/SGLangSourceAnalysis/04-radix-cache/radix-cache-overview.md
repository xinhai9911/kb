## RadixCache 前缀树缓存：数据结构与核心流程

本文基于 `sglang/srt/mem_cache/radix_cache.py`、`base_prefix_cache.py`。RadixCache 是 SGLang 默认的前缀缓存：把「token 序列 → KV cache 索引」的映射存成一棵**共享前缀的字典树**，让相同前缀的请求复用 GPU KV 块，省掉重复 prefill。所有缓存实现（`RadixCache`/`HiRadixCache`/`ChunkCache`/UnifiedRadixCache 等）都继承自统一抽象基类 `BasePrefixCache`（`base_prefix_cache.py:235`）。

### 统一接口层（base_prefix_cache.py）

| 类型 | 说明 |
|---|---|
| `BasePrefixCache`（ABC） | 抽象接口：`match_prefix`/`insert`/`evict`/`inc_lock_ref`/`dec_lock_ref`/`cache_finished_req`/`cache_unfinished_req`/`reset`，另有 `is_tree_cache()`/`is_chunk_cache()`/`evictable_size()`/`protected_size()` 等查询 |
| `MatchPrefixParams` / `MatchResult` | 匹配入参（`RadixKey` + mamba 用 `cow_mamba`/`req`）与结果；`MatchResult` 是 NamedTuple，携带 `device_indices`（命中的 KV 索引）、`last_device_node`/`last_host_node`/`best_match_node`、`host_hit_length` 等 |
| `InsertParams` / `InsertResult` / `EvictParams` / `EvictResult` | 插入/淘汰的入参与结果；`EvictResult.num_tokens_evicted` 上报实际释放 token 数 |
| `zero_match_result()` | 强制 miss（`SGLANG_RADIX_FORCE_MISS` 测试用）：把结果锚回 root，清空 `device_indices` |

`MatchResult` 中 `last_host_node` 在非 HiCache 下**必须等于** `last_device_node`；`best_match_node` 供 L2 host→device 的 `init_load_back` 作锚点（`base_prefix_cache.py:171` 注释）。

### 关键数据结构

**RadixKey**（`radix_cache.py:59`）：树的「边」标签，封装原始 token 序列（`array('q')`）：

| 字段 | 作用 |
|---|---|
| `token_ids` | 原始 token 序列（`array`） |
| `extra_key` | 调用方定义的缓存分类命名空间（如 LoRA id），不同 `extra_key` 的前缀**永不共享节点** |
| `cache_salt` | 缓存盐，与 `extra_key` 独立，命名空间化树内缓存与外部 KV 事件 |
| `is_bigram` | Eagle 投机解码视角：以相邻 token 二元组为逻辑单元（长度 = `n-1`） |
| `limit` | 原始 token 数上限（免切片，等价于 `token_ids[:limit]`） |

`RadixKey.match(other, page_size)` 求逻辑单元级共享前缀长度，用**指数搜索 + 二分**定位第一个分叉 token（`radix_cache.py:181`），避免长公共前缀上的逐 token Python 循环；`child_key(page_size)` 产出 hashable 的 dict key（首 `page_size` 个单元 + 命名空间）；`page_aligned(page_size)` 把长度向下取整到页边界。

**TreeNode**（`radix_cache.py:238`）：

```python
class TreeNode:
    children = defaultdict(TreeNode)   # child_key -> 子节点
    key: RadixKey          # 本边承载的 token 段
    value: torch.Tensor    # 本段对应的 GPU KV cache 索引（页对齐拷贝）
    lock_ref: int          # 被引用计数（>0 禁止淘汰）
    last_access_time / creation_time / hit_count
    host_ref_counter / host_value      # HiCache 用：host 侧备份与保护
    hash_value / event_hash_value      # 每页 SHA256（外部事件/存储键）
    priority                 # 优先级淘汰用（缺省 0，root 为 -sys.maxsize）
```

`node.evicted == (value is None)`，`node.backuped == (host_value is not None)`。`TreeNode.__lt__` 按 `last_access_time` 比较，供堆排序。

### match_prefix 匹配流程（radix_cache.py:377）

1. `key.maybe_to_bigram_view(self.is_eagle)` 翻转 bigram 标志（O(1)）；`self.disable` 或空 key 直接返回空结果。
2. `key = key.page_aligned(page_size)` 截到页边界。
3. `_match_prefix_helper(root, key)`：沿 `child_key` 下钻，每层用 `child.key.match(key)` 求段前缀长：
   - 匹配不足一段 → `_split_node` 把节点从 `prefix_len` 处**分裂**（新父节点继承子节点 priority/hit_count，value 分段 clone），返回。
   - 完整匹配 → `value.append(child.value)`，key 前进，继续下钻。
4. `torch.cat(value)` 拼接所有命中的 KV 索引，`last_device_node` = 终端节点。分裂使后续匹配边界更精确，**不复制数据本身**。
5. 沿途刷新 `last_access_time`（供 LRU/LFU 等策略用）。

### insert 插入流程（radix_cache.py:437 / _insert_helper :738）

- key/value 先做 bigram 视图与页对齐，`value = value[:len(key)]`；`page_size>1` 时价值也仅保留页对齐前缀。
- 从 root 沿树下钻：完全匹配的节点 `hit_count+=1`（`chunked=True` 时跳过，避免分块请求自我引用膨胀命中计数，`_inc_hit_count` :730）；部分匹配处 `_split_node` 后插入新段。
- 尾部剩余 key 新建 `TreeNode`，`node.children[child_key] = new_node`，`value.clone()` 存入，`evictable_size_ += len(key)`，并更新叶子状态。
- 返回 `prefix_len`（已存在的共享前缀长度），调用方据此把**重复分配的** KV 段 `free` 回去（见 cache_finished_req）。

### 引用计数与叶子管理

- `inc_lock_ref(node)`（:623）：沿 node 到 root 全路径 `lock_ref += 1`；首个引用把 `evictable_size_` 减掉、`protected_size_` 加上，逐节点维护 `evictable_leaves`。锁住的节点（正被请求使用的 KV）不可淘汰。
- `dec_lock_ref`（:638）对称递减；`req.cache_protected_len` 之前的受保护前缀不属于请求释放范围。
- `_update_leaf_status`（:821）：无子节点（或子节点全 evicted）且未上锁、未 evicted 的节点进 `evictable_leaves` 集合，这是淘汰的唯一候选池。

### 与调度器、内存池的衔接

| 调用方 | 调用点 | 作用 |
|---|---|---|
| `Req.init_next_round_input` | `managers/schedule_batch.py:1353` | prefill 前 `tree_cache.match_prefix(...)` 求最长可复用前缀，结果写入 `req.prefix_indices`/`req.last_node`/`cache_protected_len` 等 |
| `alloc_token_slots` / `alloc_paged_token_slots_extend` | `mem_cache/allocation.py:151/174` | 先 `evict_from_tree_cache(tree_cache, num_tokens)` 只淘汰缺口，再 `allocator.alloc/alloc_extend` |
| `maybe_cache_unfinished_req` | `mem_cache/common.py:107` | chunked prefill 每步后 `cache_unfinished_req` 把已算好的前缀写入树 |
| `cache_finished_req` | 请求完成路径 | 把 `origin_input_ids + output_ids` 全序列插入，释放重复段与未对齐尾部 |
| `SchedulePolicy.add_req/_req_inc_lock_ref` | `managers/schedule_policy.py:957` | 请求进批时 `inc_lock_ref` 保护已匹配前缀的 KV 不被淘汰 |

内存池侧：`req_to_token_pool`（`ReqToTokenPool`，`memory_pool.py:256`）是 `(req_pool_idx, token 位置)` 的二维表，`tree_cache.match_prefix` 的 KV 索引最终写入其中供模型读取；`token_to_kv_pool_allocator`（`BaseTokenToKVPoolAllocator`，`allocator/base.py:27`）管理 KV 物理槽位，`radix_cache.py:610` 淘汰时 `free_segment(x.value, start_pos=0)` 归还。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
