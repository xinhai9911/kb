## 03-kvcache-prefix KV 缓存与前缀缓存对比（二）：分层缓存、显存分配与命中率

接 `kvcache-comparison.md`（块管理与前缀缓存）。本节覆盖分层/高级缓存、显存分配公式、命中率与复用模型差异。事实基准：vLLM `gpu_worker.py:475` 的 `determine_available_memory`；SGLang `hiradix_cache.py`、`kv_cache_configurator.py`、`pool_configurator.py`。

### 四、分层/高级缓存

| 维度 | vLLM V1 | SGLang |
|---|---|---|
| 分层缓存 | **无**。KV 只存在 GPU 内存；前缀缓存仅 `BlockPool` 单层。最高抽象是 `KVCacheCoordinator`（`kv_cache_coordinator.py`）：`NoPrefixCache`/`Unitary`（单组）/`Hybrid`（多组，迭代固定点收敛各注意力前缀命中），均共享同一 GPU `BlockPool` | **HiRadixCache**（`hiradix_cache.py:77`）继承 `RadixCache`：L1=GPU 树，L2=`token_to_kv_pool_host`（CPU host 池，MHA/MLA 各自 host 池类），L3=远端存储（页 SHA256 哈希寻址，`--hicache-storage-backend`） |
| 降级策略 | —（无跨层迁移） | LRU 淘汰不丢数据，按 write policy 逐级降级 GPU→host→storage：`write_through`（淘汰即降级，默认 `write_through_selective`）/`write_back`（标注将废弃）；`_inc_hit_count`（:983）达阈值 `write_through_threshold`（write_through=1 否则 2）触发 `write_backup`；backuped 节点必须是 root 起的连续前缀（:845） |
| 回载 | — | `load_back`/`init_load_back`（:1374）：沿 evicted 链收集 host 段，长度 ≥ `load_back_threshold`(=10) 且 ≤ `mem_quota` 才回载 GPU；调度器 prefill 前 `ready_to_load_host_cache`（:1514）等 `LayerLoadingEvent`；`host_hit_length` 计 host 命中 |
| L3 存储命中 | — | `query_storage_hit_length`（:1469，TP min 后页对齐）；`prefetch_from_storage`（:1771）入队时预取，命中 ≥ `prefetch_threshold`（默认 256）才分配 host 页；`check_prefetch_progress`（:1636）按 `prefetch_stop_policy` 终止 |
| 分块缓存变体 | — | radix 禁用时 `ChunkCache`（`chunk_cache.py:35`，match 恒 miss、请求生命周期随请求）；SWA 用 `SWAChunkCache`（:115）/`PureSWAChunkCache`（:142，跳过 decode 已释放窗口防双 free）；SWA 双子池 `SWATokenToKVPoolAllocator`（`allocator/swa.py`，full/swa 分别记账） |
| 实现选型 | 按 kv_cache_spec 注册表选 manager：`FullAttention`/`RSWA`/`SlidingWindow`/`ChunkedLocal`/`Mamba`/`CrossAttention`/`SinkFull`（`single_type_kv_cache_manager.py`） | `default_radix_cache_factory`：`ChunkCache` 族 → `RadixCacheCpp`（`SGLANG_EXPERIMENTAL_CPP_RADIX_TREE`）→ `UnifiedRadixCache`（`SGLANG_ENABLE_UNIFIED_RADIX_TREE`）→ hybrid 走 unified/PureSWA → `enable_hierarchical_cache` 走 `HiRadixCache` → 默认 `RadixCache` |
| 一致性 | 单 rank 独立，无跨 rank 缓存同步 | HiRadixCache 有 `_all_reduce`/`_pp_sync`（`hiradix_cache.py:1858` 附近）保证各 rank ack 计数一致 |

### 五、显存分配：profile 估算 vs mem_fraction_static 公式

