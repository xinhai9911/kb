## 量化体系总览：注册、选择与接口契约

本文基于 `vllm/model_executor/layers/quantization/` 源码，说明量化方法如何注册、如何从 checkpoint / CLI 解析出唯一方法，以及各层类型（Linear / MoE / Attention / Embedding）的接口契约。方法对比与适用场景见 [quant-methods.md](quant-methods.md) 与 [quant-methods_part2.md](quant-methods_part2.md)；接口契约与 model_executor 衔接点见 [quantization-overview_part2.md](quantization-overview_part2.md)。

### 目录结构

| 路径 | 内容 |
|---|---|
| `quantization/__init__.py` | `QuantizationMethods` 字面量枚举、`QUANTIZATION_METHODS` 列表、`get_quantization_config`、`register_quantization_config` |
| `quantization/base_config.py` | 两个抽象基类 `QuantizeMethodBase`、`QuantizationConfig` |
| `quantization/*.py` | 单文件方法实现（`fp8.py`、`auto_awq.py`、`auto_gptq.py`、`modelopt.py`、`mxfp4.py`、`moe_wna16.py`、`fbgemm_fp8.py`、`experts_int8.py`、`fp_quant.py`、`torchao.py`、`humming.py`） |
| `quantization/kv_cache.py` | `BaseKVCacheMethod`、`KVCacheScaleParameter`（KV cache 缩放因子加载） |
| `quantization/online/` | 在线量化（加载时量化 bf16/fp16 权重）：`base.py` + `fp8.py`/`int8.py`/`mxfp4.py`/`mxfp8.py`/`nvfp4.py`/`moe_base.py` |
| `quantization/compressed_tensors/` | compressed-tensors 家族：`schemes/`（14 个 Linear scheme）、`compressed_tensors_moe/`（11 个 MoE 方法）、`transform/`（Hadamard 变换） |
| `quantization/quark/`、`quantization/inc/` | AMD Quark、Intel Neural Compressor 子体系（各带 `schemes/`） |
| `quantization/utils/` | 内核工具：`marlin_utils*.py`、`fp8_utils.py`、`int8_utils.py`、`mxfp4/6/8_utils.py`、`nvfp4_utils.py`、`machete_utils.py`、`allspark_utils.py`、`quant_utils.py`（`QuantKey`/`GroupShape`） |
| `quantization/turboquant/` | `config.py`（`TurboQuantConfig`）+ `centroids.py` |
| `quantization/input_quant_fp8.py` | `QuantFP8`（`CustomOp`），激活在线量化算子 |

### 注册表：QuantizationMethods

`__init__.py:12` 用 `typing.Literal` 声明全部合法方法名，`QUANTIZATION_METHODS = list(get_args(...))` 派生为可运行时追加的列表：

| 类别 | 方法名 |
|---|---|
| checkpoint 方法 | `awq`、`auto_awq`、`awq_marlin`、`gptq`、`auto_gptq`、`gptq_marlin`、`fp8`、`fbgemm_fp8`、`fp_quant`、`modelopt`、`modelopt_fp4`、`modelopt_mxfp8`、`modelopt_mixed`、`compressed-tensors`、`quark`、`moe_wna16`、`torchao`、`inc`、`mxfp4`、`gpt_oss_mxfp4`、`deepseek_v4_fp8`、`humming`、`experts_int8` |
| 在线量化 | `online` + 简写 `fp8_per_tensor`、`fp8_per_block`、`fp8_per_channel`、`int8_per_channel_weight_only`、`nvfp4_per_token`、`mxfp8` |

- `DEPRECATED_QUANTIZATION_METHODS = ["fbgemm_fp8", "fp_quant"]`（`__init__.py:49`），`ModelConfig._verify_quantization` 命中时告警。
- `mxfp8` 同时是 checkpoint 方法名与在线简写：`method_to_config` 显式映射到 `ModelOptMxFp8Config`，在线简写用 `setdefault` 注册，因此不会被覆盖（`__init__.py:164-175`）。

`get_quantization_config(quantization)` 是唯一工厂：先校验名字在 `QUANTIZATION_METHODS` 内，随后**惰性 import**（注释明确「avoid triggering `torch.compile` too early」）构造 `method_to_config: dict[str, type[QuantizationConfig]]` 并返回类对象（非实例）。完整名字→配置类映射见 [quant-methods.md](quant-methods.md) 方法总表。

