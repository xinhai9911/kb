## vllm/utils 基础设施与平台适配篇

承接 utils-essentials.md，本篇覆盖异步/GC/内存/缓存/序列化等基础设施，以及随机数种子相关懒加载模块（b12x/mistral）与 HPC/NUMA 适配。

### async_utils：阻塞代码接入事件循环

| 函数 | 行为 |
|---|---|
| `make_async(func, executor=None)` | 把阻塞函数包装成返回 `Future` 的异步函数，经 `loop.run_in_executor` 在线程池执行，避免阻塞 asyncio 事件循环 |
| `make_async_with_semaphore(func, executor)` | 同上但用 `asyncio.Semaphore(executor._max_workers)` 限流，便于任务启动前取消 |
| `run_in_loop(loop, function, *args)` | 已在目标 loop 则直接调用，否则 `call_soon_threadsafe` 投递 |
| `in_loop(event_loop)` | 判断当前是否运行在指定 loop 中 |
| `cancel_task_threadsafe(task)` | 跨线程安全取消 Task |
| `merge_async_iterators(*iterators)` | 多 async generator 合并为 `(i, item)` 流（`FIRST_COMPLETED` 调度，失败清理全部），单迭代器走快速路径；v0 `AsyncLLMEngine` 输出合并用 |
| `collect_from_async_generator(iterator)` | 收集 async generator 全部产出为 list |

### gc_utils：GC 观测与冻结

- `freeze_gc_heap()`：先 `gc.collect(0/1/2)` 把静态对象压入最老代，再 `gc.freeze()`。注释要求**在 server init/warmup 后调用**，以削减服务期 GC 开销。这是 vLLM 启动序列里「冻结堆」的出处。
- `maybe_attach_gc_debug_callback()`：按 `VLLM_GC_DEBUG` 环境变量（`"0"`/`"1"`/`{"top_objects": N}`）挂 `gc.callbacks` 回调，`GCDebugger` 记录每次 GC 的耗时、回收对象数及按类型分组的 Top 对象。

### mem_utils：显存画像与上下文

- 常量（`mem_constants.py`）：`KB/MB/GB_bytes = 1000/1e6/1e9`，`KiB/MiB/GiB_bytes = 2^10/2^20/2^30`；`format_kib/mib/gib` 配套。
- `MemorySnapshot`：一次显存快照。关键点是 `torch_peak` 取自 `memory_stats()["allocated_bytes.all.peak"]` 而非 `memory_reserved()`（后者在 `reset_peak_memory_stats` 后只增不减）；UMA（GH200/DGX Spark/Jetson）上 `cudaMemGetInfo` 低估可用内存，改用 `psutil.virtual_memory().available`；`non_torch_memory = cuda_memory - torch_memory` 用于测 NCCL/attention 后端缓冲等非 torch 占用。支持 `__sub__` 差分。
- `DeviceMemoryProfiler`：上下文管理器，`__exit__` 计算 `consumed_memory = final - initial`（进入/退出前均 `gc.collect()`）。
- `memory_profiling(baseline_snapshot, weights_memory)`：**显存画像核心**。进入时 `gc.collect()` + `empty_cache()` + `reset_peak_memory_stats()`，退出时产出 `MemoryProfilingResult`：`torch_peak_increase`（激活张量峰值，取自 peak diff）、`non_torch_increase`（自创建实例以来的非 torch 增长）、`total_consumed`（用 `free_memory` 差而非 `memory_reserved`，规避 cumem 等插拔 allocator 绕过 torch 跟踪导致的负数）、`transient_peak_headroom`、`non_kv_cache_memory = total_consumed + transient_peak_headroom`。这是 `determine_available_memory` 计算非 KV 常驻内存的依据。
- `get_max_shared_memory_bytes(gpu)`（`@cache`，断言 >0）、`get_cpu_memory()`（psutil total）、`release_device_memory_under_pressure`（UMA 高压下主动释放缓存）。

