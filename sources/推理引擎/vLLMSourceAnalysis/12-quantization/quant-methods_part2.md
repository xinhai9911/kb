## 在线量化简写对照与适用场景速查

本文承接 [quant-methods.md](quant-methods.md)，给出在线量化的 `QuantKey` 派发表与各方法适用场景。注册、选择与接口契约见 [quantization-overview.md](quantization-overview.md)。

### QuantKey 与在线简写对照

`vllm/config/quantization.py` 的 `_ONLINE_SHORTHANDS` 把简写脱糖为 `QuantizationConfigArgs`，`QuantSpec.weight` 用 `QuantKey`（`utils/quant_utils.py:161`：dtype + ScaleDesc + scale2 + symmetric）编码。`OnlineQuantizationConfig._dispatch`（`online/base.py:130`）以 weight `QuantKey` 为键查表：

| 简写（`--quantization`） | weight `QuantKey` | linear 方法 | moe 方法 |
|---|---|---|---|
| `fp8_per_tensor` | `kFp8StaticTensorSym` | `Fp8PerTensorOnlineLinearMethod` | `Fp8PerTensorOnlineMoEMethod` |
| `fp8_per_block` | `kFp8Static128BlockSym` | `Fp8PerBlockOnlineLinearMethod` | `Fp8PerBlockOnlineMoEMethod` |
| `fp8_per_channel` | `kFp8StaticChannelSym` | `Fp8PtpcOnlineLinearMethod` | `Fp8PtpcOnlineMoEMethod` |
| `mxfp8` | `kMxfp8Dynamic` | `Mxfp8OnlineLinearMethod` | `Mxfp8OnlineMoEMethod` |
| `mxfp4` | `kMxfp4Static` | `Mxfp4OnlineLinearMethod` | `Mxfp4OnlineMoEMethod` |
| `int8_per_channel_weight_only` | `kInt8StaticChannelSym` | —（linear 不量化） | `Int8OnlineMoEMethod` |
| `nvfp4_per_token` | `kNvfp4Static` | —（linear 不量化） | `Nvfp4OnlineMoEMethod` |

- `QuantKey` 家族（`utils/quant_utils.py:193` 起）：`ScaleDesc` = `dtype` + `static` + `group_shape`；`GroupShape` 用 `(row, col)` 编码，`PER_TENSOR=(-1,-1)` / `PER_TOKEN=(1,-1)` / `PER_CHANNEL=(-1,1)`。NVFP4 用 `scale2=kStaticTensorScale` 表达两级缩放。
- `QuantSpec` 的 `activation` 字段目前一律被 `_dispatch` 拒绝（「activation override … is not yet supported」），激活格式由方法类内部的 `supported_activation_quant` 决定。
- `QuantizationConfigArgs` 中 `int8_per_channel_weight_only` 与 `nvfp4_per_token` 只设 `moe`——linear 层保持不量化（`UnquantizedLinearMethod`）。
- 在线方法统一继承 `OnlineMoEMethodBase`（`online/moe_base.py:19`）：`uses_meta_device=True`，全精度权重建在 meta device，由 `initialize_online_processing`（QeRL layerwise 重加载系统）在 `process_weights_after_loading` 中逐层量化，降低加载峰值内存。

### 适用场景速查

| 场景 | 推荐方法 |
|---|---|
| Ampere+ 通用 FP8，兼顾精度与吞吐 | `fp8`（serialized）/ `fbgemm_fp8`（在线） |
| 无需预量化 checkpoint，加载时量化 | `online` 或 `fp8_per_tensor` / `fp8_per_block` 简写 |
| 4-bit 权重、老 GPU（Turing/Volta）兼容 | `gptq` / `gptq_marlin`（min cap 60） |
| AWQ 生态 checkpoint | `awq`（Marlin 后端优先，批量不变式场景回落 Triton） |
| llmcompressor / 元数据驱动多格式 | `compressed-tensors` |
| NVIDIA ModelOpt / TensorRT-LLM 导出 | `modelopt` / `modelopt_fp4` / `modelopt_mxfp8` |
| Blackwell（SM100）极致吞吐 | NVFP4（`modelopt_fp4`）或 MXFP4（`mxfp4`，MoE） |
| MoE 模型专家压缩 | `moe_wna16`（W4/W8A16）、`experts_int8`（在线 INT8） |
| PyTorch / AMD / Intel 平台生态 | `torchao` / `quark` / `inc` |
| 混合精度统一方案（Linear+MoE） | `humming` |
| DeepSeek V4 家族 | `deepseek_v4_fp8`（按 `expert_dtype` 分派） |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
