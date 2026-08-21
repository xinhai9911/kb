## 编译与 CUDA graph 捕获 _part1：配置、切图与编译流水线

本文覆盖 `srt/compilation/`（15 文件）及驱动它的 runner 后端 `model_executor/runner_backend/tc_piecewise_cuda_graph_backend.py`。核心思路：`torch.compile`（Dynamo+FX）按注册的 split-op 把模型 forward 切成多个子图，每个子图对若干 token 规模分别做 Inductor 编译并独立 CUDA graph 捕获，运行期按 shape 派发。Inductor 缓存与捕获/回放细节见 [compilation_part2.md](compilation_part2.md)；与 vLLM 对照也在 part2。

### 模块文件地图（srt/compilation/）

| 文件 | 职责 |
|---|---|
| `compile.py` | `install_torch_compiled`：模型 forward 包成 `torch.compile` + trampoline；`IntermediateTensors`（PP 跨阶段中间态）；动态维度推断 |
| `compilation_config.py` | `CompilationConfig(capture_sizes, compiler="eager"/"inductor", enable_debug_mode)`；`@register_split_op` 注册表 `SPLIT_OPS`；`configure_inductor`（`combo_kernels` 水平融合） |
| `backend.py` | `SGLangBackend`（torch.compile 后端）：`split_graph` 切图、`PiecewiseCompileInterpreter` 逐子图编译、`CompilerManager` 缓存 |
| `compiler_interface.py` | `CompilerInterface` 抽象 + `InductorAdaptor`（缓存与猴子补丁）/ `EagerAdapter` |
| `cuda_piecewise_backend.py` | `CUDAPiecewiseBackend`：每个 shape 的编译 + CUDA graph 捕获/回放 |
| `npu_piecewise_backend.py` / `xpu_piecewise_backend.py` | NPU/XPU 平台变体 |
| `compile_phase.py` | torch.compile 内部阶段标记：`_in_torch_compile_warmup`、`_pcg_capture_stream` |
| `pass_manager.py` | `PostGradPassManager`：post-grad 自定义 pass 顺序（`fix_functionalization` 最后） |
| `inductor_pass.py` | `InductorPass`（uuid 取源码 hash 参与缓存键）、`pass_context`（携带 runtime_shape） |
| `fix_functionalization.py` / `fx_utils.py` | 反函数化 pass / FX 工具 |
| `torch_compile_decoration.py` | decode-Full 路径（`--enable-torch-compile`）的 `patch_model` |
| `weak_ref_tensor.py` | `weak_ref_tensors`：CUDA graph 输出转弱引用省显存 |
| `compilation_counter.py` | 全局编译计数（`num_cudagraph_captured`/`num_inductor_compiles` 等，供测试断言） |

### split-op 切图：图在哪被切开

`SPLIT_OPS` 由各层 `@register_split_op()` 注册（compilation_config.py:10），`split_graph`（backend.py:225）按这些 `call_function` 节点把 FX 图切成子图（`keep_original_order=True` 保含 mutation 图的语义）：

| 注册点 | 切分 op |
|---|---|
| `layers/radix_attention.py:404,452,494` | `unified_attention_with_output` 等注意力入口 |
| `layers/radix_linear_attention.py:125`、`models/deepseek_common/.../forward_mla.py:934` | 线性注意力/MLA |
| `distributed/parallel_state.py:168` | `inplace_all_reduce`（allreduce 亦可作切分点） |
| `layers/attention/hpc_ops_backend.py:662`、`dsa/*` | HPC/DSA 后端 |
| 运行时补充 | `tc_piecewise_cuda_graph_backend.py:128`：DeepEP/Mooncake 时加 `sglang.moe_forward_piecewise_cuda_graph_impl` |

每段子图独立编译 → 独立 CUDA graph 捕获（约每层一个），即「piecewise」得名由来。

### 编译流水线（prefill / TC_PIECEWISE 路径）

runner 侧 `TcPiecewiseCudaGraphBackend`（`tc_piecewise_cuda_graph_backend.py:86`）构造时执行 `_run_compile_pass`（:151）：

1. `build_compilation_config`（:110）：从 `server_args.cuda_graph_config.prefill` 取 `bs`（捕获规模集合）与 `tc_compiler`（仅 `eager`/`inductor`），构 `CompilationConfig`。
2. `enable_tc_piecewise_cuda_graph()` 上下文内：`_toggle_fused_ops`（`BaseFusedOp` 进入 torch.compile 模式）→ 最小 shape 跑 dummy forward 热核 → `get_or_create_global_graph_memory_pool` 建全局 graph pool → `install_compile` 调 `install_torch_compiled`。
3. `enable_torch_compile_warmup()` 内对 `capture_num_tokens`（倒序；AMD 仅一次）逐 shape 跑 dummy forward，**驱动 Dynamo/Inductor 编译但跳过 CUDA graph 捕获**；最后跑一次 VLM deepstack dummy forward。

`install_torch_compiled`（compile.py:150）：
- **动态维度**：优先用 `dynamic_arg_dims`，否则按 forward 参数类型注解推断（`torch.Tensor` → dim 0 动态；mRoPE `positions`/`position_ids`/`mrope_positions` → 末维，compile.py:89）；`ForwardBatch` 无注解，单独 `_mark_dynamic_forward_batch` 逐张量标动态。
- `register_bytecode_hook` 在 Dynamo `convert_frame` 捕获编译后新 code 供缓存哈希（compile.py:175）。
- `trampoline`（:229）：仅当 `is_in_tc_piecewise_cuda_graph()`（捕获/回放上下文）才走 `compiled_callable`，否则直跑原始 forward。

`torch.compile(backend=SGLangBackend)` 后端回调（backend.py:404）：
1. 缓存目录 `SGLANG_CACHE_DIR/torch_compile_cache/{compiler_hash}/rank_0_0/{model_tag}`（`set_model_tag` 区分 backbone/eagle 等，backend.py:348）。
2. `split_graph` 切图 → `PiecewiseCompileInterpreter.run(fake_args)`（fake mode + `enable_python_dispatcher`，backend.py:296）：对每个可捕获子图先按**动态 shape**（`runtime_shape=None`）编译通用产物 `compiled_graph_for_dynamic_shape`，再 `make_backend` 装回 `PiecewiseBackend`（CUDA/XPU/NPU 按平台，backend.py:55）。
3. rank 0 落盘 `computation_graph_{ts}.py`（`split_gm.print_readable`）供调试。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
