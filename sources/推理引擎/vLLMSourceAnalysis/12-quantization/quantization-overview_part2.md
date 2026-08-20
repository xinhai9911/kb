## 量化体系：在线 QuantKey 派发、接口契约与衔接点

本文为 [quantization-overview.md](quantization-overview.md) 的续篇，覆盖在线量化配置的派发机制、`QuantizeMethodBase` / `QuantizationConfig` / `LinearMethodBase` / `FusedMoEMethodBase` 接口契约，及量化与 `model_executor` 各层类型的衔接点。

### 在线量化的 QuantKey 派发

在线量化不依赖 checkpoint，配置来自 `vllm/config/quantization.py`：`QuantSpec`（`weight`/`activation` 两个 `QuantKey`，`None` 表示回退方法类默认）+ `QuantizationConfigArgs`（`linear`/`moe` 两个 spec + `ignore` 跳过列表）。`OnlineQuantizationConfig._dispatch`（`online/base.py:130`）按 `spec.weight` 这个 `QuantKey` 查 `_ONLINE_LINEAR_METHODS` / `_ONLINE_MOE_METHODS` 两表选方法类，查不到抛 `ValueError`；`spec.activation` 目前一律拒绝，激活格式由方法类的 `supported_activation_quant` 决定。`QuantKey`（`utils/quant_utils.py:161`）= `dtype` + `scale: ScaleDesc` + `scale2` + `symmetric`，简写脱糖与完整派发表见 [quant-methods_part2.md](quant-methods_part2.md)。

### 接口契约

**`QuantizeMethodBase`（`base_config.py:20`）** —— 全部量化方法的根：

| 成员 | 必选 | 说明 |
|---|---|---|
| `uses_meta_device: bool = False` | 类属性 | `True` 时权重建在 meta device，在 `process_weights_after_loading` 中逐层量化，降低加载峰值内存 |
| `create_weights(layer, *args, **kwargs)` | 抽象 | 把参数注册为 `layer` 的属性 |
| `apply(layer, *args, **kwargs) -> Tensor` | 抽象 | 前向计算 |
| `embedding(layer, ...)` | 可选 | 默认 `NotImplementedError`；`method_has_implemented_embedding()` 用 `inspect.getattr_static` 比对是否被覆写 |
| `tie_weights(layer, embed_tokens)` | 可选 | 默认 `layer.weight = embed_tokens.weight`；权重被 repack 的方法需覆写 |
| `process_weights_after_loading(layer)` | 可选 | 默认空；转置 / repack / marlin prepare 都在此 |

**`QuantizationConfig`（`base_config.py:87`）**：

| 成员 | 类型 | 说明 |
|---|---|---|
| `get_name()` | 抽象 | 返回 `QuantizationMethods` 中的名字 |
| `get_supported_act_dtypes()` | 抽象 | 受支持激活 dtype 列表 |
| `get_min_capability()` | 抽象 classmethod | 最小 SM 能力（70=Volta / 75=Turing / 80=Ampere） |
| `get_config_filenames()` | 抽象 staticmethod | 模型目录下要搜的配置文件名 |
| `from_config(config)` | 抽象 classmethod | 由 checkpoint 配置 dict 构造 |
| `get_quant_method(layer, prefix)` | 抽象 | 按层类型 + 层名返回 `QuantizeMethodBase`，`None` 表示该层不支持 |
| `override_quantization_method(hf_quant_cfg, user_quant, hf_config=None)` | classmethod，默认 `None` | checkpoint 格式认领，只在特殊情形覆写 |
| `packed_modules_mapping` | `dict[str, list[str]]` | 实例属性，由模型初始化时写入；融合层（qkv_proj / gate_up_proj）跳过判定要靠它 |
| `get_from_keys(config, keys)` / `get_from_keys_or(..., default)` | staticmethod | 多别名取值助手 |
| `get_cache_scale_mapper()` | staticmethod | 返回 `WeightsMapper`，`AutoWeightsLoader` 自动套用，模型 `load_weights` 无需感知 KV scale |
| `apply_vllm_mapper(hf_to_vllm_mapper)` | 默认空 | 把配置里的 HF 模块名重写为 vLLM 结构名 |
| `maybe_update_config(model_name, hf_config, revision)` | 默认空 | 配置初始化后的补充推断 |
| `_ignore_unexpected_suffixes` | 类属性 | `.q_scale`/`.k_scale`/`.v_scale`/`.q_zero_point`/`.k_zero_point`/`.v_zero_point`，加载期允许「checkpoint 有、模型无」 |

`get_cache_scale_mapper()` 默认是一组 `regex` 重写规则（`base_config.py:204`），把各家命名统一到 `.attn.{q,k,v}_scale`：废弃的 `.kv_scale`、ModelOpt 的 `.self_attn.{k,v}_proj.{k,v}_scale`、融合 `qkv_proj`/`qkqkv_proj`、NemotronH 的 `.mixer.*`、HYV3 的 `.self_attn.q.scale` 等。`Fp8Config` 用 `|` 与默认 mapper 合并，追加 compressed-tensors 的 `.k_proj.output_scale` 后缀。

