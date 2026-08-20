# llama cli - Command-Line Parameters Reference

All parameters listed below apply to both `llama-cli` and `llama-completion` (they share the same parameter set). Parameters marked with `(env: ...)` can also be set via environment variables.

---

## Common Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `-h, --help, --usage` | Print usage and exit | - |
| `--version` | Show version and build info | - |
| `-cl, --cache-list` | Show list of models in cache | - |
| `--completion-bash` | Print source-able bash completion script | - |

## Threading & CPU

| Parameter | Description | Default |
|-----------|-------------|---------|
| `-t, --threads N` | CPU threads during generation | -1 (auto) |
| `-tb, --threads-batch N` | Threads during batch/prompt processing | same as --threads |
| `-C, --cpu-mask M` | CPU affinity mask (hex) | "" |
| `-Cr, --cpu-range lo-hi` | CPU range for affinity | - |
| `--cpu-strict <0\|1>` | Strict CPU placement | 0 |
| `--prio N` | Process/thread priority: low(-1), normal(0), medium(1), high(2), realtime(3) | 0 |
| `--poll <0...100>` | Polling level (0 = no polling) | 50 |
| `-Cb, --cpu-mask-batch M` | CPU affinity mask for batch processing | same as --cpu-mask |
| `-Crb, --cpu-range-batch lo-hi` | CPU range for batch processing | - |
| `--cpu-strict-batch <0\|1>` | Strict CPU placement for batch | same as --cpu-strict |
| `--prio-batch N` | Thread priority for batch processing | 0 |
| `--poll-batch <0\|1>` | Polling for batch work | same as --poll |

## Context & Prediction

| Parameter | Description | Default |
|-----------|-------------|---------|
| `-c, --ctx-size N` | Prompt context size (0 = from model) | 0 |
| `-n, --predict, --n-predict N` | Tokens to predict (-1 = infinity, -2 = until context filled) | -1 |
| `--keep N` | Tokens to keep from initial prompt (-1 = all) | 0 |
| `--swa-full` | Use full-size SWA cache | false |

## Batch Sizes

| Parameter | Description | Default |
|-----------|-------------|---------|
| `-b, --batch-size N` | Logical maximum batch size | 2048 |
| `-ub, --ubatch-size N` | Physical maximum batch size | 512 |

## Attention

| Parameter | Description | Default |
|-----------|-------------|---------|
| `-fa, --flash-attn [on\|off\|auto]` | Flash Attention mode | auto |

## Prompt Input

| Parameter | Description | Default |
|-----------|-------------|---------|
| `-p, --prompt PROMPT` | Prompt to start generation | - |
| `-f, --file FNAME` | File containing the prompt | none |
| `-bf, --binary-file FNAME` | Binary file containing the prompt | none |
| `-e, --escape, --no-escape` | Process escape sequences (\n, \r, \t, etc.) | true |
| `--perf, --no-perf` | Enable internal performance timings | false |

## Model Loading

| Parameter | Description | Default |
|-----------|-------------|---------|
| `-m, --model FNAME` | Model path to load | - |
| `-mu, --model-url MODEL_URL` | Model download URL | unused |
| `-dr, --docker-repo [<repo>/]<model>[:quant]` | Docker Hub model repo | unused |
| `-hf, -hfr, --hf-repo <user>/<model>[:quant]` | Hugging Face model repo (auto-downloads mmproj) | unused |
| `-hff, --hf-file FILE` | Hugging Face model file (overrides quant in --hf-repo) | unused |
| `-hft, --hf-token TOKEN` | Hugging Face access token (default: HF_TOKEN env) | HF_TOKEN |
| `-lm, --load-mode MODE` | Model loading mode: auto, none, mmap, mlock, mmap+mlock, dio | auto |
| `--mlock` | DEPRECATED: use --load-mode mlock | - |
| `--mmap, --no-mmap` | DEPRECATED: use --load-mode | - |
| `-dio, --direct-io` | DEPRECATED: use --load-mode dio | - |

## GPU Offloading

