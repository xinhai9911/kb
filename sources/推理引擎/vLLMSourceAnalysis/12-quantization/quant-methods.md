## 量化方法对比：方法表、内核选择与适用场景

本文基于 `vllm/model_executor/layers/quantization/` 各方法实现，汇总每种量化方法的注册名、配置类、方法类、内核后端与关键参数。配套文档：[quantization-overview.md](quantization-overview.md) 覆盖注册表与接口契约；[quant-methods_part2.md](quant-methods_part2.md) 覆盖在线简写对照与适用场景速查。

### 方法总表

| CLI / checkpoint 名 | 配置类（文件） | 最小算力 | 激活 dtype | 加载方式 | 关键特性 |
|---|---|---|---|---|---|
| `fp8` | `Fp8Config`（`fp8.py:92`） | 75 | bf16/fp16 | checkpoint serialized 或在线 | W8A8 FP8；`activation_scheme=static/dynamic`；可选 `weight_block_size` 分块权重；MoE 走 `Fp8MoEMethod` + oracle 选核 |
| `fbgemm_fp8`（废弃） | `FBGEMMFp8Config`（`fbgemm_fp8.py:45`） | 80 | bf16/fp16 | 在线 | FBGEMM kernel；无 FP8 硬件（cap<89）自动切 Marlin；`input_scale_ub`（checkpoint 键 `activation_scale_ub`） |
| `fp_quant`（废弃） | `FPQuantConfig`（`fp_quant.py:30`） | — | — | 在线 | 自定义浮点量化（`DEPRECATED_QUANTIZATION_METHODS` 之一） |
| `awq`/`auto_awq`/`awq_marlin` | `AutoAWQConfig`（`auto_awq.py:171`） | 75 | fp16/bf16 | checkpoint | W4A16 权重（仅 4bit）；Marlin / Triton / CPU / XPU 四后端；`quantize_config.json` 或 `quant_config.json` |
| `gptq`/`auto_gptq`/`gptq_marlin` | `AutoGPTQConfig`（`auto_gptq.py:97`） | 60 | fp16/bf16 | checkpoint | W4/W8 对称权重（Marlin）；`desc_act`（act_order）、`is_sym`、`dynamic` 逐模块覆盖；`quantize_config.json` |
| `moe_wna16` | `MoeWNA16Config`（`moe_wna16.py:47`） | 70 | bf16/fp16 | checkpoint | MoE 专家 W4/W8A16；Linear 层转交 AutoAWQ/AutoGPTQ；checkpoint `quant_method` 须为 `gptq`/`awq` |
| `modelopt` | `ModelOptFp8Config`（`modelopt.py:363`） | 80 | bf16/fp16 | checkpoint | NVIDIA ModelOpt FP8（per-tensor，支持静态激活）；KV cache FP8；`exclude_modules` 通配符；`hf_quant_config.json` |
| `modelopt_fp4` | `ModelOptNvFp4Config`（`modelopt.py:994`） | 75 | bf16/fp16/e4m3 | checkpoint | NVFP4 W4A4 与 W4A16；`group_size` 默认 16；`uses_weight_scale_2_pattern` |
| `modelopt_mxfp8` | `ModelOptMxFp8Config`（`modelopt.py:1657`） | 80 | bf16 | checkpoint | MXFP8 W8A8（仅 serialized checkpoint，动态量化不支持）；Marlin 内核支持 SM80+ |
| `modelopt_mixed` | `ModelOptMixedPrecisionConfig`（`modelopt.py:2143`） | — | bf16/fp16 | checkpoint | 逐层混合精度；`quantized_layers` 在新旧 checkpoint 中位置不同，缺省时穿透到文件加载 |
| `compressed-tensors` | `CompressedTensorsConfig`（`compressed_tensors/compressed_tensors.py:82`） | 70 | f32/f16/bf16 | checkpoint | 元数据驱动：`target_scheme_map` + `kv_cache_scheme` + 可选 `transform_config`（Hadamard）；`config_groups` 注入 head 数做 TP-aware 加载 |
| `quark` | `QuarkConfig`（`quark/quark.py:58`） | 70 | fp16/bf16 | checkpoint | AMD Quark 生态；`pack_method="reorder"`、`kv_cache_group`；DeepSeek-V3 系 fp4 checkpoint 自动开 `dynamic_mxfp4_quant` |
| `torchao` | `TorchAOConfig`（`torchao.py:134`） | 75 | f32/f16/bf16 | checkpoint / 用户配置 | 依赖 `torchao>=0.10.0`；`quant_type` dict / `from_config_file` / `from_config_dict_json` 三种入口 |
| `inc` | `INCConfig`（`inc/inc.py:32`） | 60 | fp16/bf16 | checkpoint | Intel Neural Compressor；`bits∈{2,3,4,8}`、`packing_format`/`backend` 枚举约束；`quantization_config.json` |
| `mxfp4` | `Mxfp4Config`（`mxfp4.py:44`） | 80 | bf16 | checkpoint | MXFP4（OCP micro-scaling）；Linear 未实现（回落 `UnquantizedLinearMethod`），MoE 用 `Mxfp4MoEMethod`（Triton） |
| `gpt_oss_mxfp4` | `GptOssMxfp4Config`（`mxfp4.py:105`） | 80 | bf16 | checkpoint | GPT-OSS 专用；认领 checkpoint `quant_method:"mxfp4"`（不回落，避免误吞全部 mxfp4 模型） |
| `deepseek_v4_fp8` | `DeepseekV4FP8Config`（`models/deepseek_v4/quant_config.py:29`） | — | bf16/fp16 | checkpoint | DeepSeek V4 家族；按 `expert_dtype`（fp4→`Mxfp4MoEMethod`，fp8→block FP8）分派 MoE；Quark MXFP4 导出自动转写为 fp8 格式 |
| `humming` | `HummingConfig`（`humming.py:148`） | 75 | bf16/fp16 | checkpoint | 统一混合精度（Linear + MoE 一体化）；接收 compressed-tensors / modelopt 格式 checkpoint；gpt-oss 改用 `--moe-backend humming` |
| `experts_int8` | `ExpertsInt8Config`（`experts_int8.py:22`） | 80 | bf16/fp16 | 在线 | 仅 MoE 专家在线 INT8（`Int8OnlineMoEMethod`），Linear 不量化；建议改用 `--quantization int8_per_channel` |
| `online` + 6 简写 | `OnlineQuantizationConfig`（`online/base.py:86`） | 75 | bf16/fp16 | 在线 | 加载时量化 bf16/fp16 权重，无需预量化 checkpoint；`QuantSpec` 按 weight `QuantKey` 派发 |
| `mxfp8`（checkpoint） | `ModelOptMxFp8Config` | — | — | — | 同时是 checkpoint 名与在线简写：MiniMax 系 checkpoint 标 `quant_method:"mxfp8"` 时按 ModelOpt MXFP8 加载 |

