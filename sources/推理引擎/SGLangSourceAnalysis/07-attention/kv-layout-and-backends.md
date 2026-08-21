## KV Cache 布局与注意力后端差异

各后端共享同一个 `token_to_kv_pool`（`mem_cache/memory_pool.py`），但用不同的元数据（kv_indptr/kv_indices/page_table）把「token → 物理槽位」映射交给内核。本文件对比 MHA/MLA 两种池布局与主要后端差异。

### MHA KV 布局（MHATokenToKVPool）

`memory_pool.py:2045` `_kv_buffer_shapes`：

| 布局模式 | K 形状 | V 形状 | 说明 |
|---|---|---|---|
| 普通（默认） | `(size+page_size, head_num, head_dim)` | `(size+page_size, head_num, v_head_dim)` | 每 token 一行；slot 0 为吸收 dummy 填充写入的哨兵页 |
| `vectorized_5d` | `(num_blocks, H, D_k//X, page_size, X)` | `(num_blocks, H, page_size//X, D_v, X)` | 页内按 X 向量化存储（`kv_cache_layout` 配置） |

- 层间复用：`k_buffer[layer_id - start_layer]`，每层独立 K/V 张量。
- 量化时以 `store_dtype=uint8` 存储（fp8 无法直接 index_put，`memory_pool.py:1645`），`set_kv_buffer` 内按 `k_scale`/`v_scale` 反量化后再写入。
- `page_size`（`model_runner.page_size`）为页内 token 数；`req_to_token_pool` 表按页对齐组织，`kv_indices // page_size` 得页号（FA 的 `page_table` 构造，`flashattention_backend.py:648`）。

### MLA KV 布局（MLATokenToKVPool）

`memory_pool.py:3932`：MLA 只存一份 KV 缓冲，单"头"：

```python
self.kv_buffer = [
    torch.zeros((self.size + self.page_size, 1, self.kv_cache_dim), dtype=...)
    for _ in range(self.layer_num)
]
# kv_cache_dim = kv_lora_rank + qk_rope_head_dim（DSA 可用 override_kv_cache_dim）
```

- 前半列存吸收后的 `w_kc`（含 V），后半列存 `k_rope`（RoPE 不参与吸收）；decode 时后端拆 `k_buffer[:, :, :v_head_dim]` 与 `k_buffer[:, :, v_head_dim:]` 分别喂给 MLA 内核（`flashinfer_mla_backend.py:727-728`）。
- 写入走 `set_mla_kv_buffer(layer, loc, k_nope, k_rope)`（`memory_pool.py:4077`），fp8 量化有独立 `set_mla_kv_buffer_triton_fp8_quant`。
- 只有 `MLATokenToKVPool` 对应 `AttentionArch.MLA`（`model_config.py:77`），`runner.use_mla_backend` 由此判定。

### 统一写位置 KVWriteLoc

`memory_pool.py:1547`：位置信息集中在注意力元数据而非池内：

| 字段 | 语义 |
|---|---|
| `loc` | 通用逐 token 写位置（非统一池下即物理槽位；统一内存池下为虚拟槽位） |
| `swa_loc` | 已翻译的 SWA 子池物理位置（混合 SWA 池用） |
| `full_loc` | 已翻译的全注意力子池物理位置（统一池用，避免每层 v2p gather） |

### 主要后端差异表

| 后端 | page 布局 | head 布局 | decode 内核 | extend 内核 | fp8 KV | MLA |
|---|---|---|---|---|---|---|
| `flashinfer` | decode 用 paged（`kv_indptr`/`kv_indices`，页表）；prefill 默认 **ragged**（`use_ragged`，q/k/v 直接拼接），chunked-prefix 时 ragged+paged 双段 + LSE merge | H2D 标准 | `BatchDecodeWithPagedKVCacheWrapper` | `BatchPrefillWithRaggedKVCacheWrapper` / Paged | 支持（`prefill_kv_access`/`decode_kv_access`，NVFP4/FP4 走 dequant workspace） | 专用 `FlashInferMLAAttnBackend` |
| `fa3`/`fa4` | `page_table`（页表，按 `seq_lens % page_size` 推 `last_page_lens`）；支持 `page_size==1` 直读 | H2D 标准 | `flash_attn_with_kvcache`（decode） | `flash_attn_varlen_func`（`fa_skip_kv_cache` 时用 raw K/V） | fa3 支持 mxfp8（`kv_cache_is_mxfp8` 走 descale）；fa4 不支持 fp8 q/k（`flashattention_backend.py:1281`） | 无（MHA） |
| `triton` | `kv_indptr`+`kv_indices`（自研 `build_unified_kv_indices`），`page_size` 特化 wrapper | H2D 标准 | `decode_attention_fwd` | `extend_attention_fwd(_unified)` | 经池层支持 | `use_mla` 标志 + verify_shared_kv |
| `flashmla` | decode 用 Triton 生成 `create_flashmla_kv_indices_triton` | MLA 单头 | `sgl_kernel.flash_mla.flash_mla_with_kvcache` | 同左 | 池层支持 | 是（继承 FlashInferMLA） |
| `trtllm_mla`/`cutedsl_mla`/`cutlass_mla`/`tokenspeed_mla` | 各自内核元数据 | MLA 单头 | TensorRT-LLM / CuteDSL / Cutlass / TokenSpeed 内核 | 同左 | 部分 | 是（仅 MLA） |
| `torch_native` / `flex_attention` | 直接张量注意力 | H2D | torch 原生 / FlexAttention | 同左 | 否 | 否（会禁用 CUDA graph） |
| `intel_amx` / `intel_xpu` / `ascend` | 平台页表（NPU 用 PA_ND block table，`out_cache_loc_dsv4`） | 平台相关 | 平台内核 | 同左 | 平台相关 | Ascend 有 MLA 变体 |

**FlashInfer 双元数据（`FlashInferAttnBackend`）**：decode 用 `kv_indptr[i]`（`paged_kernel_lens` 前缀和）与 `req_to_token` gather 的 `kv_indices`（`FlashInferIndicesUpdaterDecode.update`）；prefill 的 ragged wrapper 直接用拼接 K/V，paged wrapper 用 `kv_indices`+`qo_indptr`（`cumsum(seq_lens - prefix_lens)`），`extend_no_prefix` 时跳过 paged 段。SWA 层 `sliding_window_size != -1` 触发双 wrapper（`num_wrappers=2`），`_get_wrapper_idx` 按层选 wrapper。

**DCP / 投机**：FlashInfer decode 在 `dcp_enabled` 下 `return_lse=True` 供跨 rank online-softmax 合并；EAGLE 投机用独立 stream（`plan_stream_for_flashinfer`）；`FlashInferMultiStepDraftBackend` 按 topk 复制多份 wrapper。

**确定性**：`enable_deterministic_inference` 强制 decode 用 tensor core，并设 split tile 大小（`SGLANG_FLASHINFER_PREFILL/DECODE_SPLIT_TILE_SIZE`），CUDA graph 下禁 KV split。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
