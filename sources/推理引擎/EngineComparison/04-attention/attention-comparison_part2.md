## vLLM vs SGLang 注意力后端对比（二）：前缀缓存衔接、KV 布局与平台选择

本文承接 [attention-comparison.md](attention-comparison.md)，对比与前缀缓存的衔接、KV 布局差异与平台选择机制。

### 五、与 radix / 前缀缓存的衔接

| 维度 | vLLM | SGLang |
|---|---|---|
| 缓存组织 | BlockManager + 哈希块级 `PrefixCachingBlockAllocator`（调度层，非注意力层） | `RadixCache` 前缀树（`mem_cache/radix_cache.py:303`，调度层） |
| 注意力层接缝 | `Attention` 层（`model_executor/layers/attention/attention.py`）直接消费 `block_table_tensor`，**前缀合并发生在层内**（chunked prefill 复用缓存块） | 显式 `RadixAttention` 层（`layers/radix_attention.py:91`），所有 decoder/encoder/cross 层统一落地，是模型与「后端+KV 池」之间唯一接缝 |
| 命中信息载体 | `CommonAttentionMetadata.block_table_tensor`（块级）；`AttentionMetadataBuilder.build(common_prefix_len,...)` 传递**整批公共前缀** | `forward_batch.extend_prefix_lens_cpu`（**每请求**已缓存前缀长）+ `req_to_token_pool.req_to_token`（token 位置表） |
| 前缀跳过机制 | 公共前缀合并 + chunked prefill 层内重算未缓存 chunk（`ops/prefix_prefill.py` 等共享算子） | 后端把缓存前缀从 query 侧**剔除**：`qo_indptr = cumsum(seq_lens - prefix_lens)`，只对新 token 做 ragged 注意力，缓存部分走 paged 注意力，再 `merge_state` 按 LSE 在线 softmax 合并 |
| 层与缓存树耦合 | 层与 BlockManager 完全解耦，仅经 block table 间接联系 | `RadixAttention` 不直接接触 RadixCache 树，通过 `ForwardBatch` 携带的 `out_cache_loc`（写）与 `req_to_token_pool`（读）交互 |
| 分块 prefill 中间态 | 层内逐 chunk 消费已缓存块 | `maybe_cache_unfinished_req`（调度层）每步把已算前缀写入树，后续 chunk 的 `extend_prefix_lens` 随之增长 |

> 关键差异 ④：两者前缀缓存都在调度/内存层，但**注意力层接缝不同**——vLLM 把缓存块的复用直接落在 `Attention` 层内（层内消化 `common_prefix_len` 与 chunk 合并）；SGLang 有专门的 `RadixAttention` 层把「每请求已缓存前缀」以 `extend_prefix_lens_cpu` 传给后端，后端用 ragged（新 token）+ paged（缓存 KV）**双段注意力 + LSE merge**（FlashInfer `forward_extend` :1370-1391），正是「radix 命中不必重算前缀」的实现基础。vLLM 无对应每请求前缀剔除，前缀命中粒度是块级。

### 六、KV 布局（page / head 布局、MHA / MLA）对比

| 维度 | vLLM | SGLang |
|---|---|---|
| 布局所有权 | 后端声明 `get_kv_cache_shape()` + `get_kv_cache_stride_order()`，统一 KV 分配器按 spec 分配 | `token_to_kv_pool`（`mem_cache/memory_pool.py`）统一，MHA/MLA 两种池 |
| MHA 布局 | 逻辑形状 `(num_blocks,...)`；物理布局 `NHD`/`HND` 由 `get_required_kv_cache_layout()` 决定 | 普通：`(size+page_size, head_num, head_dim)` 每 token 一行（slot 0 为哨兵页）；`vectorized_5d`：`(num_blocks, H, D_k//X, page_size, X)` 页内向量化 |
| MLA 布局 | MLA 后端各自定义（`FLASHMLA`/`TRITON_MLA`/`CUTLASS_MLA` 等） | `MLATokenToKVPool`：`(size+page_size, 1, kv_cache_dim)` 单"头"；`kv_cache_dim = kv_lora_rank + qk_rope_head_dim`，前半列存吸收后 `w_kc`（含 V），后半列存 `k_rope`；decode 时后端拆两段喂 MLA 内核（`flashinfer_mla_backend.py:727-728`） |
| 页/块组织 | `block_size` 由后端建议（`get_preferred_block_size()`），用户 `--block-size` 可覆盖；kernel 要求经 `get_supported_kernel_block_sizes()` 校验（如 FA 要求 16 倍数） | `page_size`（`model_runner.page_size`）页内 token 数；`req_to_token_pool` 按页对齐，`kv_indices // page_size` 得页号（FA `page_table` 构造，`flashattention_backend.py:648`） |
| 逐 token 写位置 | `slot_mapping`（token→slot） | `KVWriteLoc`（`memory_pool.py:1547`）：`loc`/`swa_loc`/`full_loc`（SWA 子池/全注意力子池物理位置翻译） |
| 量化存储 | `supported_kv_cache_dtypes` 扩展（fp8、nvfp4 等）+ `get_kv_quant_mode()` | `store_dtype=uint8` 存储（fp8 无法直接 index_put，`memory_pool.py:1645`），`set_kv_buffer` 内按 `k_scale`/`v_scale` 反量化写入 |

