# llama.cpp HTTP Server - Parameters & Configuration

## Common Parameters

### General

| Argument | Env Var | Description | Default |
| -------- | ------- | ----------- | ------- |
| `-h, --help, --usage` | | Print usage and exit | |
| `--version` | | Show version and build info | |
| `-cl, --cache-list` | | Show list of models in cache | |
| `--completion-bash` | | Print bash completion script | |

### Threading & CPU

| Argument | Env Var | Description | Default |
| -------- | ------- | ----------- | ------- |
| `-t, --threads N` | `LLAMA_ARG_THREADS` | CPU threads during generation | -1 |
| `-tb, --threads-batch N` | | Threads during batch/prompt processing | same as --threads |
| `-C, --cpu-mask M` | | CPU affinity mask (hex) | "" |
| `-Cr, --cpu-range lo-hi` | | CPU range for affinity | |
| `--cpu-strict <0\|1>` | | Strict CPU placement | 0 |
| `--prio N` | | Process/thread priority (-1 to 3) | 0 |
| `--poll <0...100>` | | Polling level (0 = no polling) | 50 |

### Context & Batch

| Argument | Env Var | Description | Default |
| -------- | ------- | ----------- | ------- |
| `-c, --ctx-size N` | `LLAMA_ARG_CTX_SIZE` | Prompt context size (0 = from model) | 0 |
| `-n, --predict, --n-predict N` | `LLAMA_ARG_N_PREDICT` | Tokens to predict (-1 = infinity) | -1 |
| `-b, --batch-size N` | `LLAMA_ARG_BATCH` | Logical max batch size | 2048 |
| `-ub, --ubatch-size N` | `LLAMA_ARG_UBATCH` | Physical max batch size | 512 |
| `--keep N` | | Tokens to keep from initial prompt (0, -1 = all) | 0 |

### RoPE Configuration

| Argument | Env Var | Description | Default |
| -------- | ------- | ----------- | ------- |
| `--rope-scaling {none,linear,yarn}` | `LLAMA_ARG_ROPE_SCALING_TYPE` | RoPE frequency scaling method | linear |
| `--rope-scale N` | `LLAMA_ARG_ROPE_SCALE` | RoPE context scaling factor | |
| `--rope-freq-base N` | `LLAMA_ARG_ROPE_FREQ_BASE` | RoPE base frequency | from model |
| `--rope-freq-scale N` | `LLAMA_ARG_ROPE_FREQ_SCALE` | RoPE frequency scaling factor | |
| `--yarn-orig-ctx N` | `LLAMA_ARG_YARN_ORIG_CTX` | YaRN original context size | 0 |
| `--yarn-ext-factor N` | `LLAMA_ARG_YARN_EXT_FACTOR` | YaRN extrapolation mix factor | -1.00 |
| `--yarn-attn-factor N` | `LLAMA_ARG_YARN_ATTN_FACTOR` | YaRN attention magnitude scale | -1.00 |
| `--yarn-beta-slow N` | `LLAMA_ARG_YARN_BETA_SLOW` | YaRN high correction dim | -1.00 |
| `--yarn-beta-fast N` | `LLAMA_ARG_YARN_BETA_FAST` | YaRN low correction dim | -1.00 |

### KV Cache

| Argument | Env Var | Description | Default |
| -------- | ------- | ----------- | ------- |
| `-kvo, --kv-offload` | `LLAMA_ARG_KV_OFFLOAD` | Enable KV cache offloading | enabled |
| `-ctk, --cache-type-k TYPE` | `LLAMA_ARG_CACHE_TYPE_K` | KV cache data type for K | f16 |
| `-ctv, --cache-type-v TYPE` | `LLAMA_ARG_CACHE_TYPE_V` | KV cache data type for V | f16 |
| `--swa-full` | `LLAMA_ARG_SWA_FULL` | Use full-size SWA cache | false |

Allowed cache types: `f32`, `f16`, `bf16`, `q8_0`, `q4_0`, `q4_1`, `iq4_nl`, `q5_0`, `q5_1`

### GPU & Device Offloading

