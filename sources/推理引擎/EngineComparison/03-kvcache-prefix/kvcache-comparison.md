## 03-kvcache-prefix KV 缓存与前缀缓存对比（一）：块管理与前缀缓存

本模块对比 vLLM V1 与 SGLang 的 KV 缓存管理与前缀缓存。事实基准：vLLM `kv_cache_manager.py`/`kv_cache_utils.py`/`block_pool.py`（`vllm/vllm/v1/core/kv_cache_manager.py`）与 SGLang `radix_cache.py`/`base_prefix_cache.py`/`memory_pool.py`（`sglang/srt/mem_cache/`）。显存分配与分层缓存见 [_part2](kvcache-comparison_part2.md)。

### 一、KV 块管理与寻址模型

| 维度 | vLLM V1 | SGLang |
|---|---|---|
| 核心抽象 | 固定大小 KV **block** + 每请求 **block table**；`KVCacheBlock`（`kv_cache_utils.py`）只是元数据（`block_id`/`ref_cnt`/`_block_hash`），GPU 张量在统一 `BlockPool`（`block_pool.py`） | **三级索引**：`ReqToTokenPool`（`memory_pool.py:256`）请求→token 位置→KV 索引；`TokenToKVPoolAllocator`（`allocator/base.py:27`）token→物理槽位；`KVCache`（`memory_pool.py:1624`）数据张量。池只管理整数索引 |
| 粒度体系 | `block_size`（实际块大小）×`hash_block_size`（哈希粒度，多组为 GCD）×`scheduler_block_size`（调度 LCM）；按 `kv_cache_group` 分组（每种注意力类型一组） | `page_size`（默认 1；paged allocator 下 >1）；chunk 化 prefill 与页对齐联动 |
| 逻辑→物理映射 | 块表（`v1/worker/block_table.py`）：逻辑块号→物理 block id；分配结果以 `KVCacheBlocks`（按 group 分组的块序列）暴露 | `req_to_token[req_pool_idx, pos]` 直接存 KV 槽位索引（页对齐时展开为 `out_pages*page_size+arange`），无独立块表 |
| 空闲管理 | `FreeKVCacheBlockQueue` 双向链表 O(1) 中段删/取头/增尾：无哈希块头插（LIFO 保局部性），有哈希块尾插（LRU 序） | allocator 三成员：`free_pages`/`release_pages`/`free_group`（batch COW 惰性释放）；`available_size()`=页数×`page_size`（`allocator/base.py:57`） |
| 分配入口 | `KVCacheManager.allocate_slots(req, num_new_tokens)` 三阶段布局 `<comp>\|<new_comp>\|<ext_comp>\|<new>\|<lookahead>`；`watermark` 为 WAITING/PREEMPTED 预留空闲块比例 | `alloc_for_extend`（`allocation.py:281`）先 `alloc_req_slots` 再按 page_size 走 `alloc_token_slots`/`alloc_paged_token_slots_extend`；`alloc_for_decode`（:512）每请求 1 token；`alloc_for_spec_decode`（:646）页对齐批量 |
| 共享/引用 | `KVCacheBlock.ref_cnt`；前缀命中 `touch`（0→1 移出空闲队列，`ref_cnt+=1`）；占用中块不可分配 | radix 树 `inc_lock_ref` 沿 node→root 全路径加锁（`radix_cache.py:623`），锁定的 KV 不可淘汰；`ReqToTokenPool` 行 0 为 dummy 填充行防越界 |
| 释放路径 | `free_blocks` 逆序归还（按有无哈希分流 FIFO/LIFO）；AsyncScheduler 经 `last_sched_seq` 围栏延迟释放防在途写块 | 请求结束→`cache_finished_req` 插树并 free 重复段→`_release_overallocated_kv_indices`→`req_to_token_pool.free`（`common.py:198`） |
| 计算进度 | `num_computed_tokens` 显式推进，`num_tokens_with_spec` 为调度目标（隐式覆盖 chunked prefill） | 无等价字段；复用长度由 radix `match_prefix` 回填的 `prefix_indices`/`cache_protected_len` 表达 |

> 关键差异 ①：vLLM 是「块表 + 物理块池」两段寻址，块是 KV 复用与调度决策的最小单元；SGLang 是「请求→token→KV 页」三级索引，token 即寻址单元，radix 树直接操作连续 token 段，chunk 化只是调度侧的切分约定。

### 二、前缀缓存机制

