## Linear 线性层与 Norm 归一化层

本文基于 `srt/layers/linear.py`（约 1780 行）、`parameter.py`（601 行）与 `layernorm.py`（1429 行），对照 vLLM `21-model-layers`，说明 SGLang 并行线性层、统一 weight 加载契约与多后端 Norm 层的 `BaseFusedOp` 化。路径根均为 `python/sglang/`。

### 统一 weight 加载接口（LinearMethod 契约）

`LinearBase`（`srt/layers/linear.py:146`）与 vLLM `LinearBase` 同源（文件头注明 Adapted from vLLM v0.6.4.post1），量化与否统一走 **quant method 工厂**：

| 接口 | 职责 |
|---|---|
| `LinearBase.__init__` | `quant_config is None` → `UnquantizedLinearMethod()`；否则 `quant_config.get_quant_method(self, prefix=prefix)`。`quant_method` 非空时对其 `apply` 挂 debug kernel 日志钩子 |
| `quant_method.create_weights(...)` | 由各线性层构造时调用，创建权重并挂 `weight_loader` |
| `quant_method.apply(layer, x, bias)` | 执行 GEMM + 可选 bias；未量化默认走平台专用 `F.linear` 分发 |
| `scheme` | 类属性（默认 `None`），量化方法挂载 per-layer scheme；`scheme.requires_weight_loader_v2` 可强制走 v2 加载器 |

- **v2 加载器白名单**：`WEIGHT_LOADER_V2_SUPPORTED`（`linear.py:58`）列出 21 个 LinearMethod 类名（CompressedTensors、AWQ、GPTQMarlin、Fp8、BlockInt8、Marlin、ModelOpt、IPEXAWQ、Petit、Quark、Humming 等），命中才用 `weight_loader_v2`，否则用 `weight_loader`。
- `weight_loader_v2` 只是薄壳，委托给参数自身的 `load_column_parallel_weight / load_row_parallel_weight / load_merged_column_weight / load_qkv_weight`——切分逻辑收敛到 `srt/layers/parameter.py`。
- **平台 GEMM 分发**：`quantization/unquant.py` 未量化路径按平台分发（ROCm 有 `bf16_gemm_dispatch` 注册算子、CPU AMX 走 `sgl_kernel.weight_packed_linear`、其余 `F.linear`）；all-reduce 可选 `tensor_model_parallel_quant_all_reduce`（量化通信）。

### 并行线性层族

| 类（`linear.py`） | 切分维度 | 集合通信 | 权重形状（rank 本地） |
|---|---|---|---|
| `ReplicatedLinear:204` | 无，全量复制 | 无 | `[output_size, input_size]`，loader 直接 copy |
| `ColumnParallelLinear:302` | 输出维 | `gather_output=True` 时输出 all-gather | `[output_size/tp_size, input_size]` |
| `MergedColumnParallelLinear:507` | 输出维，各子矩阵独立切 | 同 Column | `[sum(output_sizes)/tp_size, input_size]` |
| `QKVParallelLinear:936` | 按 head 维切（q/k/v 独立） | 默认不 gather | `[(num_q+num_kv+num_kv_v)*head/tp, hidden]` |
| `RowParallelLinear:1407` | 输入维 | `reduce_results=True` 时输出 all-reduce | `[output_size, input_size/tp_size]` |
| `MergedColumnParallelRepeatedLinear:1677` | 部分切分 | — | column 部分切、repeated 部分复制 |
| `ColumnParallelBatchedLinear:1747` | 输出维（batch 维 bmm） | — | `[batch, output/tp, input]` |

关键行为：

- `ColumnParallelLinear.weight_loader`（`linear.py:402`）：`start_idx = self.tp_rank * shard_size` 沿 `output_dim` narrow；CPU 走 `narrow_padded_param_and_loaded_weight`，GPU 处理 qwen2.5-VL 非 8 对齐的 `pad_or_narrow_weight`；GGUF 的 `UninitializedParameter` 在此物化。
- `RowParallelLinear.forward`（`linear.py:1596`）：bias 只在 rank 0 且不 skip 时传给 GEMM（`bias_ = None if (self.tp_rank > 0 or self.skip_bias_add)`），避免 TP>1 时 bias 被加多次；`reduce_results and tp_size>1` 且未被 `should_skip_mlp_all_reduce()`（MoE 融合/ReduceScatter 场景）跳过时才 all-reduce。
- **DP-attention 特化**：`use_dp_attention_reduce=True` 时 all-reduce 走 `get_parallel().attn_tp_group`；GEMM 在 `use_symmetric_memory` 上下文内执行（pynccl 对称内存）。
- `MergedColumnParallelRepeatedLinear`（`:1677`）支持「列并行 + 复制」混合投影；`ColumnParallelBatchedLinear`（`:1747`）为 batched bmm。

### parameter.py：BasevLLMParameter 契约

与 vLLM 的 `BasevLLMParameter` 同源（Adapted from vLLM v0.6.4.post1）：

