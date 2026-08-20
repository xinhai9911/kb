## vllm/third_party：vendored 三方库

`vllm/third_party/` 把若干外部开源项目直接复制进 vLLM 源码树（vendored），用于规避依赖冲突、固定版本或按需惰性引入。目录本身仅含 3 个组件：`flash_linear_attention/`、`flashmla/`、`pynvml.py`；此外源码中多处引用 `vllm.third_party.<X>` 作为**回退路径**（deep_gemm、triton_kernels、fmha_sm100、tml_fa4），其中部分模块在本次源树中不存在、由发行版 wheel 打包提供。

| 组件 | 上游 | 许可证 | 形式 |
|---|---|---|---|
| `flash_linear_attention/` | flash-linear-attention 项目 | MIT（Songlin Yang, Yu Zhang, 2023-2025） | 目录（19 文件，含 `LICENSE`） |
| `flashmla/` | DeepSeek FlashMLA | 注释标记 "Sources copied from FlashMLA" | 仅 `__init__.py` 占位 |
| `pynvml.py` | nvidia-ml-py 12.570.86 | BSD（NVIDIA） | 单文件（约 240KB） |

### flash_linear_attention/：线性注意力 Triton 内核

用途：为 Gated Delta Rule / KDA 类线性注意力模型提供分块（chunk）与循环（recurrent）两种前向 Triton 内核及配套融合算子。**依赖 `vllm.triton_utils` 与 `current_platform`**，因此是 GPU/Triton 专属；绝大多数引入点位于函数体内（惰性加载），只在对应模型/后端启用时才会 import。

`ops/__init__.py` 公开导出 6 个符号：

```python
from .chunk import chunk_gated_delta_rule
from .fused_gdn_prefill_post_conv import fused_post_conv_prep
from .fused_recurrent import (
    fused_recurrent_gated_delta_rule,
    fused_recurrent_gated_delta_rule_packed_decode,
)
from .fused_sigmoid_gating import fused_sigmoid_gating_delta_rule_update
from .layernorm_guard import RMSNormGated
```

`ops/` 下 17 个模块一览（名称/签名均为源码事实）：

| 模块 | 导出核心 | 说明 |
|---|---|---|
| `chunk.py` | `chunk_gated_delta_rule_fwd` | 分块前向：cumsum→scaled dot KKT→`solve_tril`→WY→输出 |
| `chunk_delta_h.py` | `chunk_gated_delta_rule_fwd_h` | 分块隐性状态（delta_h）更新 |
| `chunk_o.py` | `chunk_fwd_o` | 分块输出计算 |
| `chunk_scaled_dot_kkt.py` | `chunk_scaled_dot_kkt_fwd` | 分块 scaled K·Kᵀ |
| `cumsum.py` | `chunk_local_cumsum` | 块内局部 cumsum（门控衰减） |
| `fused_gdn_prefill_post_conv.py` | `fused_post_conv_prep` | GDN prefill 后卷积融合准备 |
| `fused_norm_gate.py` | — | norm+gate 融合 Triton 内核 |
| `fused_recurrent.py` | `fused_recurrent_gated_delta_rule*` | 循环（解码）版 gated delta rule，含 packed_decode 变体 |
| `fused_sigmoid_gating.py` | `fused_sigmoid_gating_delta_rule_update` | sigmoid 门控增量更新融合 |
| `index.py` | `prepare_chunk_indices` | 按 `FLA_CHUNK_SIZE` 计算 chunk 索引/偏移 |
| `kda.py` | `FusedRMSNormGated`（`CustomOp`）、`fused_recurrent_kda_fwd` | KDA 融合 RMSNorm+gated 自定义算子 |
| `l2norm.py` | `l2norm_fwd` | L2 归一化 |
| `layernorm_guard.py` | `RMSNormGated` | 保留层归一化融合（供编译 pass/算子使用） |
| `op.py` | `exp`/`exp2`/`log`/`log2`、`gather`、`make_tensor_descriptor` | Triton 数学原语；`FLA_USE_FAST_OPS=1` 走 `fast_expf`；按 Triton 3.3/3.4+ 选 TMA 描述符 API |
| `solve_tril.py` | `solve_tril` | 三角系统求解 |
| `utils.py` | `FLA_CHUNK_SIZE=64`、`is_amd/is_nvidia/is_intel`、`Backend` 共享内存枚举、`tensor_cache`/`input_guard` | 平台探测与公共工具；识别 `FLA_COMPILER_MODE`/`FLA_USE_TMA`/`FLA_USE_CUDA_GRAPH` 等 |
| `wy_fast.py` | `recompute_w_u_fwd` | WY 表示计算/重计算 |

主要使用方：

