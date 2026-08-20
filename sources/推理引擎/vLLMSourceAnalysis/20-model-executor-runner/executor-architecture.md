## Executor 层次与 Worker 编排（v0 / v1 对照）

> **历史来源**：v0 executor 代码已被 `[V0 Deprecation] Remove V0 executors (#27142)` 从当前 checkout（`vllm/v1/executor/`）删除，本文件 v0 侧基于共存末期提交 `a4528f0cac`（2025-07-29），历史位置 `vllm/executor/`（`executor_base.py`/`mp_distributed_executor.py`/`ray_distributed_executor.py`/`uniproc_executor.py`/`multiproc_worker_utils.py`）。当前 v0 兼容层现状（`vllm/engine/` shim）见 [24-v0-engine-legacy](../24-v0-engine-legacy/v0-engine-legacy.md)。

### v0 Executor 类层次（`vllm/executor/`）

| 类 | 文件:行 | 角色 |
|---|---|---|
| `ExecutorBase`(ABC) | `executor_base.py:29` | 抽象基类：`_init_executor`/`collective_rpc`/`check_health` 抽象；`execute_model`(:143) 默认实现为 `collective_rpc("execute_model", args=(req,))` 取 `output[0]`；`execute_model_async`(:238) 用 `make_async` 包同步版 |
| `DistributedExecutorBase` | `executor_base.py:255` | 分布式超类：持有 `parallel_worker_tasks`，`execute_model`(:265) 首跳给远端 TP worker 发 `start_worker_execution_loop`，之后只让 driver worker 跑 `_driver_execute_model`；异步版(:337) 用 `asyncio.create_task` 起 worker 循环 |
| `MultiprocessingDistributedExecutor` | `mp_distributed_executor.py:25` | Python multiprocessing 版（`uses_ray=False`，单机多卡） |
| `RayDistributedExecutor` | `ray_distributed_executor.py:52` | Ray 版（`uses_ray=True`），支持 placement group 与 compiled DAG |
| `UniProcExecutor` | `uniproc_executor.py` | 单进程单 worker（driver worker 即进程内 worker） |

### v1 Executor 类层次（`vllm/v1/executor/`）

| 类 | 文件 | 角色 |
|---|---|---|
| `Executor`(ABC) | `abstract.py:38` | 抽象基类；`get_class`(:48) 静态工厂按 backend 选型；`collective_rpc` 带 `non_block` 参数返回 Future |
| `UniProcExecutor` | `uniproc_executor.py:51` | 单进程（`supports_async_scheduling()=True`）；`execute_model`(:119)/`sample_tokens`(:134) 拆为两次 RPC |
| `MultiprocExecutor` | `multiproc_executor.py:111` | 默认多进程，`supports_pp=True`；`FutureWrapper`(:78) 经 `futures_queue` 保证响应按序；`WorkerProc`(:600) 封装进程与消息队列 |
| `RayDistributedExecutor` | `ray_executor.py:64` | Ray 编排，v1 默认走 compiled DAG |
| `RayExecutorV2` | `ray_executor_v2.py` | `VLLM_USE_RAY_V2_EXECUTOR_BACKEND=1` 启用；继承 `MultiprocExecutor`，复用 `WorkerProc`/`FutureWrapper`，仅把进程换成 Ray actor |
| `ExecutorWithExternalLauncher` | `uniproc_executor.py:161` | torchrun 外部启动器，`env://` init method，要求确定性调度 |

### backend 选型对照

| backend 取值 | v0 | v1 |
|---|---|---|
| `"mp"` | `MultiprocessingDistributedExecutor`（`mp_distributed_executor.py`；v0.6 时代文件名为 `multiproc_gpu_executor.py`，类名 `MultiprocessingGPUExecutor`） | `MultiprocExecutor`（默认） |
| `"ray"` | `RayDistributedExecutor`（`ray_distributed_executor.py`） | `RayDistributedExecutor` 或 `RayExecutorV2` |
| `"uni"` | `UniProcExecutor` | `UniProcExecutor` |
| `"external_launcher"` | `ExecutorWithExternalLauncher` | `ExecutorWithExternalLauncher` |
| 自定义类/qualname | — | v1 `get_class` 支持 `resolve_obj_by_qualname` |

选型依据 `parallel_config.distributed_executor_backend`（v0 在 `LLMEngine._get_executor_cls`，v1 在 `Executor.get_class`）。

### sync/async 双通道

