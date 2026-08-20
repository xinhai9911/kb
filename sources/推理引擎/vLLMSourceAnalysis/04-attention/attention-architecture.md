## 注意力架构（Attention Architecture）

vLLM 注意力子系统采用「抽象后端 + 平台注册 + 延迟导入」：`Attention`/`MLAAttention` 层初始化时调用 `get_attn_backend()` 选出 `AttentionBackend` 类，由其提供 `Impl`（算子封装）、`MetadataBuilder`（每批元数据构建）与 KV cache 形状约定。

核心源码位置：

| 文件 | 职责 |
|---|---|
| `vllm/v1/attention/backend.py` | 抽象类：`AttentionBackend`、`AttentionImpl`/`MLAAttentionImpl`、`AttentionMetadata`、`CommonAttentionMetadata`、`AttentionMetadataBuilder` |
| `vllm/v1/attention/backends/registry.py` | `AttentionBackendEnum`/`MambaAttentionBackendEnum` 注册表与运行时覆盖 |
| `vllm/v1/attention/selector.py` | `get_attn_backend()` 选择入口与结果缓存 |
| `vllm/v1/attention/backends/` | 各后端实现（含 `mla/`、`mla/prefill/`） |
| `vllm/v1/attention/ops/` | 共享自研算子（`paged_attn.py`、`merge_attn_states.py`、`prefix_prefill.py`、`triton_*`、`dcp_*`） |
| `vllm/model_executor/layers/attention/attention.py` | `Attention` 层（标准 QKV 注意力） |
| `vllm/model_executor/layers/attention/mla_attention.py` | `MLAAttention` 层与 MLA 公共实现 |
| `vllm/model_executor/layers/attention_layer_base.py` | `AttentionLayerBase`：`bind_kv_cache`/`get_attn_backend`/`get_kv_cache_spec` |

`vllm/attention/` 顶层目录已不存在（旧版残留），当前全部集中于 `vllm/v1/attention/`。

### AttentionBackend 抽象

`AttentionBackend`（ABC）定义后端能力契约：

| 成员 | 含义 |
|---|---|
| `supported_dtypes` | 默认 `[torch.float16, torch.bfloat16]` |
| `supported_kv_cache_dtypes` | 默认 `["auto","float16","bfloat16"]`；后端可扩展（fp8、nvfp4 等） |
| `forward_includes_kv_cache_update` | forward 是否内含 KV cache 写入（FlashAttention 系为 False，KV 更新独立） |
| `get_name()` | 后端短名，如 `FLASH_ATTN` |
| `get_impl_cls()` / `get_builder_cls()` | 返回 `AttentionImpl` 与 `AttentionMetadataBuilder` |
| `get_kv_cache_shape()` | 逻辑形状 `(num_blocks,...)`；`get_kv_cache_stride_order()` 描述物理 dim 排列 |
| `get_supported_kernel_block_sizes()` | kernel 要求的 page 大小：固定 int 或 `MultipleOf(base)`（如 FA 要求 block_size 为 16 倍数） |
| `get_supported_head_sizes()` 等 | head_size/dtype/kv_dtype/block_size 准入检查 |
| `supports_combination()` | 细粒度组合校验（head_size+dtype+quant+...），非法返回原因串 |
| `validate_configuration()` | 汇总全部检查，返回 `list[str]`（空=合法） |
| 能力开关 | `supports_sink`、`supports_sliding_window`、`supports_non_causal`、`supports_batch_invariance`、`supports_mm_prefix`、`supports_per_head_quant_scales`、`supports_kv_connector`、`supports_pcp`、`supports_device_cpu_query_lens_mismatch`、`is_mla()`、`is_sparse()`、`is_ssm()` |
| `get_required_kv_cache_layout()` | 需要 `"NHD"` 或 `"HND"` 物理布局时返回（`KVCacheLayoutType`，见 `backends/utils.py`） |
| `customize_spec()` | 按 kernel 微调 KV cache spec（临时 API，见 issue #42449） |
| `get_preferred_block_size()` | 建议 block_size，优先保留默认值 |

