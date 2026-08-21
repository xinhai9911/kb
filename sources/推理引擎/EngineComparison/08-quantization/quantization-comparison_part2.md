## 量化体系对比：加载/检查点、硬件后端与在线量化（vLLM vs SGLang）

本文为 [quantization-comparison.md](quantization-comparison.md) 的续篇，覆盖量化 config 的来源与权重处理链路、与硬件平台后端的衔接，以及在线量化的对照。

### 一、加载/检查点：量化 config 来源与权重处理

| 环节 | vLLM | SGLang |
|---|---|---|
| 入口 | 三段式：① `ModelConfig._verify_quantization`（`config/model.py:1205`）名字裁决 → ② `weight_utils.get_quant_config`（`weight_utils.py:240`）实例化 → ③ `VllmConfig._get_quantization_config`（`config/vllm.py:743`）能力校验 | 单入口 `model_loader/loader.py::_get_quantization_config` → `weight_utils.get_quant_config`（`weight_utils.py:263`） |
| 方法认领 | `override_quantization_method(hf_quant_cfg, user_quant, hf_config)` 按固定 `overrides` 顺序探测（`auto_gptq`→…→`humming`，重后端最后）；用户显式值不一致报错 | 保留 `override_quantization_method` 接口（`base_config.py:173`）；用户方法名直接经 `get_quantization_config(model_config.quantization)` 查表，无多级 override 链 |
| checkpoint config 读取 | 主路径 `hf_config.quantization_config`（视觉模型回退 `text_config`）；`compression_config`（compressed-tensors 旧字段）；`hf_overrides` 支持 `quantization_config_file`/`quantization_config_dict_json`；`modelopt_mixed` 缺 `quantized_layers` 时穿透到文件 | `resolve_checkpoint_quant_spec(model_config.hf_config)` 读 `quant_method`；`modelopt_mixed` 缺 per-layer map 或 KV 元数据时同样穿透到 `hf_quant_config.json`（`weight_utils.py:278-291`） |
| 配置文件名 | `get_config_filenames()` 抽象方法，各方法定义搜索名（`quantize_config.json`/`hf_quant_config.json`/`quantization_config.json` 等） | 同接口；GGUF 无配置文件特例 `from_config({})`（`weight_utils.py:272`）；bitsandbytes/QLoRA 从 adapter 模型取 |
| 注入的运行时元数据 | compressed-tensors 含 `config_groups` 时注入 `total_num_heads`/`total_num_kv_heads`（TP-aware KV scale 加载） | 注入 `packed_modules_mapping`（模型类注入，`loader.py:219`）+ `hf_config`；`REQUANTIZATION_METHODS` 时注入 `requantization_method`（nvfp4/fp8→mxfp4 重量化，`weight_utils.py:297`） |
| 权重处理时机 | `process_weights_after_loading`：转置/repack/marlin prepare；`uses_meta_device=True` 时权重建 meta device 逐层量化降峰值内存（在线量化） | 同概念：scheme 的 `process_weights_after_loading` 做 `awq_marlin_repack`/`marlin_permute_scales` 等（`awq_kernels.py`） |
| KV scale 映射 | `get_cache_scale_mapper()`（`base_config.py:204`）返回 `WeightsMapper` 正则规则，`AutoWeightsLoader` 自动套用；`_ignore_unexpected_suffixes` 允许 checkpoint 有、模型无 | `kv_cache.py` 处理 KVCacheScaleParameter；FP8 KV 打包走 `kernels/ops`（`mla_kv_pack_quantize_fp8`/`fused_fp8_qkv_kv_cache`） |
| 重量化支持 | 无统一重量化入口（在线 `online` 是加载时量化而非 checkpoint 改写） | `REQUANTIZATION_METHODS`（`weight_utils.py:297`）+ `Fp8Config.is_fp4_experts`/`SGLANG_DSV4_FP4_DEQUANT` 把 DSV4 FP4 专家转 FP8（`loader.py:263-283`） |

> 关键差异 ②：vLLM 用 **override 探测链**（checkpoint 方法名 + 用户值联合裁决）与「`hf_overrides` 显式注入」两大机制选择 config 类；SGLang 简化为 **方法名直查表** + 平台条件覆写（NPU 上 `gptq`/`mxfp4` 指向 Ascend 专用 Config），并额外支持 checkpoint 侧的 **重量化转写**（DSV4 FP4→FP8、nvfp4/fp8→mxfp4）。

### 二、与硬件后端衔接

