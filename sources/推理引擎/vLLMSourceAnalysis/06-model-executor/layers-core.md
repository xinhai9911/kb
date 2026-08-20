## layers 核心算子层

### 模块概览

`vllm/model_executor/layers/` 定义了模型推理用并行算子层。`__init__.py` 为空，无聚合导出。`attention/` 与 `mla.py` 由另一模块文档负责，本文不展开。

| 文件 | 内容 | 并行切分 |
|---|---|---|
| `linear.py` | 线性层全家桶 | 行/列/复本 |
| `activation.py` | 自定义激活（与 `fc+silu` 等融合） | 无 |
| `layernorm.py` | RMSNorm / LayerNorm | 无（按隐藏维整层计算） |
| `vocab_parallel_embedding.py` | 词表并行嵌入 + 并行 LM Head | 词表维 |
| `conv.py` | `Conv2dLayer`/`Conv3dLayer`（继承 `ConvLayerBase`，视觉模型） | 无（整张量复制计算） |
| `logits_processor.py` | 隐藏态 → logits（可 gather、scale、soft_cap） | TP gather / all-gather |
| `batch_invariant.py` | 与 batch size 无关的无算子可用实现 | - |
| `fused_*.py` / `lightning_attn.py` / `resampler.py` / `sparse_attn_indexer.py` 等 | 融合/专用层 | 视层而定 |

### 线性层（`linear.py`）

基类 `LinearBase(PluggableLayer)`，参数 `input_size`/`output_size`/`bias`/`skip_bias_add`/`params_dtype`/`quant_config`/`prefix`/`return_bias`/`disable_tp`/`tp_rank`/`tp_size`。量化层走 `quant_config.get_quant_method()` 得到 `quant_method`，权重统一由该方法 `create_weights()` 创建。

| 类 | 注册名 | 并行方式 | 前向通信 |
|---|---|---|---|
| `ReplicatedLinear` | `replicated_linear` | 不切分，每 GPU 完整复本 | 无 |
| `ColumnParallelLinear` | `column_parallel_linear` | 输出维按 TP 均分（`output_size_per_partition = output_size/tp_size`） | `gather_output=True` 时 `all-gather` |
| `MergedColumnParallelLinear` | （继承） | 多个子矩阵输出维拼接后整体列切分，加载时按 `output_sizes` 分 shard | 同上 |
| `QKVParallelLinear` | （继承） | q/k/v 三个逻辑矩阵列切分；`tp_size >= kv_heads` 时 KV 头复制 `tp/kv` 份 | 关闭 gather，配 `ColmParallel` attention |
| `RowParallelLinear` | `row_parallel_linear` | 输入维切分，输出维完整 | `reduce_results=True` 时 all-reduce（bias 仅 rank0 加） |
| `DCPGroupColumnParallelLinear` | （继承） | 权重按 DCP 组粒度切分（`tp_size // dcp_world_size` 有效 TP） | decode 免 query all-gather |
| `MinimaxM3QKVParallelLinearWithIndexer` | （继承） | QKV + lightning indexer 5 组列切分，M3 专用 | - |

- `WEIGHT_LOADER_V2_SUPPORTED` 列表：支持 `weight_loader_v2`（走 `BasevLLMParameter.load_column/row/qvk_weight`）的量化方法名；其余用经典 `weight_loader`（`narrow` + `copy_`）。
- 加载特例：`adjust_marlin_shard`（Marlin tile 缩放）、`adjust_block_scale_shard`（block quant scale）、`adjust_scalar_to_fused_array`（每矩阵标量 scale 填入融合数组）、`_load_fused_module_from_checkpoint`（Phi-3 等盘上已融合的 qkv/gate_up 权重按 shard_id 拆分）。
- `LinearMethodBase`：`create_weights()` + `apply()` 抽象；`UnquantizedLinearMethod` 为其非量化实现，CPU 上转发到 `dispatch_cpu_unquantized_gemm`。

### 参数类型（`parameter.py`）

| 类 | 用途 |
|---|---|
| `BasevLLMParameter` | 线性层参数基类：携带 `weight_loader` 回调、`tp_rank`/`tp_size`，TPU 下包装同步 loader |
| `_ColumnvLLMParameter` | 列并行 `load_column_parallel_weight`/`load_merged_column_weight`/`load_qkv_weight`（含 KV 头复制偏移） |
| `RowvLLMParameter` | 行并行 `load_row_parallel_weight`（按 `input_dim` narrow） |
| `ModelWeightParameter` | 线性权重（列+行），通用形态 |
| `GroupQuantScaleParameter` / `ChannelQuantScaleParameter` / `BlockQuantScaleParameter` | 组/通道/块量化 scale，`BlockQuant` 还支持按 `weight_block_size` 调整 shard |
| `PerTensorScaleParameter` | 每逻辑矩阵一个标量 scale，按 shard_id 装入融合数组 |
| `PackedColumnParameter` / `PackedvLLMParameter` | 盘上 int4/int8 打包权重，按 `packed_factor`/`marlin_tile_size` 调整 shard 索引 |
| `SharedWeightParameter` | 支持层间共享张量（如 gate/up 变换），不随实例复制数据 |
| `permute_param_layout_` | 工具：重排参数 `input_dim`/`output_dim`/`packed_dim` 布局 |

### 量化方法（`quantization/`）

