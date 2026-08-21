## 内存池结构总览（mem_cache）

SGLang 的显存管理位于 `sglang/srt/mem_cache/`，围绕「请求→token→KV 页」三级索引组织，由三种池协作：

| 池 | 类（文件） | 数据结构 | 角色 |
|---|---|---|---|
| 请求池 | `ReqToTokenPool`（`memory_pool.py:256`） | `(size+1, max_context_len)` 的 int32 张量 | 请求 → 该请求每个 token 位置的 KV 索引（`req_to_token`） |
| 分配器 | `BaseTokenToKVPoolAllocator`（`allocator/base.py:27`）及子类 | 自由页/释放页张量 + 惰性 free 组 | token 数 → 物理 KV 槽位索引（`out_cache_loc`） |
| KV 数据池 | `KVCache`（`memory_pool.py:1624`）及子类 | 每层一个 K/V 张量 | 保存真实 K/V/scale 数据，供 attention 后端索引 |

分配器持有 `_kvcache` 引用（`allocator/base.py:42`）；radix cache（04 模块）同时持两个池，负责请求完成后的归还。池本身不感知 token 语义，只管理整数索引。

### ReqToTokenPool：请求→token 槽位

`ReqToTokenPool.__init__`（`memory_pool.py:261`）：

```python
self._alloc_size = size + 1                    # 行 0 为 dummy 填充行
self.req_to_token = torch.zeros(
    (self._alloc_size, max_context_len), dtype=torch.int32, device=device)
self.free_slots = list(range(1, self._alloc_size))   # Python 列表栈
self.req_generation = torch.zeros(self._alloc_size, dtype=torch.int64)
```

- **slot 0 保留**：cuda-graph padded batch 的 `req_pool_indices` 默认填 0，dummy 读/写落在 0 行，避免越界。
- 分配：`alloc()`（`memory_pool.py:291`）从 `free_slots` **尾部 pop**（O(need)），已持有 `req_pool_idx` 的请求（如 chunked prefill 跨 chunk）复用原槽，`req_generation` 计数自增。
- 释放：`free()`（`memory_pool.py:325`）仅把索引 append 回 `free_slots`，不清理数据；`clear()` 整体重置。
- 行宽 = `max_context_len + extra`，`extra` 由 `allocation_sizing.py:get_req_to_token_extra_context_len()` 给出（spec 解码的越界余量）。

### allocator 族：token→KV 页索引

基类以三个成员维护空闲空间（`allocator/base.py:45-48`）：

| 成员 | 语义 |
|---|---|
| `free_pages` | 可直接分配的页/槽位索引张量（分配从头取） |
| `release_pages` | 待合并的释放索引（仅 `need_sort`/PD 分离部署时使用） |
| `free_group` | free-group（batch COW）模式下暂存的惰性释放列表 |

`available_size()`（`allocator/base.py:57`）= `(len(free_pages)+len(release_pages)) * page_size`。

按 page_size 与硬件分派（`kv_cache_configurator.py:_build_token_to_kv_pool_allocator`，1606 行）：

| 分支条件 | 分配器类 | 关键行为 |
|---|---|---|
| `page_size==1` 且非 DCP | `TokenToKVPoolAllocator`（`allocator/token.py:28`） | `free_pages=arange(1,size+1)`，分配即 `free_pages[:n]`；释放 append（need_sort 时入 `release_pages`） |
| `page_size>1` 或 DCP | `PagedTokenToKVPoolAllocator`（`allocator/paged.py:105`） | 索引是页号；释放经 `torch.unique(free_index // page_size)` 去重；`alloc_extend/alloc_decode` 走 Triton 内核 |
| hybrid SWA | `SWATokenToKVPoolAllocator` / `PureSWA…`（`allocator/swa.py:20/416`） | 双子池 full/swa 分别记账 |
| HiSparse | `HiSparseTokenToKVPoolAllocator`（`allocator/hisparse.py`） | 带 host 磁盘分层 |
| NPU/DSV4 | `NPUPaged…`、`DSV4NPUTokenToKVPoolAllocator` | 返回 `DSV4OutCacheLoc` bundle |

