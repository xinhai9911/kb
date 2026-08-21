## 编译与 CUDA graph 捕获 _part2：Inductor 缓存、捕获/回放与 vLLM 对照

接 [compilation_part1.md](compilation_part1.md)。本文覆盖 `compiler_interface.py` 的 Inductor 缓存机制、`cuda_piecewise_backend.py` 的按 shape 捕获/回放、运行期与 scheduler/attention 的衔接，以及与 vLLM compilation 的对照。

### Inductor 编译与缓存（compiler_interface.py）

`InductorAdaptor`（:170）关键机制：

| 机制 | 说明 |
|---|---|
| `compute_hash` | md5(`get_inductor_factors`)（系统态 + torch 态）作缓存目录哈希 |
| `initialize_cache` | 重定向 `TORCHINDUCTOR_CACHE_DIR`/`TRITON_CACHE_DIR` 到缓存子目录，整目录可迁移复用 |
| `AlwaysHitShapeEnv`（:128） | 假 shape 环境：Dynamo 只跑一次、Inductor 按多种 shape 单独编译时，脱离 Dynamo 上下文仍命中 Inductor 代码缓存 |
| 猴子补丁 | `compiled_fx_graph_hash` 劫持拿 hash、`FxGraphCache._check_can_cache` 强制可缓存、`compile_fx_inner` 劫持拿产物路径；关闭 `fx_graph_remote_cache` 与 AOTAutograd cache |
| `set_inductor_config` | 指定具体 shape 时开 `max_autotune` + `coordinate_descent_tuning` |
| 缓存加载 | `load` 用 `FxGraphCache._lookup_graph` 按 hash 直读，包一层 list→tuple 调用约定转换 |

`CompilerManager`（backend.py:76）以 `(runtime_shape, graph_index, compiler.name)` 为键，缓存文件 `sglang_compile_cache.py`（`ast.literal_eval` 读写）。`EagerAdapter` 不编译，`compile` 原样返回 graph。

### CUDA graph 捕获/回放（cuda_piecewise_backend.py）

`CUDAPiecewiseBackend`（:47）对每个 shape 维护 `ConcreteSizeEntry`（:31：`need_to_compile`/`use_cudagraph`/`runnable`/`cudagraph`/`num_finished_warmup`）：

- 首次调用直接走 `compiled_graph_for_dynamic_shape`；其后按 `args[sym_shape_indices[0]]`（token 数）查 `concrete_size_entries`，命中才特化；未覆盖的 shape 继续走通用产物。
- 需编译的 shape 先 `compiler_manager.compile(..., runtime_shape=shape)` 得到按 shape 特化 runnable（末图编完 `save_to_file`）。
- **捕获条件**：非 warmup（`is_in_torch_compile_warmup()` 为假）、`get_pcg_capture_stream()` 非空（由 runner 的 `capture_session` 经 `set_pcg_capture_stream` 提供）、warmup ≥1 次。捕获用 `graph_pool_capture_scope()` + `torch.cuda.graph(cudagraph, pool=self.graph_pool, stream=...)`；**非首图 patch 掉 `gc.collect`/`torch.cuda.empty_cache`** 加速捕获；末图输出转 `weak_ref_tensors` 即时释放。
- **回放**：`graph_pool_replay_scope()` + `cudagraph.replay()`，返回弱引用持有的输出；`enable_debug_mode` 时比对捕获/回放输入地址（:218）。

### 运行期衔接

- runner 的 `capture_one`（:228）跑两次 forward：第一次暖 FX 状态，第二次在 `capture_session` 内完成捕获；`replay`（:254）调 `self._compiled_fn(static_forward_batch.input_ids, positions, forward_batch)` —— 即模型 forward（trampoline 因 `enable_tc_piecewise_cuda_graph()` 生效走编译路径）。
- `parallel_state.py`/`custom_all_reduce.py`/`radix_attention.py` 等检查 `is_in_tc_piecewise_cuda_graph()`：捕获/回放期间走图内 allreduce / 注意力分支，避免图外路径破坏捕获（`parallel_state.py:814,937,1131` 等）。
- **decode-Full 路径**（`torch_compile_decoration.py`）：`--enable-torch-compile` 时 `patch_model`（:42）用 `torch.compile(mode=SGLANG_TORCH_COMPILE_MODE，默认 max-autotune-no-cudagraphs)` 包 `no_grad(model.forward)`，`_to_torch` 递归切换 `BaseFusedOp`，并备份 `tp_group.ca_comm`；与 prefill 的 TC_PIECEWISE 是两条独立生命周期（文件头注明不共用 `install_torch_compiled`）。

### 与 vLLM compilation 对照

SGLang `compilation/` 显式标注「Adapted from vllm/compilation v0.10.0」：`SGLangBackend`/`split_graph`/`PiecewiseCompileInterpreter`/`CompilerManager`/`InductorAdaptor`/`PostGradPassManager` 均与 vLLM 对应物同构，差异在接线：

| 维度 | SGLang | vLLM（见 vLLM 17-compilation） |
|---|---|---|
| 配置来源 | `ServerArgs.cuda_graph_config.prefill`（bs/tc_compiler），无 O0-O3 | `CompilationLevel` O0-O3 映射全局 `VllmConfig` |
| 捕获规模 | `capture_sizes` 集合（prefill/decode 各一组） | `FULL_AND_PIECEWISE` 全量+piecewise |
| 模型接入 | `install_torch_compiled` 换 `forward` 为 trampoline，靠 `is_in_tc_piecewise_cuda_graph()` 运行时切换 | `@support_torch_compile` 改基类 + `_mark_dynamic_inputs` |
| 后端 | `SGLangBackend` → `CUDAPiecewiseBackend`（子图内自 `torch.cuda.graph` 捕获） | `VllmBackend` → `PiecewiseBackend` + 独立 `CUDAGraphWrapper` |
| pass | `PostGradPassManager` + `FixFunctionalizationPass` | `PostGradPassManager` + `fusion/ir/utility` passes |

### 附：srt/debug_utils（简要）

调试工具集（9 文件），多为 `--debug-*` 开关启用：`dumper.py`（2028 行）提供 `/dumper/{method}` 请求级/进程级 dump（HTTP 服务 + zmq 转发）；`tensor_dump_forward_hook.py` 给模型每算子挂 forward hook，按 `TP{tp}_PP{pp}_Rank{r}_pid{p}` 目录落 `Pass*.pt`（`--debug-tensor-dump-output-folder`）；`dump_comparator.py`/`text_comparator.py` 对比 dump 与文本输出；`log_parser.py` 用正则把调度日志「Decode batch … gen throughput …」解析为 polars DataFrame（`_PATTERN_DECODE`，提取 pid/TP/DP/PP 与吞吐）；`model_truncator.py`/`cuda_coredump.py`/`pr_fix_toggle.py` 分别做模型裁剪、coredump 与 PR 修复开关。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
