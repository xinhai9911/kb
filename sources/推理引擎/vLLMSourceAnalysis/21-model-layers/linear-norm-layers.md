## Linear 线性层与 Norm 归一化层

本文基于 `vllm/model_executor/layers/linear.py`（约 1670 行）与 `layernorm.py`，说明各并行线性层如何统一 weight 加载接口、配合 TP 切分，以及 Norm 层的 CustomOp 化实现。

### 统一 weight 加载接口（LinearMethodBase 契约）

`LinearBase`（`linear.py:215`）继承 `PluggableLayer`。量化与否全部走 **LinearMethod 工厂**：

| 接口 | 职责 |
|---|---|
| `LinearMethodBase(QuantizeMethodBase)` | 抽象基类，定义 `create_weights()` 与 `apply()` 两个抽象方法 |
| `create_weights(layer, input_size_per_partition, output_partition_sizes, input_size, output_size, params_dtype, **extra)` | 在 layer 上创建权重；`output_partition_sizes` 是逻辑子矩阵在 rank X 的输出宽度（QKV 为 3 元列表） |
| `apply(layer, x, bias)` | 执行 GEMM + 可选的 bias；未量化默认走 `dispatch_unquantized_gemm()` |

- `LinearBase.__init__`：`quant_config is None` → `UnquantizedLinearMethod()`；否则 `quant_config.get_quant_method(self, prefix=prefix)`。所有线性层必须支持某个 quant method，否则抛 `ValueError`。
- **量化算子白名单**：`WEIGHT_LOADER_V2_SUPPORTED` 列出 16 个 LinearMethod 类名（Unquantized、CompressedTensors×2、Fp8、FBGEMMFp8、ModelOpt 系列、AutoAWQ×2、AutoGPTQ、Quark、Humming 等），命中才使用 `weight_loader_v2` 分支；`register_weight_loader_v2_supported_method` 装饰器可扩展。
- `weight_loader_v2` 只是薄壳：0 维 scale reshape 后委托给参数自身的 `param.load_column_parallel_weight() / load_row_parallel_weight() / load_qkv_weight() / load_merged_column_weight()`——切分逻辑收敛到 `vllm/model_executor/parameter.py` 的 `BasevLLMParameter` 子类。

### TP 状态协调

`BasevLLMParameter` 在 `__init__` 里用**全局** TP rank 打标，`LinearBase.update_param_tp_status()` 再把所有子参数改成**本层**的 `tp_rank/tp_size`（`disable_tp=True` 时层内为 0/1，权重整复制不切分）。量化方法在 `process_weights_after_loading()` 里换新 Parameter 后**必须**重跑该方法，否则后续加载/refit 会按全局 rank 切分复制的权重而越界。

### 并行线性层族

| 类 | 切分维度 | 集合通信 | 权重形状（rank 本地） |
|---|---|---|---|
| `ReplicatedLinear` | 无，全量复制 | 无 | `[output_size, input_size]`，loader 直接 copy |
| `ColumnParallelLinear` | 输出维（矩阵第 2 维） | `gather_output=True` 时输出 all-gather | `[output_size/tp_size, input_size]` |
| `MergedColumnParallelLinear` | 输出维，各子矩阵独立切 | 同 Column | `[sum(output_sizes)/tp_size, input_size]` |
| `QKVParallelLinear` | 按 head 维切（q/k/v 独立） | 默认不 gather | `[(num_q+num_kv+num_kv_v)*head/tp, hidden]` |
| `RowParallelLinear` | 输入维（矩阵第 1 维） | `reduce_results=True` 时输出 all-reduce | `[output_size, input_size/tp_size]` |

关键行为：
- `ColumnParallelLinear.weight_loader`：`start_idx = self.tp_rank * shard_size`，沿 `output_dim` narrow 磁盘权重再 copy；`forward` 中 `gather_output and tp_size>1` 时 `tensor_model_parallel_all_gather`。
- `RowParallelLinear`：bias 只在 rank 0 且不 skip 时传入 GEMM（`bias_ = None if (self.tp_rank > 0 or self.skip_bias_add)`），避免 TP>1 时 bias 被加多次；`reduce_results` 关闭时禁止加 bias（`ValueError`）。
- `DCPGroupColumnParallelLinear`（`linear.py:598`）：按 **DCP group** 而不是按 rank 切分（`tp_rank = rank // group_size`），使组内每个 rank 持全组 head（MLA decode 免 query all-gather）；`_local_view()` 在 prefill 时再切回本 rank 的 TP shard。

### shard_id 契约

权重加载时 `load_weights` 从 `loaded_weight.shard_id` 属性读切分目标（`linear.py:939/1293`）：

| 层 | 合法 shard_id | 说明 |
|---|---|---|
| `MergedColumnParallelLinear` | `int \| tuple \| None` | int 为子矩阵下标；tuple 要求连续；`None` 表示磁盘上已融合（如 Phi-3 `gate_up_proj`），按 `output_sizes` 拆分后递归 |
| `QKVParallelLinear` | `"q" \| "k" \| "v" \| None` | 名称映射到 rank 本地 offset/size（`_get_shard_offset_mapping`）；`None` 走 `_load_fused_module_from_checkpoint` 拆 `total_num_heads/head_size` |

QKV 的 GQA 切分规则（`linear.py:1018`）：
```
tp_size >= total_num_kv_heads  → num_kv_heads=1, num_kv_head_replicas=tp_size//total_num_kv_heads
否则                          → num_kv_heads=total_num_kv_heads//tp_size, replicas=1
```
加载时 k/v 的 `shard_rank = tp_rank // num_kv_head_replicas`（KV head 复制场景下多个 rank 共享同一段），q 的 `shard_rank = tp_rank`。融合 scale（`adjust_scalar_to_fused_array`，`linear.py:98`）把单个标量 scale 填进 N 元 fused 数组的对应槽位；FP8 block scale（`adjust_block_scale_shard`）与 Marlin（`adjust_marlin_shard`）会额外修正 offset/size。

### 平台 GEMM 分发

`layers/utils.py:dispatch_unquantized_gemm()`：ROCm → `rocm_unquantized_gemm`（aiter triton/wvSplitK/hipblaslt 多路径），CPU → `cpu_unquantized_gemm`（zen-torch 预打包 / sgl-kernel `weight_packed_linear` / oneDNN `onednn_mm` 三级分发，小权重走 SGL、大权重走 oneDNN），其余 → `torch.nn.functional.linear`。

### Norm 层（layernorm.py）

全部为 `CustomOp` 注册，带 `forward_native/forward_cuda/forward_xpu` 多后端：

| 类 | 注册名 | 公式/要点 |
|---|---|---|
| `RMSNorm` | `rms_norm` | `x·w/sqrt(E[x²]+eps)`；`var_hidden_size` 可覆盖方差维度；`fused_add_rms_norm` 支持残差融合；`VLLM_BATCH_INVARIANT` 下走 `rms_norm_batch_invariant` |
| `GemmaRMSNorm` | `gemma_rms_norm` | weight 初始化为 0，`x*(1+w)`；`(x*w).to(orig_dtype)` 顺序不同 |
| `RMSNormGated` | `rms_norm_gated` | 分组 RMSNorm（`group_size`）+ 可选 gate（silu/sigmoid/swish）；`norm_before_gate` 决定 `norm(x)*act(z)` 还是 `norm(x*act(z))` |
| `LayerNorm` | — | 普通 nn.Module，fp32 `F.layer_norm` 后 cast 回原 dtype |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