**`LinearMethodBase`（`vllm/model_executor/layers/linear.py:125`）**：

```python
def create_weights(self, layer, input_size_per_partition, output_partition_sizes,
                   input_size, output_size, params_dtype, **extra_weight_attrs)
def apply(self, layer, x, bias=None) -> torch.Tensor
```

`output_partition_sizes` 是「本 rank 上各逻辑权重的输出宽度列表」（QKVLinear 即 `[Wq, Wk, Wv]` 宽度），`input_size`/`output_size` 是跨 rank 全局尺寸。`extra_weight_attrs["weight_loader"]` 是参数加载器。`LinearBase.__init__`（`linear.py:258`）契约很硬：`quant_config` 非空时 `get_quant_method` 返回 `None` 就抛 `ValueError`——所以不支持 Linear 的方法（如 `Mxfp4Config`）必须返回 `UnquantizedLinearMethod()` 而非 `None`。

**`FusedMoEMethodBase`（`vllm/model_executor/layers/fused_moe/fused_moe_method_base.py:27`）**：

| 成员 | 说明 |
|---|---|
| `__init__(moe: FusedMoEConfig)` | 持有 `self.moe`、`self.moe_quant_config: FusedMoEQuantConfig \| None`、`self.moe_kernel: mk.FusedMoEKernel \| None` |
| `create_weights(layer, num_experts, hidden_size, intermediate_size_per_partition, params_dtype, **extra)` | 抽象；签名与 Linear 完全不同 |
| `get_fused_moe_quant_config(layer)` | 抽象；返回 `FusedMoEQuantConfig \| None` |
| `maybe_roundup_sizes(hidden_size, intermediate_size_per_partition, act_dtype, moe_parallel_config)` | 内核对齐要求下的 shape 上取整 |
| `uses_weight_scale_2_pattern()` | 默认 `False`；FP4 类方法返回 `True`（用 `weight_scale_2` 而非 `weight_scale`） |
| `supports_internal_mk` / `mk_can_overlap_shared_experts` / `is_monolithic` / `topk_indices_dtype` | 由 `self.moe_kernel` 推导的过渡期属性 |
| `skip_forward_padding` / `has_unpadded_output` / `supports_eplb` | 默认 `False` 的能力声明 |
| `method_name` | 默认类名 |

`RoutedExperts._get_quant_method`（`fused_moe/routed_experts.py:189`）负责调用；MoE 方法统一接收 `layer.moe_config`。

**`BaseKVCacheMethod`（`kv_cache.py:42`）** —— 唯一 `create_weights(layer)` 只带 layer 的方法：

- 建 4 个 `KVCacheScaleParameter`：`q_scale`、`k_scale`、`v_scale`、`prob_scale`，初值 `-1.0`（无效哨兵）；`weight_loader` 只接受 `numel()==1` 的标量，per-head scale 走 compressed-tensors 的 `_tp_aware_loader`。`apply()` 直接 `raise RuntimeError`——不参与前向。
- `process_weights_after_loading` 核心逻辑：per-token-head 量化时 scale 恒 1.0、kernel 动态算；`is_quantized_kv_cache` 时 k/v 都 >0 用各自值、都 <0 用 1.0、仅一个 >0 说明是旧融合 `kv_scale`，取 `max` 复制给两者；FNUZ 平台（`current_platform.is_fp8_fnuz()`）一律 `*2`，非 per-tensor 抛 `ValueError`。`q_scale` 缺失回落 `k_scale` 并 `warning_once`（只影响 FP8 attention）。
- 最终写入 `layer._{q,k,v}_scale`（tensor）、`_{k,v}_scale_float`（python float）、`_{k,v}_scale_cpu`（AITER 融合 kernel 读的 host 副本），随后 `del` 掉 4 个加载期参数；`fp8_e4m3` 且 scale 全 1.0 时告警「verify that k/v_scale scaling factors are properly set」。

### 与 model_executor 的衔接点

| 层类型 | 调用位置 | 传入 |
|---|---|---|
| `LinearBase` | `layers/linear.py:260` | `self`, `prefix` |
| `RoutedExperts` | `layers/fused_moe/routed_experts.py:201` | `self`, `prefix` |
| `VocabParallelEmbedding` / `ParallelLMHead` | `layers/vocab_parallel_embedding.py:286` | `self`, `prefix` |
| `Attention` | 由各 config 的 `get_quant_method` 中 `isinstance(layer, Attention)` 分支处理，返回 `*KVCacheMethod` |
| `MLAAttention` | `layers/attention/mla_attention.py:1136` | `self`, `self.layer_name` |
| LoRA 包装层 | `lora/layers/base_linear.py:186` `_get_quant_method()` | 转发到 `base_layer.quant_method` |

`prefix` 一律是 state dict 中的完整层名，跳过判定（`is_layer_skipped` / `should_ignore_layer`）依赖它与 `packed_modules_mapping`。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
