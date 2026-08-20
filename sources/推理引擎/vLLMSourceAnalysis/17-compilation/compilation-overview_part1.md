## Compilation 编译与图捕获总览 _part1

本文基于 `vllm/compilation/` 与 `vllm/config/compilation.py`、`vllm/config/vllm.py`，说明 CompilationLevel（O0-O3）到 `torch.compile`/CUDA graph 策略的映射、`CompilationMode`、VLLM_COMPILE 后端流水线；pass 变换与 config 衔接见 [compilation-overview_part2](compilation-overview_part2.md)。CUDA graph 捕获细节见 [cuda-graph.md](cuda-graph.md)。

### 模块文件地图（vllm/compilation/）

| 文件 | 职责 |
|---|---|
| `decorators.py` | `@support_torch_compile`/`@ignore_torch_compile` 类装饰器，标记动态维、首次编译触发、AOT compile 加载 |
| `wrapper.py` | `TorchCompileWithNoGuardsWrapper`：drop guards 的 `torch.compile` 包装；`VLLM_USE_BYTECODE_HOOK` 字节码直执行 |
| `backends.py` | `VllmBackend`（VLLM_COMPILE 后端）：split_graph 切图 + `PiecewiseCompileInterpreter` + 缓存管理 |
| `piecewise_backend.py` | `PiecewiseBackend`：每个子图按 compile range 预编译，运行时按 shape 派发 |
| `compiler_interface.py` | `CompilerInterface` 抽象 + `InductorAdaptor` / `InductorStandaloneAdaptor` / `EagerAdaptor` |
| `caching.py` | `VllmSerializableFunction`：序列化/反序列化编译产物；`StandaloneCompiledArtifacts` 去重存储 |
| `codegen.py` | 把 split_gm 缝合图生成纯 Python 执行函数，绕过 FX interpreter 开销 |
| `cuda_graph.py` | `CUDAGraphWrapper`：CUDA graph 捕获/replay；`CUDAGraphLogging` 统计 |
| `breakable_cudagraph.py` | `BreakableCUDAGraphCapture`：运行时流捕获中断（VLLM_USE_BREAKABLE_CUDAGRAPH） |
| `monitor.py` | `monitor_torch_compile`/`monitor_profiling_run` 计时；`validate_cudagraph_capturing_enabled` 非法捕获监控 |
| `counter.py` | 全局 `compilation_counter`：模型数、图数、编译数、捕获数等 |
| `passes/pass_manager.py` | `PostGradPassManager`：post-grad 自定义 pass 的顺序执行与 uuid |
| `passes/` | `fusion/`（图融合）、`ir/`（IR lowering/clone 消除）、`utility/`（清理类 pass） |

### CompilationLevel O0-O3 → 策略映射

`OptimizationLevel`（`vllm/config/vllm.py:96`）为 `IntEnum`，`VllmConfig.optimization_level` 默认 O2。各级别经 `OPTIMIZATION_LEVEL_TO_CONFIG`（`vllm.py:314`）覆盖 `compilation_config` 与 `kernel_config` 的默认值：

| 级别 | torch.compile | CUDA graph | 融合 pass | 说明 |
|---|---|---|---|---|
| O0 | `CompilationMode.NONE`（纯 eager） | `CUDAGraphMode.NONE` | 全部关闭 | 最快启动，无编译无捕获；`enable_flashinfer_autotune=False` |
| O1 | `VLLM_COMPILE` | `PIECEWISE` | 仅 norm/act 量化融合、ROCm 特定 | 快速优化，无 allreduce/attn 融合 |
| O2 | `VLLM_COMPILE` | `FULL_AND_PIECEWISE` | norm/act/allreduce/attn/SP 等按平台条件开启 | 默认级别 |
| O3 | 同 O2 | 同 O2 | 同 O2 | 文档注明 "Currently the same as -O2" |

