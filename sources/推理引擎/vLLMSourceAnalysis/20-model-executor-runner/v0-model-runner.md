## v0 ModelRunner 与 v1 GPUModelRunner 对照

> **历史来源**：v0 `ModelRunner` 位于 `vllm/worker/model_runner.py`（约 2045 行，已随 `[V0 Deprecation] Remove V0 core (#25321)` 删除），本文基于共存期提交 `a4528f0cac`。v1 `GPUModelRunner` 位于 `vllm/v1/worker/gpu_model_runner.py`（当前 checkout，约 8000 行，详见 [15-v1-worker](../15-v1-worker/model-runner.md)）；当前 v0 兼容层现状（`vllm/engine/` shim）见 [24-v0-engine-legacy](../24-v0-engine-legacy/v0-engine-legacy.md)。

### v0 类层次（`vllm/worker/model_runner.py`）

| 类 | 行 | 职责 |
|---|---|---|
| `ModelInputForGPU` | :78 | 模型输入容器：`input_tokens`/`input_positions`/`seq_lens`/`attn_metadata` 等，支持 `as_broadcastable_tensor_dict`/`from_broadcasted_tensor_dict`（TP 组内广播） |
| `ModelInputForGPUWithSamplingMetadata` | :142 | 追加 `sampling_metadata`/`is_prompt`/`virtual_engine` 字段 |
| `ModelInputForGPUBuilder` | :181 | 从 `SequenceGroupMetadata` 构建输入：`prepare`/`add_seq_group`/`build`(:801)；`_use_captured_graph`(:743)/`_get_cuda_graph_pad_size`(:753) 决定 CUDA graph 填充 |
| `GPUModelRunnerBase` | :968 | 通用执行主体：持模型、`Sampler`、`graph_runners`；`_prepare_model_input_tensors`(:1161)、`capture_model`(:1371)、`profile_run` |
| `ModelRunner` | :1565 | v0 GPU runner 本体（「GPU model runner with sampling step」） |
| `CUDAGraphRunner` | :1888 | 单 batch 尺寸的 CUDA graph 包装，`capture`(:1908)/`forward`(:1991) |

### v0 execute_model 全流程（model_runner.py:1622）

```python
@torch.inference_mode()
def execute_model(self, model_input, kv_caches, intermediate_tensors=None,
                  num_steps=1, **kwargs):
    # 1) LoRA 激活
    if self.lora_config:
        self.set_active_loras(model_input.lora_requests, model_input.lora_mapping)
    self.attn_state.begin_forward(model_input)

    # 2) 选择可执行对象：decode + CUDA graph → graph_runners[virtual_engine][(batch, use_embeds)]
    prefill_meta = model_input.attn_metadata.prefill_metadata
    decode_meta = model_input.attn_metadata.decode_metadata
    if prefill_meta is None and decode_meta.use_cuda_graph:
        model_executable = self.graph_runners[virtual_engine][(graph_batch_size, use_inputs_embeds)]
    else:
        model_executable = self.model

    # 3) KV 传输 recv（阻塞，可 bypass 模型 forward，如 disagg prefill）
    if self.need_recv_kv(model_input, kv_caches):
        hidden_or_intermediate_states, bypass_model_exec, model_input = \
            get_kv_transfer_group().recv_kv_caches_and_hidden_states(...)

    # 4) 模型 forward
    with set_forward_context(model_input.attn_metadata, self.vllm_config, virtual_engine):
        hidden_or_intermediate_states = model_executable(
            input_ids=model_input.input_tokens, inputs_embeds=model_input.inputs_embeds,
            positions=model_input.input_positions, intermediate_tensors=intermediate_tensors,
            **MultiModalKwargs.as_kwargs(multi_modal_kwargs, device=self.device),
            **seqlen_agnostic_kwargs, **model_kwargs)

    # 5) KV 传输 send（非阻塞）
    if self.need_send_kv(model_input, kv_caches):
        get_kv_transfer_group().send_kv_caches_and_hidden_states(...)

    # 6) 非末 PP rank：直接返回 IntermediateTensors（由 worker 层 send_tensor_dict 传给下段）
    if not get_pp_group().is_last_rank:
        return hidden_or_intermediate_states

    # 7) 末 PP rank：logits → 采样（单段式，与 v1 两段式关键差异）
    logits = self.model.compute_logits(hidden_or_intermediate_states,
                                       model_input.sampling_metadata)
    if self.is_driver_worker:
        if model_input.async_callback is not None:
            model_input.async_callback()          # async output processing 回调
        output = self.sampler(logits=logits, sampling_metadata=model_input.sampling_metadata)

    # 8) inputs_embeds（pooling/embedding 模型）：广播 sampled_token_ids 再取 embedding
    # 9) return_hidden_states 时回填 hidden_states / prefill_hidden_states
    return [output]
```