| 步骤 | vLLM V1（`gpu_worker.py:475-563`） | SGLang（`kv_cache_configurator.py:1764` `_profile_available_bytes`） |
|---|---|---|
| 预算基准 | `requested_memory = 初始快照空闲内存 × gpu_memory_utilization`（默认 0.9） | `slack_gb = pre_model_load_memory × (1 − mem_fraction_static)`（默认约 0.9）；`rest_memory = 可用显存 − slack_gb − mm_reservation_gb` |
| 激活内存处理 | **实测**：`profile_run`（`gpu_model_runner.py:6563`）dummy forward 测峰值；`available_kv_cache = requested − non_kv_cache_memory(权重+激活峰值) − cudagraph_memory_estimate`（CUDA graph 估算默认开启，`VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPHS`） | **比例预留**：不实测激活，只从峰值内存里按比例留 slack；多模态经 `mm_runtime_reservation_gb`（:130）预扣；权重超预算报错并给 `minimum = 1 − available/pre`（:1794-1809） |
| 块数/token 容量 | `num_gpu_blocks = kv_cache字节 // (block_size × 每 token KV 字节)`，由 `get_kv_cache_config_from_groups` 按 kv_cache_groups 计算 | `max_total_num_tokens = available_bytes // cell_size`，再 `// page_size × page_size` 页对齐（`pool_configurator.py:415`）；cell_size 按注意力类型：MHA=`num_kv_heads×(head_dim+v_head_dim)×layers×dtype`（:327-333），MLA 走 `calculate_mla_kv_cache_dim`，DSA/MiniMax 加 indexer 成本 |
| 手动指定 | `--kv-cache-memory-bytes` 可跳过 profiling | `--max-total-tokens` 封顶；`--mem-fraction-static` 调比例 |
| 请求数约束 | 受 `max_num_seqs`/`max_num_reqs`（由 `max_num_seqs` 派生） | `resolve_max_num_reqs`（:1873）：`token_capacity/context_len×512` 夹 `[2048, 4096]`，再 `min(估算, token_capacity//2)` |
| 关键区别 | **运行时实测**更准但需 dummy forward + 编译；手动指定时仍须 profile 编译 | **纯静态公式**零实测，启动快；但对激活峰值、CUDA graph、批大小的变化不敏感，靠 `1−fraction` 的 slack 兜底 |

### 六、命中率与复用模型差异及对调度的影响

| 维度 | vLLM V1 | SGLang |
|---|---|---|
| 命中单位 | 整块哈希；fine-grained partial 可命中块内 `hash_block_size` 段（FullAttention manager） | token 段（页对齐），可精确到任意共享前缀长度 |
| 调度内嵌 | waiting 调度时逐请求 `get_computed_blocks`（上限 `num_tokens-1`）；命中请求走 `CachedRequestData` 增量（仅传 `num_computed_tokens` 之后） | `SchedulePolicy.calc_priority`（`schedule_policy.py:237`）内嵌 `match_prefix`；`CacheAwarePolicy`（lpm/dfs-weight）**先匹配再排序**；批内 `_compute_prefix_matches`（:321）对共享前缀请求临时降权，兄弟先跑把公共前缀写入 radix 树下轮批量命中 |
| 命中率影响因素 | 块边界对齐敏感：prompt 轻微变化即破坏整块哈希（partial 缓解）；跨请求前缀需块大小对齐才复用 | 树按实际 token 序列共享，任意公共前缀都聚合；chunked 时 `chunked=True` 抑制 hit_count 虚增 |
| 对 prefill 的收益 | 命中跳过对应 prefill，`num_computed_tokens` 直接推进；外部 KV connector 可异步加载进 `WAITING_FOR_REMOTE_KVS` | 命中段 KV 直接复用，`prefix_indices` 回填只算未命中部分；L2/L3 命中经 `load_back` 回载 |
| 抢占后 | `num_computed_tokens=0` 全量重算（前缀缓存命中除外） | 重新 `match_prefix`，树中已缓存前缀仍免重算 |
| 缓存感知策略 | **无**：调度策略仅 `FCFS`/`PRIORITY`，与 cache 解耦 | **有**：`lpm` 按 `-num_matched_prefix_tokens` 排序、`dfs-weight` 按子树请求数 DFS 序；`tree_cache.disable` 时自动降级 fcfs |
| 可观测性 | `PrefixCacheStats`（`record_prefix_cache_stats`）、`SchedulerStats.kv_cache_usage`、`KVCacheMetricsCollector`（采样生命周期/驱逐事件） | 无等价公开指标；`evictable_size()`/`protected_size()`/`hit_count` 内部可见 |

### 七、速查表

| 对比项 | vLLM V1 | SGLang |
|---|---|---|
| 块管理 | 块表 + `BlockPool` + `FreeKVCacheBlockQueue` | `ReqToTokenPool` + `TokenToKVPoolAllocator` + `KVCache` 三级索引 |
| 前缀缓存 | 扁平块哈希字典（`enable_prefix_caching`） | 前缀树 `RadixCache`（默认开） |
| 匹配粒度 | 整块/部分块（CoW） | token 段（页对齐，跨段拼接） |
| 淘汰 | LRU 近似（FIFO 尾插） | 7 策略 + `evictable_leaves` 只淘汰叶子 |
| 分层缓存 | 无 | HiRadixCache L1 GPU/L2 host/L3 storage |
| 显存分配 | profile_run 实测 + `gpu_memory_utilization` | `mem_fraction_static` 静态公式 + cell_size |
| 调度耦合 | 调度时逐请求查询，无 cache 感知策略 | 调度策略内嵌 `match_prefix`，cache-aware 排序 |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