### cache：带统计与 pin 的 LRU

`LRUCache(cachetools.LRUCache)` 扩展：
- `pin(key)` 钉住条目防止 LRU 驱逐；`popitem(remove_pinned=False)` 默认跳过已 pin 项，全钉时抛 `RuntimeError("All items are pinned...")`。
- `touch(key)` 更新访问序；`stat(delta=False)` 返回 `CacheInfo(hits, total, hit_ratio)`，`delta=True` 返回自上次调用以来的增量。
- `get`/`put`/`pop` 覆盖；`_on_remove` 为空钩子可被子类重写（如分布式算子缓存回收回调）。`cache`/`order` 属性暴露只读有序视图。

### tqdm_utils 与 misc

- `maybe_tqdm(it, *, use_tqdm, **kwargs)`：`use_tqdm` 为 False 时原样返回可迭代对象；为可调用对象时用其作为 tqdm 工厂（离线加载进度条开关）。
- `__init__.py`：`random_uuid()`（64 位随机 ID 的 16 位十六进制串，请求 ID 用）、`length_from_prompt_token_ids_or_embeds`、`is_moe_layer`（沿继承链查 `MoERunnerInterface` 名字规避循环导入）。

### 随机数相关懒加载模块

| 模块 | 用途 |
|---|---|
| `b12x.py` | 可选 `b12x` 包（Block-Scaled/FP8 GEMM 内核）懒加载门控：`has_b12x()`、`get_b12x_blockscaled/intrinsics/mxfp8_linear/tensor_fp8_linear`；`b12x_warmup_token_counts` 提供 warmup token 集合（让 B12X 自行去重形状策略）；`reuse_packed_weight_storage` 在布局兼容时复用打包权重地址 |
| `mistral.py` | Mistral tokenizer/工具解析器的免导入类型判断：`is_mistral_tokenizer`（先查 `IS_MISTRAL_TOKENIZER` 类标记，命中才 `isinstance` 确认）、`is_mistral_tool_parser`（只查 `IS_MISTRAL_TOOL_PARSER` 标记）；经 `LazyLoader` 懒加载 `vllm.tokenizers.mistral` |

### HPC 与 NUMA 适配

- `hpc.py`：`has_hpc()` 用 `find_spec` 探测（避免 CUDA 初始化副作用）；`hpc_fuse_moe` / `hpc_fuse_moe_blockwise` 包装 `hpc` 包（Tencent hpc-ops）的 MoE kernel，含对应 fake 实现（签名里保留注释掉的 `@torch.library.custom_op` 说明改用 `direct_register_custom_op` 路线）。`__all__ = ["has_hpc", "hpc_fuse_moe", "hpc_fuse_moe_blockwise"]`。
- `numa_utils.py`：worker 进程 NUMA 绑定。`get_libnuma()`（`@cache`，ctypes 加载 `libnuma.so[.1]`）；`_can_set_mempolicy()` 用 `get_mempolicy` 探测权限；自动 NUMA 检测要求多节点、非受限 CPU 亲和性；内部通过 `_VLLM_INTERNAL_NUMACTL_ARGS` / `_VLLM_INTERNAL_NUMACTL_PYTHON_EXECUTABLE` 环境变量把 numactl 参数透传给 worker 启动（配套 `numa_wrapper.sh`）。经 `vllm/envs.py` 的 `VLLM_NUMA_BIND_NODES` 等配置驱动，`get_worker_numa_memory_policy` 等提供 worker 侧查询。
- 其他平台类：`platform_utils.py`（`is_pin_memory_available` 等）、`system_utils.py`、`cpu_resource_utils.py`、`ompmultiprocessing.py`（OMP 感知的 multiprocessing）、`multi_stream_utils.py`、`nccl.py`（`find_nccl_library`，供 import_utils 运行时读 NCCL 版本）、`network_utils.py`（端口/网卡发现）、`collection_utils.py`（`merge_dicts` 等集合工具）。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
