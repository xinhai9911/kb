## v1 Worker 执行侧总览

vLLM V1 中 Worker 是模型实际运行的载体：位于 EngineCore 独立进程内，由 `Executor`（`vllm/v1/executor/abstract.py`）持有。`EngineCore.step()` 调度出 `SchedulerOutput` 后经 `model_executor.execute_model(...)` 广播到所有 worker，driver worker 汇总输出。本文覆盖 `vllm/v1/worker/`。

### Worker 类层次

| 类 | 文件 | 说明 |
|---|---|---|
| `WorkerBase` | `worker_base.py:39` | 抽象接口：生命周期 + 执行契约 |
| `Worker`（GPU） | `gpu_worker.py:142` | CUDA/ROCm 参考实现，CPU/XPU 均继承它 |
| `CPUWorker` | `cpu_worker.py:33` | 继承 GPU `Worker`，改写设备初始化/内存核算 |
| `XPUWorker` | `xpu_worker.py:24` | 继承 GPU `Worker`，INTEL XPU 后端 |
| `WorkerWrapperBase` | `worker_base.py:191` | 每 worker 一个进程壳：懒初始化 + 生命周期代理 |
| `AsyncIntermediateTensors` | `gpu_worker.py:110` | PP 中间张量 + 非阻塞通信句柄 |

`v1/worker/` 下没有独立的 neuron worker；该仓库平台层（`vllm/platforms/`）仅含 cuda/rocm/cpu/tpu/xpu。

### 生命周期方法（EngineCore 通过 Executor.collective_rpc 驱动）

| 方法 | 调用时机 | GPU Worker 行为 |
|---|---|---|
| `init_device()` | 进程启动 | DP local rank 重算、选 device、初始化分布式环境、内存快照，然后构造 `model_runner`（`use_v2_model_runner` 决定 V1/V2 类） |
| `load_model()` | 启动 | 调 `model_runner.load_model`，加载权重（含 dummy weights） |
| `determine_available_memory()` | 启动 | `model_runner.profile_run()` dummy forward 测峰值激活内存，反推 KV cache 可用字节 |
| `initialize_from_config(kv_cache_config)` | 启动 | 写回 `num_gpu_blocks`，`model_runner.initialize_kv_cache` 分配 KV cache |
| `compile_or_warm_up_model()` | 启动 | 编译 warmup + 内核 warmup + `capture_model()` CUDA graph，返回 `CompilationTimes` |
| `execute_model(scheduler_output)` | 每 step | 见下 |
| `sample_tokens(grammar_output)` | execute_model 返回 None 后 | 委托 `model_runner.sample_tokens` |
| `sleep(level)`/`wake_up(tags)` | 空闲 | SleepModeBackend 暂停/恢复，level2 时保存 buffers 到 CPU |
| `shutdown()` | 退出 | 清理；`WorkerSentinel`（`enable_fault_tolerance` 时）监督进程存活 |

### Worker.execute_model 执行流程（gpu_worker.py:1053）

1. 等待上一轮非阻塞 PP send（`self._pp_send_work`）完成。
2. `forward_pass = scheduler_output.total_num_scheduled_tokens > 0`。
3. PP>1 且非首 rank：`irecv_tensor_dict` 收前段中间张量，包成 `AsyncIntermediateTensors`。
4. 调 `self.model_runner.execute_model(scheduler_output, intermediate_tensors)`。
5. 返回类型分流：
   - `ModelRunnerOutput`/`AsyncModelRunnerOutput`/`None` → 直接返回（末 rank 采样路径；`None` 表示需随后 `sample_tokens`）；
   - `IntermediateTensors` → 非末 rank，`isend_tensor_dict` 非阻塞发往后段，返回 `None`。
6. 采样阶段：EngineCore 对返回 `None` 的 step 再调 `worker.sample_tokens(grammar_output)` → `model_runner.sample_tokens`。

### 与 EngineCore 的衔接

`EngineCore.step()`（`vllm/v1/engine/core.py:583`）：

```
scheduler_output = scheduler.schedule(...)          # 调度结果
future = model_executor.execute_model(scheduler_output, non_block=True)  # → collective_rpc → worker.execute_model
model_output = future.result()
if model_output is None: model_output = sample_tokens(grammar_output)
engine_core_outputs = scheduler.update_from_output(scheduler_output, model_output)
```

- `Executor.execute_model`（`v1/executor/abstract.py:223`）做 `collective_rpc("execute_model", args=(scheduler_output,))` 只取 `output[0]`（driver 结果），所有 worker 都执行以维持 NCCL/PP 同步。
- `WorkerWrapperBase.execute_model` 先 `_apply_mm_cache`（shm 多模态特征缓存），再转发真实 worker。
- worker 不直接见 `EngineCoreRequest`；它消费的是调度器派生的 `SchedulerOutput`（`v1/core/sched/output.py`）：`scheduled_new_reqs`/`scheduled_cached_reqs`/`num_scheduled_tokens`/`total_num_scheduled_tokens`/`scheduled_spec_decode_tokens`/`finished_req_ids`/`block_ids` 等。`NewRequestData` 携带 `prompt_token_ids`/`mm_features`/`sampling_params`/`pooling_params`/`lora_request` 等请求体字段。

### 不同硬件 Worker 差异

| 维度 | GPU `Worker` | `CPUWorker` | `XPUWorker` |
|---|---|---|---|
| 设备 | `cuda:{local_rank}` | `cpu`（numa 内存绑定、`init_cpu_memory_env`） | `xpu:{local_rank}`（CCL/oneccl env） |
| ModelRunner | `GPUModelRunner`（V1/V2） | `CPUModelRunner`（继承 GPUModelRunner） | `XPUModelRunner`（V1/V2） |
| 内存核算 | GPU memory snapshot + `gpu_memory_utilization` | CPU RSS + numa 可用内存（`--gpu-memory-utilization` 语义改为 CPU 内存） | 同 GPU |
| CUDA graph | `capture_model` | 无（torch.compile 路径） | 无 |
| sleep/wake | 支持（含 level2 权重卸载） | 不支持（直接忽略） | 继承 GPU |
| 分布后端 | NCCL | gloo/MPI | xccl |

`CPUModelRunner`（`cpu_model_runner.py:25`）与 `XPUModelRunner`（`xpu_model_runner.py`）均继承 `GPUModelRunner`，`execute_model` 主流程完全复用，仅覆写设备属性、KV cache 分配、`_to_list`（避免 `tensor.cpu()` 同步开销）等。

### worker_cls 解析与扩展

`WorkerWrapperBase.init_worker`（worker_base.py:234）按 `parallel_config.worker_cls`（字符串 qualname）解析 worker 类；若配置了 `worker_extension_cls`，则动态把扩展类注入 worker 的 `__bases__`（冲突属性断言后），实现 `collective_rpc` 的扩展控制面。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
