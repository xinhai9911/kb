## 特殊池与周边模块（SWA / unified / embedding / DSV4）

除标准 MHA/MLA 池外，`mem_cache/` 还承载滑动窗口、统一内存、多模态 embedding 缓存、DeepSeek V4 压缩态等专用存储。

### SWA 混合池

| 类 | 文件:行号 | 说明 |
|---|---|---|
| `BaseSWAKVPool` | `base_swa_memory_pool.py:9` | ABC：暴露 `swa_kv_pool` 子池 + `full→swa` 索引映射 + `translate_loc_from_full_to_swa` |
| `SWAKVPool` | `swa_memory_pool.py:19` | full 与 SWA 层分开两块池，层号按 `swa/full_attention_layer_ids` 划分 |
| `SWATokenToKVPoolAllocator` | `allocator/swa.py:20` | 双记账分配器：`full_available_size()` / `swa_available_size()` 分开查空 |
| `PureSWATokenToKVPoolAllocator` | `allocator/swa.py:416` | 纯 SWA（full 容量为 0），`available_size()` 只算 swa |

SWA 窗口外 token 由 `common.py:free_swa_out_of_window_slots`（52 行）批量归还：按 `swa_evicted_seqlen` 从窗口前缘推进，取 `req_to_token` 行切片 `token_to_kv_pool_allocator.free_swa()`；chunk cache 无 radix 树，逐出到窗口边界即可，radix 场景则保留到 `page_floor` 之下避免全墓碑叶（`common.py:75-89`）。

### unified 内存池（--enable-unified-memory）

`unified_memory_pool.py` 把 hybrid Mamba / hybrid SWA 的多个池放进**一个连续字节缓冲**：

| 类 | 行号 | 角色 |
|---|---|---|
| `SubPoolSpec`（MHA/MLA/Mamba） | 75/101/148/182 | 各子池的布局描述（层数、head、字节） |
| `UnifiedKVPool` | 217 | 单缓冲管理，按 spec 切分物理页 |
| `UnifiedMHATokenToKVPool` / `UnifiedMLATokenToKVPool` / `UnifiedMambaPool` | 452 / 602 / 711 | 虚拟槽位（virtual id）写入，物理地址由 unified allocator 翻译 |
| `UnifiedMambaSlotAllocator` | 856 | mamba 槽位分配（`multi_ended_allocator.py` 支撑） |
| `UnifiedHybridReqToTokenPool` / `UnifiedPoolBundle` | 952 / 1078 | 请求池 + 池 bundle |
| `UnifiedSWAKVPool` / `UnifiedSWAPoolBundle` | 1318 / 1562 | SWA 统一池 |

统一池的分配器在 `multi_ended_allocator.py`（2559 行）：`UnifiedMambaTokenToKVPoolAllocator` / `UnifiedSWATokenToKVPoolAllocator` 发放**虚拟 token id**，KV 写入经 `full_loc` 预解析物理位置（见 `KVWriteLoc`）。PD 分离部署对 unified 有限制：仅 MLA hybrid-Mamba 支持（`kv_cache_configurator.py:389-426`）。

### embedding 缓存（多模态）

| 组件 | 文件:行号 | 说明 |
|---|---|---|
| `EmbeddingStore`（ABC） | `embedding_store.py:14` | 按内容 hash 存/取预计算 vision/audio embedding，跨节点共享（`batch_get/batch_put/batch_is_exist`）；工厂注册 mooncake 后端（`embedding_store.py:123`） |
| `EmbeddingPool` | `embedding_cache_controller.py:166` | 每 modality 一个固定字节预算的页池，`RangePageAllocator` 偏好连续物理页 |
| `RangePageAllocator` | `embedding_cache_controller.py:59` | 空闲区间列表（`free_ranges`），分配时合并碎片 |
| `EvictableLRU` | 127 | 可逐出候选（READY + 零 pin）的 LRU 队列 |
| `EmbeddingCacheEntry` | 213 | hash → page_runs 映射，`ref_count` pin/unpin，`is_evictable = READY and ref_count==0` |
| `EmbeddingCacheController` | 344 | 异步 prefetch/insert（`AsyncCopyHandle`），host↔device 传输 |

页大小按 `TARGET_PAGE_BYTES=256KB` 反推（`compute_page_size`，`embedding_cache_controller.py:37`）；GPU 池与 host 池按 `VISION_POOL_RATIO=0.8` 划分。这解释了 `allocation-sizing.md` 中多模态预留的 `mm_runtime_reservation_gb`。

### DeepSeek V4 / HiSparse 专用池

| 类 | 文件:行号 | 说明 |
|---|---|---|
| `CompressStatePool` | `deepseek_v4_compress_state.py:83` | c4/c128 压缩注意力状态池：`(size, last_dim)` 的 kv+score 联合缓冲（`KVAndScore`），`ring_size` 按 ratio=4/128 与是否 spec 定（`get_compress_state_ring_size`，34 行）；`translate_from_swa_loc_to_state_loc` 做 SWA 页→状态槽换算 |
| `DeepSeekV4SingleKVPool` | `deepseek_v4_memory_pool.py:59` | DSV4 FP8 K（nope）+BF16 rope+scale 打包布局，584 字节/token（118-124 行断言） |
| `HiSparseC4DevicePool` | 177 | c4 池的 HiSparse 变体 |
| `DeepSeekV4IndexerPool` | 260 | 压缩 indexer 池 |
| `DeepSeekV4UnifiedKVPool` | 398 | DSV4 统一池（full/swa/c4/c128 分层条目） |
| `DeepSeekV4TokenToKVPool` | 463 | DSV4 分配器 + `BaseSWAKVPool` |
| `HiSparseDSATokenToKVPool` | `hisparse_memory_pool.py:28` | DSA indexer 的 HiSparse 版 |

DSV4-NPU 的 `ReqToTokenPool` 子类 `free()` 额外归还 c4/c128 状态页（`common.py:238-240` 注释），DSV4 allocator 经 `register_dsv4_allocator` 回写（`kv_cache_configurator.py:1729-1732`）。HiSparse 开启时 `host_to_device_ratio` 决定 indexer 上移 host 的比例（`pool_configurator.py:368-371`）。

### 事件与周边

| 组件 | 文件:行号 | 说明 |
|---|---|---|
| `KVCacheEventRecorder` | `events.py:38` | KV 放置事件（`BlockStored/BlockRemoved/AllBlocksCleared`）收集器，供 KV-aware 路由（dynamo）消费；按 `page_size` 分块发出，`enqueue` 对同构事件合并，`take` 原子取出 |
| `flush_cache.py` | 33 | 独立小工具：`python -m sglang.srt.mem_cache.flush_cache --url …` 调 `/flush_cache` HTTP 接口 |
| `kv_cache_builder.py` | 366 | KV 池构建辅助（radix cache 组装用） |
| `kv_cache_dtype.py` | 101 | KV dtype 解析（含 fp8/mxfp8/fp4 系列） |
| `kv_vmm_backing.py` | 278 | CUDA-VMM 虚拟地址预占（post-capture backing） |
| `mamba_checkpoint_pool.py` / `mamba_slot_fused.py` | - | Mamba checkpoint/融合槽位池 |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
