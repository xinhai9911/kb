## RoPE、激活函数与融合层

### RoPE 工厂与变体

`rotary_embedding/__init__.py:get_rope()` 是唯一入口，按 `rope_parameters["rope_type"]` 分派并缓存：

```python
rotary_dim = rope_parameters.get("rope_dim") or int(head_size * partial_rotary_factor)
key = (head_size, rotary_dim, max_position, is_neox_style, rope_parameters_args, ..., dtype)
if key in _ROPE_DICT: return _ROPE_DICT[key]
```

| `rope_type` | 类 | 说明 |
|---|---|---|
| `default` | `RotaryEmbedding` | 基础；`mrope_section` 时用 `MRotaryEmbedding`，`use_fope` 用 `FourierRotaryEmbedding` |
| `proportional` | `Gemma4RotaryEmbedding` | Gemma4 全局 attention |
| `llama3` | `Llama3RotaryEmbedding` | factor/low_freq/high_freq 三段式 |
| `linear` / `ntk` / `dynamic` | `LinearScaling/NTKScaling/DynamicNTKAlpha|Scaling` | 经典长度外推；dynamic 需 `alpha` 或 `factor` |
| `xdrope` | `XDRotaryEmbedding` | 需 `alpha` 与 `xdrope_section` |
| `yarn` | `YaRNScalingRotaryEmbedding` | 含 extrapolation/attn_factor/beta_fast/slow/truncate；配 `mrope_section` 时回落到 Mrope |
| `deepseek_yarn` / `deepseek_llama_scaling` | `DeepseekScalingRotaryEmbedding` / `DeepseekV4ScalingRotaryEmbedding` | 含 mscale；`is_deepseek_v4` 切换 |
| `longrope` | `Phi3LongRoPEScaledRotaryEmbedding` | short/long factor 双组 |
| `openpangu` | `MRotaryEmbeddingInterleaved` | interleaved mrope |
| `telechat3-yarn` | `TeleChat3RoPEScaledRotaryEmbedding` | 无 original_max 时按 max_position 推算 factor |
| 非 rope_type | `DualChunkRotaryEmbedding` | `dual_chunk_attention_config` 非空时优先 |

### RoPE 计算体系（base.py / common.py）

- `RotaryEmbeddingBase(CustomOp)`：`_compute_inv_freq`（`inv_freq = 1/base^(arange(0,rotary_dim,2)/rotary_dim)`，刻意在 GPU 生成、与 HF 有微小数值差）→ `_compute_cos_sin_cache`（`einsum("i,j->ij", t, inv_freq)` 后 `cat(cos, sin)`）→ 注册为 `cos_sin_cache` buffer（`persistent=False`）。`get_cos_sin(seqlen)` 按 `chunk(2, -1)` 切 cos/sin。
- `RotaryEmbedding.forward(positions, query, key)`：CUDA 走 `_custom_ops.rotary_embedding`（**原地**修改 query/key）；flashinfer 走 `vllm.flashinfer_rotary_embedding`（`common.py` 用 `direct_register_custom_op` 注册、声明 `mutates_args=["query","key"]`）；ROCm 可走 aiter Triton（`use_aiter`）；`forward_static` 是纯 PyTorch 参考实现（`index_select` cache → `ApplyRotaryEmb` 旋转 → `cat` 回 pass-through 段）。
- 旋转风格：`is_neox_style=True` 半切旋转（`rotate_neox`：`cat((-x2, x1))`）；GPT-J 交错式（`rotate_gptj`：`[..., ::2]`/`[..., 1::2]` 交错）。`ApplyRotaryEmb.forward_static`：`o1=x1*cos−x2*sin, o2=x2*cos+x1*sin`，支持 `enable_fp32_compute`。

### 融合线性/嵌入/Norm 层

| 文件 | 融合内容 |
|---|---|
| `fused_embed_norm.py` | `VLLM_REPLICATE_EMBED=1` 时嵌入整表复制到每 rank（`make_input_embedding(disable_tp=True)`），解锁 `fused_embed_norm`（gather+首个 RMSNorm 单 Triton launch）与 `fused_embed_eh_norm`（MTP 深度层：gather+pos-0 清零+enorm/hnorm+cat 成 `[N,2H]`）；与 tie-word-embedding 冲突时 TP>1 断言拒绝 |
| `fused_qk_norm_rope.py` | Qwen3.5 `attn_output_gate`：`split → GemmaRMSNorm → 部分 RoPE → gate 拷贝` 折叠为单 kernel（`fused_qk_rmsnorm_rope_gate`）；`HAS_PASS` 处理 `rotary_dim<head_dim` 的 pass-through 段 |
| `fused_allreduce_gemma_rms_norm.py` | attention o_proj 的 `RowParallelLinear` 部分和 + 残差 + GemmaRMSNorm 三合一（flashinfer `kARResidualRMSNorm`，需 NVSwitch、bf16/fp16、token 预算 `_max_token_num`）；不可用时回退 `all_reduce + norm`，数值一致 |

`layers/fusion/` 仅含 `quant_activation.py`（量化激活融合）；QKV/GateUp 融合线性本身在 `linear.py` 内（见 linear-norm-layers.md）。

### 激活函数（activation.py）

全部 `@CustomOp.register`，命名即语义：`silu_and_mul`（`silu(x[:d])*x[d:]`）、`mul_and_silu`（顺序相反）、`gelu_and_mul`/`gelu_and_mul_sparse`、`fatrelu_and_mul`（threshold 截断）、`situ_and_mul`（Kimi，`β·tanh(g/β)·σ(g)·u`，可对 up 线性截断）、`silu_and_mul_with_clamp`、`swigluoai_and_mul`、`swiglustep_and_mul`（Triton，limit=7 截断）、`gelu`/`gelu_tanh`/`gelu_new`/`gelu_fast`/`quick_gelu`/`relu2`/`xielu`。GPU 走 `torch.ops._C.*` 内核，native 路径保留 PyTorch 语义。

### FusedMoE 工厂（fused_moe/layer.py）

`FusedMoEFactory`（`layer.py:99`）是 MoE 层统一构造入口，产出 **Router + RoutedExperts + MoERunner** 三段管线：

| 组件 | 职责 |
|---|---|
| `FusedMoERouter`（`create_fused_moe_router`） | top-k 路由、`renormalize`、grouped-topk、`scoring_func`、EPLB 专家负载均衡 |
| `RoutedExperts` | 持有全部专家权重参数：`gate_up_proj`（MergedColumn 融合）+ `down_proj`（RowParallel） |
| `MoERunner` | 编排完整前向：router → permute → grouped GEMM → unpermute → 最终 all-reduce |

并行：`make_parallel_config` 组装 `FusedMoEParallelConfig`（TP/DP/PCP/SP，`sp_size = tp_size` 当开启序列并行）；`reduce_results=False` 且非 all2all/SP 时推迟最终 all-reduce（`skip_final_all_reduce`）。权重加载通过 `fused_moe_make_expert_params_mapping` 委托 EPLB 管理器生成 ckpt 名→参数映射（`ckpt_names` 默认 `("gate_proj","down_proj","up_proj")`，Mixtral 风格 w1/w3/w2 由模型层映射）。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
