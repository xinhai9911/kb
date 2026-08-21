## vLLM vs SGLang 注意力后端对比（一）：抽象契约、注册表与默认选择

本模块对比两大引擎的注意力后端子系统。事实基准：vLLM V1（`vllm/v1/attention/`，KB 见 `vLLMSourceAnalysis/04-attention/`）与 SGLang SRT（`sglang/srt/layers/attention/`，KB 见 `SGLangSourceAnalysis/07-attention/`）。其余维度见 [_part2](attention-comparison_part2.md)。

### 一、后端抽象契约对比

| 维度 | vLLM `AttentionBackend` | SGLang `AttentionBackend` |
|---|---|---|
| 基类位置 | `vllm/v1/attention/backend.py`（含 `AttentionImpl`/`MLAAttentionImpl`/`AttentionMetadata`/`AttentionMetadataBuilder`） | `layers/attention/base_attn_backend.py:36` |
| 核心三件套 | `get_impl_cls()`（算子封装）+ `get_builder_cls()`（元数据构建）+ `get_kv_cache_shape()`（KV 形状约定） | `init_forward_metadata(forward_batch)`（元数据规划）+ `forward(q,k,v,layer,forward_batch)`（`forward_decode`/`forward_extend`/`forward_mixed` 三分派） |
| 能力声明方式 | **类静态校验**：`supported_dtypes`/`get_supported_kernel_block_sizes()`/`get_supported_head_sizes()`/`supports_combination()`→`validate_configuration()` 汇总返回 `list[str]` | **运行时标志**：`needs_cpu_seq_lens`、`supports_ragged_verify_graph`、`supports_full_cuda_graph_chunked_prefix`、`shared_read_ends(fm)` 等 |
| 能力开关 | `supports_sink`/`supports_sliding_window`/`supports_non_causal`/`supports_mm_prefix`/`supports_pcp` 等 10+ 个 | `prefill_attention_backend_str`/`decode_attention_backend_str`（模式名，`build_attention_backends` 盖章） |
| KV 形状约定 | `get_kv_cache_shape()` 逻辑形状 `(num_blocks,...)`；`get_kv_cache_stride_order()` 物理排列；`get_required_kv_cache_layout()` 返回 `"NHD"`/`"HND"`；`get_kv_cache_spec()` 生成 `FullAttentionSpec`/`SlidingWindowSpec` | 池布局由 `token_to_kv_pool` 统一决定（MHA/MLA 两种池），后端只消费 `kv_indptr`/`kv_indices`/`page_table` 元数据 |
| 元数据构建入口 | `AttentionMetadataBuilder.build(common_prefix_len, common_attn_metadata, fast_build)` 从通用元数据构建各层专用元数据 | 每次 forward batch 调用：`init_forward_metadata_out_graph`（host 侧规划）+ `init_forward_metadata_in_graph`（可录制 GPU op） |
| CUDA Graph 支持 | `_cudagraph_support`：`ALWAYS`/`UNIFORM_BATCH`/`UNIFORM_SINGLE_TOKEN_DECODE`/`NEVER` | `supports_ragged_verify_graph`/`supports_full_cuda_graph_chunked_prefix` 标志 + `init_cuda_graph_state` |

> 关键差异 ①：vLLM 契约是**「类静态能力声明 + Impl/MetadataBuilder 工厂」**——选型阶段用 `validate_configuration()` 过滤非法组合，运行期只构建元数据；SGLang 契约是**「每批运行时元数据规划 + forward 模式分派」**——不提前校验，靠 `init_forward_metadata` 与 forward 内部分派（`IDLE`/`DECODE`/`MIXED`/extend）。两者都遵循「decode/verify 共用 decode 内核、extend/target-verify 共用 prefill 内核」。

### 二、后端注册机制对比

| 维度 | vLLM | SGLang |
|---|---|---|
| 注册表结构 | `AttentionBackendEnum`（`backends/registry.py:34`），**枚举值 = 后端全限定类路径** | `ATTENTION_BACKENDS: dict[str, Callable]`（`attention_registry.py:31`），注册名 → 工厂函数 |
| 注册 API | `register_backend(enum, class_path)` 装饰器，**运行时把枚举名覆盖**为自定义类（含 `CUSTOM=None` 占位，未注册即用报错） | `register_attention_backend(name)` 装饰工厂函数（`attention_registry.py:34`），`_build_full_attention_backend_from_str`（`attention_backend_setup.py:251`）查表构造 |
| 加载方式 | `get_class()` 经 `resolve_obj_by_qualname` **延迟导入** | 工厂内 `import`，运行期实例化 |
| 扩展通道 | 覆盖现有枚举 + `CUSTOM` 占位 + `TORCH_SDPA=""`（仅 ViT 标签） | 直接 `ATTENTION_BACKENDS[name] = fn` 注入 |
| 二次注册表 | `MambaAttentionBackendEnum`：`MAMBA1`/`MAMBA2`/`SHORT_CONV`/`LINEAR`/`GDN_ATTN`（SSM 后端同机制） | 混合架构经 `attn_backend_wrapper`（`attention_registry.py:309`）把 full-attention 与线性/稀疏后端组合 |

### 三、后端清单对比

vLLM（`AttentionBackendEnum`，约 35 项）：