要点：
- **单段式**：`execute_model` 内完成 forward + 采样，直接返回 `List[SamplerOutput]`；v1 拆成 `execute_model`（返回 None 存 `ExecuteModelState`）→ 下一跳 `sample_tokens(grammar_output)`。
- **采样元数据在引擎侧构建**：`prepare_model_input`（:1584）先 `_prepare_model_input_tensors`，末 PP rank 再 `SamplingMetadata.prepare(seq_group_metadata_list, seq_lens, query_lens, generators, sampling_metadata_cache)`；v1 改由 `InputBatch` 持久化 + 每 step 增量刷新。
- **CUDA graph**：`graph_runners[virtual_engine][(graph_batch_size, use_inputs_embeds)]` 按 batch 尺寸 + 是否用 inputs_embeds 双重索引，仅 decode 阶段启用。
- **PP**：非末 rank 返回 `IntermediateTensors`，由 `LocalOrDistributedWorkerBase.execute_model`（worker_base.py:385）负责 `recv_tensor_dict`（非首 rank）/`send_tensor_dict`（非末 rank），并注入 `model_execute_time` 观测字段。
- **KV transfer / disagg**：`need_recv_kv`/`need_send_kv`（:1835/:1860）支持远端 KV 接收（可完全跳过 forward）与发送。

### 与 v1 GPUModelRunner 差异

| 维度 | v0 ModelRunner | v1 GPUModelRunner |
|---|---|---|
| 位置 | `vllm/worker/model_runner.py` | `vllm/v1/worker/gpu_model_runner.py:501` |
| 执行阶段 | forward + 采样一步完成 | 两段式：`execute_model` 只 forward 并暂存状态，`sample_tokens` 后采样 |
| 输入载体 | `ModelInputForGPU(WithSamplingMetadata)` 每步重建 | `InputBatch`（`gpu_input_batch.py:92`）跨 step 持久化，预分配张量增量更新 |
| 采样元数据 | `SamplingMetadata.prepare`（引擎侧按需建） | `_make_sampling_metadata`（:860）张量化到 InputBatch |
| 结构化输出 | `_build_logits_processors` 编译成 LogitsProcessor（见下） | `sample_tokens` 内 `apply_grammar_bitmask(grammar_output)` 屏蔽 logits |
| 驱动方式 | Executor 每步把 `ExecuteModelRequest` 广播给 worker | EngineCore 直发 `SchedulerOutput`，`non_block` 重叠 |
| 返回 | `List[SamplerOutput]`（含 hidden_states 可选） | `ModelRunnerOutput` / `AsyncModelRunnerOutput` |
| 采样器 | `Sampler`（`model_executor/layers/sampler.py`） | v1 `Sampler`（`vllm/v1/sampler.py`）+ spec 场景 `RejectionSampler` |

### 附：guided decoding 在 v0 侧的接入

v0 通过「LogitsProcessor」接入，目录 `vllm/model_executor/guided_decoding/`：

| 文件 | 内容 |
|---|---|
| `__init__.py` | `get_local_guided_decoding_logits_processor` / `get_guided_decoding_logits_processor`（async，线程池跑 FSM 编译）；`maybe_backend_fallback` 做后端回退 |
| `outlines_decoding.py` | `JSONLogitsProcessor`/`RegexLogitsProcessor`（`outlines_logits_processors.py`），`GuidedDecodingMode` = JSON/REGEX/CHOICE；grammar 已移除支持 |
| `xgrammar_decoding.py` | `get_local_xgrammar_guided_decoding_logits_processor`，XGrammar 编译 grammar → 每步 `logits_mask` |
| `lm_format_enforcer_decoding.py` / `guidance_decoding.py` | lm-format-enforcer / guidance 后端 |

接入点：`LLMEngine._build_logits_processors`（`vllm/engine/llm_engine.py:1983`，随 `[V0 Deprecation] Guided decoding (#21347)` 删除）——请求入队时把 `sampling_params.guided_decoding` 编译为 logits processor 追加进 `logits_processors`，并清空原字段；后端缺省取 `decoding_config.backend`，`"auto"` 在 v0 等价于 `"xgrammar"`。生效位置在 `Sampler` 的 logits 处理链中（与温度/top-k 等共用同一批 `LogitsProcessor`），而非 v1 那样的 logits 位掩码。reasoning 后端可选地包一层 `ReasoningParser`。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
