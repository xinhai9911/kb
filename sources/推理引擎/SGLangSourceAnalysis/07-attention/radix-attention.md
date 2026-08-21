## RadixAttention 注意力层实现

`RadixAttention`（`sglang/srt/layers/radix_attention.py:91`）是所有 decoder/encoder/cross-attention 层最终落地的 nn.Module，是模型 forward 与「注意力后端 + KV 池」之间的唯一接缝。它不直接接触 RadixCache 树，而是通过 `ForwardBatch` 携带的 KV 元数据（`out_cache_loc` 写位置、`req_to_token_pool` 读索引）与缓存交互。

### AttentionType 枚举

`radix_attention.py:77`，字符串值（兼容 `torch.compile`）：

| 值 | 含义 |
|---|---|
| `DECODER = "decoder"` | decoder 层常规因果注意力（前后层 Q/K/V） |
| `DECODER_BIDIRECTIONAL = "decoder_bidirectional"` | 图像 token 上的双向注意力（多模态） |
| `ENCODER_ONLY = "encoder_only"` | encoder 非因果注意力（encoder-decoder 模型） |

`is_cross_attention` 标志与 `attn_type == ENCODER_ONLY` 共同决定后端是否关闭 `causal` mask（见 FlashInfer `forward_extend` 中对 `causal` 的计算）。

### 构造参数与量化

`__init__`（`radix_attention.py:96`）关键参数：

| 参数 | 说明 |
|---|---|
| `num_heads` / `num_kv_heads` | TP 局部 Q/KV 头数（存为 `tp_q_head_num`/`tp_k_head_num`/`tp_v_head_num`） |
| `head_dim` / `v_head_dim` | QK 头维与 V 头维（`v_head_dim=-1` 时取 `head_dim`，MLA 分离用） |
| `scaling` | softmax 缩放（通常 `1/sqrt(head_dim)`） |
| `layer_id` | 全局层号，用于索引 `token_to_kv_pool` 的分层 KV buffer |
| `logit_cap` / `logit_capping_method` | logits 软上限（如 Gemma 的 tanh cap） |
| `sliding_window_size` | 滑窗大小（-1 表示全注意力），驱动 SWA wrapper 选择 |
| `quant_config` | 量化配置，构造时 `create_weights` 创建 fp8 等 scale 权重（`k_scale`/`v_scale` 等） |

注意两个实例可共享同一 `layer_id`（DeepSeek MLA 每层 `attn_mqa` 与 `attn_mha` 两个 RadixAttention），自定义 op 用 `use_mha_companion` 保持调用实例身份。

### forward 流程与 PCG 路由

`forward`（`radix_attention.py:150`）签名：`(q, k, v, forward_batch, save_kv_cache=True, key_value_num_tokens=None, **kwargs)`。流程：

1. **k/v reshape**：`k.view(-1, tp_k_head_num, qk_head_dim)`、`v.view(-1, tp_v_head_num, v_head_dim)`；MLA 场景传入 `k_rope` 时 k 按 `v_head_dim` 切分（`radix_attention.py:163-167`）。
2. **extend 且处于 tc-piecewise 上下文**：走 `unified_attention_with_output` 系列自定义 op（`register_custom_op` + `register_split_op`），把注意力调用编入 CUDA graph 分段；否则直接调用 `get_attn_backend().forward(...)`（`radix_attention.py:279`）。
3. **特殊 kwargs 旁路**：`score_mod`/`aux_tensors`/`rel_bias`/`q_descale` 等无法穿过 custom-op schema，改走 `attention_with_output_extra_kwargs` 纯 eager 路径（`radix_attention.py:558`）。

```python
# radix_attention.py:169-180 核心路由判断
context = get_tc_piecewise_forward_context()
if (forward_batch.forward_mode.is_extend()
        and context is not None
        and (torch.compiler.is_compiling() or not _force_eager_attn.get())):
    # 走 unified_attention_with_output[_and_lse] / 稀疏路径
else:
    return get_attn_backend().forward(q, k, v, self, forward_batch, save_kv_cache, **kwargs)
```