### 主流方法关键参数

| 配置类 | 关键构造参数 | 语义 |
|---|---|---|
| `Fp8Config` | `is_checkpoint_fp8_serialized` | 权重是否已按 FP8 序列化；`False` 时 Linear 走在线 `Fp8PerTensorOnlineLinearMethod` |
| | `activation_scheme` | `"static"` / `"dynamic"`；分块量化强制 `dynamic` |
| | `weight_block_size=[r,c]` | 分块权重（如 `[128,128]`），要求 serialized + dynamic |
| | `store_dtype` | `"mxfp4"` 时 MoE 改用 `Mxfp4MoEMethod` 存储 |
| `FBGEMMFp8Config` | `input_scale_ub` | 激活缩放上界（checkpoint `activation_scale_ub`）；`use_marlin` 由算力自动决定 |
| `AutoAWQConfig` | `weight_bits`、`group_size`、`zero_point` | W4A16 + 按 group 缩放 + 非对称零点；`TYPE_MAP={4: uint4}` 仅支持 4bit |
| | `lm_head_quantized` | 是否量化 `ParallelLMHead` |
| | `modules_to_not_convert` | 跳过层（加载期可从未量化 dtype 的 safetensors 元数据推断） |
| `AutoGPTQConfig` | `weight_bits`、`group_size`、`desc_act`、`is_sym` | `TYPE_MAP={(4,True): uint4b8, (8,True): uint8b128}`，仅对称 |
| | `dynamic` | 正则键（`+:`/`-:` 前缀）的逐模块位宽/分组覆盖（GPTQModel 约定） |
| | `modules_in_block_to_quantize` | 量化层白名单（autoround 也复用该字段） |
| `ModelOptQuantConfigBase` | `exclude_modules` | 排除层通配符；`is_layer_excluded` 依次做 exact / substring / `fnmatch` 匹配 |
| | `LinearMethodCls` / `FusedMoEMethodCls` / `KVCacheMethodCls` | 类级钩子，子类替换即换方法实现 |
| `OnlineQuantizationConfig` | `args: QuantizationConfigArgs` | `linear`/`moe` 两个 `QuantSpec`（weight `QuantKey`）+ `ignore` 跳过列表 |

### 后端 / 内核选择逻辑

**AWQ 四后端**（`auto_awq.py:285` `get_quant_method`）——方法名不决定内核，按平台与 shape 动态选：

```python
# CPU/XPU → AutoAWQMarlinLinearMethod（CPUWNA16LinearKernel / XPUwNa16LinearKernel）
# CUDA + Marlin 可用 + 非 VLLM_BATCH_INVARIANT → AutoAWQMarlinLinearMethod（Conch/Exllama/Marlin）
# 其余 → AutoAWQLinearMethod（Triton 内核）
# MoE：AutoAWQMoEMethod；tile 不匹配时回落 MoeWNA16Config
```

**FP8**：`Fp8LinearMethod.create_weights` 调 `init_fp8_linear_kernel`（`model_executor/kernels/linear/`），按平台在 Cutlass FP8 scaled-MM / Marlin FP8 / DeepGEMM 间选择；`fbgemm_fp8` 在无 FP8 硬件时 `prepare_fp8_layer_for_marlin` 转 Marlin 布局。MoE 端 `Fp8MoEMethod` 经 `select_fp8_moe_backend`（oracle）选择内核。

**MoE WNA16**：`MoeWNA16Method` 经 `select_wna16_moe_backend`（oracle）选择；`get_fused_moe_quant_config` 返回 `FusedMoEQuantConfig` 供 `RoutedExperts` 装配。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
