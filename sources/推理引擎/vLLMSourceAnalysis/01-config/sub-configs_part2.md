## ParallelConfig 并行配置

`ParallelConfig`(`vllm/config/parallel.py`,约 1050 行)描述 TP/PP/DP/PCP/DCP/EP 等全部并行维度,支持 PD 分离与专家并行(EPLB)。`__post_init__` 推导 `world_size`、`rank` 等派生值。

| 参数名 | 类型 | 必选 | 说明 |
|--------|------|------|------|
| `pipeline_parallel_size` | `integer` | 否 | PP 流水线并行度,默认 1 |
| `tensor_parallel_size` | `integer` | 否 | TP 张量并行度,默认 1 |
| `prefill_context_parallel_size` | `integer` | 否 | PCP 预填充上下文并行,默认 1 |
| `decode_context_parallel_size` | `integer` | 否 | DCP 解码上下文并行,默认 1 |
| `data_parallel_size` / `data_parallel_size_local` | `integer` | 否 | DP 度 / 本机 DP 度 |
| `data_parallel_rank` / `data_parallel_rank_local` | `integer` | 否 | DP rank / 本地 DP rank |
| `data_parallel_master_ip` / `data_parallel_master_port` / `data_parallel_rpc_port` | `string`/`integer` | 否 | DP 组通信地址 |
| `data_parallel_backend` | `DataParallelBackend` | 否 | `mp`/`ray` |
| `data_parallel_external_lb` / `data_parallel_hybrid_lb` | `boolean` | 否 | 外部 / 混合负载均衡 |
| `is_moe_model` | `boolean \| None` | 否 | 由 `ModelConfig.is_moe` 在 VllmConfig 装配后写回 |
| `enable_expert_parallel` | `boolean` | 否 | 启用专家并行(EP) |
| `enable_ep_weight_filter` | `boolean` | 否 | EP 权重过滤 |
| `enable_eplb` | `boolean` | 否 | 启用 EPLB 专家负载均衡 |
| `eplb_config` | `EPLBConfig` | 否 | EPLB 参数(见下) |
| `expert_placement_strategy` | `ExpertPlacementStrategy` | 否 | `linear`/`round_robin` expert 分布 |
| `max_parallel_loading_workers` | `integer \| None` | 否 | 权重并行加载 worker 数 |
| `disable_custom_all_reduce` | `boolean` | 否 | 禁用自定义 all-reduce(TP) |
| `enable_elastic_ep` | `boolean` | 否 | 弹性专家并行 |
| `enable_dbo` | `boolean` | 否 | 动态批处理优化(DPO) |
| `ubatch_size` | `integer` | 否 | 微批大小(DBO),默认 0 |
| `distributed_executor_backend` | `DistributedExecutorBackend` | 否 | `ray`/`mp`/`uni`/`external_launcher` |
| `worker_cls` / `sd_worker_cls` | `string` | 否 | worker 类(默认 `auto`) |
| `master_addr` / `master_port` | `string`/`integer` | 否 | 主节点地址,默认 `127.0.0.1:29501` |
| `node_rank` / `nnodes` | `integer` | 否 | 节点 rank / 总节点数 |
| `numa_bind` | `boolean` | 否 | NUMA 绑定;`numa_bind_nodes`/`numa_bind_cpus` 指定节点与 CPU |
| `assigned_physical_gpu_ids` | `array` | 否 | 显式指定 GPU 设备 id |
| `distributed_timeout_seconds` | `integer \| None` | 否 | 分布式超时 |
| `world_size` / `rank` | `integer` | 否(init=False) | 世界大小 / 当前 rank |
| `dcp_comm_backend` | `DCPCommBackend` | 否 | DCP 通信:`ag_rs`(AllGather-ReduceScatter)/`a2a` |
| `dcp_kv_cache_interleave_size` / `cp_kv_cache_interleave_size` | `integer` | 否 | DCP/CP KV 交错粒度 |

`EPLBConfig`(vllm/config/parallel.py)字段:`window_size`(默认 1000,负载均衡窗口)、`step_interval`(默认 3000)、`num_redundant_experts`(默认 0)、`log_balancedness`、`log_balancedness_interval`、`use_async`(默认 True)、`policy`(`default`)、`communicator`(`torch_nccl`/`torch_gloo`/`nixl`/`pynccl`)。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
