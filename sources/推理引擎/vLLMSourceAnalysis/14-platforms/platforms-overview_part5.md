## Platform 硬件平台抽象总览（五）：能力钩子分类（下）与兜底代理

本文承接 [platforms-overview_part4.md](platforms-overview_part4.md)。

**注意力后端选择**

| 钩子 | 默认 |
|---|---|
| `get_attn_backend_cls(selected_backend, attn_selector_config, num_heads=None)` | `""`（基类不选择，各后端必须实现） |
| `get_supported_vit_attn_backends()` | `[AttentionBackendEnum.TORCH_SDPA]` |
| `get_vit_attn_backend(head_size, dtype, backend=None)` | 传入 `backend` 时断言其在支持列表内；否则返回 `TORCH_SDPA`。docstring 明确要求 ViT attention 只能在平台层覆写，不得在 `model_executor/models/<model>.py` 中覆写 |

**配置介入（三个时机不同的钩子）**

| 钩子 | 调用时机 |
|---|---|
| `pre_register_and_update(parser=None)` | 全局 `VllmConfig` 初始化**之前**、CLI 解析之前。供树外平台动态注册量化配置等 |
| `apply_config_platform_defaults(vllm_config)` | CLI 解析后、`VllmConfig` 初始化期间。改写**默认值**（如按启用特性开关 custom_ops） |
| `check_and_update_config(vllm_config)` | 校验兼容性：可抛异常，也可就地改写配置 |

三者均按引用修改配置。相关的还有 `verify_model_arch(model_arch)`（默认全部支持）、`verify_quantization(quant)`、`register_custom_kv_cache_specs(vllm_config)`（默认 `pass`）、`check_max_model_len(max_model_len)`（默认原样返回）、`validate_request(processed_inputs, params)`（默认空实现）。

**block size 对齐**（`update_block_size_for_backend`，基类实现三阶段）

1. 若用户未指定 `--block-size`，用 `_find_non_ssm_backend()` 找到首个非 SSM 后端，取其 `get_preferred_block_size_for_config()`。
2. `model_config.is_hybrid` 时调 `_align_hybrid_block_size()`：保证 attention page ≥ mamba page，并把 `mamba_page_size_padded` 补齐到与 attention page **完全相等**（`mamba_cache_mode` 为 `all` 时还需对齐 mamba chunk size 与内核块粒度的 `lcm`；MLA 混合模型额外要求块粒度 ≥128）。
3. `cache_config.kv_cache_dtype_skip_layers` 非空时调 `_align_heterogeneous_kv_block_size()`：量化主 spec（如 nvfp4）与高精度 padded spec 共享 block pool 且 per-token page 非整数倍时，抬高主 `block_size` 直至覆盖，并把共享 page 写入 `skip_page_size_padded`。阶段 2、3 都**可能覆盖用户显式设置**。

**计算特性与 dtype**

| 钩子 | 默认 |
|---|---|
| `supports_mx()` / `supports_fp8()` | `False` |
| `is_fp8_fnuz()` | `False`（docstring：仅 AMD MI300/MI325 原生 FNUZ，其余硬件收敛到 OCP FP8） |
| `fp8_dtype()` | `torch.float8_e4m3fn` |
| `check_if_supports_dtype(dtype)` | ⚠ |
| `get_infinity_values(dtype)` | `(float("-inf"), float("inf"))` |
| `can_update_inplace()` | `True` |
| `supports_mx` / `support_deep_gemm` / `is_arch_support_pdl` | `False` |

**分布式、编译与其他**

| 钩子 | 默认 |
|---|---|
| `get_device_communicator_cls()` | `…base_device_communicator.DeviceCommunicatorBase` |
| `stateless_init_device_torch_dist_pg(...)` | ⚠ |
| `use_all_gather()` | `True`（LogitsProcessor 是否用 allgather 汇聚 logits） |
| `use_custom_allreduce()` | `False` |
| `use_custom_op_collectives()` | `False`——是否走 `torch.ops.vllm.*` 自定义集合通信算子，注释强调平台须显式 opt-in |
| `opaque_attention_op()` | `False`——是否把 attention 注册为一个巨型不透明 custom op |
| `get_static_graph_wrapper_cls()` | `…base_static_graph.AbstractStaticGraphWrapper` |
| `support_static_graph_mode()` / `support_hybrid_kv_cache()` | `False` |
| `get_pass_manager_cls()` | `…passes.pass_manager.PostGradPassManager` |
| `get_default_ir_op_priority(vllm_config)` | `IrOpPriorityConfig.with_default(["native"])` |
| `import_kernels()` | `import vllm._C`（失败仅 `warning_once`）+ 可选 `vllm._moe_C_stable_libtorch` |
| `import_ir_kernels()` | `import vllm.kernels`；树外平台应覆写以导入自有内核模块 |
| `get_punica_wrapper()` | ⚠ |
| `get_lora_vocab_padding_size()` | `256` |
| `use_sync_weight_loader()` | `False`；`make_synced_weight_loader(loader)` 在其为真时包装出「非 CPU 参数加载后调 `torch._sync(param)`」的版本，否则原样返回 |
| `check_runner_kv_caches_multi_layer()` | ⚠——用于声明 ModelRunner 能否处理同一 layer index 上的多个 attention 层（如 BART 的 cross+self attention）。**默认抛异常**，已验证的平台需显式覆写为 `pass` |
| `get_nixl_supported_devices()` / `get_nixl_memory_type()` | `{}` / `None`（树内平台均未覆写） |
| `set_additional_forward_context(*args, **kwargs)` | `{}` |

### 兜底属性代理

`Platform.__getattr__` 让平台对象可以透明转发到 `torch.<device_type>` 模块：

```python
device = getattr(torch, self.device_type, None)
if device is not None and hasattr(device, key):
    attr = getattr(device, key)
    if attr is not None:
        return attr
logger.warning_once("Current platform %s does not have '%s' attribute.", ...)
return None
```

因此 `current_platform.empty_cache()`、`current_platform.synchronize()` 之类调用无需在每个平台重复声明。两点细节：以双下划线开头结尾的 key 直接抛 `AttributeError`（否则 pickle 探测 `__getstate__` 时会拿到 `None` 并试图调用它）；`hasattr` 为真但值为 `None` 时继续走告警路径，最终返回 `None` 而非抛错——调用方需自行容忍。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
