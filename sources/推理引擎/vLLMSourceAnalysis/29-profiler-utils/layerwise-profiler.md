## vLLM Profiler 逐层剖析与 worker 集成

`vllm/profiler/` 只有 4 个文件（`__init__.py` 为空），承担两类职责：**离线逐层剖析**（layerwise_profile.py + utils.py）与**在线 worker 采样**（wrapper.py）。后者被 `v1/worker/gpu_worker.py`、`cpu_worker.py`、`xpu_worker.py` 三个 worker 复用。

### 模块职责总览

| 文件 | 核心类/函数 | 职责 |
|---|---|---|
| `layerwise_profile.py` | `layerwise_profile`、`LayerwiseProfileResults`、`_ModuleTreeNode`、`_StatsTreeNode` | 在 torch profiler 结果上重建「模块树」，输出每层 CPU/CUDA 时间与占比 |
| `utils.py` | `TablePrinter`、`event_has_module`、`event_module_repr`、`event_torch_op_stack_trace` 等 | `_ProfilerEvent` 事件解析与表格打印工具，供 layerwise 与 `tools/profiler/` 复用 |
| `wrapper.py` | `WorkerProfiler`(ABC)、`TorchProfilerWrapper`、`ProtonProfilerWrapper`、`CudaProfilerWrapper` | 三种 profiler 的 worker 侧封装，带 delay/max-iterations 状态机 |

### layerwise_profile：逐层时间/显存如何计算

`layerwise_profile`（`layerwise_profile.py:373`）是 `torch.profiler.profile` 的子类，构造参数固定为：

```python
super().__init__(
    activities=[ProfilerActivity.CPU, ProfilerActivity.CUDA],
    record_shapes=True, with_stack=True, with_modules=True,
    experimental_config=_ExperimentalConfig(verbose=True),
)
```

`__exit__` 时把 `self.profiler.kineto_results` 连同 `num_running_seqs` 元数据交给 `LayerwiseProfileResults`，其 `__post_init__` 依次做三步建树：

1. **`_build_correlation_map`**：按 `correlation_id()` 把 kineto 事件索引成 `{correlation_id: [_KinetoEvent]}`，用于 CPU 侧事件到 GPU kineto 事件的关联。
2. **`_build_module_tree`**：对 `experimental_event_tree()` 做深度优先遍历，**只保留 `start_tid == 1` 的线程**（注释说明 tensor parallel 下暂只分析 task 1）。遇到 `event_has_module`（PyCall 且带 module）的节点生成 `_ModuleTreeNode`；叶子节点则附加 `event_torch_op_stack_trace` 得到的算子调用栈字符串（`op1 <- op2`）。
3. **`_build_stats_trees`**：基于模块树并行建两棵树——`summary_stats_tree`（按「模块全路径」聚合，同名多次调用合并并累计 `invocations`）与 `model_stats_tree`（保留树形结构、每个叶子一行）。

**CUDA 时间的取法**（`_cumulative_cuda_time`）：
- 叶子节点：`_get_kineto_gpu_event` 在 correlation map 中找同名的 CUDA device 事件，取 `duration_ns() / 1000.0`（微秒）。
- 非叶子模块：递归累加子树各叶子的 GPU 时间，即模块的**累计 CUDA 时间**。
- 时间占比 `pct_cuda_time` 以所有根节点的累计 CUDA 时间总和为分母。

注意：layerwise 本身**不测量显存**——`record_shapes` 只记录张量形状；`print_model_table` 输出列仅 `name/cpu_time_us/cuda_time_us/pct_cuda_time/trace`。显存相关的测度在 `vllm/utils/mem_utils.py`（见 utils-essentials.md）。输出 `filtered_*_table` 时只保留 `cuda_time_us > 0` 或 `cpu_time_us > 0` 的行。

### LayerwiseProfileResults 输出接口

