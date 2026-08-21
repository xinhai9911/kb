## SamplingBatchInfo 批量张量化与参数流转

本文承接 [sampling.md](sampling.md)。前文讲 `SamplingParams` 单请求参数模型，本文讲 `SamplingBatchInfo`（`srt/sampling/sampling_batch_info.py`）如何把整批请求的采样参数组织成 GPU 张量，以及参数从请求到 `Sampler` 的完整流转链路。

### 字段总览：dataclass 张量化结构

`SamplingBatchInfo` 是 `@dataclasses.dataclass`（`sampling_batch_info.py:28`）。核心是 4 个「长度 = 批大小」的一维张量，加上若干聚合布尔标志与可选组件：

| 字段 | 类型 | 说明 |
|---|---|---|
| `temperatures` | `torch.Tensor` | float，形状 `(bs, 1)`，采样温度 |
| `top_ps` | `torch.Tensor` | float `(bs,)`，核采样阈值 |
| `top_ks` | `torch.Tensor` | int32 `(bs,)`，top-k 值 |
| `min_ps` | `torch.Tensor` | float `(bs,)`，min-p 阈值 |
| `is_all_greedy` / `is_any_greedy` | `bool` | 全部/存在 `top_k <= 1` 的请求 |
| `need_top_p_sampling` / `need_top_k_sampling` / `need_min_p_sampling` | `bool` | 任一请求需要对应采样（`sampling_batch_info.py:42-48`） |
| `grammars` / `grammar_mask` | `Optional[...]` | 文法约束（结构化输出）的掩码 |
| `penalizer_orchestrator` | `Optional[BatchedPenalizerOrchestrator]` | 四类惩罚器的批量化编排 |
| `acc_additive_penalties` / `acc_scaling_penalties` | `Optional[torch.Tensor]` | 预累积的加性/缩放惩罚（overlap 模式用） |
| `custom_logit_processor` / `custom_params` / `has_custom_logit_processor` | 混合 | 自定义 logit processor 及其按请求的 bool 掩码 |
| `sampling_seed` | `Optional[torch.Tensor]` | int64，仅确定性推理启用时非 None |
| `logit_bias` | `Optional[torch.Tensor]` | `(bs, vocab_size)` 稀疏偏置张量 |
| `return_sampling_masks` / `sampling_mask_max_top_k` | `List[bool]` / `int` | 稀疏采样掩码返回 |
| `device` | `str` | 默认 `"cuda"` |

### from_schedule_batch：单请求参数 → GPU 张量

工厂方法 `from_schedule_batch(batch, vocab_size)`（`sampling_batch_info.py:87`）是唯一入口，从 `batch.reqs` 逐请求读取 `r.sampling_params`，主机侧组张量后 `pin_memory` + `non_blocking=True` 异步拷贝到 `batch.device`：

| 输出字段 | 输入来源 | dtype | 特殊处理 |
|---|---|---|---|
| `temperatures` | `sampling_params.temperature` | float | `.view(-1, 1)`（`sampling_batch_info.py:100`） |
| `top_ps` | `sampling_params.top_p` | float | 直接组张量 |
| `top_ks` | `sampling_params.top_k` | int32 | 直接组张量 |
| `min_ps` | `sampling_params.min_p` | float | 直接组张量 |
| `sampling_seed` | `sampling_params.sampling_seed` | int64 | `None` 统一填 `42`；仅 `get_exec().deterministic.enable_deterministic_inference` 时生成（`sampling_batch_info.py:88,117-132`） |
| `logit_bias` | `sampling_params.logit_bias` dict | float | 任一请求非 None 时建 `zeros(bs, vocab_size)`，按 `logit_bias[i, int(key)] = value` 稀疏填充（`sampling_batch_info.py:134-140`） |

聚合标志在同一方法内由生成器推导（`sampling_batch_info.py:204-208`）：

- `is_all_greedy = all(top_k <= 1)`；`is_any_greedy = any(top_k <= 1)`
- `need_top_p_sampling = any(top_p != 1.0)`；`need_top_k_sampling = any(top_k != TOP_K_ALL)`；`need_min_p_sampling = any(min_p > 0)`

**两个重组件**：

1. **自定义 logit processor 合并**（`sampling_batch_info.py:153-178`）：仅在 `get_exec().features.enable_custom_logit_processor` 且存在 `req.custom_logit_processor` 时启用（先查开关再查请求，短路）。同类型 processor 按 `hash(processor_str)` 合并为一个 dict：值为 `(反序列化的 CustomLogitProcessor, 该请求的 bool 掩码张量)`，掩码用 `scatter_` 置 True。`custom_params` 按请求顺序收集。
2. **惩罚器编排**（`sampling_batch_info.py:187-196`）：`BatchedPenalizerOrchestrator` 聚合 `BatchedFrequencyPenalizer`、`BatchedMinNewTokensPenalizer`、`BatchedPresencePenalizer`、`BatchedRepetitionPenalizer` 四类。各惩罚器通过 `_is_required()` 自查是否生效，无需时零开销；统一创建是为了让 `ScheduleBatch` 的 `filter_batch`/`merge_batch` 无需特判。