| Argument | Env Var | Description | Default |
| -------- | ------- | ----------- | ------- |
| `-ngl, --gpu-layers N` | `LLAMA_ARG_N_GPU_LAYERS` | Layers to store in VRAM (auto/all/number) | auto |
| `-sm, --split-mode` | `LLAMA_ARG_SPLIT_MODE` | Multi-GPU split mode | layer |
| `-ts, --tensor-split N0,N1,...` | `LLAMA_ARG_TENSOR_SPLIT` | Fraction per GPU | |
| `-mg, --main-gpu INDEX` | `LLAMA_ARG_MAIN_GPU` | Main GPU index | 0 |
| `-dev, --device <dev1,dev2>` | `LLAMA_ARG_DEVICE` | Devices for offloading | |
| `-fit, --fit [on\|off]` | `LLAMA_ARG_FIT` | Auto-adjust to fit device memory | on |
| `-fitt, --fit-target MiB0,...` | `LLAMA_ARG_FIT_TARGET` | Target margin per device | 1024 |
| `-fitc, --fit-ctx N` | `LLAMA_ARG_FIT_CTX` | Min ctx size for --fit | 4096 |

Split modes: `none` (one GPU), `layer` (pipelined), `row` (parallelized), `tensor` (experimental)

### Model Loading

| Argument | Env Var | Description | Default |
| -------- | ------- | ----------- | ------- |
| `-m, --model FNAME` | `LLAMA_ARG_MODEL` | Model path | |
| `-mu, --model-url URL` | `LLAMA_ARG_MODEL_URL` | Model download URL | unused |
| `-hf, --hf-repo <user>/<model>[:quant]` | `LLAMA_ARG_HF_REPO` | HuggingFace repo | unused |
| `-hff, --hf-file FILE` | `LLAMA_ARG_HF_FILE` | HuggingFace model file | unused |
| `-hft, --hf-token TOKEN` | `HF_TOKEN` | HuggingFace access token | from env |
| `-lm, --load-mode MODE` | `LLAMA_ARG_LOAD_MODE` | Model loading mode | auto |
| `-dr, --docker-repo [<repo>/]<model>[:quant]` | `LLAMA_ARG_DOCKER_REPO` | Docker Hub model repo | unused |

Load modes: `auto`, `none`, `mmap`, `mlock`, `mmap+mlock`, `dio`

### LoRA Adapters

| Argument | Env Var | Description | Default |
| -------- | ------- | ----------- | ------- |
| `--lora FNAME` | | LoRA adapter path (comma-separated) | |
| `--lora-scaled FNAME:SCALE,...` | | LoRA with scaling | |
| `--lora-init-without-apply` | | Load without applying (apply later via API) | disabled |

### Control Vectors

| Argument | Description |
| -------- | ----------- |
| `--control-vector FNAME` | Add control vector (comma-separated for multiple) |
| `--control-vector-scaled FNAME:SCALE,...` | Control vector with scaling |
| `--control-vector-layer-range START END` | Layer range for control vectors |

## Sampling Parameters

| Argument | Env Var | Description | Default |
| -------- | ------- | ----------- | ------- |
| `--samplers SAMPLERS` | | Sampler order (semicolon-separated) | penalties;dry;top_n_sigma;top_k;typ_p;top_p;min_p;xtc;temperature |
| `-s, --seed SEED` | | RNG seed (-1 = random) | -1 |
| `--temp, --temperature N` | | Temperature | 0.80 |
| `--top-k N` | `LLAMA_ARG_TOP_K` | Top-k sampling (0 = disabled) | 40 |
| `--top-p N` | | Top-p sampling (1.0 = disabled) | 0.95 |
| `--min-p N` | | Min-p sampling (0.0 = disabled) | 0.05 |
| `--top-nsigma N` | | Top-n-sigma sampling (-1.0 = disabled) | -1.00 |
| `--typical, --typical-p N` | | Typical sampling (1.0 = disabled) | 1.00 |
| `--mirostat N` | | Mirostat sampling (0=off, 1=v1, 2=v2) | 0 |
| `--mirostat-lr N` | | Mirostat learning rate | 0.10 |
| `--mirostat-ent N` | | Mirostat target entropy | 5.00 |

### Repetition Penalties