| 参数类 | 切分方法 | 说明 |
|---|---|---|
| `_ColumnvLLMParameter` | `load_column_parallel_weight / load_merged_column_weight / load_qkv_weight` | 带 `output_dim`；`load_qkv_weight` 中 `shard_id = tp_rank if shard_id=="q" else tp_rank // num_heads`（KV head 复制时多 rank 共享同一段） |
| `RowvLLMParameter` | `load_row_parallel_weight` | 带 `input_dim` |
| `ModelWeightParameter` | 兼列/行 | 双继承 |
| `PerTensorScaleParameter` | `qkv_idxs={"q":0,"k":1,"v":2}` | 标量 scale 填入 fused 数组对应槽位 |
| `PackedvLLMParameter` / `PackedColumnParameter` | `adjust_shard_indexes_for_packing` | `packed_factor`/`packed_dim`/`marlin_tile_size` 修正切分 |
| `BlockQuantScaleParameter` / `GroupQuantScaleParameter` / `ChannelQuantScaleParameter` | 列+行 | block/group/channel 量化 scale |

- `copy_with_check`（`parameter.py:51`）禁止降精度拷贝（fp8 < bf16/fp16 < fp32 < fp64 分层级），除非 `SGLANG_QUANT_ALLOW_DOWNCASTING`。
- `linear.py` 顶层 `adjust_marlin_shard`（scale 按 tile 放大）、`adjust_bitsandbytes_4bit_shard`、`adjust_scalar_to_fused_array`、`adjust_shard_offsets`（CPU 权重比目标小时等比缩放）是 fused 场景的切分修正。

### QKV 的 GQA 切分规则

`QKVParallelLinear.__init__`（`linear.py:1001`）：

```
kv_tp_size >= total_num_kv_heads → num_kv_heads=1, num_kv_head_replicas=kv_tp_size/total_num_kv_heads
否则                            → num_kv_heads=total_num_kv_heads/kv_tp_size, replicas=1
```

- `q_proj_shard_size = num_heads*head_size`，`v_proj_shard_size = num_kv_heads*v_head_size`（支持 `v_head_size != head_size`）。
- `weight_loader` 中 q 用 `tp_rank`，k/v 用 `kv_tp_rank // num_kv_head_replicas`（`linear.py:1353`）；`loaded_shard_id=None` 表示 checkpoint 已融合（如 Phi-3），按 total head 数拆 q/k/v 后递归。
- `BlockQuantScaleParameter` 分支按 `weight_block_size[0]` 计算 block 级 offset（`_load_qkv_block_scale`）。

### Norm 层（layernorm.py）

全部继承 `BaseFusedOp`（`sglang/kernels/fused_op.py:332`），`forward()` 按平台/后端自动分发到 `forward_native` + `forward_cuda/hip/xpu/npu/cpu/musa`：

| 类 | 要点 |
|---|---|
| `RMSNorm:423` | `x·w/sqrt(E[x²]+eps)`；`var_hidden_size` 覆盖方差维度（取 `x[..., :var]`）；`cast_x_before_out_mul` 切 HF 语义（先 cast 后乘）；`fp32_residual`；`x_pad_to_multiple` 融合零填充 |
| `LayerNorm:968` | flashinfer.layernorm 快路径（bf16 x + fp32 参数），否则 fp32 `F.layer_norm` 后 cast 回 |
| `GemmaRMSNorm:1052` | weight 初始 0；`gemma_weight=weight+1` 预计算 buffer；自定义 `_weight_loader` 在加载后同步 +1 |
| `Gemma3RMSNorm:1265` | `(x*(1+w)).type_as(x)` 顺序（transformers#29402 语义） |
| `Gemma4RMSNorm:1323` | `scale_shift`/`with_scale`，支持 `norm(x)*(w+shift)` 或纯 `norm(x)` |
| `RMSNormWithoutScale:1409` | 无 weight，纯归一化 |

关键机制：

- **残差融合**：`fused_add_rmsnorm(x, residual, w, eps)`（sgl_kernel）原地更新；`post_residual_addition` 先并入 residual（注：是 `x+(residual+post)` 而非 `(x+residual)+post`，源码有 TODO）。
- **batch-invariant**：`is_batch_invariant_mode_enabled()` 时走 `rms_norm_batch_invariant`（`srt/batch_invariant_ops.py`），与 CUDA Graph 无关，输出与 token 数解耦。
- **all-reduce 融合**：`forward_with_allreduce_fusion` → 优先 flashinfer `flashinfer_allreduce_residual_rmsnorm`，ROCm+aiter 时 `tensor_model_parallel_fused_allreduce_rmsnorm`；`forward_with_allreduce_fusion_quant_per_group` 在 ROCm/gfx95 上把 AR+RMSNorm+per-group FP8 quant 融成单 kernel（`keep_bf16=True` 时返回 `(bf16, fp8, scale)` 供 GDN 双投影层用）。
- **FP8 quant 融合**：`forward_with_per_tensor_quant_fusion` 把 RMSNorm + 下游 FP8 静态 per-tensor 激活量化融进 flashinfer kernel（`quant_linear` 需为 `Fp8LinearMethod` 非 block/mxfp8/marlin，或 compressed-tensors W8A8 静态输入）。
- NPU/CPU 分别走 `torch_npu.*` 与 `sgl_kernel.*_cpu`。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
