## ModelRunner 模型执行器与 TP Worker

本文基于 `sglang/srt/model_executor/model_runner.py` 与 `sglang/srt/managers/tp_worker.py`，说明模型执行进程（TPWorker）如何接收调度批、执行模型 forward、返回采样结果，以及 ModelRunner 的初始化与执行体系。

### 分层调用链

```text
Scheduler.event_loop_* (scheduler.py / scheduler_pp_mixin.py)
  └─ run_batch(batch, pp_proxy_tensors)
       └─ model_worker.forward_batch_generation(batch, ...)   # → TpModelWorker
            ├─ ForwardBatch.init_new(batch, model_runner)     # ScheduleBatch → ForwardBatch
            └─ model_runner.forward(forward_batch, pp_proxy_tensors=...)
                 └─ _forward_raw() → EagerRunner / CudaGraphRunner → model.forward(...)
                 └─ sample(logits_output, forward_batch) → next_token_ids
```

- `TpModelWorker`（`managers/tp_worker.py:299`）是模型执行进程主体，由 `Scheduler`（`scheduler.py:921`）实例化；`BaseTpWorker`（`tp_worker.py:74`）抽象 `forward_batch_generation` / `model_runner`。
- 调度与执行同进程但异流：`forward_stream_ctx` 内 `forward_stream.wait_stream(schedule_stream)`（`scheduler.py:3735`），实现 overlap schedule。
- 生成式返回 `GenerationBatchResult`（`managers/utils.py:44`）；embedding/奖励模型走 `forward_batch_embedding`。

### TpModelWorker 职责

| 成员 | 位置 | 说明 |
|---|---|---|
| `_init_model_config` | `tp_worker.py:444` | `ModelConfig.from_server_args`，draft worker 用 `speculative_draft_model_path` |
| `_init_model_runner` | `tp_worker.py:463` | 构造 `ModelRunner`；多层 EAGLE 时 `_init_multi_layer_eagle_model_runners` 建 `model_runner_list` |
| `forward_batch_generation` | `tp_worker.py:574` | 核心执行入口：`ForwardBatch.init_new` → `model_runner.forward` → `sample` |
| `forward_batch_split_prefill` | `tp_worker.py:684` | PD 多路复用：split_index==0 时建 FB 并存 `batch.split_forward_batch`，随后按层推进 |
| `forward_batch_embedding` | `tp_worker.py:289` | embedding/pooler 路径，返回 `logits_output` |
| `alloc_memory_pool` / `init_attention_backends` / `init_cuda_graphs` | `tp_worker.py:390/418/424` | 启动期由 Scheduler 调用（`scheduler.py:964/983/989`） |
| 权重相关 RPC | `tp_worker.py:131-287` | `update_weights_from_disk/distributed/tensor/ipc`、权重发送 group、LoRA 加载，委托 `weight_updater` / `weight_exporter` |

`forward_batch_generation` 关键逻辑（`tp_worker.py:574-682`）：

```python
if batch is not None:
    forward_batch = ForwardBatch.init_new(batch, self.model_runner, ...)
if self.pp_group.is_last_rank:
    out = self.model_runner.forward(forward_batch, pp_proxy_tensors=pp_proxy_tensors)
    logits_output, can_run_cuda_graph = out.logits_output, out.can_run_graph
    if not forward_batch.is_prefill_only:
        batch_result.next_token_ids = self.model_runner.sample(logits_output, forward_batch)
    ...
else:  # 非末 PP rank
    out = self.model_runner.forward(forward_batch, pp_proxy_tensors=pp_proxy_tensors)
    pp_proxy_tensors, can_run_cuda_graph = out.logits_output, out.can_run_graph
```

要点：**末 rank 才采样**（非末 rank 输出 `PPProxyTensors`，经 `GenerationBatchResult.pp_hidden_states_proxy_tensors` 传下一 stage）；**overlap 延迟采样**（`enable_overlap` 且带 grammar 或 `SGLANG_ENABLE_DELAY_SAMPLE` 时把采样封装进 `batch_result.delay_sample_func`，由调度器下轮执行，`tp_worker.py:628-647`）。

### ModelRunner 初始化

`ModelRunner.__init__`（`model_runner.py:287`）按序完成：

| 步骤 | 方法 | 说明 |
|---|---|---|
| 设备与分布式 | `init_shared_mooncake_transfer_engine`、`init_torch_distributed`（`model_runner.py:1029`） | 得 `tp_group`/`pp_group`/`attention_tp_group`/`pre_model_load_memory` |
| 权重加载 | `self.initialize()` → `load_model()`（`model_runner.py:1049`） | 见 weight-loading.md |
| 层信息 | `resolve_layer_indices` → `layer_info`（start/end layer，PP 用） | `model_runner.py:647` |
| KV cache dtype | `configure_kv_cache_dtype`（`model_runner.py:1314`） | 结合 FP8 门控、spec 算法解析最终 dtype |
| PP 支持探测 | `"pp_proxy_tensors" in inspect.signature(self.model.forward).parameters` | `support_pp`，PP>1 时模型必须支持（`model_runner.py:445`） |
| 运行期组件 | `init_weight_updater` / `init_weight_exporter` | 见 weight-loading.md |

