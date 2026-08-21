## 01-config 配置体系对比：校验/哈希与关键参数对照

接 `config-comparison.md`（配置载体与装配）。源码：`vllm/config/vllm.py`、`sglang/srt/server_args.py`。

### 1. 校验机制对比

| 维度 | vLLM | SGLang |
|---|---|---|
| 触发点 | `VllmConfig.__post_init__`（`vllm/config/vllm.py`） | `ServerArgs.__post_init__` → `_run_resolution_pipeline()`（`server_args.py:3620`） |
| 校验结构 | 两段式：①按 `architecture` 查 `MODELS_CONFIG_MAP` 执行架构级 `verify_and_update_config`；②子配置内部校验（`ModelConfig.verify_with_parallel_config`、hybrid 配置、Run.ai 加载格式） | 约 60 步有序 `_handle_*` dispatcher 边解析边校验，末尾 `check_server_args()`（`server_args.py:9225`）断言级交叉校验 |
| 幂等 | `config_updated` 标志防止重复执行 | dispatcher 单次执行，解析后字段只读 |
| 跨配置校验示例 | `--enable-return-routed-experts` 与 PP>1 / 上下文并行（DCP/PCP>1）冲突时报错 | `chunked_prefill_size % page_size == 0`；优先级调度要求 `schedule_policy in [fcfs, lof]`；`(tp_size*pp_size) % nnodes == 0` |
| 子配置内部校验 | SchedulerConfig：`max_num_batched_tokens >= max_num_seqs`；未开 chunked 时 `>= max_model_len`；encoder-decoder 强制关 chunked prefill | `check_server_args()` 内统一断言 |
| 防御机制 | pydantic `ConfigDict(extra="forbid")` 禁未知字段；类型不符抛 `ValueError` | `__setattr__` 守卫（`server_args.py:9110`）字段只读，修改报错提示 `get_context().override(...)` |

**差异本质**：vLLM 校验分布在"装配时架构级 + 各子配置 `__post_init__`"，SGLang 收敛到一条单行管线里的 `_handle_*` 步骤 + 集中断言。

### 2. 哈希机制对比

| 维度 | vLLM | SGLang |
|---|---|---|
| 接口 | 每个配置类均有 `compute_hash()`；`VllmConfig.compute_hash()`（`vllm.py:423`）聚合 | 无 `compute_hash`，无对应机制 |
| 字段规范化 | `utils.normalize_value()`：枚举（带 FQN）、torch.dtype、Path、dataclass、容器 → JSON 可序列化结构 | — |
| 哈希算法 | `get_hash_factors` + `hash_factors` 输出 SHA-256 | — |
| 聚合方式 | 版本号 + 各子配置哈希（`model_config`/`cache_config`/`parallel_config`/`multimodal_config` 等），各子配置声明"影响计算图结构"的字段集合 | — |
| 用途 | torch.compile / CUDA graph 缓存键 | 编译缓存键不依赖配置哈希（CUDA graph 由 `cuda_graph_config` 控制） |
| 缓存 | `compute_hash_cached` 按对象身份缓存 | — |
| 非图字段 | 如 tokenizer、seed 等不参与哈希（ModelConfig 注记） | — |

### 3. 关键参数对照：并行维度

| 语义 | vLLM 参数 | SGLang 参数 | 默认 |
|---|---|---|---|
| 张量并行 | `tensor_parallel_size` | `tp_size`（alias `--tensor-parallel-size`） | 1 |
| 流水线并行 | `pipeline_parallel_size` | `pp_size` | 1 |
| 数据并行 | `data_parallel_size`（含 `_local`/rank 派生） | `dp_size` | 1 |
| 解码上下文并行 | `decode_context_parallel_size` | `dcp_size`（alias `--decode-context-parallel-size`） | 1 |
| 预填充上下文并行 | `prefill_context_parallel_size` | `attn_cp_size` | 1 |
| 专家并行 | `enable_expert_parallel` + `expert_placement_strategy`（linear/round_robin） | `moe_runner_backend` + `moe_dp_size` + `eplb_*` | 关 |
| 多机拓扑 | `nnodes` / `node_rank` | `nnodes` / `node_rank`（要求 `(tp*pp)%nnodes==0`） | 1 / 0 |
| 分布式后端 | `distributed_executor_backend`（ray/mp/uni/external_launcher） | `load_balance_method`（拓扑相关） | — |

### 4. 关键参数对照：显存与调度