| Argument | Description | Default |
| -------- | ----------- | ------- |
| `--repeat-last-n N` | Last n tokens for penalty (0 = disabled) | 64 |
| `--repeat-penalty N` | Repeat penalty (1.0 = disabled) | 1.00 |
| `--presence-penalty N` | Presence penalty (0.0 = disabled) | 0.00 |
| `--frequency-penalty N` | Frequency penalty (0.0 = disabled) | 0.00 |

### DRY Sampling

| Argument | Description | Default |
| -------- | ----------- | ------- |
| `--dry-multiplier N` | DRY multiplier (0.0 = disabled) | 0.00 |
| `--dry-base N` | DRY base value | 1.75 |
| `--dry-allowed-length N` | DRY allowed length | 2 |
| `--dry-penalty-last-n N` | DRY penalty scan window | 64 |
| `--dry-sequence-breaker STRING` | DRY sequence breakers | `['\n', ':', '"', '*']` |

### XTC Sampling

| Argument | Description | Default |
| -------- | ----------- | ------- |
| `--xtc-probability N` | XTC probability (0.0 = disabled) | 0.00 |
| `--xtc-threshold N` | XTC threshold (>0.5 disables) | 0.10 |

### Dynamic Temperature

| Argument | Description | Default |
| -------- | ----------- | ------- |
| `--dynatemp-range N` | Dynamic temp range (0.0 = disabled) | 0.00 |
| `--dynatemp-exp N` | Dynamic temp exponent | 1.00 |

### Grammar & JSON Schema

| Argument | Description |
| -------- | ----------- |
| `--grammar GRAMMAR` | BNF grammar to constrain generation |
| `--grammar-file FNAME` | File containing grammar |
| `-j, --json-schema SCHEMA` | JSON schema to constrain generation |
| `-jf, --json-schema-file FILE` | File containing JSON schema |
| `-bs, --backend-sampling` | Enable backend sampling (experimental) |

## Server-Specific Parameters

### Network & Server

| Argument | Env Var | Description | Default |
| -------- | ------- | ----------- | ------- |
| `--host HOST` | `LLAMA_ARG_HOST` | Listen IP (or .sock for UNIX socket) | 127.0.0.1 |
| `--port PORT` | `LLAMA_ARG_PORT` | Listen port | 8080 |
| `--reuse-port` | `LLAMA_ARG_REUSE_PORT` | Allow multiple sockets on same port | disabled |
| `-to, --timeout N` | `LLAMA_ARG_TIMEOUT` | Read/write timeout (seconds) | 3600 |
| `--threads-http N` | `LLAMA_ARG_THREADS_HTTP` | HTTP request processing threads | -1 |
| `--api-prefix PREFIX` | `LLAMA_ARG_API_PREFIX` | API prefix path (no trailing slash) | |

### CORS

| Argument | Env Var | Description | Default |
| -------- | ------- | ----------- | ------- |
| `--cors-origins ORIGINS` | `LLAMA_ARG_CORS_ORIGINS` | Allowed origins (comma-separated) | * |
| `--cors-methods METHODS` | `LLAMA_ARG_CORS_METHODS` | Allowed methods | GET, POST, DELETE, OPTIONS |
| `--cors-headers HEADERS` | `LLAMA_ARG_CORS_HEADERS` | Allowed headers | * |
| `--cors-credentials` | `LLAMA_ARG_CORS_CREDENTIALS` | Allow credentials | enabled |

### Authentication

| Argument | Env Var | Description | Default |
| -------- | ------- | ----------- | ------- |
| `--api-key KEY` | `LLAMA_API_KEY` | API key (comma-separated for multiple) | none |
| `--api-key-file FNAME` | `LLAMA_ARG_API_KEY_FILE` | File with API keys (one per line) | none |

### SSL/TLS

| Argument | Env Var | Description |
| -------- | ------- | ----------- |
| `--ssl-key-file FNAME` | `LLAMA_ARG_SSL_KEY_FILE` | PEM SSL private key |
| `--ssl-cert-file FNAME` | `LLAMA_ARG_SSL_CERT_FILE` | PEM SSL certificate |

### Prompt Caching

| Argument | Env Var | Description | Default |
| -------- | ------- | ----------- | ------- |
| `--cache-prompt` | `LLAMA_ARG_CACHE_PROMPT` | Enable prompt caching | enabled |
| `--cache-reuse N` | `LLAMA_ARG_CACHE_REUSE` | Min chunk size for KV shifting reuse | 0 |