| 族 | 成员 |
|---|---|
| 标准注意力 | `FLASH_ATTN`、`FLASH_ATTN_DIFFKV`、`TRITON_ATTN`、`TRITON_ATTN_DIFFKV`、`FLEX_ATTENTION`、`TURBOQUANT`、`HPC_ATTN`、`NO_ATTENTION` |
| FlashInfer | `FLASHINFER`、`FLASHINFER_MLA`、`FLASHINFER_MLA_SPARSE`、`FLASHINFER_MLA_SPARSE_SM120`、`FLASHINFER_MLA_SPARSE_DSV4` |
| MLA 专用 | `TRITON_MLA`、`CUTLASS_MLA`、`TOKENSPEED_MLA`、`FLASHMLA`、`FLASHMLA_SPARSE`、`FLASHMLA_SPARSE_DSV4`、`FLASH_ATTN_MLA`、`FLASH_ATTN_MLA_SPARSE` |
| ROCm | `ROCM_ATTN`、`ROCM_AITER_FA`、`ROCM_AITER_MLA`、`ROCM_AITER_TRITON_MLA`、`ROCM_AITER_MLA_SPARSE`、`ROCM_AITER_UNIFIED_ATTN`、`ROCM_FLASHMLA_SPARSE_DSV4` |
| 其它平台 | `CPU_ATTN`、`CPU_MLA`、`XPU_MLA_SPARSE` |
| 模型驱动 | `MINIMAX_M3_SPARSE`、`CUTLASS_MSA`、`TRITON_MSA`（MiniMax 稀疏） |
| 占位 | `CUSTOM`（第三方）、`TORCH_SDPA`（ViT 专用标签） |

SGLang（`ATTENTION_BACKENDS`，20+ 项）：

| 族 | 注册名 |
|---|---|
| 通用 | `flashinfer`（MLA 时切 `FlashInferMLAAttnBackend`）、`fa3`、`fa4`、`triton` |
| MLA 专用 | `flashmla`（继承 FlashInferMLA，decode 用 `sgl_kernel.flash_mla`）、`trtllm_mla`、`cutedsl_mla`、`cutlass_mla`、`tokenspeed_mla` |
| MHA 专用 | `trtllm_mha` |
| 平台/算法变体 | `aiter`、`wave`、`intel_amx`、`intel_xpu`、`torch_native`、`flex_attention`、`hpc_ops`、`dual_chunk_flash_attn` |
| NPU | `ascend`、`dsv4`（DeepSeek V4，NPU/HIP/CUDA 三分支） |
| 稀疏 | `dsa`（`DeepseekSparseAttnBackend`；`nsa` 废弃别名） |

> 关键差异 ②：vLLM 以「后端类」为中心，枚举值即类路径，靠平台层选型；SGLang 以「工厂函数」为中心，同名后端（fa3/fa4 都落 `FlashAttentionBackend`，仅 `fa_impl_ver` 不同）复用实现。

### 四、默认后端选择对比

vLLM（平台层 `get_attn_backend_cls`，`vllm/platforms/*.py`）：

| 平台 | 规则 |
|---|---|
| CUDA 非 MLA | SM100 且非 causal → `FLASHINFER`→`FLASH_ATTN`→`TRITON_ATTN`→`FLEX_ATTENTION`→`TURBOQUANT`；其余 → `FLASH_ATTN` 优先 |
| CUDA MLA | SM100 → `FLASHINFER_MLA`→`TOKENSPEED_MLA`→`CUTLASS_MLA`→`FLASH_ATTN_MLA`→`FLASHMLA`→`TRITON_MLA`+sparse 族；SM120 → `TRITON_MLA`→`FLASHINFER_MLA_SPARSE_SM120`；其余 → `FLASH_ATTN_MLA` 优先 |
| CPU | 固定 `CPU_ATTN`；MLA→`CPU_MLA`（decode 仅 block_size=16）；`use_sparse` 报错 |
| XPU | `turboquant_*` KV dtype→`TURBOQUANT`；sparse→`XPU_MLA_SPARSE`；MLA→`TRITON_MLA`；mm-prefix-LM→`TRITON_ATTN` |
| ROCm | 候选 `ROCM_ATTN`/`ROCM_AITER_FA`/`ROCM_AITER_UNIFIED_ATTN`/`TRITON_ATTN`/`TURBOQUANT`；MLA → AITER 启用则 `ROCM_AITER_MLA`，否则 `TRITON_MLA` |

SGLang（`_get_default_attn_backend`，`server_args.py:5903`）：

| 场景 | 默认后端 |
|---|---|
| MHA + Hopper（CUDA≥12.3，无 spec 或 topk=1） | `fa3`（flashinfer 0.6.1 在 Hopper 有性能回退） |
| MHA + SM100/103（Blackwell） | 非对称 KV→`fa4`；否则 `trtllm_mha`（SM120 不支持则回退 flashinfer） |
| MHA + HIP / MPS | `aiter` / `torch_native` |
| MHA + 其余 | `flashinfer`（可用且无 attention sinks）否则 `triton` |
| MLA + Hopper/SM100/HIP/其余 | `fa3` / `flashinfer` / `aiter`（头数 128/16）或 `triton` / `triton` |

> 关键差异 ③：vLLM 默认选择权在**平台层**（按 GPU 架构分优先级表 + `validate_configuration()` 逐个过滤），选中后**全局单一后端**，仅 `AttentionConfig.backend_per_kind` 按 `KVCacheSpecKind`（FULL/SLIDING_WINDOW/MLA/CROSS/ENCODER_ONLY）细粒度覆盖；SGLang 默认选择权在**模型配置+硬件启发式**（server_args），支持 `--prefill-attention-backend`/`--decode-attention-backend` 把 prefill 与 decode **拆成两个后端**（`HybridAttnBackend`，`hybrid_attn_backend.py:21` 按模式路由），vLLM 无此拆分。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
