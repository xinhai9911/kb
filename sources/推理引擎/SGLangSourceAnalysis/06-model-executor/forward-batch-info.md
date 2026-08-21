## ForwardBatch 前向批次数据结构

`ForwardBatch`（`sglang/srt/model_executor/forward_batch_info.py:378`）承载一次 forward 的全部低层张量输入。模块 docstring 明确其数据流：**`ScheduleBatch`（调度器管理、多数在 CPU）→ `ForwardBatch`（ModelRunner 管理、多数为 GPU 张量），由 `ForwardBatch.init_new` 直接从 `ScheduleBatch` 构造**。

```text
ScheduleBatch (managers/schedule_batch.py)
  ├─ reqs / seq_lens / input_ids / req_pool_indices / out_cache_loc   # 核心借用张量
  ├─ sampling_info / spec_info / multimodal_inputs / 各类 flags
  └─ ForwardBatch.init_new(batch, model_runner, ...)
       ├─ 派生 positions / extend_* 张量（forward 流上构造）
       └─ DP/MLP-sync 填充、attn-TP 归一化 → 交给 model_runner.forward
```

### ForwardMode 枚举

`forward_batch_info.py:100`，IntEnum，决定执行路径：

| 值 | 含义 | 典型执行路径 |
|---|---|---|
| `EXTEND` | 扩展（prefill），前缀 KV 已就绪 | Eager/Preifll CUDA graph |
| `DECODE` | 每步解码一个 token | Decode CUDA graph 或 Eager |
| `MIXED` | chunked prefill 时同批混有 EXTEND 与 DECODE | Eager |
| `IDLE` | 无序列（DP attention 时空闲 rank） | 空 forward |
| `TARGET_VERIFY` | 投机解码：目标模型验证批 | 同 decode graph |
| `DRAFT_EXTEND_V2` | 投机解码：draft 模型扩展批 | Eager |
| `PREBUILT` | 解耦 decode worker：KV 已就绪待解码 | 专用事件循环 |
| `SPLIT_PREFILL` | PD 多路复用下的按层拆分 prefill | `forward_split_prefill` |
| `DLLM_EXTEND` | dLLM（离散扩散 LLM）扩展 | dLLM 算法 |

谓词方法（`is_extend`/`is_decode`/`is_cuda_graph`/`is_split_prefill` 等）驱动 `_forward_raw` 的分派与 runner 选择。

### ForwardBatch 核心字段

`init_new` 传参分组（`forward_batch_info.py:761-807`）可作为字段权威清单：

| 分组 | 字段 | 说明 |
|---|---|---|
| 必选核心 | `forward_mode`/`batch_size`/`input_ids`/`req_pool_indices`/`seq_lens`/`out_cache_loc`/`seq_lens_sum` | 自 `ScheduleBatch` 借用（引用别名） |
| 借用张量 | `orig_seq_lens`、`mamba_track_indices/mask/seqlens`、`mamba_cow_*/mamba_clear_indices`、`input_embeds`、`replace_embeds`+`replace_positions`（token embedding 覆盖）、`token_type_ids`、`encoder_lens`/`encoder_out_cache_loc` | 多模态/encoder-decoder/SSM 用 |
| 标量配置 | `return_logprob`、`is_prefill_only`、`spec_algorithm`、`dimensions`、`return_pooled_hidden_states` | 采样与池化开关 |
| DP attention | `is_extend_in_batch`、`can_run_dp_cuda_graph`、`global_forward_mode`、`global_num_tokens_cpu/gpu`、`dp_padding_mode`、`global_dp_buffer_len` | 见下方 padding 说明 |
| 宿主侧 | `seq_lens_cpu`、`top_logprobs_nums`、`token_ids_logprobs`、`mm_inputs`（`List[MultimodalInputs]`）、`lora_ids`、`rids` | 日志概率与多模态 |
| 复合对象 | `sampling_info`（`SamplingBatchInfo`）、`spec_info`（`SpecInput`） | 自带设备张量 |
| forward 派生 | `positions`、`extend_num_tokens`/`extend_seq_lens`/`extend_prefix_lens`/`extend_start_loc`/`extend_seq_lens_cpu` 等 | `init_new` 在 forward 流上计算 |
| 运行期填充 | `num_token_non_padded`（scalar tensor + cpu）、`dp_local_start_pos`/`dp_local_num_tokens`、`attn_cp_metadata`、`attn_dcp_metadata`、`dcp_kv_mask`、`mrope_positions`（Qwen2-VL）、`ngram_embedding_info` | 后端/注意力规划期写入 |