### Endpoints & Monitoring

| Argument | Env Var | Description | Default |
| -------- | ------- | ----------- | ------- |
| `--metrics` | `LLAMA_ARG_ENDPOINT_METRICS` | Enable Prometheus metrics | disabled |
| `--props` | `LLAMA_ARG_ENDPOINT_PROPS` | Enable POST /props | disabled |
| `--slots` | `LLAMA_ARG_ENDPOINT_SLOTS` | Expose slots monitoring | enabled |
| `--embedding, --embeddings` | `LLAMA_ARG_EMBEDDINGS` | Embedding-only mode | disabled |
| `--rerank, --reranking` | `LLAMA_ARG_RERANKING` | Enable reranking endpoint | disabled |
| `--sse-ping-interval N` | `LLAMA_ARG_SSE_PING_INTERVAL` | SSE ping interval (seconds, -1 = disabled) | 30 |

### Parallelism & Batching

| Argument | Env Var | Description | Default |
| -------- | ------- | ----------- | ------- |
| `-np, --parallel N` | `LLAMA_ARG_N_PARALLEL` | Server slots (-1 = auto) | -1 |
| `-cb, --cont-batching` | `LLAMA_ARG_CONT_BATCHING` | Enable continuous batching | enabled |
| `-kvu, --kv-unified` | `LLAMA_ARG_KV_UNIFIED` | Unified KV buffer across sequences | auto |
| `--cache-idle-slots` | `LLAMA_ARG_CACHE_IDLE_SLOTS` | Save idle slots to prompt cache | enabled |
| `-cram, --cache-ram N` | `LLAMA_ARG_CACHE_RAM` | Max cache size in MiB (-1 = no limit) | 8192 |

### Context Management

| Argument | Env Var | Description | Default |
| -------- | ------- | ----------- | ------- |
| `--context-shift` | `LLAMA_ARG_CONTEXT_SHIFT` | Context shift for infinite generation | disabled |
| `-ctxcp, --ctx-checkpoints N` | `LLAMA_ARG_CTX_CHECKPOINTS` | Max context checkpoints per slot | 32 |
| `-cms, --checkpoint-min-step N` | `LLAMA_ARG_CHECKPOINT_MIN_SPACING_NT` | Min spacing between checkpoints | 8192 |

### Chat & Template

| Argument | Env Var | Description | Default |
| -------- | ------- | ----------- | ------- |
| `--jinja` | `LLAMA_ARG_JINJA` | Use Jinja template engine | enabled |
| `--chat-template JINJA_TEMPLATE` | `LLAMA_ARG_CHAT_TEMPLATE` | Custom Jinja chat template | from model |
| `--chat-template-file FILE` | `LLAMA_ARG_CHAT_TEMPLATE_FILE` | Custom Jinja template file | from model |
| `--chat-template-kwargs STRING` | `LLAMA_ARG_CHAT_TEMPLATE_KWARGS` | Additional template params (JSON) | |
| `-a, --alias STRING` | `LLAMA_ARG_ALIAS` | Model name aliases (comma-separated) | |
| `--tags STRING` | `LLAMA_ARG_TAGS` | Model tags (comma-separated) | |
| `--skip-chat-parsing` | `LLAMA_ARG_SKIP_CHAT_PARSING` | Force pure content parser | disabled |
| `--prefill-assistant` | `LLAMA_ARG_PREFILL_ASSISTANT` | Prefill assistant response | enabled |

### Reasoning/Thinking

| Argument | Env Var | Description | Default |
| -------- | ------- | ----------- | ------- |
| `--reasoning-format FORMAT` | `LLAMA_ARG_THINK` | Reasoning format (none/deepseek/auto) | auto |
| `-rea, --reasoning [on\|off\|auto]` | `LLAMA_ARG_REASONING` | Use reasoning in chat | auto |
| `--reasoning-effort LEVEL` | `LLAMA_ARG_REASONING_EFFORT` | Reasoning effort level | default |
| `--reasoning-budget N` | `LLAMA_ARG_THINK_BUDGET` | Token budget (-1 = unlimited) | -1 |
| `--reasoning-budget-message MSG` | `LLAMA_ARG_THINK_BUDGET_MESSAGE` | Message when budget exhausted | none |
| `--reasoning-preserve` | `LLAMA_ARG_REASONING_PRESERVE` | Preserve reasoning in history | template default |