| Parameter | Description | Default |
|-----------|-------------|---------|
| `-ngl, --gpu-layers, --n-gpu-layers N` | Layers to store in VRAM (exact number, 'auto', or 'all') | auto |
| `-sm, --split-mode {none,layer,row,tensor}` | Multi-GPU split mode | layer |
| `-ts, --tensor-split N0,N1,...` | Fraction of model per GPU | - |
| `-mg, --main-gpu INDEX` | Main GPU index | 0 |
| `-dev, --device <dev1,dev2,...>` | Devices for offloading (none = don't offload) | auto |
| `--list-devices` | Print available devices and exit | - |
| `-ot, --override-tensor <pattern>=<buffer type>` | Override tensor buffer type | - |
| `-fit, --fit [on\|off]` | Adjust args to fit in device memory | on |
| `-fitt, --fit-target MiB0,...` | Target margin per device for --fit | 1024 |
| `-fitc, --fit-ctx N` | Minimum ctx size for --fit | 4096 |

## MoE (Mixture of Experts)

| Parameter | Description | Default |
|-----------|-------------|---------|
| `-cmoe, --cpu-moe` | Keep all MoE weights in CPU | - |
| `-ncmoe, --n-cpu-moe N` | Keep first N MoE layers in CPU | - |

## KV Cache

| Parameter | Description | Default |
|-----------|-------------|---------|
| `-ctk, --cache-type-k TYPE` | KV cache type for K (f32, f16, bf16, q8_0, q4_0, q4_1, iq4_nl, q5_0, q5_1) | f16 |
| `-ctv, --cache-type-v TYPE` | KV cache type for V (same values) | f16 |
| `-kvo, --kv-offload` | Enable KV cache offloading | enabled |
| `-np, --parallel N` | Number of parallel sequences | 1 |

## RoPE (Rotary Position Embedding)

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--rope-scaling {none,linear,yarn}` | RoPE frequency scaling method | linear (or model default) |
| `--rope-scale N` | Context scaling factor | - |
| `--rope-freq-base N` | RoPE base frequency | from model |
| `--rope-freq-scale N` | RoPE frequency scaling factor | - |

## YaRN

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--yarn-orig-ctx N` | Original context size | 0 (model training size) |
| `--yarn-ext-factor N` | Extrapolation mix factor | -1.0 (full interpolation) |
| `--yarn-attn-factor N` | Attention magnitude scale | -1.0 |
| `--yarn-beta-slow N` | High correction dim (alpha) | -1.0 |
| `--yarn-beta-fast N` | Low correction dim (beta) | -1.0 |

## Model Metadata & Overrides

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--check-tensors` | Check tensor data for invalid values | false |
| `--override-kv KEY=TYPE:VALUE` | Override model metadata (types: int, float, bool, str) | - |
| `--repack, -nr, --no-repack` | Enable weight repacking | enabled |
| `--no-host` | Bypass host buffer | - |
| `--op-offload, --no-op-offload` | Offload host tensor ops to device | true |

## LoRA & Control Vectors

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--lora FNAME` | LoRA adapter path (comma-separated for multiple) | - |
| `--lora-scaled FNAME:SCALE,...` | LoRA adapter with custom scaling | - |
| `--control-vector FNAME` | Control vector (comma-separated for multiple) | - |
| `--control-vector-scaled FNAME:SCALE,...` | Control vector with custom scaling | - |
| `--control-vector-layer-range START END` | Layer range for control vectors | - |

## Networking & RPC

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--rpc SERVERS` | Comma-separated RPC servers (host:port) | - |
| `--offline` | Offline mode (forces cache, no network) | - |

## Logging

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--log-disable` | Disable logging | - |
| `--log-file FNAME` | Log to file | - |
| `--log-colors [on\|off\|auto]` | Colored logging | auto |
| `-v, --verbose` | Maximum verbosity | - |
| `-lv, --verbosity N` | Verbosity threshold (0=generic, 1=error, 2=warning, 3=info, 4=trace, 5=debug) | 3 |
| `--log-prefix, --no-log-prefix` | Log message prefix | - |
| `--log-timestamps, --no-log-timestamps` | Log timestamps | - |
| `--log-prompts-dir PATH` | Log prompts to directory | disabled |

---

## Sampling Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--samplers SAMPLERS` | Samplers in order, separated by ';' | penalties;dry;top_n_sigma;top_k;typ_p;top_p;min_p;xtc;temperature |
| `-s, --seed SEED` | RNG seed (-1 = random) | -1 |
| `--sampler-seq SEQUENCE` | Simplified sampler sequence | edskypmxt |
| `--ignore-eos` | Ignore end-of-stream token | - |
| `--temp, --temperature N` | Temperature | 0.80 |
| `--top-k N` | Top-k sampling (0 = disabled) | 40 |
| `--top-p N` | Top-p sampling (1.0 = disabled) | 0.95 |
| `--min-p N` | Min-p sampling (0.0 = disabled) | 0.05 |
| `--top-nsigma N` | Top-n-sigma sampling (-1.0 = disabled) | -1.0 |
| `--xtc-probability N` | XTC probability (0.0 = disabled) | 0.0 |
| `--xtc-threshold N` | XTC threshold (1.0 = disabled) | 0.1 |
| `--typical-p N` | Locally typical sampling (1.0 = disabled) | 1.0 |
| `--repeat-last-n N` | Last n tokens for repetition penalty (0 = disabled) | 64 |
| `--repeat-penalty N` | Repeat penalty (1.0 = disabled) | 1.0 |
| `--presence-penalty N` | Presence penalty (0.0 = disabled) | 0.0 |
| `--frequency-penalty N` | Frequency penalty (0.0 = disabled) | 0.0 |

### DRY Sampling

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--dry-multiplier N` | DRY multiplier (0.0 = disabled) | 0.0 |
| `--dry-base N` | DRY base value | 1.75 |
| `--dry-allowed-length N` | Allowed repetition length | 2 |
| `--dry-penalty-last-n N` | DRY penalty for last n tokens | 64 |
| `--dry-sequence-breaker STRING` | Sequence breaker (clears defaults) | - |

### Adaptive-P

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--adaptive-target N` | Target probability (0.0-1.0; negative = disabled) | -1.0 |
| `--adaptive-decay N` | Decay rate for target adaptation | 0.90 |

### Dynamic Temperature

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--dynatemp-range N` | Dynamic temperature range (0.0 = disabled) | 0.0 |
| `--dynatemp-exp N` | Dynamic temperature exponent | 1.0 |

### Mirostat

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--mirostat N` | Mirostat mode (0=disabled, 1=v1, 2=v2) | 0 |
| `--mirostat-lr N` | Learning rate (eta) | 0.10 |
| `--mirostat-ent N` | Target entropy (tau) | 5.00 |

### Logit Bias

| Parameter | Description | Default |
|-----------|-------------|---------|
| `-l, --logit-bias TOKEN_ID(+/-)BIAS` | Modify token likelihood | - |

### Constrained Generation

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--grammar GRAMMAR` | BNF-like grammar | - |
| `--grammar-file FNAME` | Grammar file | - |
| `-j, --json-schema SCHEMA` | JSON schema for constrained output | - |
| `-jf, --json-schema-file FILE` | JSON schema file | - |
| `-bs, --backend-sampling` | Backend sampling (experimental) | disabled |

---

## CLI-Specific Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--server-base URL` | Connect to existing server | none |
| `--verbose-prompt` | Print verbose prompt | false |
| `--display-prompt, --no-display-prompt` | Print prompt at generation | true |
| `-co, --color [on\|off\|auto]` | Colorize output | auto |
| `-sys, --system-prompt PROMPT` | System prompt | - |
| `-sysf, --system-prompt-file FNAME` | System prompt file | none |
| `-r, --reverse-prompt PROMPT` | Halt generation at prompt | - |
| `-sp, --special` | Special tokens output | false |
| `-cnv, --conversation` | Conversation mode | auto (if template available) |
| `-st, --single-turn` | Single turn, then exit | false |
| `-mli, --multiline-input` | Multiline input | - |
| `--warmup, --no-warmup` | Warmup with empty run | enabled |
| `--show-timings, --no-show-timings` | Show timing info | true |
| `--simple-io` | Basic IO for subprocesses | - |
| `-ctxcp, --ctx-checkpoints N` | Max context checkpoints per slot | 32 |
| `-cram, --cache-ram N` | Max cache size in MiB | 8192 |
| `--context-shift, --no-context-shift` | Context shift on infinite generation | disabled |

### Multimodal

| Parameter | Description | Default |
|-----------|-------------|---------|
| `-mm, --mmproj FILE` | Multimodal projector file | - |
| `-mmu, --mmproj-url URL` | Multimodal projector URL | - |
| `--mmproj-auto, --no-mmproj` | Auto-use mmproj if available | enabled |
| `--mmproj-offload, --no-mmproj-offload` | GPU offload mmproj | enabled |
| `--image, --audio, --video FILE` | Media file path (comma-separated) | - |
| `--image-min-tokens N` | Min tokens per image | from model |
| `--image-max-tokens N` | Max tokens per image | from model |

### Chat Template

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--chat-template JINJA_TEMPLATE` | Custom Jinja chat template | from model metadata |
| `--chat-template-file FILE` | Custom Jinja template file | from model metadata |
| `--jinja, --no-jinja` | Use Jinja template engine | enabled |
| `--chat-template-kwargs STRING` | Additional JSON params for template | - |
| `--skip-chat-parsing, --no-skip-chat-parsing` | Force pure content parser | disabled |

### Reasoning / Thinking

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--reasoning-format FORMAT` | Thought tag handling (none/deepseek/deepseek-legacy) | auto |
| `-rea, --reasoning [on\|off\|auto]` | Enable reasoning in chat | auto |
| `--reasoning-effort LEVEL` | Reasoning effort (minimal/low/medium/high/xhigh/max) | default |
| `--reasoning-budget N` | Token budget (-1=unlimited, 0=immediate end) | -1 |
| `--reasoning-budget-message MESSAGE` | Message when budget exhausted | none |
| `--reasoning-preserve, --no-reasoning-preserve` | Preserve reasoning trace in history | template default |

### Output

| Parameter | Description | Default |
|-----------|-------------|---------|
| `-o, --output, --output-file FNAME` | Output file | '' |

---

## Speculative Decoding Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--spec-draft-model, -md, --model-draft FNAME` | Draft model for speculative decoding | unused |
| `--spec-type TYPE` | Speculative decoding type (none, draft-simple, draft-eagle3, draft-mtp, draft-dflash, draft-dspark, ngram-simple, ngram-map-k, ngram-map-k4v, ngram-mod, ngram-cache) | none |
| `--spec-draft-n-max N` | Max draft tokens | 3 |
| `--spec-draft-n-min N` | Min draft tokens | 0 |
| `--spec-draft-p-split P` | Split probability | 0.10 |
| `--spec-draft-p-min P` | Min speculative probability (greedy) | 0.00 |
| `--spec-draft-ngl, -ngld N` | Draft model GPU layers | auto |
| `--spec-draft-device, -devd <dev1,dev2,...>` | Draft model devices | - |
| `--spec-draft-threads, -td N` | Draft model threads | same as --threads |
| `--spec-ngram-mod-n-min N` | Ngram-mod minimum tokens | 48 |
| `--spec-ngram-mod-n-max N` | Ngram-mod maximum tokens | 64 |
| `--spec-ngram-mod-n-match N` | Ngram-mod lookup length | 24 |
| `--spec-ngram-simple-size-n N` | Ngram-simple lookup length | 12 |
| `--spec-ngram-simple-size-m N` | Ngram-simple draft length | 48 |
| `--spec-ngram-simple-min-hits N` | Ngram-simple minimum hits | 1 |
| `--spec-ngram-map-k-size-n N` | Ngram-map-k lookup length | 12 |
| `--spec-ngram-map-k-size-m N` | Ngram-map-k draft length | 48 |
| `--spec-ngram-map-k-min-hits N` | Ngram-map-k minimum hits | 1 |
| `--spec-ngram-map-k4v-size-n N` | Ngram-map-k4v lookup length | 12 |
| `--spec-ngram-map-k4v-size-m N` | Ngram-map-k4v draft length | 48 |
| `--spec-ngram-map-k4v-min-hits N` | Ngram-map-k4v minimum hits | 1 |
| `--spec-draft-backend-sampling` | Offload draft sampling to backend | enabled |

### Draft Model KV Cache

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--spec-draft-type-k, -ctkd TYPE` | Draft model K cache type | f16 |
| `--spec-draft-type-v, -ctvd TYPE` | Draft model V cache type | f16 |

### Draft Model CPU/MoE

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--spec-draft-cpu-mask, -Cd M` | Draft model CPU affinity mask | same as --cpu-mask |
| `--spec-draft-cpu-range, -Crd lo-hi` | Draft model CPU range | - |
| `--spec-draft-cpu-strict <0\|1>` | Draft model strict CPU placement | same as --cpu-strict |
| `--spec-draft-prio N` | Draft model thread priority | 0 |
| `--spec-draft-cpu-moe` | Keep all MoE weights in CPU for draft | - |
| `--spec-draft-n-cpu-moe N` | Keep first N MoE layers in CPU for draft | - |
