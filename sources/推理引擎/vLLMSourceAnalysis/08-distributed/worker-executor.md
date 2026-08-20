## Executor/Worker 执行模型

### Executor 类层次

`vllm/v1/executor/` 中 `Executor`（`abstract.py`）为抽象基类，通过 `Executor.get_class(vllm_config)` 按 `parallel_config.distributed_executor_backend` 选型：

| backend 取值 | 类 | 说明 |
|---|---|---|
| `"mp"` | `MultiprocExecutor`（`multiproc_executor.py`） | 默认多进程，`supports_pp=True` |
| `"ray"` | `RayDistributedExecutor`（`ray_executor.py`）或 `RayExecutorV2`（`VLLM_USE_RAY_V2_EXECUTOR_BACKEND=1`） | Ray 编排 |
| `"uni"` | `UniProcExecutor`（`uniproc_executor.py`） | 单进程（同进程 worker） |
| `"external_launcher"` | `ExecutorWithExternalLauncher` | 外部启动器（torchrun 等），v1 调度仍未完全确定性 |
| str/类 | `resolve_obj_by_qualname` 或直接类型 | 自定义 executor |

`Executor` 提供 `collective_rpc`（对每个 worker 的 RPC）、`initialize_from_config(kv_cache_configs)`、`compile_or_warm_up_model`、`execute_model`、`sample_tokens`、`shutdown` 等。`MultiprocExecutor` 用 `FutureWrapper`（`FuturesQueue` 保证响应按序）聚合各 worker 返回；`WorkerProc`（`multiproc_executor.py`）封装进程生命周期与 `UnreadyWorkerProcHandle` 就绪过渡。

### Worker 抽象

`vllm/v1/worker/worker_base.py`：

| 类 | 职责 |
|---|---|
| `WorkerBase` | Worker 接口 + 通用构造（持 vllm_config、rank、local_rank、device、model_runner 等），抽象方法见下 |
| `WorkerWrapperBase` | Executor 侧 worker 包装：`rpc_rank`/`global_rank` 区分 executor 内位次与分布式全局位次；`init_worker(all_kwargs)` 按 `parallel_config.worker_cls`（限字符串，需与 `worker_extension_cls` 动态混入）构造 worker |

`WorkerBase` 关键抽象方法：`init_device`、`load_model`、`determine_available_memory`、`get_model`、`get_model_inspection`、`get_kv_cache_spec`、`initialize_from_config`、`compile_or_warm_up_model`、`execute_model`、`sample_tokens`、`get_cache_block_size_bytes`、`check_health`、`shutdown`，以及 LoRA 族（`add_lora`/`remove_lora`/`pin_lora`/`list_loras`）与 `apply_model`/`get_model_inspection`。

### GPU Worker 初始化流程（gpu_worker.py）

```
Worker.init_device():
  1. 弹出 NCCL_ASYNC_ERROR_HANDLING（Ray 导致 graph 异常）
  2. 按 DP_LOCAL_RANK * TP_PP_SIZE + TP_LOCAL_RANK 修正 local_rank（多 DP 时）
  3. 发布逻辑→物理 GPU 映射（assigned_physical_gpu_ids）
  4. 计算 visible device 并 set_device；随后 init_worker_distributed_environment()
     └─ init_batch_invariance → override_envs_for_eplb → set_custom_all_reduce
        └─ init_distributed_environment(world_size,rank,init_method,local_rank,backend,timeout)
           └─ ensure_model_parallel_initialized(TP,PP,PCP,DCP)
           └─ ensure_ec_transfer_initialized (EPD disagg)
  5. 设随机种子 → 显存快照 MemorySnapshot → 构造 GPUModelRunner → 加载 encoder/decoder KV connector
  └─ load_model() → determine_available_memory() → initialize_from_config(kv_cache) → compile_or_warm_up_model()
```

`init_worker_distributed_environment`（同文件底部）即 worker 侧分布式初始化入口，其余 executor 共用。

### Task/调用模型

- Executor 用 `collective_rpc(method, args, kwargs)` 对全部 `WorkerWrapperBase` 发起同名方法调用，支持 `track_tasks` 返回 Future，DP 场景按 `get_inner_dp_world_group` 分批。
- model 执行经 `WorkerBase.execute_model`：输入 `SchedulerOutput`（batch/ubatch/spec decode 等），输出 `ModelRunnerOutput`/`AsyncModelRunnerOutput`；PP 跨阶段张量经 `IntermediateTensors` 与 `get_pp_group().send_tensor_dict`/`recv_tensor_dict`/`broadcast_tensor_dict` 同步（`AsyncIntermediateTensors` 做 lazy comm 同步）。
- 采样 `sample_tokens` 在 driver worker 分配 token ids，跨设备用 `Handle`（`is_completed`/`wait`）异步同步。

### startup_plan（启动计划复用）

`v1/worker/startup_plan.py`：`VLLM_ENABLE_STARTUP_PLAN=1` 时把内存 profiling 得到的 `kv_cache_memory_bytes` 持久化到 `{VLLM_CACHE_ROOT}/startup_plan/`，以 `compute_plan_fingerprint`（schema+vLLM版本+config hash+设备能力+rank+world_size）为 key；下次启动指纹匹配且当前空闲显存 ≥ 基线时直接应用，跳过 profiling 与 CUDA-graph 内存估算；否则回退完整 profiling。

### KV 传输（disagg / prefix caching 跨实例）

`vllm/distributed/kv_transfer/`，核心接口 `KVConnectorBase`（= `KVConnectorBase_V1`，`kv_connector/v1/base.py`）：

| 侧 | 职责 |
|---|---|
| Scheduler 侧 | `get_num_new_matched_tokens`（远端已缓存 token 数）、`update_state_after_alloc`、`update_connector_output`、`request_finished`（返回是否由 connector 异步释放）、`take_events` |
| Worker 侧 | `handle_preemptions`、`start_load_kv`/`wait_for_layer_load`、`save_kv_layer`/`wait_for_save`、`get_finished`、`build_connector_worker_meta` |

实现（`kv_connector/v1/`）：`lmcache_connector`、`flexkv_connector`、`nixl/`、`offloading/`（简单 CPU 卸载 `simple_cpu_offload_connector`）、`mooncake/`、`hf3fs/`、`moriio/`、`multi_connector`、`example_connector` 等。

KV 事件（`kv_events.py`）：`BlockStored`/`BlockRemoved`/`AllBlocksCleared`；发布器 `ZmqEventPublisher`/`NullEventPublisher`/`EventPublisherFactory`，支持 `KVEventAggregator`。张量传输语义统一为 `CopyBlocksOp`（`h2d`/`d2h`）。

关联子模块：`ec_transfer/`（encoder-decoder EPD disagg 连接器）、`weight_transfer/`（`WeightTransferEngine`，NCCL/IPC 权重同步，含 `nccl_engine`、`sparse_nccl_engine`、`ipc_engine`）、`nixl_utils.py`、`elastic_ep/`。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)