#### unified_attention_with_output 实现要点（`_unified_attention_with_output_impl` :290）

| 步骤 | 行为 |
|---|---|
| real-token 窄化 | 按 `forward_batch.num_token_non_padded_cpu` 截取 q/k/v，pcg 捕获的填充尾被切掉（PCG 把 Q/K/V 填充到静态桶大小） |
| 层解析 | `attention_layers[layer_id]` 取到真正的 RadixAttention 实例；`use_mha_companion` 时替换为 mha 伴生层 |
| FB 窄化 | 临时把 `forward_batch.out_cache_loc`/`positions` 截到 real-token 范围（保证 KV 写位置与查询对齐，调用后恢复） |
| 输出缓冲 | `forward_batch._attn_output = output[:real_query_num_tokens]`，FA 后端直接写入预分配输出 |
| 填充尾清零 | `_zero_padded_pcg_tail`（`radix_attention.py:57`）把 replay 时 `torch.empty` 的垃圾尾部清零，防止 NaN/Inf 流入残差/MoE 路由/allreduce |
| LSE 返回 | `return_lse`（`forward_batch.mha_return_lse`，chunked-prefix MHA 需要）时把 LSE 一并 pad 回桶大小 |

`breakable_unified_attention_with_output` 与 `breakable_*_and_lse` 是 `eager_on_graph(True)` 包装的「可断图」版本（BCG 在分段之间以 eager 执行）。`unified_sparse_attention_with_output`（:495）是 MiniMax/DSA 稀疏注意力的自定义 op（idx_q/idx_k 索引路径）。

### 与 RadixCache 的衔接（读/写 KV）

RadixAttention 不在层内做前缀匹配——调度器已把匹配结果落到 ForwardBatch 张量：

| 数据流 | 载体 | 说明 |
|---|---|---|
| **读（前缀命中）** | `forward_batch.req_pool_indices` → `req_to_token_pool.req_to_token` | `req_to_token[i]` 是请求 i 的 token 位置表，命中前缀的 KV 索引直接进入表内，后端据此构造 `kv_indices`/`kv_indptr`（FlashInfer `FlashInferIndicesUpdaterPrefill`、Triton `_fill_kv_indptr_and_indices`） |
| **读（chunked prefix）** | `forward_batch.extend_prefix_lens_cpu` | 每条请求「已缓存前缀长度」，后端把它从 query 侧剔除（`qo_indptr = cumsum(seq_lens - prefix_lens)`），只对新 token 做 ragged 注意力，缓存部分走 paged 注意力并 `merge_state` |
| **写（新 token）** | `forward_batch.out_cache_loc` | 新 token 在 `token_to_kv_pool` 中的槽位，后端 `set_kv_buffer` 把 K/V 写入；SWA 池经 `swa_out_cache_loc` 翻译；encoder 用 `encoder_out_cache_loc` |
| **chunked 中间态** | `maybe_cache_unfinished_req`（04 模块） | 分块 prefill 每步后把已算前缀写入树，后续 chunk 的 `extend_prefix_lens` 随之增长 |

RAgged + paged 双段注意力的合并（FlashInfer `forward_extend` :1370-1391）：ragged 段（新 token）与 paged 段（缓存前缀）分别 `forward_return_lse`，再用 `_safe_merge_state`（`merge_state.py`，CUDA `merge_state_v2`，兜底 Triton）按 LSE 在线 softmax 合并。这正是「radix 命中不必重算前缀」的实现基础。

### 与 06 ForwardBatch 的衔接

- `forward_batch.forward_mode.is_extend()/is_decode()/is_mixed()/is_idle()` 驱动后端 `forward` 的三分派（见 attention-backends.md）。
- `mha_return_lse` 字段（DeepSeek MHA mixin）开启 chunked-prefix MHA 的 LSE 返回路径。
- `forward_metadata`（各后端私有）在 `ModelRunner._forward_raw` 中由 `attn_backend.init_forward_metadata(forward_batch)` 规划（`model_runner.py:1482`），层 forward 时只读。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