### Multimodal

| Argument | Env Var | Description | Default |
| -------- | ------- | ----------- | ------- |
| `-mm, --mmproj FILE` | `LLAMA_ARG_MMPROJ` | Multimodal projector file | |
| `-mmu, --mmproj-url URL` | `LLAMA_ARG_MMPROJ_URL` | Multimodal projector URL | |
| `--mmproj-auto` | `LLAMA_ARG_MMPROJ_AUTO` | Auto-use multimodal projector | enabled |
| `--mmproj-offload` | `LLAMA_ARG_MMPROJ_OFFLOAD` | GPU offload for projector | enabled |
| `--image-min-tokens N` | `LLAMA_ARG_IMAGE_MIN_TOKENS` | Min tokens per image | from model |
| `--image-max-tokens N` | `LLAMA_ARG_IMAGE_MAX_TOKENS` | Max tokens per image | from model |
| `--mtmd-batch-max-tokens N` | `LLAMA_ARG_MTMD_BATCH_MAX_TOKENS` | Max image tokens per batch | 1024 |

### Web UI

| Argument | Env Var | Description | Default |
| -------- | ------- | ----------- | ------- |
| `--ui, --webui` | `LLAMA_ARG_UI` | Enable Web UI | enabled |
| `--path PATH` | `LLAMA_ARG_STATIC_PATH` | Static files path | |
| `--ui-config JSON` | `LLAMA_ARG_UI_CONFIG` | Default UI settings (JSON) | |
| `--ui-config-file PATH` | `LLAMA_ARG_UI_CONFIG_FILE` | UI settings file | |
| `--media-path PATH` | | Local media files directory | disabled |

### Logging

| Argument | Env Var | Description | Default |
| -------- | ------- | ----------- | ------- |
| `--log-disable` | | Disable logging | |
| `--log-file FNAME` | `LLAMA_ARG_LOG_FILE` | Log to file | |
| `--log-colors [on\|off\|auto]` | `LLAMA_ARG_LOG_COLORS` | Colored logging | auto |
| `-v, --verbose` | | Set max verbosity | |
| `-lv, --verbosity N` | `LLAMA_ARG_LOG_VERBOSITY` | Verbosity threshold (0-5) | 3 |
| `--log-prefix` | `LLAMA_ARG_LOG_PREFIX` | Enable log prefix | disabled |
| `--log-timestamps` | `LLAMA_ARG_LOG_TIMESTAMPS` | Enable log timestamps | disabled |
| `--log-prompts-dir PATH` | | Log prompts to directory | disabled |

Verbosity levels: 0=generic, 1=error, 2=warning, 3=info, 4=trace, 5=debug

### Agent & Tools

| Argument | Env Var | Description | Default |
| -------- | ------- | ----------- | ------- |
| `--tools TOOL1,TOOL2,...` | `LLAMA_ARG_TOOLS` | Enable server tools ("all" for all) | none |
| `--tools-runtime OPTION` | `LLAMA_ARG_TOOLS_RUNTIME` | Tool runtime (docker/podman/ssh) | none |
| `-ag, --agent` | `LLAMA_ARG_AGENT` | Enable CORS proxy + all tools | disabled |
| `--mcp-servers-config PATH` | `LLAMA_ARG_MCP_SERVERS_CONFIG` | MCP server config file | none |
| `--mcp-servers-json JSON` | `LLAMA_ARG_MCP_SERVERS_JSON` | MCP server config inline | none |

### Speculative Decoding

