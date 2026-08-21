## HiRadixCache 分层缓存（L1 GPU / L2 Host / L3 Storage）

`HiRadixCache`（`hiradix_cache.py:77`）继承 `RadixCache`，在普通 radix 树（L1，GPU KV）之上叠加两层：L2 为 CPU host 内存池（`mem_pool_host`），L3 为远端存储后端（`--hicache-storage-backend`）。核心思路：**LRU 淘汰不直接丢数据，而是按 write policy 逐级降级**——GPU → host → storage；命中时反向 `load_back` 升回 GPU。本文覆盖其与普通 RadixCache 的差异、淘汰/回载流程、与调度衔接。

### 分层架构与初始化（hiradix_cache.py:79）

| 层 | 载体 | 用途 |
|---|---|---|
| L1 | 继承自 `RadixCache` 的树 + `token_to_kv_pool_allocator` | 设备 KV，节点 `value` 非空（`evicted=False`） |
| L2 | `token_to_kv_pool_host`（`HostKVCache` 子类） | 节点 `host_value` 非空（`backuped=True`）；按 kv_cache 类型选择 MHA/MLA host pool 类，或用 `attach_hybrid_dsa_pool_to_hiradix_cache` 挂载 DSA/MiniMax 混合池 |
| L3 | `HiCacheController.storage_backend`（由 `StorageBackendFactory` 创建） | 远端存储，按页 SHA256 哈希寻址，可运行时 attach/detach |

`HiCacheController`（`managers/cache_controller.py:262`）是异步 IO 引擎：`write_queue`/`load_queue` 批处理 D→H、H→D 传输，经 `L2TransferEngine`（`l2_transfer.py`）提交；`ack_write_queue`/`ack_load_queue` 保存完成的 ack；`prefetch_thread`/`backup_thread`/`prefetch_io_aux_thread` 三个 daemon 线程处理 L3 IO。write policy 三选一：`write_through` / `write_through_selective`（默认）/ `write_back`。

### 与 RadixCache 的差异（重点）

| 维度 | RadixCache | HiRadixCache |
|---|---|---|
| `_match_prefix_helper` | 只取 `value` | 跳过 `evicted` 节点的 value，可命中 host 段（`hiradix_cache.py:1858`） |
| `match_prefix` 结果 | `last_host_node == last_device_node` | 额外回溯：沿 `evicted` 链累加 `host_hit_length`，`last_host_node` 锚到最近的 `backuped` 祖先（:1738） |
| `_split_node` | 只 split `value` | 同时 split `host_value`/`hash_value`，并处理 split 时的 write-through ack 替换 |
| `insert` | 新段直接存 | 若存储/事件启用，算 `hash_value`；`write_policy != write_back` 时触发 `_inc_hit_count` 写回检查 |
| 淘汰 | 删除叶子即释放 | 区分 `_evict_regular`（无备份）/`_evict_backuped`（降级） |
| TP/PP | 无跨 rank 同步 | `_all_reduce`/`_pp_sync` 保证各 rank 一致推进 ack 计数 |

### 写回触发：_inc_hit_count（hiradix_cache.py:983）

```python
if self.cache_controller.write_policy == "write_back" or chunked: return
node.hit_count += 1
if not node.backuped and node.hit_count >= self.write_through_threshold:
    self.write_backup(node)   # 阈值：write_through=1，否则 2
```

`write_backup`（:841）调 `cache_controller.write(device_indices, node_id)` 申请 host 页并排队 D→H；成功则 `node.host_value` 赋值、`_track_write_through_node` 登记、`inc_lock_ref` 保护。写回不变量：**backuped 节点必须是从 root 起的连续前缀**（父未 backup 则跳过，:845）。写 back 模式下 `_inc_hit_count` 不计数、不写回。

### 淘汰：write_through vs write_back（evict, :1189）

- **write_through / write_through_selective**（`_evict_write_through` :1213）：淘汰时**不 stage 任何东西**。对堆顶叶子：`backuped` → `_evict_backuped`（释放 GPU 槽，host 副本保留）；否则 `_evict_regular`（直接 `free` GPU）。被淘汰节点的 host 副本之后由 `evict_host`（:1339，基于 `evictable_host_leaves`）按需清理。
- **write_back**（`_evict_write_back` :1231，标注将废弃）：`backuped` 节点降级；未 backup 的**先写回 host 再摘除**（staged 批量 flush）；host 内存不足则 `_drop_subtree_no_host` 整棵子树丢弃并告警。

`evict_host` 只淘汰 `evicted`（GPU 已释放）节点的 host 值，保护 `host_ref_counter > 0` 的节点，逐层把父节点补入 host 淘汰堆。

### 回载 load_back / init_load_back（:1374）

`load_back(node, mem_quota)`：从 `node` 沿 `evicted` 链向上收集 `nodes_to_load`，`torch.cat` host 索引后：长度 < `load_back_threshold`(=10) 或超过 `mem_quota` 则放弃；否则 `cache_controller.load` 申请 GPU 槽、排队 H→D，成功后把 `device_indices` 按段回填 `node.value`，`evictable_size_` 恢复，`inc_lock_ref(last_hit_node)`。GPU 不足时先 `self.evict(...)` 腾空间再重试。调度器 `ready_to_load_host_cache()`（:1514）在 prefill 前调用 `controller.start_loading()` 返回 producer index，模型按层等待 `LayerLoadingEvent`。

### L3 存储命中与预取（enable_storage 时）

- `query_storage_hit_length`（:1469）：用页哈希问 `_storage_hit_query`，TP 同步取 min 后页对齐返回命中长度。
- `prefetch_from_storage`（:1771）：调度器 `_prefetch_kvcache`（`scheduler.py:2721`）在请求入队时把「未覆盖输入」发给 prefetch 线程；命中数达标（`>= prefetch_threshold`，默认 256）才分配 host 页，否则 `_revoke_pending_prefetch`。
- `check_prefetch_progress`（:1636）：按 `prefetch_stop_policy`（`best_effort`/`wait_complete`/`timeout`）判断可终止，把已取页 `_insert_helper_host` 挂成 `value=None` 的 host 节点，`prefetch_loaded_tokens_by_reqid` 记录实际 L3 命中。
- `check_hicache_events`（:1521）：调度器每轮事件循环调用，用 `_sync_hicache_ready_counts` 对 `ack_write_queue`/`ack_load_queue`/storage 队列长度做 TP all-reduce（MIN），再统一 `writing_check`/`loading_check`，保证所有 rank 消费一致的 ack 数（PP 下走 `_pp_sync` 串联）。

### 缓存实现选型（registry.py）

`default_radix_cache_factory`（`registry.py:80`）按优先级：radix 禁用 + chunk → `ChunkCache` 族；`SGLANG_EXPERIMENTAL_CPP_RADIX_TREE` → `RadixCacheCpp`（`radix_cache_cpp.py:35`，C++ 树封装，不支 cache_salt/kv events）；`SGLANG_ENABLE_UNIFIED_RADIX_TREE` → `UnifiedRadixCache`；hybrid SWA/SSM → unified 或 `PureSWARadixCache`；`enable_hierarchical_cache` → MHA/MLA 模型用 `HiRadixCache`（hybrid/DSA 走 unified）；否则普通 `RadixCache`。`--radix-cache-backend` 可注册插件工厂。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