| 使用方 | 用途 |
|---|---|
| `v1/attention/backends/gdn_attn.py:174,193` | GDN 注意力后端：`FLA_CHUNK_SIZE` 分块、`prepare_chunk_indices`（预计算 chunk 元数据避免 GPU→CPU 同步） |
| `model_executor/layers/mamba/gdn/qwen_gdn_linear_attn.py:50` | Qwen GDN 线性注意力层 |
| `model_executor/layers/mamba/gdn/olmo_gdn_linear_attn.py:36` | OLMo GDN 线性注意力层 |
| `model_executor/layers/mamba/gdn/kimi_gdn_linear_attn.py:25` | Kimi GDN，用 `FusedRMSNormGated` |
| `model_executor/layers/mamba/linear/bailing_linear_attn.py:32` | bailing 线性注意力，用 `layernorm_guard` |
| `model_executor/models/bailing_moe_v3.py:75` | bailing_moe_v3 模型，用 `ops.kda` |
| `models/kimi_k3/nvidia\|amd/kda.py`、`kda_metadata.py` | Kimi K3 的 KDA 实现（`ops/third_party/kda/` 内另有 kda 变体，复用本目录 `ops.*` 原语） |
| `model_executor/warmup/qwen_triton_warmup.py:177,207`、`kimi_k3_triton_warmup.py` | warmup 流程惰性加载内核 |
| `model_executor/layers/layernorm.py:289`、`compilation/passes/fusion/matcher_utils.py:195` | `RMSNormGated` 层归一化融合/匹配 |

### flashmla/：FlashMLA 接口占位

`flashmla/__init__.py` 仅一行注释 "Sources copied from FlashMLA"。真实接口模块 `vllm.third_party.flashmla.flash_mla_interface` 由 `v1/attention/ops/flashmla.py:87` 引用（该文件头部注明 adapted from FlashMLA 上游 `flash_mla_interface.py`），导出 `flash_attn_varlen_func`、`flash_attn_varlen_kvpacked_func`、`flash_mla_with_kvcache`、`get_mla_metadata`、`FlashMLASchedMeta` 等。

引入时机受编译扩展把关：

```python
if current_platform.is_cuda():
    try:
        import vllm._flashmla_C          # 需 nvcc 版本/目标架构满足
        _flashmla_C_AVAILABLE = True
    except ImportError:
        _flashmla_C_AVAILABLE = False
# ... _flashmla_extension_C 同理
if _is_flashmla_available()[0]:
    from vllm.third_party.flashmla.flash_mla_interface import (...)
else:
    # 各函数替换为 _raise_flashmla_unavailable，调用即抛 RuntimeError
```

即**只有 wheel 中带 `vllm._flashmla_C` 与 `vllm._flashmla_extension_C` 两个编译扩展时才真正 import 该接口**；否则模块内所有入口（含 FP8 扩展 `get_mla_metadata_dense_fp8` 等）都指向抛错函数。`is_flashmla_dense_supported`（仅 Hopper）与 `is_flashmla_sparse_supported`（Hopper+Blackwell DC）由 MLA 注意力后端 `v1/attention/backends/mla/flashmla.py` 消费做能力判定。

### pynvml.py：NVML 官方包装的强制内嵌

`pynvml.py` 是 PyPI `nvidia-ml-py`（12.570.86）官方包装的单文件复制。`utils/import_utils.py:26` 的 `import_pynvml()` 直接 `import vllm.third_party.pynvml`，其 docstring 说明了原因：社区存在 `pynvml` 非官方同名包，Python 包优先级高于官方单文件模块，二者共存会造成错误（如 `nvcr.io/nvidia/pytorch:24.12-py3` 场景，issue #12847），因此 vLLM 把官方模块复制进来绕开冲突。

用途：**在不初始化 CUDA context 的前提下读取 GPU 状态**。消费者为平台层：

| 调用方 | 用法 |
|---|---|
| `platforms/cuda.py:49` | 模块级 `pynvml = import_pynvml()`；`with_nvml_context` 做 `nvmlInit()`/`nvmlShutdown()` 配对；`nvmlDeviceGetHandleByUUID/ByIndex`、`nvmlDeviceGetCudaComputeCapability`、`nvmlDeviceGetUUID` 等实现设备 UUID/索引/算力查询 |
| `platforms/__init__.py:65` | 通用平台路径同样经 `import_pynvml()` 取 pynvml |

### 源码引用但不在本源树的 vendored 路径

以下 `vllm.third_party.<X>` 引用存在于代码中，作为**安装包缺失时的回退分支**，对应目录未出现在本次签出的 `third_party/` 下（通常由发行版 wheel 打包）：

| 模块 | 引用点 | 语义 |
|---|---|---|
| `deep_gemm` | `utils/deep_gemm.py:193` | `_import_deep_gemm()` 优先 site-packages 的外部 `deep_gemm`，`ImportError` 后回退 `vllm.third_party.deep_gemm`；`models/dots3_note/nvidia/vision.py:14`、`models/deepseek_v4/xpu/model.py` 亦直接引用 |
| `triton_kernels` | `utils/import_utils.py:70` | `import_triton_kernels()` 优先外部包，回退后写入 `sys.modules["triton_kernels"]` 统一符号 |
| `fmha_sm100` | `models/minimax_m3/nvidia/*`（`sparse_attention_msa.py:266`、`msa_cutlass_sparse_decode.py:76`、`indexer_msa.py:202` 等） | Blackwell SM100 FMHA sparse/cutlass 算子，函数内惰性 import |
| `tml_fa4` | `models/inkling/nvidia/ops/fa4_rel_attention.py:171` | FA4 相对注意力实现 |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