`AttentionImpl`（标准）与 `MLAAttentionImpl`（MLA）共用 `AttentionImplBase`。`__new__` 读取 `dcp_world_size`/`pcp_world_size`，依 `can_return_lse_for_decode` 决定是否返回 softmax `lse`；`lse_base_on_e` 标记自然对数底（DCP 合并分母依赖）。两者另含融合钩子 `fused_output_quant_supported()`、`fused_qk_norm_rope_kvcache_supported()`。

### 后端注册中心

`registry.py` 的 `AttentionBackendEnum` 枚举值即后端全限定路径；`register_backend()` 装饰器可运行时把枚举名覆盖为自定义类（含 `CUSTOM=None` 占位）。`get_class()` 经 `resolve_obj_by_qualname` 延迟导入。`MambaAttentionBackendEnum` 以同机制管理 SSM 后端（`MAMBA1`/`MAMBA2`/`SHORT_CONV`/`LINEAR`/`GDN_ATTN`）。

### 选择机制

`selector.py::get_attn_backend(head_size, dtype, kv_cache_dtype, use_mla, ...)`：

1. 从当前 `VllmConfig` 装配 `AttentionSelectorConfig`（NamedTuple，可 hash 缓存）；`block_size` 仅用户显式 `--block-size` 时传入，否则 None 让后端自选。
2. 【按 KV 组覆盖】`AttentionConfig.backend_per_kind` 按 `KVCacheSpecKind`（`get_attn_spec_kind()` 推导：`FULL_ATTENTION`/`SLIDING_WINDOW`/`MLA_ATTENTION`/`CROSS_ATTENTION`/`ENCODER_ONLY_ATTENTION` 等）覆盖全局 `AttentionConfig.backend`。
3. 调 `current_platform.get_attn_backend_cls(...)`，结果 `@cache` 缓存。

各平台实现（`vllm/platforms/*.py`）定最终类：

- **CPU**：忽略用户选择，MLA→`CPU_MLA`，否则→`CPU_ATTN`。
- **XPU**：`turboquant_*` KV dtype→`TURBOQUANT`；`use_sparse`→`XPU_MLA_SPARSE`；`use_mla`→`TRITON_MLA`；否则回退 FlashAttention。
- **CUDA**（核心）：用户显式指定 backend 时先 `validate_configuration`，非法直接报错；否则 `get_valid_backends` 按 `_get_backend_priorities()` 优先序逐项校验，取 priority 最小者：

| 场景 | 优先序（高→低） |
|---|---|
| 非 MLA，SM100 且非 causal | `FLASHINFER`→`FLASH_ATTN`→`TRITON_ATTN`→`FLEX_ATTENTION`→`TURBOQUANT` |
| 非 MLA，其它 | `FLASH_ATTN`→`FLASHINFER`→`TRITON_ATTN`→`FLEX_ATTENTION`→`TURBOQUANT` |
| MLA，SM100 | `FLASHINFER_MLA`→`TOKENSPEED_MLA`→`CUTLASS_MLA`→`FLASH_ATTN_MLA`→`FLASHMLA`→`TRITON_MLA`→稀疏后端（fp8 KV 或低 head 数下 `FLASHINFER_MLA_SPARSE` 优先，否则 `FLASHMLA_SPARSE`） |
| MLA，SM120 | `TRITON_MLA`→`FLASHINFER_MLA_SPARSE_SM120` |
| MLA，其它 | `FLASH_ATTN_MLA`→`FLASHMLA`→`FLASHINFER_MLA`→`TRITON_MLA`→`FLASH_ATTN_MLA_SPARSE`→`FLASHMLA_SPARSE` |

选中后若 `get_required_kv_cache_layout()` 非空，设置全局 KV cache 布局。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