注册入口 `get_quantization_config()` / `register_quantization_config()`，定义于 `quantization/__init__.py`。方法到配置类映射见源码 `method_to_config`，主要：

| 方法串（不完全） | 配置类 | 文件 |
|---|---|---|
| `awq`/`awq_marlin`/`auto_awq` | `AutoAWQConfig` | `auto_awq.py` |
| `gptq`/`gptq_marlin`/`auto_gptq` | `AutoGPTQConfig` | `auto_gptq.py` |
| `fp8` | `Fp8Config` | `fp8.py` |
| `fbgemm_fp8`（弃用） | `FBGEMMFp8Config` | `fbgemm_fp8.py` |
| `modelopt`/`modelopt_fp4`/`modelopt_mxfp8`/`modelopt_mixed` | `ModelOpt*` | `modelopt.py` |
| `compressed-tensors` | `CompressedTensorsConfig` | `compressed_tensors/` |
| `gpt_oss_mxfp4` / `mxfp4` | `Mxfp4Config` / `ModelOptMxFp8Config` | `mxfp4.py` |
| `experts_int8` | `ExpertsInt8Config` | `experts_int8.py` |
| `moe_wna16` | `MoeWNA16Config` | `moe_wna16.py` |
| `torchao` | `TorchAOConfig` | `torchao.py` |
| `humming` | `HummingConfig` | `humming.py` |
| `quark` | `QuarkConfig` | `quark/` |
| `inc` | `INCConfig` | `inc.py` |
| `fp_quant`（弃用） | `FPQuantConfig` | `fp_quant.py` |
| `online`（及 `fp8_per_tensor` 等速记） | `OnlineQuantizationConfig` | `online/` |

`QuantizeMethodBase` 在每个量化方法模块中实现，`get_quant_method()` 按层类型（linear/attention/embedding）创建对应方法；`method_has_implemented_embedding()` 用于校验嵌入层。

### 激活函数（`activation.py`）

`get_act_fn()` / `get_act_and_mul_fn()` 按名取注册表；`*_and_mul` 系列为融合「激活 + 乘以 up」的 CUDA 算子（`x.shape[-1]//2` 切 gate/up）。

| 激活 | 注册名 | 计算 |
|---|---|---|
| `SiluAndMul` | `silu_and_mul` | SwiGLU：`silu(gate)*up` |
| `MulAndSilu` | `mul_and_silu` | `gate*silu(up)` |
| `GeluAndMul` | `gelu_and_mul` | GeGLU：`gelu(gate)*up` |
| `GeluAndMulSparse` | `gelu_and_mul_sparse` | Gemma3n：高斯 top-k 稀疏 gate 后 gelu 乘 up |
| `SiluAndMulWithClamp` | `silu_and_mul_with_clamp` | 夹取版 SwiGLU（MoE 共享专家），`alpha`/`beta` |
| `SituAndMul` | `situ_and_mul` | Kimi SituGLU（beta-tanh 平滑） |
| `SwigluOAIAndMul` | `swigluoai_and_mul` | GPT-OSS OAI 风格（`alpha=1.702`、`limit=7.0`） |
| `SwigluStepAndMul` | `swiglustep_and_mul` | 夹取版（Triton 内核） |
| `FatreluAndMul` | `fatrelu_and_mul` | MiniCPM FATReLU |
| `GELU`/`GELUTanh`/`NewGELU`/`FastGELU`/`QuickGELU`/`ReLUSquaredActivation`/`XIELU` | `gelu`/`gelu_tanh`/`gelu_new`/`gelu_fast`/`quick_gelu`/`relu2`/`xielu` | 各类 GELU 变体、`relu^2`、可学习参数的 xIELU |

### 归一化层（`layernorm.py`）

| 类 | 说明 |
|---|---|
| `RMSNorm`（`rms_norm`） | 有/无 weight、`var_hidden_size` 覆盖、`fused_add_rms_norm` 残余融合；`VLLM_BATCH_INVARIANT` 时走 `rms_norm_batch_invariant` |
| `GemmaRMSNorm`（`gemma_rms_norm`） | `x*(1+w)`、`(x*w).to(orig_dtype)`，weight 初始为 0 |
| `RMSNormGated`（`rms_norm_gated`） | 分组 RMS + 可选 SiLU/Sigmoid 门控（gate 在归一化前/后），`norm_before_gate` 控制 |
| `LayerNorm` | 普通 PyTorch `F.layer_norm` 包装，fp32 累加 |
| `poly_norm` | 调 `vllm._custom_ops.poly_norm` |

### 嵌入与 LM Head（`vocab_parallel_embedding.py`）

- `vocab_size` 按 `DEFAULT_VOCAB_PADDING_SIZE=64` 对齐（先 pad 基础词表、再 pad LoRA 附加词表，LoRA 嵌入恒在张量尾部）。
- `VocabParallelEmbedding`（`vocab_parallel_embedding`）：词表维 TP 切分；`forward` TP>1 时先 `torch.compile` 的 `get_masked_input_and_mask` 生成 mask，`F.embedding` 后所有 rank `all-reduce`；`get_sharded_to_full_mapping()` 供采样重排 logits。
- `ParallelLMHead`（`parallel_lm_head`）：LM Head，权重只在 sampler 中使用，`forward` 抛 `RuntimeError`；`tie_weights` 与 embedding 共享权重。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)