**前端 page 元数据形态差异**：vLLM 各后端统一消费 `block_table_tensor`（页表）；SGLang 按后端分裂为 `kv_indptr`/`kv_indices`（FlashInfer/Triton）与 `page_table`（FA 系）两类元数据。FlashInfer decode 用 paged（`kv_indptr`+`kv_indices`），prefill 默认 **ragged**（`use_ragged`，q/k/v 直接拼接），chunked-prefix 时 ragged+paged 双段 + LSE merge；FA3/FA4 用 `page_table`（按 `seq_lens % page_size` 推 `last_page_lens`，支持 `page_size==1` 直读）；Triton 自研 `build_unified_kv_indices`。

### 七、平台选择机制对比

| 维度 | vLLM | SGLang |
|---|---|---|
| 入口 | `selector.py::get_attn_backend(head_size, dtype, kv_cache_dtype, use_mla,...)` → 调 `current_platform.get_attn_backend_cls(...)`，结果 `@cache` 缓存 | `attention_backends_of`（`arg_groups/overrides.py:277`）：拆分字段为空回退 `attention_backend`，返回 `(prefill, decode)` |
| 选择权所在 | **平台类**（`vllm/platforms/*.py`），按设备能力分优先级 | **模型配置 + 硬件启发式**（`server_args.py:5903`），按架构（MHA/MLA）+ 计算能力 |
| 选型过滤 | CUDA 先 `validate_configuration()`，非法直接报错；合法时按 `_get_backend_priorities()` 逐个校验取 priority 最小者 | 无组合校验，靠默认表 + 修正 pass（`torch_native`/`flex_attention` 禁 CUDA graph、fa3 fp8 回退、MLA/KV4 页面约束等） |
| 运行时覆盖 | `register_backend()` 覆盖枚举；`backend_per_kind` 按 `KVCacheSpecKind` 覆盖全局选择 | 运行时仅 draft worker 用 `draft_attention_backend` 覆盖为单后端（`resolve_attention_backend_strs`，`attention_backend_setup.py:158`） |
| 多后端共存 | 全局单一后端（+按 KV kind 覆盖），无 prefill/decode 拆分 | `HybridAttnBackend` 组合 prefill+decode 两后端；`attn_backend_wrapper` 为混合架构组合 full-attention+线性/稀疏后端（`MiniMaxHybridAttnBackend`、`HybridLinearAttnBackend`） |
| 平台联动 | 平台层同时注入 `import_kernels`（CUDA `_C_stable_libtorch` 等）、`check_and_update_config`（如 CPU 强制 block_size 默认 128） | 后端实例化读 `runner.use_mla_backend`/`server_args`；EAGLE 投机时 FlashInfer 额外规划 stream（`plan_stream_for_flashinfer`） |

> 关键差异 ⑤：vLLM 的注意力后端选择是**平台责任**（每平台一份优先级表，选择结果以 `get_attn_backend_cls` 全限定路径返回、延迟导入），强调「选型期校验、运行期稳定」；SGLang 的选择是**配置启发式**（按 MHA/MLA × 硬件算一个默认值），强调「prefill/decode 可拆分、混合架构可组合」，灵活性更高但无统一选型校验层。SGLang 的 PDmux/two-batch overlap 装配（`build_attention_backends`，`attention_backend_setup.py:69`）进一步允许多后端按 SM 组分组，vLLM 无对应机制。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