| 语义 | vLLM | SGLang | 默认对比 |
|---|---|---|---|
| GPU 显存比例 | `gpu_memory_utilization`，(0,1]，默认 `0.92` | `mem_fraction_static`，`None`→启发式 `(gpu_mem - reserved)/gpu_mem`，reserved≈`512 + activation_tokens*1.5 + tp*pp/8*1024 + 图缓冲`；显存不可得取 0.88，VLM 再下调 | 固定 0.92 vs 自动计算 |
| 显存用途常量 | `CacheConfig` 内部规划 | `constants.py` 三类常量：`GPU_MEMORY_TYPE_KV_CACHE/WEIGHTS/CUDA_GRAPH` | — |
| chunked prefill | `enable_chunked_prefill`（默认 `True`）+ `max_num_batched_tokens`（默认 2048） | `chunked_prefill_size`（`None`→按显存分级：<20G→2048、<35G→2048、<60G→4096、<90G→8192、≥160G→16384；`-1` 禁用）+ `enable_mixed_chunk`（默认 `False`） | 开关式 vs 显存分级 |
| prefill 批上限 | `max_num_batched_tokens`（2048） | `max_prefill_tokens`（16384） | 数值差异大 |
| 前缀缓存 | `enable_prefix_caching`（默认 `True`）+ `prefix_caching_hash_algo`（sha256/sha256_cbor/xxhash/xxhash_cbor，xxhash 快但有碰撞风险） | `disable_radix_cache`（默认 `False`，RadixAttention 默认开启）+ `radix_eviction_policy`（lru 默认/lfu/slru/priority） | 都默认开启 |
| 调度策略 | `policy`：`fcfs`/`priority` | `schedule_policy`：`lpm/random/fcfs/dfs-weight/lof/priority/routing-key`；优先级调度仅配 fcfs/lof | fcfs 一致，SGLang 选项更多 |
| KV 页大小 | `block_size`（默认 16） | `page_size`（resolvable；`check_server_args` 要求 `chunked_prefill_size % page_size == 0`） | 固定 16 vs 自动 |
| 批大小 | `max_num_seqs`（默认 128） | `max_total_tokens` | — |
| 长提示阈值 | `long_prefill_token_threshold`（0 不设限） | `max_prefill_tokens` 边界 | — |
| 异步调度 | `async_scheduling` / `scheduler_cls` | `disable_overlap_schedule`（默认 False，即默认重叠调度） | — |

### 5. 关键参数对照：生成/解码

| 语义 | vLLM | SGLang |
|---|---|---|
| grammar 后端 | `structured_outputs_config`（`StructuredOutputsConfig` 子配置） | `grammar_backend`：`xgrammar/outlines/llguidance/none`（默认 None） |
| 投机解码 | `speculative_config`（`SpeculativeConfig` 子配置） | `speculative_algorithm` + `speculative_num_draft_tokens` |
| LoRA | `lora_config`（`LoRAConfig`） | `enable_lora`、`max_loras_per_batch`、`lora_paths` |
| PD 分离 | `kv_transfer_config`（`KVTransferConfig`，分布式 KV 传输） | `disaggregation_mode`、`disaggregation_transfer_backend` |
| 量化 | `quantization`（ModelConfig）+ `quant_config`（运行时） | `quantization` + `kv_cache_dtype`（ServerArgs 直接字段） |
| 确定性推理 | `seed`（ModelConfig） | `random_seed` + `enable_deterministic_inference`（默认关） |
| 模型上下文长度 | `max_model_len`（支持 `1k/25.6k` 可读格式、`-1` 自动取最大可装入长度） | `context_length` |
| 显式 KV 显存 | `kv_cache_memory_bytes`（指定后忽略 gpu_memory_utilization） | — |

### 6. 模块小结

| 维度 | vLLM | SGLang |
|---|---|---|
| 配置哲学 | 职责拆分子配置，pydantic 强类型 + `extra="forbid"`，配置即编译缓存键 | 单类全量承载 + 注解驱动 CLI + 解析管线，配置即只读运行契约 |
| 可组合性 | `VllmConfig` 可编程重组（`replace`/`update_config`/`with_hf_config`） | 声明式 `overrides.py` + `get_context().override(...)` |
| 缓存键设计 | SHA-256 聚合哈希（图结构敏感字段） | 无配置哈希 |
| 环境变量治理 | dict 注册 + 懒加载 + 未知变量拒绝 | 描述符注册 + 废弃迁移 + 第三方缓存重定向 |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