`alloc_memory_pool`（`model_runner.py:799`）由 Scheduler 在加载后调用：`KVCacheConfigurator.configure(pre_model_load_memory=...)` 分配 KV 池，写回 `max_total_num_tokens`/`max_running_requests`/`req_to_token_pool`/`token_to_kv_pool_allocator`。`init_attention_backends`（`model_runner.py:919`）解析并构建 attention 后端（prefill/decode 可不同，见 `attention_backend_setup.py`）。

### forward 执行流程

`ModelRunner.forward`（`model_runner.py:1497`）返回 `ModelRunnerOutput`（`logits_output` + `can_run_graph` + EPLB/专家捕获输出），核心在 `_forward_raw`（`model_runner.py:1641`）：

1. 建立 `ForwardContext(attn_backend=...)`（`forward_context.py`），供模型层读取当前 attention 后端。
2. 判定 `can_run_graph`：`forward_mode.is_cuda_graph()` 且 `decode_cuda_graph_runner.can_run_graph(forward_batch)`。
3. **CUDA graph decode**：`decode_cuda_graph_runner.execute(forward_batch, pp_proxy_tensors)` 直接回放（静态批槽位 + 负载写回）。
4. 否则 `_prepare_eager_forward_batch`：DP/MLP-sync padding、attn-TP `num_token_non_padded` 归一化、hisparse 计数（`model_runner.py:1408`）。
5. 按 forward_mode 分派：
   - `is_split_prefill` → `forward_split_prefill`（按 `split_index` 逐段调用 `model.forward_split_prefill`）；
   - extend 且 prefill CUDA graph 可用 → `prefill_cuda_graph_runner.execute`（piecewise graph）；
   - 其余 → `eager_runner.execute`（`eager_runner.py:204` 内再按 decode/idle/extend 分派）。
6. `sample`（`model_runner.py:1758`）：`_preprocess_logits`（regex vocab mask、logits bias）→ `self.sampler(...)`（`create_sampler`，`layers/sampler.py:545`）→ `ngram_embedding_manager.update_after_decode`。prefill-only 请求走 `compute_logits_only`（`model_runner.py:1794`）。

模型层执行入口统一为 `model.forward(input_ids, positions, forward_batch, **kwargs)`，attention 层经 `RadixAttention` 读取 `ForwardBatch` 中的池与后端元数据。

### PP 下 tp_worker 的流水线

PP 事件循环在调度器侧（`managers/scheduler_pp_mixin.py:69` `event_loop_pp`，详见 03-scheduler/scheduler-pp-mixin.md），tp_worker 只承担「每 stage 本地的 forward」：

- 每 stage 用 `PPBatchMetadata` 记录 `can_run_cuda_graph`；`pp_proxy_tensors` 经 `_pp_recv_proxy_tensors` 获得后传入 `forward_batch_generation`。
- 非末 rank 的 forward 输出 `PPProxyTensors`（`forward_batch_info.py:1716`，`Dict[str, torch.Tensor]`，仿 vLLM `IntermediateTensors`），随 `pp_hidden_states_proxy_tensors.tensors` 异步 send 给下一 stage（`scheduler_pp_mixin.py:165`）。
- 末 rank 得真实 `LogitsProcessorOutput` 并采样；`pp_async_batch_depth` 允许末 stage 缓冲输出，与下个 micro-batch 计算重叠。

### 与 vLLM GPUModelRunner 对照

| 维度 | SGLang `ModelRunner` | vLLM V1 `ModelRunner` |
|---|---|---|
| 批次载体 | `ForwardBatch`（扁平 GPU 张量，直接来自 `ScheduleBatch`） | `ModelInputForGPUWithSamplingMetadata`（`InputBatch` + `ModelInputForGPU`） |
| 执行封装 | `EagerRunner` + `DecodeCudaGraphRunner` + `PrefillCudaGraphRunner` 分派 | `model_execute`（eager/torch.compile）+ CUDA graph 一体 |
| 采样 | worker 内 `model_runner.sample()` 后入 `GenerationBatchResult` | `Sampler` 在 `sample_tokens` 阶段执行，输出 `SamplerOutput` |
| PP 中间态 | `PPProxyTensors`（纯张量 dict） | `IntermediateTensors` |
| 与调度器关系 | 调度器与模型执行同进程、双流重叠 | EngineCore 独立进程，`execute_model` 经 ZMQ 下发 |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
