## 注意力架构（续）：元数据与 Attention 层接线

本文承接 [attention-architecture.md](attention-architecture.md)，说明元数据构建与 `Attention` 层接线。

### 元数据（Metadata）

- `AttentionMetadata`：空标记基类，各后端 dataclass 继承。
- `CommonAttentionMetadata`：跨层跨后端共享的每批元数据。含 `query_start_loc`（device+CPU 双份）、`seq_lens`、`num_reqs`、`num_actual_tokens`、`max_query_len`、`max_seq_len`、`block_table_tensor`、`slot_mapping`、`causal`、`positions`、`is_prefilling`、`encoder_seq_lens`、`mm_req_doc_ranges`（PrefixLM 双向区间）、`rswa_prefix_lens`、`replayssm_decode_base_cpu`（Mamba2）等。`seq_lens_cpu`/`num_computed_tokens_cpu` 已 deprecated（避免隐式 H→D 同步）。
- `AttentionMetadataBuilder`：`build(common_prefix_len, common_attn_metadata, fast_build)` 从通用元数据构建各层专用元数据。类属性 `_cudagraph_support` 依 `AttentionCGSupport` 声明 CUDA Graph 等级：

| 值 | 含义 |
|---|---|
| `ALWAYS` | 恒支持，含混合 prefill-decode |
| `UNIFORM_BATCH` | 仅同 query 长度批次（可作 spec-decode） |
| `UNIFORM_SINGLE_TOKEN_DECODE` | 仅 query_len==1 的 decode |
| `NEVER` | 不支持 |

`reorder_batch_threshold` 控制把短 query 请求重排为 decode；spec-decode 按 `num_speculative_tokens` 自动上调；DCP 且不支持 varlen 时强制为 1。另有 `build_for_cudagraph_capture()`、`build_for_drafting()`、`update_block_table()`、`update_draft_decode_metadata()` 钩子。

### Attention 层接线

`Attention.__init__`（`layer/attention/attention.py`）：

1. 解析 `kv_cache_dtype`（含 checkpoint `kv_cache_scheme`→fp8、per-head quant scales、`kv_cache_dtype_skip_layers`）。
2. `get_attn_backend(head_size, dtype, kv_cache_dtype, use_mla=False, ...)` 选后端。
3. 后端能力校验：`use_alibi_sqrt` 需 `supports_alibi_sqrt()`；`chunk_lookback` 仅 `TRITON_ATTN`；`FLEX_ATTENTION` 读 `flex_attn_block_m/n`。
4. `self.impl = backend.get_impl_cls()(...)`（num_heads/head_size/scale/num_kv_heads/alibi/sliding_window/kv_cache_dtype 等），并把层注册进 `compilation_config.static_forward_context[prefix]`。
5. 分发：CUDA/ROCm/CPU 上 `use_direct_call=False`，走 custom op `torch.ops.vllm.unified_attention_with_output`（元数据/层从 forward context 取出，`kv_cache_dummy_dep` 保证 KV 更新与注意力编译期顺序）；其它平台直接调 impl。KV cache 形状由 `get_kv_cache_spec()` 生成 `FullAttentionSpec`/`SlidingWindowSpec`，量化经 `get_kv_quant_mode()` 统一。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
