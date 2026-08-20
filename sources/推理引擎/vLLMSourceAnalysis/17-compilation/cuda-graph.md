## CUDA Graph 捕获与 Replay 机制

本文聚焦 `CUDAGraphMode` 策略、`CUDAGraphWrapper` 的捕获/replay 流程、piecewise vs full 运行时分发，以及 `breakable_cudagraph` 的流捕获中断方案。编译侧详见 [compilation-overview_part1.md](compilation-overview_part1.md) 与 [compilation-overview_part2.md](compilation-overview_part2.md)。

### CUDAGraphMode 策略枚举（vllm/config/compilation.py:53）

| 枚举 | 值 | 含义 |
|---|---|---|
| `NONE` | 0 | 不捕获 CUDA graph |
| `PIECEWISE` | 1 | 仅分段捕获：把 attention 等"非图安全" op 留在图外 |
| `FULL` | 2 | 整图捕获（小模型/小 prompt 场景；很多后端不支持） |
| `FULL_DECODE_ONLY` | `(FULL, NONE)` | 仅 decode batch 整图捕获，prefill/混合 batch 不捕获 |
| `FULL_AND_PIECEWISE` | `(FULL, PIECEWISE)` | decode 整图 + prefill/混合 batch 分段捕获（v1 默认，性能最好） |

复合模式通过 `decode_mode()`/`mixed_mode()` 拆解：decode 例程走整图、混合例程走分段。`NONE`/`PIECEWISE`/`FULL` 三个原子值是**运行时** `cudagraph_runtime_mode`（ForwardContext 字段），由模型 runner 按 batch 形状决定下发给 wrapper 做分发。

### 运行时分发契约

`CUDAGraphWrapper.__call__`（`cuda_graph.py:233`）的判定顺序：

```python
if not is_forward_context_available():   # 无 forward context（如视觉编码器）→ 直接执行
    return self.runnable(*args, **kwargs)
batch_descriptor = forward_context.batch_descriptor
mode = forward_context.cudagraph_runtime_mode
if mode == NONE or mode != self.runtime_mode:   # profile/warmup 或模式不匹配 → 直接执行
    return self.runnable(*args, **kwargs)
# 按 batch_descriptor 命中缓存：捕获（首次）或 replay（后续）
```

- 一个 wrapper 只绑定一个 `runtime_mode`（PIECEWISE 或 FULL），实现多个 wrapper 嵌套时的正确分发。
- 缓存键是 `BatchDescriptor`（编码 batch 形状/均匀性），`concrete_cudagraph_entries` 按 descriptor 存 `CUDAGraphEntry`。
- `CUDAGraphWrapper.clear_all_graphs()` 通过类级 `WeakSet` 清空所有实例，供弹性 EP 等场景重置。

### 捕获流程（首次遇到某 batch descriptor）

```
validate_cudagraph_capturing_enabled()      # monitor.py：非法时机捕获会抛错
记录 input_addresses（DEBUG 模式 replay 时校验一致性）
cudagraph = torch.cuda.CUDAGraph()
set_graph_pool_id(graph_pool)               # 平台全局 graph pool
get_offloader().sync_prev_onload()          # 同步 offloader copy stream
with torch.cuda.graph(cudagraph, pool=..., stream=current_stream()):
    output = self.runnable(*args, **kwargs) # 在捕获流上执行
    get_offloader().join_after_forward()    # 合并 copy stream，避免 unjoined stream 错误
    output = weak_ref_tensors(output)       # 弱引用释放强引用，省内存
entry.cudagraph = cudagraph
return output                               # 返回真引用供 torch 管理捕获期内存
```

Replay 路径：`get_offloader().sync_prev_onload()` → `entry.cudagraph.replay()` → 返回弱引用 output。wrapper 不自行维护静态输入缓冲拷贝——`cudagraph_copy_inputs=True` 时由 `make_copy_and_call`（`backends.py:59`）在 VllmBackend 层做动态输入 → 静态 buffer 的 `copy_`。

### Piecewise 与 Full 的实现差异

| 维度 | PIECEWISE | FULL |
|---|---|---|
| 切分 | Dynamo FX 层 `split_graph`（splitting_ops 处切）或 Inductor 分区（`use_inductor_graph_partition=True`） | 不切分（或外层整图捕获） |
| wrapper 数量 | N+1 个（每个可捕获子图一个 wrapper） | 1 个 |
| 捕获开销优化 | 仅首个图 debug log；非首图 `gc_disable`（patch gc.collect 与 empty_cache）；最后图 `weak_ref_output` | 默认 |
| 兼容性 | attention 等 op 留在图外，灵活性高 | 需 attention 后端 `AttentionCGSupport.ALWAYS` |

