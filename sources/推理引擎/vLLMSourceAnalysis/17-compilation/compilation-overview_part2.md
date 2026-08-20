## Compilation 编译与图捕获总览 _part2

承接 [compilation-overview_part1](compilation-overview_part1.md)：介绍 PostGradPassManager 图变换体系与 01-config 的衔接。

### PostGradPassManager 与图变换

`PostGradPassManager`（`passes/pass_manager.py:91`）作为 Inductor 的 `post_grad_custom_post_pass` 挂载，执行顺序：

```python
1. 用户/配置自定义 pass（PassConfig 决定）
2. NoOpEliminationPass（eliminate_noops=True 时，默认）
3. 各 Fusion pass（见下）
4. post_cleanup（拓扑排序 + DCE）
5. VllmIRLoweringPass（vllm_ir op → 按优先级选实现）
6. clone_elimination（UnsafeCloneEliminationPass）
7. post_cleanup 再清理
8. FixFunctionalizationPass（defunctionalize，最后执行）
```

`PassConfig`（`config/compilation.py:107`）关键开关与对应 fusion pass（按平台条件 import，见 `pass_manager.py` 顶部）：

| 开关 | 对应 fusion/transformation pass | 平台 |
|---|---|---|
| `fuse_norm_quant` | `RMSNormQuantFusionPass`（RMSNorm+FP8 quant） | CUDA/XPU/ROCm |
| `fuse_act_quant` | `ActivationQuantFusionPass`（SiluMul+quant） | CUDA/XPU |
| `fuse_attn_quant` | `AttnQuantFusionPass`/`MLAAttnQuantFusionPass` | CUDA |
| `fuse_allreduce_rms` | `AllReduceFusionPass`（flashinfer）/ ROCm `RocmAiterAllReduceFusionPass` | CUDA+flashinfer/ROCm |
| `enable_sp` / `fuse_gemm_comms` | `SequenceParallelismPass` / `AsyncTPPass` | CUDA/XPU |
| `fuse_qk_norm_rope_kvcache` | `SplitCoalescingPass`+`ScatterSplitReplacementPass`+`QkNormRopeKvCacheFusionPass`（AITER） | ROCm |
| `fuse_rope_kvcache` | `RopeKVCacheFusionPass` | ROCm/AITER |
| `fuse_mla_dual_rms_norm` | `MLADualRMSNormFusionPass` | ROCm |
| `enable_qk_norm_rope_fusion` | `QKNormRoPEFusionPass` | CUDA/XPU |

辅助 pass：

- `NoOpEliminationPass`（`utility/noop_elimination.py`）消除冗余 reshape/slice/slice_scatter（RMSNorm-quant 融合前置条件），处理 reshape 链重写与"shape 等价"的 no-op。
- `SplitCoalescingPass`（`utility/split_coalescing.py`）合并重复 `split_with_sizes`（绕开 B200+FP8 下 CSE 缺口）；`ScatterSplitReplacementPass` 配套处理 slice_scatter。
- `PostCleanupPass` 拓扑排序 + DCE；`FixFunctionalizationPass` 对 `auto_functionalized` 节点做 defunctionalize（rope/rms_norm/silu_and_mul 等）以减少拷贝；`UnsafeCloneEliminationPass`（`ir/clone_elimination.py`）消除 unsafe clone。
- `VllmIRLoweringPass`（`ir/lowering_pass.py`）把 `vllm_ir` op 按 `IrOp` 优先级列表 lower 到实现，记录 `selected_impls`；其 `uuid()` 包含 IR 优先级与 impl 源码哈希。
- `VllmPatternMatcherPass` 基于 `torch._inductor.pattern_matcher` 注册 pattern/replacement，`register` 走 `pm.register_replacement`（trace 后先 `view_to_reshape`、移除 noop permute）；全局 `match_table` 统计命中。
- 每个 pass 的 `uuid()` 由源码哈希/对象类型哈希生成（`inductor_pass.py`），参与 Inductor 代码缓存键；`PostGradPassManager.uuid()` 聚合 `pass_config.compute_hash()` + 各 pass uuid + `compile_range`，保证不同 pass 配置触发重编译。

### 与 01-config 的衔接

- `VllmConfig.compilation_config` 即 `CompilationConfig`（含嵌套 `PassConfig`、`DynamicShapesConfig`）。`CompilationConfig.compute_hash()`（`config/compilation.py:781`）排除路径/计时/上下文字段，单独聚合 `pass_config.compute_hash()` 与 `dynamic_shapes_config.compute_hash()`，作为编译缓存键的一部分。
- `set_splitting_ops_for_v1`（`config/compilation.py:1134`）在 v1 引擎 post-init 时把默认 `splitting_ops` 设为 `_attention_ops`（`vllm::unified_attention_with_output` 等），并追加 `vllm::unified_kv_cache_update`/`unified_mla_kv_cache_update`（Inductor 无法复用 piecewise 图问题）。
- `pass_config.fuse_gemm_comms` 强制 `enable_sp=True`；SP 要求 TP>1 且 hidden_size 达到阈值（H100/Blackwell 8192），否则自动关闭。`fuse_attn_quant` 与 piecewise cudagraph 冲突时改走 FULL（`set_splitting_ops_for_attn_fusion`）。
- 平台默认：`backend == ""` 时取 `current_platform.get_compile_backend()`（CUDA 系为 `inductor`）；`custom_ops` 在 Inductor 下默认 `["none"]`，eager 下默认 `["all"]`（`vllm.py:1375`），`is_custom_op_enabled(op)` 用 `+op/-op` 语法判定。
- `monitor_torch_compile`（`monitor.py`）把编译耗时写回 `compilation_config.compilation_time`；`VLLM_COMPILE` 模式下 `compile_debug_dump_path()` 启用 depyf dump（生成 `computation_graph.py`、`transformed_code.py` 调试产物）。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