- v0 引擎分同步/异步两套 API：`ExecutorBase.execute_model`（同步）与 `execute_model_async`（`make_async` 包装，仅供 `AsyncLLMEngine`）。`DistributedExecutorBase` 的异步路径额外用 `asyncio.create_task` 启动 `_start_worker_execution_loop`。
- v1 统一为同一接口 + `non_block` 标志：`collective_rpc(..., non_block=True)` 立即返回 `Future`（`MultiprocExecutor` 用 `FutureWrapper`；`UniProcExecutor` 用 `concurrent.futures.Future` 或 `AsyncOutputFuture` 包 `AsyncModelRunnerOutput`）。EngineCore 的 batch queue 据此让调度与模型执行重叠。

### 多进程 worker 通信（v0 `multiproc_worker_utils.py`）

```
Engine(父进程)                          Worker 子进程
ProcessWorkerWrapper ──task_queue──▶ _run_worker_process 事件循环
   execute_method() 注册 ResultFuture      for items in iter(task_queue.get, _TERMINATE):
                                              output = run_method(worker, method, args, kwargs)
ResultHandler(线程) ◀──result_queue──       result_queue.put(Result(task_id, value, exception))
   run(): iter(result_queue.get, _TERMINATE) → 按 task_id 回填 future
WorkerMonitor(线程): multiprocessing.connection.wait(worker.sentinel)
   任一 worker 退出 → kill 其余 worker、关闭 result handler
```

- `_run_workers` 先向所有远端 worker 投递任务，再 `run_method(self.driver_worker, ...)` 本地执行 driver，结果 `[driver] + [f.get() for f in worker_outputs]`。
- `async_run_tensor_parallel_workers_only=True` 时只投递非 driver worker 并直接返回 future 列表（不阻塞），用于 worker execution loop。
- `_driver_execute_model_async` 对 PP 各 stage 用 `asyncio.Lock`（`pp_locks`）防止多个 virtual engine 同时跑同一 stage，`asyncio.gather` 后取 `results[-1]`（末 PP stage 才有输出）。

### Ray worker 通信（v0/v1 `ray_distributed_executor.py`）

- 普通模式：`_run_workers` 用 `worker.execute_method.remote(sent_method, *args, **kwargs)` + `ray.get`；driver worker 在进程内。v0 若未启用 compiled DAG，走 `driver_exec_method = make_async(self.driver_worker.execute_method)`。
- v1 强制 `VLLM_USE_RAY_SPMD_WORKER=1` + `VLLM_USE_RAY_COMPILED_DAG=1`（SPMD 模式），`execute_model` 经 `self.forward_dag.execute(serialized_data)`，`ray.get` 取回 `outputs[0]`；v0 侧用 `msgspec.msgpack` 编解码 `ExecuteModelRequest`/`List[SamplerOutput]`（`input_encoder`/`output_decoder`），v1 直传对象。通道类型由 `VLLM_USE_RAY_COMPILED_DAG_CHANNEL_TYPE` 控制（`nccl`/`shm`）。
- `_init_workers_ray` 在 `placement_group` 内创建 Ray actor；`RayWorkerMetaData` 维护 worker 元数据（rank、pid 等）。

### worker execution loop 模式

v0 的分布式 executor 让非 driver 的 TP worker 常驻一个忙循环（`WorkerBase.start_worker_execution_loop`，`worker_base.py:83`）：

```python
with self.current_platform.inference_mode():
    while True:
        output = self.execute_model(execute_model_req=None)
        if output is None:
            return None
```

`DistributedExecutorBase.execute_model` 首跳以 `async_run_tensor_parallel_workers_only=True` 启动该循环，之后每步只有 driver 调用 `_driver_execute_model`；driver 的 `execute_model(None)` 会让远端 worker 的 `prepare_input(None)` 返回 `None` 从而退出循环。引擎空闲时 `stop_remote_worker_execution_loop()` 显式停止，避免 worker 阻塞在 torch.distributed 上。v1 已废除该模式，改为每步 `collective_rpc` 全 worker 同步（`non_block` 重叠调度）。

### 关键对照

| 维度 | v0 | v1 |
|---|---|---|
| execute_model 接口 | `execute_model(ExecuteModelRequest) -> List[SamplerOutput]`（单段） | `execute_model(SchedulerOutput, non_block) -> ModelRunnerOutput` + 独立 `sample_tokens(grammar_output)`（两段） |
| 异步 | 独立 `execute_model_async` 方法 | 同方法 `non_block=True` 返回 Future |
| 远端 worker | driver + 远端 worker 常驻循环 | 每步全量 RPC，`FutureWrapper` 保序聚合 |
| 输出 rank | driver 进程内 | `output_rank`（`unique_reply_rank`），可配 KV/EC aggregator 就地合并 |
| PP | `pp_locks` + virtual engine 串行 | 调度层 batch queue + `AsyncIntermediateTensors` |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