- `mode` 的默认解析在 `VllmConfig.__post_init__`（`vllm.py:1362`）：未显式指定时 `optimization_level > O0` → `CompilationMode.VLLM_COMPILE`，否则 `NONE`。
- 融合开关多为惰性 callable（如 `enable_norm_fusion`、`enable_allreduce_rms_fusion`），根据 custom op 是否启用、TP 规模、平台能力（Hopper/Blackwell + flashinfer）在 config post-init 时才求值。

### CompilationMode（config/compilation.py:37）

| 枚举 | 值 | 含义 |
|---|---|---|
| `NONE` | 0 | 不编译，纯 eager |
| `STOCK_TORCH_COMPILE` | 1 | 标准 `torch.compile`（保留 guards） |
| `DYNAMO_TRACE_ONCE` | 2 | 单次 Dynamo trace，去 guards 避免重编译 |
| `VLLM_COMPILE` | 3 | 自定义 vLLM Inductor 后端：缓存、piecewise 编译、shape 特化、自定义 pass（V1 默认） |

### 编译流水线（VLLM_COMPILE 路径）

```
@support_torch_compile 类                       decorators.py
  └─ __call__ → _mark_dynamic_inputs (mark_dynamic / mark_unbacked)
  └─ TorchCompileWithNoGuardsWrapper.__call__   wrapper.py
       └─ torch.compile(backend=...)
            └─ VllmBackend.__call__             backends.py
                 ├─ configure_post_pass() → 挂 PostGradPassManager 到 inductor_config["post_grad_custom_post_pass"]
                 ├─ split_graph(graph, splitting_ops) → split_gm + SplitItem 列表
                 ├─ PiecewiseCompileInterpreter.run(fake_args) → 对每个子图建 PiecewiseBackend
                 │    └─ PiecewiseBackend.compile_all_ranges() → CompilerManager.compile() 逐 range 编译
                 │         └─ InductorAdaptor/StandaloneAdaptor.compile()
                 ├─ generate_execution_code(split_gm) + compile_execution_fn()   codegen.py
                 └─ 返回 VllmSerializableFunction（可序列化/反序列化）
```

关键行为：

- `@support_torch_compile`（`decorators.py:118`）通过把基类改为 `TorchCompileWithNoGuardsWrapper` 劫持 `__call__`；`dynamic_arg_dims` 未显式给出时按 forward 类型注解推断第 0 维动态；UNBACKED 模式走 `torch._dynamo.decorators.mark_unbacked`（2.11+ 支持 shape_id）。首次编译时 patch `InliningInstructionTranslator.inline_call_` 收集 `traced_files` 供缓存哈希使用。
- `split_graph`（`backends.py:553`）先 `_decompose_size_nodes` 把 `x.size()` 拆成逐维 `sym_size.int`（`torch.Size` 无法跨切分边界），再按 `splitting_ops` 用 `torch.fx.passes.split_module` 切分（`keep_original_order=True` 保语义）；`_merge_empty_only_subgraphs` 把纯 `empty` 分配子图并入前序以避免空 cudagraph 捕获。
- `PiecewiseBackend`（`piecewise_backend.py`）对每个子图维护 `range_entries`：`compile_ranges`（来自 `compile_ranges_endpoints`）+ `compile_sizes`（单 size range）；运行时按 `runtime_shape` 找到对应 range entry 调用已编译 runnable。encoder 编译时末 range 上界设为 `MAX_INT32`。
- 编译缓存：`CompilerManager`（`backends.py:124`）以 `(compile_range, graph_index, compiler_name)` 为键；`InductorAdaptor` 通过 patch `compiled_fx_graph_hash`/`AlwaysHitShapeEnv` 强制缓存命中；`InductorStandaloneAdaptor` 走 `torch._inductor.standalone_compile`（2.8+，`VLLM_USE_STANDALONE_COMPILE`）。缓存目录由 `env_hash + config_hash + code_hash + compiler_hash` 派生（`backends.py:1063`）。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