| 维度 | vLLM | SGLang |
|---|---|---|
| 平台放行 | `current_platform.verify_quantization(self.quantization)`（`config/model.py`）；平台层在 `vllm/platforms/` | `current_platform.is_out_of_tree()` 时优先 `current_platform.get_quantization_config(quantization)`（`quantization/__init__.py:163`）——OOT 平台可整体接管方法实现 |
| 平台分派位置 | 方法内分支：CPU/XPU/GPU 走不同 method 类（如 `AutoAWQMarlinLinearMethod` vs `AutoAWQLinearMethod`）；内核选择 `init_fp8_linear_kernel` 按平台 | `hardware_backend/` 6 平台目录（`gpu/cpu/npu/mlx/musa/xpu`）各带 `quantization/` 平台分派壳（`gpu/quantization/awq_kernels.py`/`gptq_kernels.py`；CPU 同构），由 scheme 引用 |
| 平台能力清单 | 方法名注册时自动 append 到 `current_platform.supported_quantization`（`register_quantization_config`） | `CPU_QUANTIZATION_METHODS` 白名单（CPU+AMX 时校验，`quantization/__init__.py:154`）；NPU/MPS 按平台条件注入方法 |
| NPU 深度适配 | 无独立 NPU 量化路径（XPU/CPU 有） | `hardware_backend/npu/quantization/`：`linear_method_npu`/`moe_methods`/`online_moe_methods`；`GPTQAscendConfig`/`Mxfp4W4A4Config` 专属方案 |
| 平台分派粒度 | 方法 → 平台 → 内核 两级 | scheme → **平台壳**（选 kernel 门面）→ `BaseFusedOp`（`forward_<device>` × `forward_<backend>` 正交），三级且内核出处与设备解耦 |

### 三、在线量化对比

| 维度 | vLLM | SGLang |
|---|---|---|
| 入口 | `--quantization online` + 6 简写（`fp8_per_tensor`/`fp8_per_block`/`fp8_per_channel`/`mxfp8`/`int8_per_channel_weight_only`/`nvfp4_per_token`） | `nvfp4_online`（`NvFp4OnlineConfig`） |
| 配置 | `OnlineQuantizationConfig`（`online/base.py:86`）+ `QuantSpec`（weight/activation 两个 `QuantKey`，activation 暂拒）+ `QuantizationConfigArgs`；`_dispatch`（`online/base.py:130`）按 weight `QuantKey` 查 `_ONLINE_LINEAR_METHODS`/`_ONLINE_MOE_METHODS` | 独立 `OnlineMoEMethodBase` 族 + NPU `online_moe_methods`；`fp8`/`w8a8_*` 亦可加载时量化（依赖 scheme 的 `uses_meta_device`） |
| 派发键 | `QuantKey`（`utils/quant_utils.py:161`）= dtype + `ScaleDesc`(static/group_shape) + `scale2` + symmetric；`GroupShape` 编码 `PER_TENSOR/PER_TOKEN/PER_CHANNEL` | 无等价 QuantKey 抽象，方法名直接映射 |
| 重量加载 | `uses_meta_device=True`，全精度权重建 meta device，`process_weights_after_loading` 逐层量化（QeRL layerwise） | 同思路：scheme 处理在线量化权重；NPU 有 `online_moe_methods` 专门路径 |

### 四、方法名映射速查

| vLLM 名 | SGLang 名 | 说明 |
|---|---|---|
| `awq`/`auto_awq`/`awq_marlin` | `awq`/`awq_marlin` | SGLang 少两个别名 |
| `gptq`/`auto_gptq`/`gptq_marlin` | `gptq`/`gptq_marlin` | 同上 |
| `fp8` | `fp8`/`w8a8_fp8` | SGLang 拆出独立 W8A8 方案 |
| `modelopt_mxfp8` | `mxfp8`→`Fp8Config` | SGLang 复用 Fp8Config |
| `mxfp4`（MoE） | `mxfp4`（CUDA/CPU）/`mxfp_w4a8`（NPU） | NPU 上被覆盖 |
| `experts_int8` | `w8a8_int8` | 概念对应 |
| `deepseek_v4_fp8` | （`quark_int4fp8_moe` 覆盖类似场景） | 实现路径不同 |
| — | `bitsandbytes`/`gguf`/`auto-round`/`modelslim`/`petit_nvfp4`/`mlx_q4`/`mlx_q8` | SGLang 独有 |
| `torchao`/`inc`/`fbgemm_fp8`/`fp_quant` | — | vLLM 独有（后两者已废弃） |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
