## 量化体系对比：抽象层、方法清单与内核组织（vLLM vs SGLang）

本模块对比两大引擎的**量化体系**。事实基准：vLLM `vllm/model_executor/layers/quantization/`（KB 12-quantization）与 SGLang `python/sglang/srt/layers/quantization/`（scheme 层，标注 **Adapted from vLLM v0.5.5**）＋`python/sglang/kernels/`（内核层，KB 16-hardware-kernels）。加载/检查点与硬件后端衔接见 [_part2](quantization-comparison_part2.md)。

### 一、量化抽象：分层架构对比

| 维度 | vLLM | SGLang |
|---|---|---|
| 抽象层数 | 两层：**配置/方法层**（`layers/quantization/`）+ 每方法独立内核工具 | 三层：**scheme 层**（`srt/layers/quantization/`，改编自 vLLM v0.5.5）→ **平台分派层**（`srt/hardware_backend/*/quantization/`）→ **统一内核层**（`sglang/kernels/ops/quantization/`） |
| 配置抽象 | `QuantizationConfig`（`base_config.py:87`）：`get_name`/`get_supported_act_dtypes`/`get_min_capability`/`get_config_filenames`/`from_config`/`get_quant_method`/`override_quantization_method` | `QuantizationConfig`（`base_config.py`，接口基本同 vLLM）；`override_quantization_method`（`base_config.py:173`）+ `_modelopt_override_quantization_method` |
| 方法抽象 | `QuantizeMethodBase`（`base_config.py:20`）→ 按层类型派生 `LinearMethodBase`（`layers/linear.py:125`）/`FusedMoEMethodBase`（`fused_moe_method_base.py:27`）/`BaseKVCacheMethod`（`kv_cache.py:42`） | `schemes/` 子目录（如 `awq/schemes/awq_linear.py`）+ `base_scheme.py` 契约；每层类引用 scheme 的 `process_weights_after_loading`/`apply` |
| 注册表 | `QuantizationMethods` **Literal 字面量**（`__init__.py:12`）→ `QUANTIZATION_METHODS` 列表；`register_quantization_config` 装饰器（`__init__.py:58`）可运行时追加/覆盖 | `BASE_QUANTIZATION_METHODS: dict[str, Type[QuantizationConfig]]`（`__init__.py:72`），按平台条件 update（CPU/CUDA/gfx95→`mxfp4`；NPU→覆盖 `gptq`/`mxfp4`；MPS→`mlx_q4`/`mlx_q8`）；另设 `CPU_QUANTIZATION_METHODS` 白名单 |
| 内核抽象 | 无统一内核注册表：每方法自带内核选择逻辑，工具散落 `quantization/utils/` | 统一内核命名空间：`KernelSpec` 元数据（`kernels/spec.py`）→ `KernelRegistry`（`registry.py`）→ `select_kernel`（`selector.py`，无启发式优先级）→ `BaseFusedOp`（`fused_op.py:332`） |
| 谱系 | 自研体系（Megatron 无关） | scheme 层显式源自 vLLM v0.5.5；内核层按 RFC #29630 重构为统一命名空间 |

> 关键差异 ①：vLLM 以「**方法**」为组织单元——一个方法一个文件（`fp8.py`/`auto_awq.py`…），方法内自行决定内核（平台/形状分支 + oracle 选核）；SGLang 把「**scheme**（量化方案）」与「**内核**」解耦——同一 AWQ 方案可有 marlin/triton/cpu/sgl_kernel 多实现，由 `BaseFusedOp` 的 `forward_<backend>` 统一分派。

### 二、接口契约对比

| 契约 | vLLM | SGLang |
|---|---|---|
| 方法/方案 | `QuantizeMethodBase`（`base_config.py:20`：`uses_meta_device`/`create_weights`/`apply`/`process_weights_after_loading`）→ 派生 `LinearMethodBase`/`FusedMoEMethodBase`/`BaseKVCacheMethod` | scheme 类同构继承（`process_weights_after_loading` 做 repack/permute，`apply` 调内核门面 `AWQLinearKernel`/`AWQMarlinLinearKernel`，见 `hardware_backend/gpu/quantization/awq_kernels.py`） |
| 配置类 | `get_min_capability`/`get_config_filenames`/`from_config`/`get_quant_method`/`packed_modules_mapping`（融合层跳过判定）/`get_cache_scale_mapper`（KV scale 的 `WeightsMapper` 自动改写）/`_ignore_unexpected_suffixes` | 同保留 `packed_modules_mapping`（`get_quant_config` 由模型类注入，`loader.py:219`）；KV scale 走 `kv_cache.py`；MoE 独立 scheme，NPU 另设 `moe_methods` |

### 三、方法清单总表

**vLLM**（`QuantizationMethods` Literal，`__init__.py:12`）：checkpoint 方法 23 名 + 在线量化 7 名（见 part2）。**SGLang**（`BASE_QUANTIZATION_METHODS`，`__init__.py:72`）：29 键名 + 平台条件追加。重叠与独有：