**PagedTokenToKVPoolAllocator 的分配**（`allocator/paged.py:149-259`）：`alloc()` 取整页并把页号展开为 token 索引（`out_pages[:,None]*page_size + arange(page_size)`）；`alloc_extend/alloc_decode` 由 `alloc_extend_kernel`/`alloc_decode_kernel`（`sgl_kernel`）在 GPU 上算 `last_loc` 续页。`free_segment`（`paged.py:273`）用「跨页首 token + 步长为页的切片」代替 `torch.unique`，避免 device sync。

### KVCache 池族：KV 数据张量

`KVCache`（`memory_pool.py:1624`）抽象出 `get_key_buffer/get_value_buffer/set_kv_buffer/move_kv_cache`。关键属性：`size`（token 容量）、`page_size`、`layer_num`、`store_dtype`（fp8 系列以 `uint8` 存储，`memory_pool.py:1645-1649`，因 `index_put` 不支持 fp8）。子类按模型注意力类型划分：

| 池类 | 行号 | 适用 |
|---|---|---|
| `MHATokenToKVPool` | 1755 | 标准 MHA；NHD/HND 两种布局；缓冲 `(size+page_size, head_num, head_dim)`（HND 折叠为 `(num_pages, H, page, D)`，`memory_pool.py:2045-2056`） |
| `PageMajorMHATokenToKVPool` | 3135 | page-major 布局（`SGLANG_USE_PAGE_MAJOR_KVCACHE`） |
| `MHATokenToKVPoolFP4` / `MXFP8` | 2981 / 3289 | 量化 KV，带 scale 缓冲 |
| `MLATokenToKVPool` / `FP4` | 3932 / 4208 | DeepSeek MLA（latent + rope 分离，`set_mla_kv_buffer`） |
| `DSATokenToKVPool` | 4348 | DSA（DeepSeek V3.2）indexer |
| `HybridLinearKVPool` | 3577 | Mamba/linear-attention 混合 |
| `MiniMaxSparseKVPool` | 4679 | MiniMax 稀疏注意力（主池+单头 indexer 池） |
| `NoOpMHATokenToKVPool` | 2867 | prefill-only 关闭 KV cache 的 no-op |
| `MHATokenToKOnlyPool` | 4580 | 仅 K 不存 V |

缓冲多一层 `+page_size` padding（`memory_pool.py:2052`）：slot 0 所在页吸收 dummy padded-token 写入，同时保证页对齐。`set_kv_buffer` 的写入位置由 `KVWriteLoc`（`memory_pool.py:1547`）打包 `loc / swa_loc / full_loc` 三元组，供普通/SWA/统一池一个调用多路写。

### 与调度、radix cache 的衔接

分配入口在 `allocation.py`，调度器（03 模块）在每个 step 调用：

| 函数 | 行号 | 用途 |
|---|---|---|
| `alloc_for_extend` | 281 | prefill：先 `alloc_req_slots`（`allocation.py:230`，失败抛 `RuntimeError` 提示调整 `--max-running-requests`），再按 page_size 走 `alloc_token_slots`/`alloc_paged_token_slots_extend`，最后 `write_cache_indices` 把 `out_cache_loc` 写进 `req_to_token` 行 |
| `alloc_for_decode` | 512 | decode：每请求 1 个 token（或 `token_per_req`），直接写 `req_to_token[req_pool_indices, seq_lens]` |
| `alloc_for_spec_decode` | 646 | spec 解码批量分配，`nxt_kv_lens` 页对齐，Triton `assign_req_to_token_pool` 回写 |
| `alloc_token_slots` | 151 | 分配前先 `evict_from_tree_cache`（`common.py:114`）按缺额触发 radix 逐出，OOM 时打印 `available_and_evictable_str` |

释放链路在 `common.py:release_kv_cache`（198 行）：请求结束 → `tree_cache.cache_finished_req`（04 模块，插入 radix 树并 free 重复 KV）→ `_release_overallocated_kv_indices`（244 行，spec 解码整体分配的超额尾部）→ `req_to_token_pool.free(req)`。radix 树节点被逐出时调用 `token_to_kv_pool_allocator.free()` 归还页（对应 `allocation.py:155` 的 evict 预估）。

free-group 机制（`allocator/base.py:63-75`）：batch COW 场景先 `free_group_begin()` 收集 `free_group`，`free_group_end()` 统一 `torch.cat` 归还，避免同一页被同批多次归还。`KVWriteLoc` 中 `full_loc`（统一内存池物理位置）在 attention metadata 一次性解析（`memory_pool.py:1551-1565`）。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
