## v1 内核非生成任务：Pooling / Embedding / 扩散（tti）执行链路

池化与 embedding 类模型（`runner_type == "pooling"`）不产出 token，而是对 hidden states 做池化聚合；扩散模型（dLLM）每个 denoising 步不采样 token。二者共享 `EngineCore.step` 的调度→执行骨架，但**跳过采样阶段**，输出走 `EngineCoreOutput.pooler_output` / diffusion 专用字段。本文聚焦 `vllm/v1/pool/` 组件契约及其在 step 链路中的分流。

### 文件布局（v1/pool/）

| 文件 | 内容 |
|---|---|
| `late_interaction.py` | late-interaction 打分：参数构建、MaxSim 批量计算、按 query_key 的引擎（DP）选择 |
| `late_interaction_runner.py` | worker 侧状态：query 嵌入缓存、query_uses 计数、池化输出后处理 |
| `metadata.py` | `PoolingMetadata`/`PoolingCursor`/`PoolingStates` 张量结构 |

### EngineCore 侧分流（engine/core.py）

- 启动时 `is_pooling_model = model_config.runner_type == "pooling"`。
- `step()` / `step_with_batch_queue()` 中 `if self.is_pooling_model or not model_executed:` → 不调 `sample_tokens`，`future = exec_future` 直通。
- `batch_queue` 入队元组仍为 `(future, scheduler_output, exec_future)`，但池化模型的 future 即模型执行结果。
- 调度侧 `num_sampled_tokens_per_step = 1 if not is_diffusion else 0`（`sched/scheduler.py`），扩散模型每步不预留采样 token 位。
- 扩散模型在 `check_for_draft_tokens` 中被视为需要取草稿/中间结果的对象（`use_spec_decode or is_diffusion`），`num_sampled_tokens_per_step=0` 对应其 denoising 步。

### 池化执行路径（worker 侧）

旧 runner（`v1/worker/gpu_model_runner.py`，`self.is_pooling_model` 分支）：

```
execute_model → 前向得 hidden_states → pooling 分支：
  pooling_metadata = input_batch.get_pooling_metadata()
  pooling_metadata.build_pooling_cursor(num_scheduled_tokens, seq_lens_cpu, query_start_loc_gpu)
  raw_pooler_output = model.pooler(hidden_states, pooling_metadata)
  finished_mask = [seq_len == prompt_len for ...]
  raw_pooler_output = late_interaction_runner.postprocess_pooler_output(...)
  → AsyncGPUPoolingModelRunnerOutput（CUDA stream 异步拷回 CPU）
```

- 新 runner（`v1/worker/gpu/model_runner.py`）使用 `PoolingRunner`（`v1/worker/gpu/pool/pooling_runner.py`），面向 `InputBatch` 持久化状态，逻辑同构。
- `finished_mask` 语义：只有 `seq_len == prompt_len`（prompt 全部处理完）的请求才产出最终池化结果；chunked prefill 的中间 chunk 返回 `[None]*num_reqs`，不误发中间结果。

### PoolingMetadata / PoolingCursor 契约（pool/metadata.py）

`PoolingMetadata`：`prompt_lens`（CPU）、`prompt_token_ids`（GPU）与 `prompt_token_ids_cpu`（`requires_token_ids` 任务用，如 token_classify）、`pooling_params`、`pooling_states`；`__post_init__` 要求**每个请求都显式设置 task**。

| 成员 | 说明 |
|---|---|
| `build_pooling_cursor(num_scheduled_tokens, seq_lens_cpu, ...)` | 由 `query_start_loc_gpu`（前缀和）定位每请求首/末 token 下标，构建 `PoolingCursor` |
| `PoolingCursor.first_token_indices_gpu` / `last_token_indices_gpu` | 池化聚合的起止 token 索引（GPU） |
| `PoolingCursor.is_finished()` | `prompt_lens == seq_lens`，即该请求已见全部 prompt token |
| `PoolingCursor.is_partial_prefill()` | 本步未覆盖整个 prompt（chunked） |
| `PoolingStates` | 每请求状态：`hidden_states_cache`（chunked prefill + ALL pooling 时缓存 hidden states） |

支持任务集合 `_SUPPORTED_TASKS = {"embed", "classify", "token_embed", "token_classify", "embed&token_classify"}`；`PoolingTask` 为 `vllm/tasks.py` 中的枚举，模型 `pooler.get_supported_tasks()` 与之求交集，无交集时提示 `VLLM_USE_V2_MODEL_RUNNER=0` 回退。`add_request` 时 `model.pooler.get_pooling_updates(task).apply(pooling_params)` 预配置任务专属参数。

### LateInteractionRunner（late_interaction_runner.py）

worker 侧持 `_query_cache: dict[query_key, Tensor]`、`_query_uses`、`_doc_query_keys`，服务于 ColBERT 类「query 嵌入缓存、doc 后打分」的 late-interaction 检索：

| 方法 | 契约 |
|---|---|
| `register_request(req_id, pooling_params)` | `SCORE_DOC` 模式登记 req→query_key 映射 |
| `postprocess_pooler_output(raw, pooling_params, req_ids, finished_mask)` | 对 finished 请求按模式处理：`CACHE_QUERY` → `output.clone()` 存缓存、输出置 0 标量；`SCORE_DOC` → 用缓存 query 调 `compute_maxsim_score_batched` 算 MaxSim 分数替换输出 |
| `on_requests_finished(req_ids)` | 请求结束释放 query_uses；计数归零时清缓存 |
| `clear()` | 清空全部状态（reset） |

- `compute_maxsim_score_batched(q_embs, d_embs, max_batch_size=64, max_score_matrix_elements=64M)`：mini-batch 内把 query/doc 填充到统一长度，`torch.bmm` 计算 token 级内积矩阵，`amax(dim=-1)` 取每 query token 的最佳 doc token 分并求和；分块条件 `batch*max_q*max_d > 64M` 防超大分配。
- `late_interaction.py::get_late_interaction_engine_index`：DP>1 时按 `zlib.crc32(query_key) % num_engines` 把同一 query_key 的请求钉到同一引擎（query 嵌入缓存是进程本地的）。
- `build_late_interaction_query_params` / `build_late_interaction_doc_params`：为请求构造 `LateInteractionParams(mode=..., query_key=..., query_uses=...)`。

### 输出与前端衔接

- `ModelRunnerOutput.pooler_output`（`PoolerOutput`）为 `list[torch.Tensor | None]`（CPU，`_copy_pooler_output_to_cpu` 按 `finished_mask` 过滤非空行）。
- `scheduler.update_from_output` 读取 `pooler_output` 按 req 配入 `EngineCoreOutput.pooling_output`，前端 `OutputProcessor` 组装为 `RequestOutput.pooling` / 聊天完成。
- 池化请求在调度器内与生成请求同队列，占用相同 `max_num_seqs`/token 预算；`get_computed_blocks` 在前缀缓存命中时对「all pooling」请求跳过 KV 读（`prefix_cache_lookup_enabled` 返回 False，因无需重算末 token logits）。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