| 方法 | 行为 |
|---|---|
| `print_model_table(column_widths=None)` | 打印带深度缩进（`\|---- `）的模型统计表，默认列宽 `name=60, cpu_time_us=12, cuda_time_us=12, pct_cuda_time=12, trace=60` |
| `print_summary_table(...)` | 打印按路径聚合的汇总表（列 `name/cuda_time_us/pct_cuda_time/invocations`） |
| `export_model_stats_table_csv(filename)` / `export_summary_stats_table_csv(filename)` | 依赖可选依赖 `pandas`（缺失时 `PlaceholderModule` 兜底），把扁平化树转 `DataFrame` 写 CSV |
| `convert_stats_to_dict()` | 返回 `{"metadata": {"num_running_seqs": ...}, "summary_stats": [...], "model_stats": [...]}`，树形 JSON（`{"entry": ..., "children": [...]}`），供 `tools/profiler/visualize_layerwise_profile.py` 可视化 |

下游工具在 `vllm/tools/profiler/`：`print_layerwise_table.py`（表格打印）、`visualize_layerwise_profile.py`（读 JSON 出火焰图/图表）。layerwise_profile 不接入 worker 在线路径，属离线工具。

### WorkerProfiler 状态机

`WorkerProfiler`（wrapper.py:28）是 worker 侧基类，核心是区分两个布尔量：

| 状态 | 含义 | 置位时机 |
|---|---|---|
| `_active` | 收到 `start_profile` 请求 | `start()` 置 True；`stop()` 置 False |
| `_running` | 底层 profiler 真正在采数据 | `_call_start()` 成功；`_call_stop()` 后清零 |

`step()` 在每个 worker step 被调用，处理两类场景：
- **延迟启动**：`delay_iterations > 0` 时，等 `_active_iteration_count == delay` 才真正 `_call_start()`。
- **自动停止**：`max_iterations > 0` 且累计有效采样步 `_profiling_for_iters > max` 时 `_call_stop()`（用 `>` 而非 `>=`，与 ProfilerConfig 校验语义一致）。
- `_profiler_step()` 默认返回 True；`TorchProfilerWrapper` 重写后：有 schedule 时调 `profiler.step()`，warmup 剩余步数内返回 False（不计数为有效采样步）。

抽象方法：`_start()`/`_stop()`（实现类负责真正开关）、`annotate_context_manager(name)`（返回 trace 标注上下文管理器）。

### 三种 Worker Profiler 实现

| 实现 | 底层 | 关键行为 |
|---|---|---|
| `TorchProfilerWrapper` | `torch.profiler.profile` | `on_trace_ready` 默认 `tensorboard_trace_handler(dir, worker_name, use_gzip)`；支持 `warmup/wait/active` schedule（任一 >0 即启用，`skip_first=0, repeat=1`）；`_stop` 后按 `torch_profiler_dump_cuda_time_total`/仅 CPU 场景写 `profiler_out_{rank}.txt`（URI 路径如 gs:// 跳过文件写）；`_maybe_add_version_metadata` 把 vLLM 版本写入 trace metadata（schedule 下 Kineto 在 WAIT 结束后才可用，因此每次 `_profiler_step` 再试一次） |
| `ProtonProfilerWrapper` | `triton.profiler`（Proton） | 懒导入，缺失抛 RuntimeError；输出 `proton_{worker_name}_{pid}{uuid}_run{run_id}`；`_validate_capabilities` 检查 `output_format`/`periodic_flushing` 需要 Triton >= 3.7.0；实例名带 pid+uuid 防止覆盖旧 server 残留 |
| `CudaProfilerWrapper` | `torch.cuda.profiler` | 最简：`start()`/`stop()` 直通；`annotate_context_manager` 返回 `torch.cuda.nvtx.range(name)` |

`ProfilerConfig`（`vllm/config/profiler.py`）驱动选择：`profiler` 字段取 `'torch'|'cuda'|'proton'`。`gpu_worker.py:1170` 的 `start_profile` 处理中按类型实例化 wrapper（`worker_name` 为 `profile_prefix_` + `get_worker_rank_suffix(global_rank)`），此后每次 start/stop 复用同一实例。`profiler.step()` 由 worker 的 step 流程驱动。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