| 维度 | vLLM prefix caching | SGLang RadixCache |
|---|---|---|
| 数据结构 | **链式块哈希**：`BlockHash = NewType(..., bytes)`（`kv_cache_utils.py`）逐块链接；`cached_block_hash_to_block: {block_hash(+group_id): block}` 字典，同哈希可对多块（`dict[int, KVCacheBlock]`） | **前缀树**：`RadixKey`（`radix_cache.py:59`）作边标签（`token_ids`/`extra_key`/`cache_salt`/`is_bigram`/`limit`）；`TreeNode`（:238）存段 KV 索引、`lock_ref`、访问/创建时间、`hit_count`、页哈希 |
| 启用开关 | `--enable-prefix-caching`；关闭或注意力无关模型走 `KVCacheCoordinatorNoPrefixCache` | 默认开启；禁用后由 `default_radix_cache_factory`（`registry.py:80`）落到 `ChunkCache` 族 |
| 匹配算法 | 整块哈希比对：`cache_full_blocks` 写满登记；`cache_partial_block` 支持块内 `hash_block_size` 边界的**部分条目**（fine-grained）；`get_computed_blocks` 最长命中，上限 `num_tokens-1`（末 token 必须重算取 logits） | `RadixKey.match` 指数搜索+二分定位分叉 token（`radix_cache.py:181`）；`match_prefix`（:377）沿 `child_key` 下钻，段内部分匹配时 `_split_node` 分裂（不复制数据）；`torch.cat(value)` 拼接命中索引；先 `page_aligned` 截到页边界 |
| 插入时机 | 块写满即登记哈希（阻塞时以 `block_mask` 跳过 SWA/Mamba 稀疏组）；部分块经 `_cache_partial_tail_block` | `cache_finished_req`（:459）插 `origin_input_ids+output_ids` 全序列；chunked prefill 每 chunk 后 `cache_unfinished_req`（:516，`chunked=True` 抑制 hit_count 虚增）；未对齐残页不入树 |
| 命中粒度 | 整块为主；partial-hit 经 CoW 复制（`take_kv_cache_block_copies` 取 `KVCacheBlockCopy(src,dst)`） | 段级（页对齐），一次可跨多段命中；Eagle bigram 视图下按二元组单元 |
| 命名空间 | `cache_salt`（`Request` 构造参数，`sequence-model_part1.md`） | `extra_key`（如 LoRA id）+ 独立 `cache_salt`；不同命名空间的前缀**永不共享节点** |
| 共享前缀保护 | `touch` 后 ref_cnt 累加，命中块被复用（不被错误归还） | `inc_lock_ref`/`dec_lock_ref`（:623/:638）；`req.cache_protected_len` 之前的受保护前缀不在请求释放范围 |

### 三、淘汰策略

| 维度 | vLLM | SGLang |
|---|---|---|
| 候选池 | 有哈希的块在 `FreeKVCacheBlockQueue` 尾端（FIFO 序近似 LRU）；`evict_blocks` 仅按 block_id 从前缀哈希表驱逐，不改变池内占用 | `evictable_leaves`（`_update_leaf_status` :821）：无子节点、未上锁、未 evicted 的叶子；**只从叶子淘汰**，父节点变新叶子后补入堆逐层收缩 |
| 策略 | LRU（尾插天然序）；无策略可选项 | 7 种（`evict_policy.py`）：`LRU`（默认，按 `last_access_time`）/`LFU`/`FIFO`/`MRU`/`FILO`/`Priority`/`SLRU`（两段 protected/probationary）；priority 沿路径向上传播（`radix_cache.py:752`） |
| 触发时机 | 分配时 `_maybe_evict_cached_block`（`get_new_blocks` 内清哈希发 `BlockRemoved`）；`reset_prefix_cache` 全清（仅当所有块空闲） | 调度侧 `evict_from_tree_cache`（`common.py:114`）先查 `allocator.available_size()`，只按缺额淘汰不整批清理；`alloc_token_slots` 前调用 |
| 事件 | `BlockRemoved`（`vllm/distributed/kv_events.py`）经 `kv_event_publisher` 发布 | `kv_events.record_remove(x)` 发布 BlockRemoved（若启用） |

> 关键差异 ②：vLLM 前缀缓存是**扁平哈希字典**，命中以块为单位、靠 `ref_cnt`+队列序管理；SGLang 是**字典树**，命中以 token 段为单位、可精确到任意公共前缀长度，且能区分「可淘汰叶子」做分级回收——这是 SGLang 复用粒度更细、vLLM 实现更简单直接的根源。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