注意 `awq`/`awq_marlin`/`auto_awq` 三个名字共用 `AutoAWQConfig`，`gptq` 三兄弟共用 `AutoGPTQConfig`——后端（Marlin / Triton / XPU / CPU）在 `get_quant_method` 内按平台与 shape 动态选择，而非由方法名决定。

### 自定义方法注册

`register_quantization_config(quantization)` 是类装饰器（`__init__.py:58`）：

| 行为 | 说明 |
|---|---|
| 名字已存在 | 记 `debug` 日志并覆盖 |
| 名字是新的 | append 到 `QUANTIZATION_METHODS`，并 append 到 `current_platform.supported_quantization`（自动视为受支持） |
| 类型校验 | 非 `QuantizationConfig` 子类抛 `ValueError` |
| 存储 | 写入模块级 `_CUSTOMIZED_METHOD_TO_QUANT_CONFIG`，`get_quantization_config` 末尾 `method_to_config.update(...)`——因此自定义方法可覆盖内置方法 |

### 方法选择：三段式解析

**第一段 — 名字裁决（`vllm/config/model.py:1205` `_verify_quantization`）**

从 `model_arch_config.quantization_config` 取出 checkpoint 的 `quant_method`，然后**按固定优先级顺序**遍历所有方法类，调用 `override_quantization_method(hf_quant_cfg, user_quant, hf_config)`，首个返回非 `None` 者胜出：

```python
overrides = ["auto_gptq", "gptq", "gptq_marlin", "auto_awq", "awq", "awq_marlin",
             "inc", "moe_wna16", "modelopt", "modelopt_fp4", "modelopt_mxfp8",
             "mxfp8", "modelopt_mixed",
             # 重后端最后探测，避免 override 检测期就 import Triton
             "mxfp4", "gpt_oss_mxfp4", "deepseek_v4_fp8", "humming"]
quantization_methods = [q for q in supported_quantization if q not in overrides] + overrides
```

- 非 override 方法排在前面，**自定义 override 因不在 `overrides` 列表中而天然优先于内置 override**。
- 保护性断言：若某方法名在 `QuantizationMethods` 内且实现了 override 却未登记进 `overrides`，抛 `ValueError`（`model.py:1264`）。
- 若用户显式 `--quantization humming`，`overrides` 前置 `"humming"`。
- 用户指定值与 checkpoint 推断值不一致时报错；一致或用户未指定则采用推断值。
- 最后 `current_platform.verify_quantization(self.quantization)` 做平台级放行。

典型 `override_quantization_method` 实现（`auto_awq.py:259`）：CPU 平台返回 `None`（交由 CPU 路径）；`quant_method != "awq"` 返回 `None`；用户值必须落在 `{None, "awq", "awq_marlin", "auto_awq", "marlin"}` 才接管。`GptOssMxfp4Config` 更严格——必须 `hf_config.model_type == "gpt_oss"`，注释强调「Do NOT fall back … as that would silently claim all mxfp4 checkpoints」。

**第二段 — 实例化（`weight_utils.py:240` `get_quant_config`）**

| 来源顺序 | 行为 |
|---|---|
| `hf_config.quantization_config` | 主路径；视觉模型回退查 `hf_config.text_config.quantization_config` |
| `hf_config.compression_config` | compressed-tensors 的旧字段名 |
| — | compressed-tensors 且含 `config_groups` 时，注入 `total_num_heads`/`total_num_kv_heads`，供 attn-head scale 的 TP-aware 加载 |
| 命中 | `quant_cls.from_config(hf_quant_config)`；`modelopt_mixed` 缺 `quantized_layers` 时故意穿透到文件路径 |
| `hf_overrides["quantization_config_file"]` | `quant_cls.from_config_file(...)`（仅 `TorchAOConfig` 实现） |
| `hf_overrides["quantization_config_dict_json"]` | `quant_cls.from_config_dict_json(...)` |
| `model_config.quantization_config` | 在线量化：直接 `OnlineQuantizationConfig(args=...)`，不读 checkpoint |

**第三段 — 能力校验（`vllm/config/vllm.py:743` `VllmConfig._get_quantization_config`）**

```python
if capability < quant_config.get_min_capability():  raise ValueError(...)
if model_config.dtype not in quant_config.get_supported_act_dtypes(): raise ValueError(...)
quant_config.maybe_update_config(model, hf_config=..., revision=...)
```

`VllmConfig.get_quantization_config`（公开版）先 `copy.deepcopy(model_config)`，因为下划线版会就地修改 `model_config`。结果写入 `VllmConfig.quant_config`（`vllm.py:1102`）。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
