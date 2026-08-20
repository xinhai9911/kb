## v0 采样/生成循环：step 直到完成

> **历史来源**：vLLM 该仓库历史中不存在独立的 `llm_generator.py`。v0 的「采样循环 / 输出生成」由 `LLMEngine.step()`（`vllm/engine/llm_engine.py`）驱动：LLM 端在 `while` 循环里反复调用 `step()`，直至 `has_unfinished_requests()` 为假。本文基于 v0 共存期提交 `a4528f0cac`（`step()` 在 `llm_engine.py:1194`）；该文件当前已退化为 v1 别名 shim，见 [24-v0-engine-legacy](../24-v0-engine-legacy/v0-engine-legacy.md)。

### 外层驱动（`vllm/entrypoints/llm.py`）

```python
# LLM._run_engine（llm.py:1673）
while self.llm_engine.has_unfinished_requests():
    step_outputs = self.llm_engine.step()     # 每步产出新生成的 RequestOutput
```

- 离线 `LLM.generate`：`_run_engine` 同步循环收集 `step_outputs`，按 `request_id` 聚合为 `RequestOutput` 列表返回。
- 在线 `AsyncLLMEngine`：由各请求的 `request_streaming` / output 队列驱动，每轮循环执行 `engine.step()` 并分发 `RequestOutput` 到对应请求的流式迭代器（async 输出处理下 `SamplerOutput` 可异步消费）。

### LLMEngine.step() 单步流程（llm_engine.py:1194）

```
1) 取缓存：cached_scheduler_outputs[virtual_engine]（multi-step 复用上一轮 schedule）
2) 调度：若无剩余多步且非 skip_scheduling_next_step
     → scheduler[virtual_engine].schedule()
     → seq_group_metadata_list / scheduler_outputs / allow_async_output_proc
     → finished_requests_ids（清理 seq_id_to_seq_group）
     → multi-step 且 num_lookahead_slots>0 时缓存 scheduler 输出
3) 组 ExecuteModelRequest：
     seq_group_metadata_list / blocks_to_swap_in/out / blocks_to_copy /
     num_lookahead_slots / running_queue_size / finished_requests_ids /
     last_sampled_token_ids（PP 复用上一步采样结果）
     allow_async_output_proc 时挂 async_callback
4) outputs = self.model_executor.execute_model(execute_model_req)
     （异常 InputProcessingError → _abort_and_cache_schedule + re-raise）
5) 收尾：multi-step 时 seq_group.finish_step()；
   ctx.append_output()（把 SamplerOutput 按 seq_group 暂存到 output_queue）
   allow_async_output_proc=False → _process_model_outputs(ctx)（同步路径）
6) 全部完成 → stop_remote_worker_execution_loop()，解除远端 worker 忙循环
7) 返回 ctx.request_outputs
```

### 输出产生（_process_model_outputs）

- `SchedulerOutputState`/`SchedulerContext`（`llm_engine.py:72/95`）按 virtual engine 缓存 `seq_group_metadata_list`、`scheduler_outputs`，`output_queue` 攒批；`append_output`（:107）按 is_async 选择同步/异步后处理。
- `_process_model_outputs`（:913）把 `SamplerOutput` 按 `SequenceGroupOutput` 逐条 `update` 到 `SequenceGroup`（`seq.logprobs`、`output_token`、`finish_reason` 等），并 `free_finished_seq_groups`；`OutputData`（:80，NamedTuple）记录 `outputs`/`seq_group_metadata_list`/`is_async` 等供调度器 `free_finished_seq_groups` 使用。
- 判定是否结束：`has_unfinished_requests()`（:838）即 `any(scheduler.has_unfinished_seqs() for scheduler in self.scheduler)`；`get_num_unfinished_requests()`（:833）累加各调度器的 `get_num_unfinished_seq_groups()`。
- 采样本身发生在 `ModelRunner.execute_model` 的 `Sampler`（见 [v0-model-runner.md](v0-model-runner.md)），`LLMEngine` 只做「调度 → 执行 → 输出回写」的编排。

### multi-step 与异步输出处理

- `is_multi_step`：`num_steps > 1` 时 `_cache_scheduler_outputs_for_multi_step` 缓存 schedule，`_has_remaining_steps`（:1456）判断是否跳过下一轮调度；`cached_scheduler_outputs` 每轮只更新 `scheduler_outputs`/`seq_group_metadata_list`/`allow_async_output_proc`。`last_sampled_token_ids` 经 `_get_last_sampled_token_ids`（:1501）透传给非末 PP stage 做原地 prepare。
- `allow_async_output_proc`：scheduler 允许时把 `ExecuteModelRequest.async_callback` 注入，`ModelRunner` 采样后回调，输出后处理与调度重叠；一旦序列组不满足条件（如 beam search）回退同步路径，先 drain `output_queue` 再继续。

### 与 v1 EngineCore.step 对照

| 维度 | v0 LLMEngine.step | v1 EngineCore.step（当前） |
|---|---|---|
| 调度→执行 | `scheduler.schedule()` → `model_executor.execute_model(req)` 同步返回 | `scheduler.schedule()` → `model_executor.execute_model(non_block=True)` → 可延迟 `sample_tokens(grammar)` → `scheduler.update_from_output()` |
| 输出载体 | `RequestOutput`/`PoolingRequestOutput`（引擎进程内聚合） | `EngineCoreOutputs`（msgpack 下发前端，`OutputProcessor` 转 `RequestOutput`） |
| 重叠 | 单 virtual engine + async_callback 重叠输出后处理 | `batch_queue`（`max_concurrent_batches>1`）让调度与模型执行跨步重叠 |
| 空闲停止 | `stop_remote_worker_execution_loop()`（worker 忙循环退出） | busy loop 轮询 input_queue，无工作时阻塞；abort 走独立 `aborts_queue` |
| 采样位置 | `ModelRunner` 单段采样，`Sampler` 输出 `List[SamplerOutput]` | `GPUModelRunner.sample_tokens` 两段式（详见 [15-v1-worker](../15-v1-worker/model-runner.md)） |
| 结构化输出 | 请求入队时编译成 LogitsProcessor | 每步 `apply_grammar_bitmask(grammar_output, logits)` |

v1 详细循环（`EngineCoreProc.run_busy_loop` 的 `_process_engine_step`、batch queue 语义）见 [02-engine-core](../02-engine-core/engine-overview.md)。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
