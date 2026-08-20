## v1 Speculative Decoding：worker 侧形态

v1 的投机解码完全落在 ModelRunner 进程内：`GPUModelRunner` 构造时按 `SpeculativeConfig.method` 创建 drafter（proposer），每次 `sample_tokens` 后用 proposer 产下一轮 draft tokens，采样时用 `RejectionSampler` 验收。调度器只负责把 draft tokens 排进 `SchedulerOutput.scheduled_spec_decode_tokens`。

### Proposer 体系（vllm/v1/spec_decode/）

| 类 | 文件 | method 关键字 |
|---|---|---|
| `SpecDecodeBaseProposer` | `llm_base_proposer.py:71` | 基类：持 draft 模型 config、hidden_size、draft 模型副本 |
| `NgramProposer` | `ngram_proposer.py` | `ngram`（CPU 端 n-gram 匹配） |
| `NgramProposerGPU` | `ngram_proposer_gpu.py` | `ngram_gpu`（GPU 端） |
| `SuffixDecodingProposer` | `suffix_decoding.py` | `suffix` |
| `EagleProposer` | `eagle.py` | `eagle`/`eagle3` |
| `DFlashProposer` | `dflash.py` | `dflash`（并行 drafting） |
| `DraftModelProposer` | `draft_model.py` | `draft_model`（复用 draft model） |
| `MedusaProposer` | `medusa.py` | `medusa` |
| `Gemma4Proposer` / `Step3p5MTPProposer` | `gemma4.py` / `step3p5.py` | `gemma4_mtp` / `step3p5_mtp` |
| `ExtractHiddenStatesProposer` | `extract_hidden_states.py` | `extract_hidden_states` |
| `custom_class` | `custom_class_proposer.py` | 用户自定义 |

`propose()`（`llm_base_proposer.py:510`）是核心接口，输入上轮 sampled tokens + 每请求历史 token 序列，输出 draft token ids。`SpecDecodeBaseProposer.__init__` 从 `draft_model_config` 取 hidden_size（draft 模型可不同于 target，如 Llama-3.3-70B）。

### drafter 创建（gpu_model_runner.py:630-709）

`GPUModelRunner.__init__` 中（仅 `get_pp_group().is_last_rank`）按 `speculative_config.method` 分支实例化 drafter，并创建 `RejectionSampler(self.sampler, self.speculative_config, self.device)`。EAGLE3/DFlash/extract_hidden_states 会设置 `use_aux_hidden_state_outputs=True`，使 forward 额外返回 `aux_hidden_states` 供 drafter 用。CPU 后端（`cpu_worker.py`）同样走此路径，仅提示需 LD_PRELOAD libiomp。

### 每 step 的 spec 流程

```
execute_model:  _calc_spec_decode_metadata(scheduler_output)   # 建 SpecDecodeMetadata（gpu_model_runner.py:2923）
sample_tokens:  _sample → rejection_sampler 验收 draft → 得最终 token
                propose_draft_token_ids() → drafter.propose → _copy_draft_token_ids_to_cpu
EngineCore.post_step: model_executor.take_draft_token_ids() → scheduler.update_draft_token_ids()
```

- `SpecDecodeMetadata`（`vllm/v1/spec_decode/metadata.py:10`）描述本轮 draft 布局：`draft_token_ids`、`num_draft_tokens`、`cu_num_draft_tokens`、`cu_num_sampled_tokens`、`target_logits_indices`、`bonus_logits_indices`、`logits_indices`（draft+bonus 的 logits 索引，`__post_init__` 取 `max_spec_len`）。target logits 与 bonus logits 同批计算后按索引切分。
- `propose_draft_token_ids`（gpu_model_runner.py:5126）按 method 分发到各 drafter 的 `propose`；EAGLE/DFlash/DraftModel/ExtractHiddenStates 类 drafter 可复用 GPU sampled tokens（`use_gpu_toks`），无需等 bookkeeping。
- 结构化输出场景：EngineCore 在 `post_step`（`v1/engine/core.py:615`，非 async 路径）取回 draft ids 后先 `update_draft_token_ids`，无效 spec token 会被 pad 为 -1，在 grammar bitmask 计算中跳过。
- 采样验收：`_sample`（gpu_model_runner.py:3765）在 spec 路径取 `_get_spec_decode_draft_probs` 后调 `rejection_sampler(spec_decode_metadata, draft_probs, logits, sampling_metadata)`；`use_async_scheduling` 时需 `update_async_spec_token_ids` 把真实 draft tokens 写回（penalty/bad_words 依赖）。

### Speculator（vllm/v1/worker/gpu/spec_decode/speculator.py）

| 类 | 职责 |
|---|---|
| `BaseSpeculator`（ABC） | `propose`/`capture`/`init_cudagraph_manager` 接口 |
| `DraftModelSpeculator` | 包一层完整 draft 模型：`load_draft_model`、`_build_draft_attn_metadata`、`_greedy_sample_draft`、`sample_draft`；支持 EPLB、独立 CUDA graph 捕获 |

`rejection_sampler.py`/`rejection_sampler_utils.py`/`adaptive_verification.py` 实现 token 验收与自适应验证（动态裁剪 draft 长度）。`worker/gpu/spec_decode/autoregressive/`、`mtp/` 等子目录放具体 draft 模型结构。

### 与 engine-core 的衔接

- 调度侧：`SchedulerOutput.scheduled_spec_decode_tokens`（`req_id → draft token ids`）与 `num_spec_tokens_to_schedule` 由调度器产出，worker 据此建 `SpecDecodeMetadata`。
- 输出侧：draft 验收后的 token 以普通 `sampled_token_ids` 回流，经 `scheduler.update_from_output` 成 `EngineCoreOutputs`。
- 同步路径下 draft ids 经 `take_draft_token_ids()`（gpu_model_runner.py:5005，D2H 拷贝成 `DraftTokenIds`）回填调度器，供下一轮预排；async 路径在 worker 进程内直接更新（`core.py` 注释明确说明）。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
