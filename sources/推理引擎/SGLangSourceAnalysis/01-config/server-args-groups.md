## ServerArgs 参数分组与关键默认值

`ServerArgs` 字段按注释横幅（`# ---`）划分为 40+ 个语义分组（`server_args.py:495-3615`）。下表给出主要分组、行号范围与代表性字段。

### 分组总览

| 分组（行号起） | 代表性字段 |
|---|---|
| Model and tokenizer（495） | `model_path`、`tokenizer_path/mode/backend`、`load_format`、`context_length`、`model_impl` |
| Quantization and data type（643） | `dtype`、`quantization`、`kv_cache_dtype`、`enable_tf32_matmul` |
| Memory and scheduling（777） | `mem_fraction_static`、`chunked_prefill_size`、`schedule_policy`、`max_total_tokens`、`page_size` |
| Distributed topology（998） | `tp_size/pp_size/dp_size/dcp_size/attn_cp_size`、`nnodes/node_rank`、`load_balance_method` |
| Device info and timeout（1219） | `device`、`random_seed`、`base_gpu_id` |
| HTTP server（1285） | `host`、`port`、`enable_http2`、`grpc_port` |
| SSL/TLS（1348） / API related（1367） | `ssl_keyfile`；`api_key`、`served_model_name` |
| Logging, metrics, tracing（1505） | `log_level`、`enable_metrics`、`metrics_http_port` |
| Constrained decoding（1692） | `grammar_backend`、`reasoning_parser`、`tool_call_parser` |
| Kernel backend（1706） | `attention_backend`、`sampling_backend`、`fp8_gemm_runner_backend` |
| Cuda graphs（1875） | `cuda_graph_config`（decode/prefill 分相） |
| Speculative decoding（2094 / 2320） | `speculative_algorithm`、`speculative_num_draft_tokens` |
| Expert parallelism（2358） | `moe_runner_backend`、`moe_dp_size`、`eplb_*` |
| Mamba cache / linear attn（2553） | `mamba_ssm_dtype`、`linear_attn_kernel_backend` |
| Hierarchical cache（2688）/ HSA（2776） | `enable_hicache`；`enable_hisparse` |
| LoRA（2908） | `enable_lora`、`max_loras_per_batch`、`lora_paths` |
| PD disaggregation（3130） | `disaggregation_mode`、`disaggregation_transfer_backend` |
| Deterministic inference（3426） | `enable_deterministic_inference` |
| Weight cache（3567） | `weight_cache_mode` |
| Custom hooks/plugins（3600） | `enable_custom_hook`、`probe_*` |

### 关键默认值与语义

| 参数 | 默认 | 说明 |
|---|---|---|
| `tp_size` / `pp_size` / `dp_size` / `dcp_size` / `attn_cp_size` | `1` / `1` / `1` / `1` / `1` | 张量/流水线/数据/解码上下文/注意力上下文并行度；`dcp_size` 别名 `--decode-context-parallel-size` |
| `nnodes` / `node_rank` | `1` / `0` | 多机拓扑；`check_server_args` 要求 `(tp_size*pp_size) % nnodes == 0` |
| `mem_fraction_static` | `None`→自动 | 解析管线按 GPU 显存启发式：`(gpu_mem - reserved) / gpu_mem`，其中 `reserved = 512 + activation_tokens*1.5 + tp*pp/8*1024 + 图缓冲`（`server_args.py:4981-5016`）；gpu_mem 不可得时取 0.88；VLM 模型再下调 |
| `chunked_prefill_size` | `None`→按显存分级 | <20GB→2048、<35GB→2048、<60GB→4096、<90GB→8192、≥160GB→16384（`server_args.py:4862-4916`）；`-1` 表示禁用 chunked prefill |
| `disable_radix_cache` | `False` | RadixAttention 前缀缓存默认**开启**；`radix_eviction_policy="lru"`（可选 `lfu/slru/priority`） |
| `schedule_policy` | `"fcfs"` | 可选 `lpm/random/fcfs/dfs-weight/lof/priority/routing-key`；优先级调度仅配 `fcfs`/`lof` |
| `grammar_backend` | `None` | 可选 `xgrammar/outlines/llguidance/none`；`_handle_grammar_backend` 解析 |
| `attention_backend` | `None`（resolvable） | 可选 `triton/torch_native/flashinfer/fa3/fa4/dsa/...`；`_get_default_attn_backend` 按设备/模型自动选择 |
| `sampling_backend` | `None` | `flashinfer/pytorch/ascend`，`SGLANG_KV_CANARY_ENABLE_TOKEN_ORACLE` 时加 `token_oracle` |
| `max_prefill_tokens` | `16384` | prefill 批 token 上限 |
| `page_size` | `None`（resolvable） | KV 页大小，`check_server_args` 要求 `chunked_prefill_size % page_size == 0` |
| `enable_mixed_chunk` | `False` | chunked prefill 下 prefill/decode 混批 |
| `disable_overlap_schedule` | `False` | 关闭 CPU 调度与 GPU 执行重叠 |
| `host` / `port` | `127.0.0.1` / `30000` | HTTP 服务地址 |
| `load_format` | `"auto"` | 可选 17 种（`pt/safetensors/npcache/dummy/presharded/gguf/...`）；`IPC_CACHE` 不暴露 CLI |

### 动态 choices 扩展

模块级 `add_*_choices` 函数（`server_args.py:414-450`）供 OOT 平台插件向 `ATTENTION_BACKEND_CHOICES`、`GRAMMAR_BACKEND_CHOICES`、`DISAGG_TRANSFER_BACKEND_CHOICES`、`RADIX_EVICTION_POLICY_CHOICES` 等列表追加选项；`reasoning_parser`/`tool_call_parser` 的 choices 在 `add_cli_args` 时从插件注册表动态计算。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
