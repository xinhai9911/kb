## Sampler 采样层与 Pooler 池化层

采样不在 `layers/` 目录下——v1 的 `Sampler` 位于 `vllm/v1/sample/sampler.py`；池化层在 `vllm/model_executor/layers/pooler/`。本文说明两者与 engine 采样/池化流程的衔接，以及词表并行 logits 链路。

### 词表并行嵌入与 logits 链路

`vocab_parallel_embedding.py`：

| 类 | 职责 |
|---|---|
| `UnquantizedEmbeddingMethod` | embedding 用 `F.embedding`；`tie_weights()` 让 lm_head 直接复用 embed 权重 |
| `VocabParallelEmbedding` | 词表维并行嵌入；vocab 先 `pad_vocab_size`（默认 64）再按 TP 切分 |
| `ParallelLMHead(VocabParallelEmbedding)` | LM head；可选 bias；`forward` 直接 `raise RuntimeError("LMHead's weights should be used in the sampler.")`——权重只在采样器侧使用 |

关键设计：**base 嵌入与 LoRA 新增嵌入分开 pad、分开切分**，TP 布局为 `base | base-padding | lora | lora-padding`。`VocabParallelEmbeddingShardIndices` 记录每 rank 的 org/added 起止索引；`forward` 在 TP>1 时用 `get_masked_input_and_mask`（torch.compile 融合）把本 rank 词表外的 token 掩掉，`embedding` 后 `masked_fill_(...,0)` 再 `tensor_model_parallel_all_reduce`。`get_sharded_to_full_mapping()` 提供 gathered logits 的 index→token_id 重排表，供采样后处理使用。

`logits_processor.py` 的 `LogitsProcessor` 承接 hidden_states→logits：

```
_apply_head(lm_head, hidden_states, embedding_bias)  # head_dtype 支持 fp32 out_dtype mm
  → 若 lm_head.tp_size>1: _gather_logits()          # platform.use_all_gather → all_gather / gather
  → logits[..., :org_vocab_size]                     # 截掉 vocab padding
  → soft_cap（Gemma2 的 tanh 软封顶）→ scale 缩放
```

`get_top_tokens()` 提供**免全 gather 的 vocab 并行 argmax**：本地 argmax → all-gather `(value, index)` 对 → 归约出全局 top token，通信量从 O(batch×vocab) 降到 O(batch×2×tp)。

### Sampler 契约（v1/sample/sampler.py）

`Sampler(nn.Module)`，构造参数 `logprobs_mode`（`raw_logprobs`/`raw_logits`/`processed_logprobs`/`processed_logits`）与 `use_fp64_gumbel`。`forward(logits, sampling_metadata, predict_bonus_token, logprobs_mode_override)` 步骤顺序：

1. 需要 logprobs 时先用**原始 logits** 算 `compute_logprobs`（`log_softmax` fp32），v0 用处理后 logits、v1 用原始 logits（源码注释明确注明差异）；
2. logits 转 fp32 → allowed-token 白名单 mask → bad words 排除（`apply_bad_words`）；
3. 非 argmax 不变式 logit processor（min_tokens、logit bias）→ 惩罚（repetition/frequency/presence，`apply_all_penalties`）；
4. `sample()`：greedy argmax 兜底 → `apply_temperature`（`temp<1e-5` 视为 greedy）→ argmax 不变式 processor（如 min_p）→ `TopKTopPSampler`（top_k/top_p + 随机采样，含 FP64 Gumbel 选项）；
5. `gather_logprobs` 收集 topk 与采样 token 的 logprobs/rank，产出 `SamplerOutput(sampled_token_ids=[num_requests,1], logprobs_tensors=LogprobsTensors)`。

`SamplingMetadata`（`v1/sample/metadata.py`）是采样参数载体的 dataclass：`temperature/all_greedy/all_random/top_p/top_k/generators/max_num_logprobs/no_penalties/prompt_token_ids/三类 penalties/output_token_ids/allowed_token_ids_mask/bad_words_token_ids/logitsprocs/spec_token_ids/thinking_budget_state_holder`。它由 `v1/worker/gpu_input_batch.py:943` 从每请求 `SamplingParams` 构造（与 05-sampling 的 `SamplingParams` 一一对应，`generators` 为请求级随机源）。

### 与 engine 采样流程衔接

```
v1/worker/gpu_model_runner.py:596  self.sampler = Sampler(logprobs_mode=self.model_config.logprobs_mode)
v1/worker/gpu_model_runner.py:3765 _sample():
    sampling_metadata = self.input_batch.sampling_metadata
    self.input_batch.update_async_output_token_ids()   # 异步调度下回填上一步 token
    return self.sampler(logits=logits, sampling_metadata=sampling_metadata)
    # 投机解码时改走 self.rejection_sampler(spec_decode_metadata, ...)（rejection_sampler.py 内部复用 Sampler）
```

`SamplerOutput` 沿 GPU 异步路径回传，由引擎侧 `LogprobsProcessor` 处理 topk 合并（注释说明最终 logprobs 数可能是 `max_num_logprobs+1`）。profile_run 阶段（`gpu_model_runner.py:6398`）用 dummy metadata 预热采样内核。

### Pooler 池化层（layers/pooler/）

抽象契约 `Pooler(nn.Module, ABC)`（`abstract.py`）：`get_supported_tasks()`、`get_pooling_updates(task)->PoolingParamsUpdate`、`forward(hidden_states, pooling_metadata)->PoolerOutput`。`PoolingParamsUpdate` 的 `requires_token_ids` 声明是否需要在 forward 时下发 prompt token ids。

`DispatchPooler`（`special.py`）按请求分组分发任务：
- `for_embedding(pooler_config)` → `{token_embed, embed}`
- `for_seq_cls(pooler_config, classifier=...)` → `{token_classify, classify}`
- forward 用 `groupby(pooling_metadata.tasks)` 分组，借助 `pooling_cursor.num_scheduled_tokens_cpu`（CPU 计数避免 GPU→CPU 同步）从 `hidden_states` 切出各组 token 段再交子池化器。

子池化器组件：

| 组件 | 说明 |
|---|---|
| `SequencePoolingMethod` | CLS（取 `first_token_indices_gpu`，不支持 partial prefill）、LAST（`last_token_indices_gpu`）、MEAN（`repeat_interleave` 分段求和，fp32） |
| `SequencePoolerHead` | `EmbeddingPoolerHead`（ST projector、matryoshka `dimensions` 截断、L2 normalize）、`ClassifierPoolerHead`（classifier、`logit_mean/sigma` 仿射校准、activation） |
| `PoolerActivation` | Identity / Normalize / Classify（softmax/sigmoid）/ MultiLabelClassify / Lambda；`get_act_fn` 按 HF config `problem_type` 选择 |
| 专用 | `IdentityPooler`（plugin）、`BOSEOSFilter`（剥首尾 BOS/EOS）、`BgeM3Pooler`（embed 与 token_classify 拼接，任务 `embed&token_classify`） |

模型侧装配在 `model_executor/models/transformers/pooling.py`：`EmbeddingMixin` 建 `DispatchPooler.for_embedding(pooler_config)`；`SequenceClassificationMixin` 在 meta 设备上实例化 `AutoModelForSequenceClassification` 提取 `classifier/score`（移除池化层、包一层 `ClassifierWithReshape` 补维度），再 `for_seq_cls`。engine 侧由 `gpu_model_runner.py:3548` 从 input_batch 取 `PoolingMetadata`、构建 cursor 后调用模型 pooler，输出 `PoolerOutput` 经 `EngineCoreOutputs.pooling_output` 回传前端。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
