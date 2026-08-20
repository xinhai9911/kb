## CacheConfig KV Cache 配置

`CacheConfig`(`vllm/config/cache.py`,约 310 行)管理 KV cache 的块大小、dtype、显存占用与前缀缓存。默认块大小 `DEFAULT_BLOCK_SIZE=16`;`block_size=None` 时经 `_apply_block_size_default` 解析为默认值并记录 `user_specified_block_size`。

| 参数名 | 类型 | 必选 | 说明 |
|--------|------|------|------|
| `block_size` | `integer` | 否 | 连续 cache 块包含的 token 数,>=1,默认 16 |
| `prefix_match_unit` | `integer \| None` | 否 | 前缀缓存命中可落点的最细 token 边界 |
| `gpu_memory_utilization` | `number` | 否 | 模型执行器可用 GPU 显存比例,默认 0.92,(0,1] |
| `cache_dtype` | `CacheDType` | 否 | `auto`/`float16`/`bfloat16`/`fp8`(`=fp8_e4m3`)/`fp8_e5m2`/`fp8_inc`/`nvfp4` 及 per-token-head 量化类型 |
| `is_attention_free` | `boolean` | 否 | 无注意力模型标记,与 ModelConfig 保持一致 |
| `num_gpu_blocks_override` | `integer \| None` | 否 | 覆盖 profile 出的 GPU block 数(测试抢占用) |
| `sliding_window` | `integer \| None` | 否 | 滑动窗口大小(由 ModelConfig 复制) |
| `enable_prefix_caching` | `boolean` | 否 | 是否启用前缀缓存,默认 `True` |
| `prefix_caching_hash_algo` | `PrefixCachingHashAlgo` | 否 | `sha256`/`sha256_cbor`/`xxhash`/`xxhash_cbor`;xxhash 更快但非加密哈希,多租户有碰撞风险 |
| `prefix_cache_retention_interval` | `integer \| None` | 否 | 滑窗/Mamba 前缀检查点保留间隔(`VLLM_PREFIX_CACHE_RETENTION_INTERVAL` 已弃用) |
| `kv_cache_dtype_skip_layers` | `array` | 否 | 跳过 KV 量化的层(索引如 `'0'` 或类型如 `'sliding_window'`) |
| `mamba_block_size` | `integer \| None` | 否 | mamba cache 块大小,须为 8 的倍数(对齐 causal_conv1d) |
| `mamba_cache_dtype` | `MambaDType` | 否 | mamba cache(conv+ssm)dtype,`auto` 从模型推断 |
| `mamba_ssm_cache_dtype` | `MambaDType` | 否 | 仅 ssm 状态的 dtype |
| `mamba_cache_mode` | `MambaCacheMode` | 否 | `none`(无前缀缓存)/`all`/`align`(每调度步末 token) |
| `replayssm_buffer_len` | `integer` | 否 | ReplaySSM 历史缓冲 B,默认 16 |
| `use_replayssm` | `boolean` | 否 | ReplaySSM 解码内核(需 triton mamba 后端) |
| `kv_sharing_fast_prefill` | `boolean` | 否 | KV 共享(YOCO 类)跳过 prefill 层 |
| `kv_cache_memory_bytes` | `integer \| None` | 否 | 每 GPU KV cache 字节数,指定后忽略 `gpu_memory_utilization` |
| `kv_offloading_size` | `number \| None` | 否 | KV cache CPU offload 缓冲 GiB(TP>1 时按总大小) |
| `kv_offloading_backend` | `KVOffloadingBackend` | 否 | `native`/`lmcache` |
| `num_gpu_blocks` / `num_cpu_blocks` | `integer \| None` | 否(init=False) | profile 后分配到的 GPU/CPU 块数 |
| `kv_cache_size_tokens` / `kv_cache_max_concurrency` | init=False | 否(init=False) | 每 DP 引擎 token 容量(组感知)/最大并发 |

## SchedulerConfig 调度器配置

`SchedulerConfig`(`vllm/config/scheduler.py`,约 285 行)定义调度策略、批处理与预填充参数。两个 `InitVar` 必填:`max_model_len`(模型最大长度)、`is_encoder_decoder`(是否编码器-解码器)。`default_factory()` 为 VllmConfig 提供缺省(`max_model_len=8192`、`is_encoder_decoder=False`)。

| 参数名 | 类型 | 必选 | 说明 |
|--------|------|------|------|
| `runner_type` | `RunnerType` | 否 | `generate`/`pooling`/`draft` |
| `max_num_batched_tokens` | `integer` | 否 | 单次迭代最大 token 数,默认 2048(DP 批 256) |
| `max_num_scheduled_tokens` | `integer \| None` | 否 | 单次迭代允许调度 token 数,缺省等于 `max_num_batched_tokens`(投机解码可能更小) |
| `max_num_seqs` | `integer` | 否 | 单次迭代最大序列数,默认 128 |
| `long_prefill_token_threshold` | `integer` | 否 | chunked prefill 的长提示阈值,0 不设限(默认) |
| `enable_chunked_prefill` | `boolean` | 否 | 启用分块预填充,默认 `True` |
| `policy` | `SchedulerPolicy` | 否 | `fcfs`/`priority` 调度策略 |
| `disable_chunked_mm_input` | `boolean` | 否 | 多模态输入不部分调度(V1) |
| `scheduler_cls` | `str \| type \| None` | 否 | 自定义调度器类或 `mod.custom_class` 路径 |
| `disable_hybrid_kv_cache_manager` | `boolean \| None` | 否 | 混合注意力层是否分配相同 KV 大小 |
| `scheduler_reserve_full_isl` | `boolean` | 否 | 准入前检查完整输入长度能否容纳,默认 `True` |
| `watermark` | `number` | 否 | KV 空闲水位比例,[0,1),默认 0 |
| `prefill_schedule_interval` | `integer` | 否 | DP 场景每 N 步准入 prefill,默认 1 |
| `async_scheduling` | `boolean \| None` | 否 | 异步调度(`scheduler_cls` 缺省时据此选 AsyncScheduler/Scheduler) |
| `stream_interval` | `integer` | 否 | 流式输出缓冲,默认 1 |

`__post_init__` 校验:`max_num_batched_tokens >= max_num_seqs`;未启用 chunked prefill 时 `max_num_batched_tokens` 不得小于 `max_model_len`;编码器-解码器强制关闭 chunked prefill 与禁用混合输入。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