收尾调用可覆写钩子 `adjusted_from_schedule_batch`（默认 pass，`sampling_batch_info.py:223`），供特殊采样路径子类扩展。

### 生命周期：filter / merge / copy_for_forward

`SamplingBatchInfo` 随 `ScheduleBatch` 跨步存活，批动态变化时同步张量：

| 方法（行号） | 行为 |
|---|---|
| `filter_batch(keep_indices, keep_indices_device)`（302） | 先 `penalizer_orchestrator.filter`，再对 `temperatures/top_ps/top_ks/min_ps/sampling_seed` 做 `value[keep_indices_device]` 高级索引（仅当值非 None）；`logit_bias` 同样索引；自定义 processor 掩码重筛，全 False 的处理器丢弃、空 dict 则整个禁用（328-346） |
| `merge_batch(other)`（388） | `penalizer_orchestrator.merge`；合并处理器与 `custom_params`；`logit_bias` 用 `merge_bias_tensor`（459）补 `0.0` 填充对齐后 `cat`；5 个基础张量 `torch.cat`；布尔标志 `&=`/`\|=` 聚合。**注**：`__len__` 定义在 `temperatures` 上（236），故所有依赖 `len(self)` 的合并必须先于 temperatures 更新（注释 414、430） |
| `copy_for_forward()`（453） | 先 `update_penalties()`（266）把惩罚累积进预分配缓冲 `acc_additive_penalties`/`acc_scaling_penalties`，再 `dataclasses.replace(self, penalizer_orchestrator=None)` 解绑编排器 |

`update_penalties` 仅当 `orchestrator.is_required` 时分配 `(bs, vocab_size)` 缓冲并做累加；后续 `apply_logits_bias`（283）按「非 overlap 用 orchestrator.apply、overlap 用预累积缓冲 + `apply_scaling_penalties`」双路径把惩罚/文法掩码/logit_bias 施加到 logits。

> 注：早期版本曾有 `sampling_info_done` 生命周期标记，**当前源码（本仓库 python/sglang 全树）中不存在该字段**。现行为由 `scheduler.py` 的 `_forward_isolation` 上下文管理器承担：每次 forward 前 `copy_for_forward()` 生成 forward 专用副本（`scheduler.py:3675-3679`），防止 overlap 模式下多次 `init_new` 重复累积惩罚。

### 参数流转链路：SamplingParams → Sampler

| 环节 | 代码位置 | 动作 |
|---|---|---|
| 请求侧 | `srt/sampling/sampling_params.py` | 每 `Req` 持 `sampling_params`，见 [sampling.md](sampling.md) |
| 构建 | `schedule_batch.py:2632`（prefill/extend）、`schedule_batch.py:2956`（`prepare_for_idle` 空批）、`scheduler.py:3057` | `SamplingBatchInfo.from_schedule_batch(self, vocab_size)`，字段存于 `ScheduleBatch.sampling_info`（`schedule_batch.py:2186`） |
| 跨步维护 | `schedule_batch.py:3220/3231` | `filter_batch`/`merge_batch` 同步张量与惩罚状态 |
| 惩罚记账 | `schedule_batch.py:3050,3074`（`prepare_for_decode` → `cumulate_penalty_output_tokens`） | 把上一步 `output_ids[-1]` 送入 `penalizer_orchestrator.cumulate_output_tokens` |
| forward 隔离 | `scheduler.py:3651-3679` | `_forward_isolation` 快照旧值 → `copy_for_forward()` 换副本 |
| 交接 ForwardBatch | `model_executor/forward_batch_info.py:472,805` | `ForwardBatch.sampling_info = batch.sampling_info`（借用而非复制，携带各自 GPU 张量） |
| 消费 | `srt/layers/sampler.py:98` `Sampler.forward(logits_output, sampling_info, ...)` | `_preprocess_logits`（90）先跑自定义 processor 与 NaN 清洗；`is_all_greedy` 走 `argmax`/aiter 贪心（130-137），否则 `logits.div_(temperatures)`（193）后按 `need_*` 标志分流 top-k/top-p/min-p（274-295） |

`Sampler` 只读 `sampling_info` 张量、不修改其内容；整个链路上 `SamplingParams`（CPU 逐请求）→ `SamplingBatchInfo`（GPU 批量张量）→ `Sampler`（一次 kernel 调用消费）是「标量 → 张量 → 采样」的三段式降维。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