| 类别 | vLLM | SGLang | 对应关系 |
|---|---|---|---|
| AWQ | `awq`/`auto_awq`/`awq_marlin`（共用 `AutoAWQConfig`） | `awq`/`awq_marlin` | SGLang 无 `auto_awq` 别名，名→类一一对应 |
| GPTQ | `gptq`/`auto_gptq`/`gptq_marlin`（共用 `AutoGPTQConfig`） | `gptq`/`gptq_marlin`（NPU 上 `gptq`→`GPTQAscendConfig`） | SGLang 无 `auto_gptq`；`_modelopt_override` 保留 |
| FP8 | `fp8`/`fbgemm_fp8`(废弃)/`fp_quant`(废弃)/`modelopt`/`modelopt_mxfp8` | `fp8`/`mxfp8`（**同一个 `Fp8Config`**）/`modelopt`/`modelopt_fp8`/`w8a8_fp8` | SGLang 把 `mxfp8` 直接映射回 `Fp8Config`；`w8a8_fp8` 为独立 W8A8 FP8 方案 |
| MXFP4 | `mxfp4`/`gpt_oss_mxfp4` | `mxfp4`（OCP-MoE，仅 CPU/CUDA/gfx95；NPU 上被 `Mxfp4W4A4Config` 覆盖）/`mxfp_w4a8` | 均支持 OCP micro-scaling MoE；SGLang 另有 NPU W4A4 变体 |
| NVFP4 | `modelopt_fp4` | `modelopt_fp4`/`nvfp4_online`/`petit_nvfp4` | SGLang 多在线 NVFP4 与 Petit NVFP4（小模型） |
| INT8 | `experts_int8`（在线） | `w8a8_int8`/`blockwise_int8`/`auto-round-int8` | SGLang 主推整层 W8A8；vLLM 仅 MoE 专家 INT8 |
| compressed-tensors | `compressed-tensors` | `compressed-tensors` | 两引擎同源（SGLang 有 `DummyConfig` 占位兼容 vllm 缺失时） |
| MoE 专用 | `moe_wna16` | `moe_wna16` | 同 |
| 混合精度 | `humming`/`modelopt_mixed`/`deepseek_v4_fp8` | `humming`/`modelopt_mixed`/`quark_int4fp8_moe` | vLLM 独有 `deepseek_v4_fp8`；SGLang 用 `quark_int4fp8_moe` 覆盖同类 |
| 生态 | `torchao`/`quark`/`inc` | `quark`/`quark_mxfp4`/`auto-round`/`bitsandbytes`/`gguf`/`modelslim` | 交叉极少：vLLM 独有 torchao/inc；SGLang 独有 bitsandbytes/gguf/auto-round/modelslim |
| 平台特化 | — | `mlx_q4`/`mlx_q8`（MPS/Apple Silicon） | vLLM 无 MLX 路径 |

### 四、内核实现差异：独立 per-method vs 统一 kernel 分派

| 维度 | vLLM | SGLang |
|---|---|---|
| 组织方式 | 每方法独立内核工具模块：`utils/marlin_utils*.py`、`fp8_utils.py`、`int8_utils.py`、`mxfp4/6/8_utils.py`、`nvfp4_utils.py`、`machete_utils.py`、`allspark_utils.py`（`quantization/utils/`）；方法内选核 | 统一 `kernels/ops/quantization/` 算子组：`awq_dequantize.py`/`awq_marlin_repack.py`/`awq_triton.py`/`gptq_marlin(_repack).py`/`fp8_kernel.py`/`fp8_quantize.py`/`per_tensor_quant_fp8.py`/`per_token_quant_fp8.py`/`mxfp8_quant.py`/`int8_kernel.py`/`hadamard.py`/`nvfp4_gemm_swiglu_nvfp4_quant.py` 等 |
| 内核选法 | 方法内分支（AutoAWQ 四后端：CPU/XPU→`AutoAWQMarlinLinearMethod`、CUDA+Marlin→Conch/Exllama/Marlin、其余→Triton）+ oracle 选核（`select_fp8_moe_backend`/`select_wna16_moe_backend`）＋ `init_fp8_linear_kernel` 平台选（Cutlass/Marlin/DeepGEMM） | scheme → 平台分派壳（`hardware_backend/gpu/quantization/awq_kernels.py`：XPU→`sgl_kernel.awq_dequantize`、HIP→Triton、CUDA→JIT 优先逐级回退 `sgl_kernel`）→ `select_kernel`（`BaseFusedOp` 按 `forward_<backend>` 优先级：AOT→JIT→FLASHINFER→DEEPGEMM→CUTE_DSL→AITER→TORCH_NPU→TRITON→TORCH） |
| 内核出处 | 平台无关的 C++/Triton（`csrc/` + `triton_utils/`）；按平台 import 分支 | `KernelBackend`（`spec.py:29`）显式标注出处：`TORCH/TORCH_COMPILE/TRITON/JIT/AOT/CUTE_DSL/FLYDSL/FLASHINFER/DEEPGEMM/AITER/TORCH_NPU`；同后端跨设备解析不同实现 |
| AOT/JIT | C++ 编入 vLLM 包（`libtorch_*`） | AOT 独立 `sgl_kernel` 轮子（`kernels/aot/`）+ JIT nvcc/hipcc 即时编译（`kernels/jit/`，ninja 缓存 + 跨进程构建锁） |
| 第三方内核 | DeepGEMM（vLLM 自身集成点） | FLASHINFER/DEEPGEMM/AITER 均为一等 `KernelBackend`，可用 `SGLANG_FORCE_FUSED_OP_BACKEND` 全局强制 |
| 多实现并存 | 单方法通常单实现 + 平台分支 | 同算子多 `forward_<backend>` 并存（RMSNorm 范式：AOT CUDA / AITER HIP / TORCH_NPU NPU），`select_kernel` 无启发式，多个可用必须显式 `backend=` |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