`wrap_with_cudagraph_if_needed`（`backends.py:633`）统一对 PiecewiseBackend 套 wrapper：`debug_log_enable=is_first_graph`、`gc_disable=not is_first_graph`、`weak_ref_output=is_last_graph`。Inductor 分区模式（`use_inductor_graph_partition`）下，`maybe_use_cudagraph_partition_wrapper`（`decorators.py:724`）注册 `torch._inductor.utils.set_customized_partition_wrappers`，让 Inductor 在每个分区外包 wrapper（分区 id 决定 gc/debug 行为）。

### cudagraph_capture_sizes 与显存估计

- 默认候选集（`vllm/config/vllm.py:1872`）：`[1,2,4] + range(8,256,8) + range(256, max_graph_size+1,16)`；`max_graph_size = min(max_num_seqs * decode_query_len * 2, default_max)`，Blackwell 数据中心默认 1024、其余 512；`max_num_batched_tokens` 若在界内也追加。
- 运行时：batch ≤ 某 capture size 时用最近的上取整图；batch 超过最大 size 则不用 cudagraph（`vllm.py:1901`）。
- spec-decode 场景 `adjust_cudagraph_sizes_for_spec_decode` 把 sizes 向上取整为 `uniform_decode_query_len`（及 SP 时的 TP 大小）的倍数。
- 显存：模型 runner 捕获时对前 2 个 descriptor 测内存差，估计 `first_capture + (n-1)*per_graph`（`gpu_model_runner.py:6866`），供 KV cache 预算使用。
- 捕获保护：捕获窗口由 `set_cudagraph_capturing_enabled(True/False)`（monitor.py）控制，profiling 之后才允许真正捕获；`validate_cudagraph_capturing_enabled()` 在 wrapper 内每次捕获前校验。
- `cudagraph_specialize_lora=True` 时按 LoRA 是否激活分别捕获，避免无 adapter 时付出 LoRA 开销。
- Mamba 模型整图 decode 需 `max_num_seqs ≤ kv_cache_config.num_blocks`（每个 seq 一块 cache），否则报错（`config/compilation.py:1499`）。

### 模式自动降级：resolve_cudagraph_mode_and_sizes

`CompilationConfig.resolve_cudagraph_mode_and_sizes`（`config/compilation.py:1369`）按 attention 后端的 `AttentionCGSupport`（`NEVER`/`UNIFORM_BATCH`/`ALWAYS` 等）做向下兼容：

- 混合 batch FULL 不被支持且 `splitting_ops_contain_attention()` → 降为 `FULL_AND_PIECEWISE`；否则降 `FULL_DECODE_ONLY`。
- decode FULL 不被支持但 attention 已 piecewise 编译 → 降 `PIECEWISE`；否则降 `NONE`。
- spec-decode（`uniform_decode_query_len>1`）下 decode FULL 不支持 → 同样降级。
- 降级后仍要求 FULL 却 `NEVER` → 抛 `ValueError`。

### Breakable CUDA Graph（实验性）

`breakable_cudagraph.py`（`VLLM_USE_BREAKABLE_CUDAGRAPH=1` 启用）替代"FX 预切分 + 每片一个 wrapper"：单个捕获上下文驱动整个 forward，`@eager_break_during_capture` 装饰的自定义 op（如 `unified_attention_with_output`）在被调度时**结束当前流捕获段 → eager 执行该 op → 开始新段**。产物是零参 callable 列表（各段 `CUDAGraph.replay` 或 eager fn），replay 按序执行。约束：eager 段必须写入调用方提供的静态输出 buffer（新返回 tensor 会地址漂移破坏后续段）；`FULL` 模式不加断点；装饰器须为最外层（host 副作用如 KV 传输须留在 eager 段）。wrapper 接口与 `CUDAGraphWrapper` 一致，`BreakableCUDAGraphWrapper` 按任意非 NONE 模式捕获（capture 产物与 prefill/decode 无关，仅按 BatchDescriptor 分键）。

### 统计与日志

`CUDAGraphLogging`（`cuda_graph.py:40`）聚合每次捕获的 `CUDAGraphStat`（未填充 tokens/填充 tokens/填充次数/运行模式），按频率生成 markdown 指标表输出；`compilation_counter` 记录 `num_cudagraph_captured`、`num_gpu_runner_capture_triggers` 等。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
