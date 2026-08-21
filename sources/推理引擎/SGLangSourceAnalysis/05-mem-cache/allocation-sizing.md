## 静态显存分配策略（allocation-sizing）

KV 池容量在启动期一次性算出，核心是 `mem_fraction_static` 启发式 + 逐字节成本（cell_size）除法。总入口 `KVCacheConfigurator.configure()`（`kv_cache_configurator.py:276`），关键计算集中在 `_profile_available_bytes`、`_compute_cell_size`、`calculate_pool_sizes` 与 `resolve_max_num_reqs`。

### mem_fraction_static：KV 预算切片

`_profile_available_bytes`（`kv_cache_configurator.py:1764`）：

```python
available_gpu_memory = get_available_gpu_memory(...)
slack_gb = pre_model_load_memory * (1 - mem_fraction_static)
rest_memory = available_gpu_memory - slack_gb - mm_reservation_gb
return int(rest_memory * (1 << 30))
```

- `pre_model_load_memory`：模型加载后的显存占用（含权重、draft 权重）。
- `mem_fraction_static`（`--mem-fraction-static`，默认约 0.9）：静态 KV 预算占**峰值**内存的比例，`1 - fraction` 即留给权重/runtime 的 slack。已有驻留显存（权重）也计入 slack 被扣减。
- 权重超预算时报错并给出最小可行值：`minimum = 1 - available/pre`（`kv_cache_configurator.py:1794-1809`）。
- 多模态预留：`mm_runtime_reservation_gb`（`kv_cache_configurator.py:130`）把 embedding cache 与 feature-transport 池的后续分配额从 KV 预算中预扣。
- Mamba/PP 特例：post-capture 场景 slack 不小于预激活预留；`_handle_max_mamba_cache`（1970 行）按 PP 各 stage 最大 mamba 层数份额扣减。

### cell_size：每 token 字节成本

`DefaultPoolConfigurator._compute_cell_size`（`pool_configurator.py:235`）按注意力类型算单 token KV 成本（`cell_size` 字节），随后 `calculate_pool_sizes`（`pool_configurator.py:415`）：

```python
max_total_num_tokens = available_bytes // self._cell_size
max_total_num_tokens = max_total_num_tokens // page_size * page_size   # 页对齐
```

各类型 cell_size 公式（均× `effective_num_layers`）：

| 类型 | 公式要点（源码位置） |
|---|---|
| MHA | `num_kv_heads × (head_dim + v_head_dim) × layers × dtype字节`（`pool_configurator.py:327-333`），TP/DCP 参与 `get_num_kv_heads` |
| MLA | `calculate_mla_kv_cache_dim`（`kv_cache_configurator.py:2139`）× layers × dtype 字节；FP4 时加 scale buffer（`pool_configurator.py:266-276`） |
| DSA | MLA 基础上加 indexer 成本（`_compute_dsa_indexer_cell_size`，`pool_configurator.py:352`） |
| MiniMax sparse | 主池（dense+sparse 层 K+V）+ indexer 池（单头 sparse，k-only 层只存 K）（`pool_configurator.py:284-325`） |
| EAGLE/DFLASH | 目标 cell_size 按 `draft_num_layers/num_layers` 比例放大，draft KV 计入同一预算（`pool_configurator.py:178-233`） |

FP4 另含共享 FP8 dequant workspace；MXFP8 加 scale_block=32 的 scale 成本。hybrid SWA 用 `HybridSWAPoolConfigurator`（`pool_configurator.py:433`）按系数+bias 解 full/swa 双池；DSV4 用 `DSV4PoolConfigurator`（`pool_configurator.py:715`）按 full token 容量反推 c4/c128/state 池大小。

### 请求数约束

`resolve_max_num_reqs`（`kv_cache_configurator.py:1873`）：

```python
estimated = int(token_capacity / context_len * 512)
estimated = max(min(estimated, 4096), 2048)   # 经验估算，夹在 [2048, 4096]
max_num_reqs = min(estimated, token_capacity // 2)   # 或用户值 min(requested, cap//2)
```

- `--max-running-requests` 未给时用估算；给了则按 `// attn_dp_size` 折算每 worker。
- Mamba 模型另受 `max_mamba_cache_size / ratio` 封顶（`kv_cache_configurator.py:1889-1913`），ratio 由 `_calculate_mamba_ratio`（1813 行）给出：基数 3（radix 场景），overlap/lazy 各追加 2/1。

### 外部约束与统一入口

`_apply_token_constraints`（`kv_cache_configurator.py:1844`）追加三层约束：

| 约束 | 行为 |
|---|---|
| `--max-total-tokens` | `min(token_capacity, user_limit)`，超预算时告警 |
| PP 同步 | 各 rank 按层数不同，`all_reduce(MIN)` 取最小（1862-1869 行） |
| 页对齐 | 统一在 `configurator.calculate_pool_sizes` 内 `// page_size * page_size` |

`config_from_budget`（`kv_cache_configurator.py:1946`）把「字节预算 → 池配置」流程封装；`_resolve_memory_pool_config`（1928 行）串起 profile → 计算 → max_num_reqs → `finalize_with_max_running_requests`，最后回填 `mem_fraction_static`。

### 池大小派生（_derive_pool_sizes）

`_derive_pool_sizes`（`kv_cache_configurator.py:324`）把 `MemoryPoolConfig` 展开为 `_PoolSizes`：

- hybrid SWA：拆 `full_max_total_num_tokens` / `swa_max_total_num_tokens`；
- DCP 场景 draft worker 池复制（`loc_space_scale`，316 行），`max_total_num_tokens *= attn_dcp_size`；
- DSV4 draft worker 的 c4/c128/state 池清零（归 target rank）；
- 输出给 `_init_pools`（376 行）分别建 `ReqToTokenPool`、`KVCache`、allocator（含 `--enable-unified-memory` 的 unified 快速路径）。

`ReqToTokenPool` 行数 = `max_running_requests`（每 worker），行宽 = `context_len + get_req_to_token_extra_context_len()`（`allocation_sizing.py:80`，spec 解码页对齐预留）；PD decode 模式追加 `disaggregation_decode_extra_slots` 预分配行（`kv_cache_configurator.py:764-766`）。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