多模态输入以 `mm_inputs: List[MultimodalInputs]` 携带（`mm_input_embeds` 在 forward 前由模型层填充）。LoRA 由 `lora_manager.prepare_lora_batch(ret)` 处理。

### init_new 流程要点

`ForwardBatch.init_new`（`forward_batch_info.py:705`）按序：

1. 解析 `capture_hidden_mode`（`CaptureHiddenMode`：`NULL`/`LAST`/`FULL`，`forward_batch_info.py:201`），与 server 配置、`spec_info` 取 max。
2. 从 `ScheduleBatch` 拷入核心字段（`ret = cls(...)`）。
3. 把 `sampling_info.grammars` 镜像到 batch（`batch.has_grammar` 时）。
4. 计算 positions：decode/target_verify 用 `clamp_position(batch.seq_lens)`（CUDA 内核版，`forward_batch_info.py:1786`）；extend 用 `compute_position`（Triton/torch 两实现，`forward_batch_info.py:1746`）生成 `positions` 与 `extend_start_loc`。
5. dLLM 或 spec 时用 `spec_info.positions` 覆盖；Qwen2-VL 走 `mrope_positions` 计算。
6. `init_mlp_sync_metadata`（`forward_batch_info.py:672`）：有 DP attention 时从 `batch.global_num_tokens` 派生 `global_num_tokens_cpu/gpu`（spec 场景经 `spec_scale_global_num_tokens` 缩放）。
7. LoRA 批准备；DCP（decode context parallel）时生成 `dcp_kv_mask`。
8. `forward_metadata_ready` 标记：多步 draft / 预规划场景可调用 `mark_forward_metadata_ready` 跳过 forward 内的注意力元数据初始化（`forward_batch_info.py:607`），防止重复规划破坏预规划状态。

### DP attention 的 MLP-sync 填充

`prepare_mlp_sync_batch`（`forward_batch_info.py:1272`）把各 DP rank 的 token 数对齐以匹配通信几何：

- 每个 `global_num_tokens[i]` 按 `attn_tp_size` 与 CP 对齐大小 `ceil_align`；`DpPaddingMode`（`is_max_len` / `SUM_LEN`）决定按全局 max 填充还是按本 rank 求和。
- prefill breakable CUDA graph 下强制 `MAX_LEN`（每 rank 相同捕获形状）；空闲 rank 会「伪造」一个覆盖 `num_tokens` 的 dummy 请求（hybrid-SSM 家族强制走此路径）。
- 前向结束后 `post_forward_mlp_sync_batch`（`forward_batch_info.py:1594`）把 `positions`/`seq_lens`/`logits` 等按原始形状切片还原，并恢复 `_original_forward_mode`/`_original_batch_size`。

### PPProxyTensors

`forward_batch_info.py:1716`：PP 下非末 stage 的 forward 输出载体，仅一个 `Dict[str, torch.Tensor]` 字段，支持下标/切片访问。仿 vLLM `IntermediateTensors` 设计，draft 注释注明手动定义 `__init__` 以便 Dynamo 识别来源文件。`PPProxyTensors` 与 `PPBatchMetadata`（`scheduler_pp_mixin.py:63`）配合完成 stage 间 hidden state 传递。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