| Argument | Env Var | Description | Default |
| -------- | ------- | ----------- | ------- |
| `--spec-type TYPES` | `LLAMA_ARG_SPEC_TYPE` | Speculative decoding types | none |
| `--spec-draft-model, -md FNAME` | `LLAMA_ARG_SPEC_DRAFT_MODEL` | Draft model path | unused |
| `--spec-draft-ngl N` | `LLAMA_ARG_N_GPU_LAYERS_DRAFT` | Draft model GPU layers | auto |
| `--spec-draft-n-max N` | `LLAMA_ARG_SPEC_DRAFT_N_MAX` | Max draft tokens | 3 |
| `--spec-draft-n-min N` | `LLAMA_ARG_SPEC_DRAFT_N_MIN` | Min draft tokens | 0 |
| `--spec-draft-p-split P` | `LLAMA_ARG_SPEC_DRAFT_P_SPLIT` | Split probability | 0.10 |
| `--spec-draft-p-min P` | `LLAMA_ARG_SPEC_DRAFT_P_MIN` | Min speculative probability | 0.00 |

Speculative types: `none`, `draft-simple`, `draft-eagle3`, `draft-mtp`, `draft-dflash`, `draft-dspark`, `ngram-simple`, `ngram-map-k`, `ngram-map-k4v`, `ngram-mod`, `ngram-cache`

### Router Server

| Argument | Env Var | Description | Default |
| -------- | ------- | ----------- | ------- |
| `--models-dir PATH` | `LLAMA_ARG_MODELS_DIR` | Models directory | disabled |
| `--models-preset PATH` | `LLAMA_ARG_MODELS_PRESET` | Model presets INI file | disabled |
| `--models-max N` | `LLAMA_ARG_MODELS_MAX` | Max concurrent models | 4 |
| `--models-autoload` | `LLAMA_ARG_MODELS_AUTOLOAD` | Auto-load models | enabled |

### Miscellaneous

| Argument | Env Var | Description | Default |
| -------- | ------- | ----------- | ------- |
| `--numa TYPE` | `LLAMA_ARG_NUMA` | NUMA optimizations | |
| `-ot, --override-tensor PATTERN=TYPE` | `LLAMA_ARG_OVERRIDE_TENSOR` | Override tensor buffer type | |
| `--override-kv KEY=TYPE:VALUE` | | Override model metadata | |
| `--check-tensors` | | Check tensor data for invalid values | false |
| `--no-host` | `LLAMA_ARG_NO_HOST` | Bypass host buffer | |
| `--repack` | `LLAMA_ARG_REPACK` | Enable weight repacking | enabled |
| `--op-offload` | | Offload host tensor ops to device | true |
| `--warmup` | | Perform warmup with empty run | enabled |
| `--spm-infill` | | Use Suffix/Prefix/Middle for infill | disabled |
| `--pooling {none,mean,cls,last,rank}` | `LLAMA_ARG_POOLING` | Embedding pooling type | from model |
| `--embd-normalize N` | | Embedding normalization | 2 |
| `-sp, --special` | | Enable special tokens output | false |
| `-e, --escape` | | Process escape sequences | true |
| `--offline` | `LLAMA_ARG_OFFLINE` | Force cache, prevent network | disabled |
| `--slot-save-path PATH` | | Path to save slot KV cache | disabled |
| `--sleep-idle-seconds N` | | Idle seconds before sleep (-1 = disabled) | -1 |
| `--lora-init-without-apply` | | Load LoRA without applying | disabled |
| `-bs, --backend-sampling` | `LLAMA_ARG_BACKEND_SAMPLING` | Backend sampling (experimental) | disabled |

### Default Model Presets (Quick Start)

| Argument | Description |
| -------- | ----------- |
| `--embd-gemma-default` | Use default EmbeddingGemma model |
| `--fim-qwen-1.5b-default` | Use default Qwen 2.5 Coder 1.5B |
| `--fim-qwen-3b-default` | Use default Qwen 2.5 Coder 3B |
| `--fim-qwen-7b-default` | Use default Qwen 2.5 Coder 7B |
| `--fim-qwen-7b-spec` | Qwen 2.5 Coder 7B + 0.5B draft (speculative) |
| `--fim-qwen-14b-spec` | Qwen 2.5 Coder 14B + 0.5B draft (speculative) |
| `--fim-qwen-30b-default` | Use default Qwen 3 Coder 30B |
| `--vision-gemma-4b-default` | Use Gemma 3 4B QAT |
| `--vision-gemma-12b-default` | Use Gemma 3 12B QAT |
| `--spec-default` | Enable default speculative decoding config |
