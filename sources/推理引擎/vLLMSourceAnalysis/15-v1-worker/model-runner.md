## v1 ModelRunner：捕获输入 → forward → 采样 → 输出

`GPUModelRunner`（`vllm/v1/worker/gpu_model_runner.py`，约 8000 行）是 v1 执行核心：把 `SchedulerOutput` 转成 GPU 张量、跑模型 forward、采样并产出 `ModelRunnerOutput`。`CPUModelRunner`/`XPUModelRunner` 继承它；新架构下还有 `vllm/v1/worker/gpu/model_runner.py` 的 `GPUModelRunner`（V2，`use_v2_model_runner=True` 时启用）。

### 核心状态与关键类

| 类/对象 | 文件 | 职责 |
|---|---|---|
| `GPUModelRunner` | `gpu_model_runner.py:501` | 执行主体；持模型、采样器、drafter、InputBatch |
| `ExecuteModelState`（NamedTuple） | `gpu_model_runner.py:485` | execute_model 与 sample_tokens 之间的临时状态（logits、spec 元数据、hidden_states 等） |
| `InputBatch` | `gpu_input_batch.py:92` | 持久化 batch：预分配 GPU/CPU 张量 + numpy 视图，跨 step 复用 |
| `CachedRequestState` | `gpu_input_batch.py:35` | 请求持久状态：`prompt_token_ids`/`block_ids`/`num_computed_tokens`/`sampling_params`/`generator`/`output_token_ids` |
| `Sampler` | `vllm/v1/sampler.py` | 单步采样（logits→token） |
| `RejectionSampler` | `vllm/v1/worker/gpu/spec_decode/rejection_sampler.py` | spec decode 时验收 draft tokens |
| `ModelRunnerOutput` | `vllm/v1/outputs.py:310` | 输出载体（`sampled_token_ids`/`logprobs`/`pooler_output`/`cudagraph_stats` 等） |
| `AsyncModelRunnerOutput` | `vllm/v1/outputs.py:403` | async 调度下 GPU→CPU 拷贝的异步封装，`get_output()` 阻塞取结果 |

### execute_model 流程（gpu_model_runner.py:4294）

```
1) 守卫：execute_model_state 非空说明上轮 sample_tokens 未调用 → 抛错
2) ngram_gpu：copy scheduler_output（避免污染引擎进程侧对象）
3) kv_transfer：handle_preemptions；ec_transfer 分支只跑 encoder
4) 无 token → 返回 EMPTY_MODEL_RUNNER_OUTPUT
5) _update_states()：收尾上轮、增删请求、同步 block_table/零块
6) _prepare_inputs()：拼 input_ids/positions、logits_indices、spec_decode_metadata
7) _determine_batch_execution_and_padding()：定 cudagraph_mode/batch_desc/是否 ubatch
8) _get_slot_mappings() + _build_attention_metadata()：KV 槽位与注意力元数据
9) _preprocess()：产出 input_ids/inputs_embeds/positions/intermediate_tensors/model_kwargs
10) set_forward_context() + _model_forward()：CUDA graph 下跑模型 forward → hidden_states
11) postprocess：hidden_states[logits_indices] → model.compute_logits
12) 存 ExecuteModelState，返回 None（采样延后）
```

关键点：
- **两段式执行**：`execute_model` 返回 `None`（而非输出），由 EngineCore 下一跳调 `sample_tokens(grammar_output)`。这让采样与模型执行解耦，配合 async scheduling 重叠调度与执行。
- **InputBatch 持久化**：`token_ids_cpu`（`max_num_reqs×max_model_len` int32 numpy）、`num_computed_tokens_cpu`、`block_table` 等常驻内存，每 step 只增量更新，`_prepare_inputs` 用 `torch.index_select` 高效取 token ids。
- **CUDA graph**：`_determine_batch_execution_and_padding` 依据 batch 形状选 `CUDAGraphMode`（NONE/PIECEWISE/FULL），`set_forward_context` 带 `batch_descriptor`、`ubatch_slices` 进入图执行；`pad_attn` 时按 padded 维建 slot mapping。
- **PP**：非末 rank 返回 `IntermediateTensors`，由 Worker 层 isend 后段；末 rank 才算 logits。
- **结构化输出**：`sample_tokens` 先 `apply_grammar_bitmask(scheduler_output, grammar_output, input_batch, logits)` 再采样。

### sample_tokens 流程（gpu_model_runner.py:4673）

```
1) 解包并清空 ExecuteModelState
2) grammar_output → apply_grammar_bitmask
3) _sample(logits, spec_decode_metadata)：普通路径走 sampler；spec 路径走 rejection_sampler
4) _update_states_after_model_execute()：把采样结果回写 input_batch/请求状态
5) spec decode：propose_draft_token_ids() → drafter.propose → _copy_draft_token_ids_to_cpu
6) _bookkeeping_sync()：产出 req_ids/sampled_token_ids/logprobs/prompt_logprobs → ModelRunnerOutput
```

`_sample`（:3765）在 spec_decode_metadata 为空时直接调 `self.sampler(logits, sampling_metadata)`；否则取 `_draft_probs` 后走 `rejection_sampler(spec_decode_metadata, draft_probs, logits, sampling_metadata)`。

### InputBatch 主要字段（gpu_input_batch.py:93）

| 字段 | 形状 | 说明 |
|---|---|---|
| `token_ids_cpu` | `(max_num_reqs, max_model_len)` int32 | 每请求完整 token 序列（CPU） |
| `num_computed_tokens_cpu` | `(max_num_reqs,)` | 已计算 token 数，决定 position 起点 |
| `block_table`（`MultiGroupBlockTable`） | 多 KV group | 物理块表 → slot mapping |
| `sampling_metadata` | — | `_make_sampling_metadata`（:860）构造，随 batch 变化重建 |
| `temperature`/`top_p`/`top_k`/`generators` | `(max_num_reqs,)` | 采样参数张量化 |
| `req_prompt_embeds` | dict | prompt embeddings（避免大张量预分配） |

`add_request`（:350）/`remove_request`（:530）/`condense`（:708，压缩空槽）维护持久 batch；`refresh_metadata`（:840）在请求集变化后重建采样元数据。

### V2 ModelRunner（vllm/v1/worker/gpu/model_runner.py）

- `GPUModelRunner(LoRAModelRunnerMixin)`，`execute_model`（:1410）同样两段式，但用 `prepare_inputs`/`prepare_attn`/`sample`/`postprocess_sampled` 拆得更细，模型执行更依赖 JIT/Triton。
- Worker 侧 `use_v2_model_runner` 开关选择；pooling 模型在 `execute_model` 返回 None 时由 Worker 补调 `model_runner.pool()`。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
