# llama-completion - Parameters Reference

`llama-completion` uses the same parameter set as `llama-cli`. This document focuses on completion-specific parameters and usage patterns.

For the full parameter reference (common, sampling, GPU, etc.), see [cli-params.md](cli-params.md).

---

## Completion-Specific Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--verbose-prompt` | Print verbose prompt before generation | false |
| `--display-prompt, --no-display-prompt` | Print prompt at generation | true |
| `-co, --color [on\|off\|auto]` | Colorize output to distinguish prompt/user/generation | auto |
| `--context-shift, --no-context-shift` | Context shift on infinite text generation | disabled |
| `-sys, --system-prompt PROMPT` | System prompt (depends on chat template) | - |
| `-sysf, --system-prompt-file FNAME` | System prompt file | none |
| `-ptc, --print-token-count N` | Print token count every N tokens | -1 |
| `--prompt-cache FNAME` | File to cache prompt state | none |
| `--prompt-cache-all` | Save user input and generations to cache | - |
| `--prompt-cache-ro` | Use prompt cache without updating | - |
| `-r, --reverse-prompt PROMPT` | Halt generation at PROMPT, return control in interactive mode | - |
| `-sp, --special` | Special tokens output enabled | false |
| `-cnv, --conversation` | Conversation mode (no special tokens, interactive) | auto |
| `-st, --single-turn` | Single turn only, then exit | false |
| `-i, --interactive` | Interactive mode | false |
| `-if, --interactive-first` | Interactive mode, wait for input immediately | false |
| `-mli, --multiline-input` | Multiline input without trailing `\` | - |
| `--in-prefix-bos` | Prefix BOS to user inputs | - |
| `--in-prefix STRING` | String to prefix user inputs | empty |
| `--in-suffix STRING` | String to suffix user inputs | empty |
| `--warmup, --no-warmup` | Warmup with empty run | enabled |
| `-gan, --grp-attn-n N` | Group-attention factor | 1 |
| `-gaw, --grp-attn-w N` | Group-attention width | 512 |
| `--jinja, --no-jinja` | Jinja template engine for chat | disabled |
| `--reasoning-format FORMAT` | Thought tag handling (none/deepseek/deepseek-legacy) | auto |
| `-rea, --reasoning [on\|off\|auto]` | Reasoning/thinking in chat | auto |
| `--reasoning-effort LEVEL` | Reasoning effort (minimal/low/medium/high/xhigh/max) | default |
| `--reasoning-budget N` | Token budget for thinking (-1=unlimited, 0=end) | -1 |
| `--reasoning-budget-message MESSAGE` | Message when budget exhausted | none |
| `--reasoning-preserve, --no-reasoning-preserve` | Preserve reasoning trace in history | template default |
| `--chat-template JINJA_TEMPLATE` | Custom Jinja chat template (string, not filename) | from model metadata |
| `--chat-template-file FILE` | Custom Jinja chat template file | from model metadata |
| `--chat-template-kwargs STRING` | Additional JSON params for template parser | - |
| `--skip-chat-parsing, --no-skip-chat-parsing` | Force pure content parser | disabled |
| `--simple-io` | Basic IO for subprocesses and limited consoles | - |

---

## Common Parameter Summary

These are the most commonly used parameters (full list in [cli-params.md](cli-params.md)):

### Model Selection

| Parameter | Description | Default |
|-----------|-------------|---------|
| `-m, --model FNAME` | Model file path | - |
| `-hf, --hf-repo <user>/<model>[:quant]` | Hugging Face repo (auto-downloads) | unused |
| `-hff, --hf-file FILE` | Hugging Face file override | unused |
| `-mu, --model-url MODEL_URL` | Remote model URL | unused |
| `-mm, --mmproj FILE` | Multimodal projector file | - |

### Generation Length

| Parameter | Description | Default |
|-----------|-------------|---------|
| `-n, --predict N` | Tokens to predict (-1=infinity, -2=context fill) | -1 |
| `-c, --ctx-size N` | Context size (0=from model) | 0 |
| `--keep N` | Tokens to keep from initial prompt (-1=all) | 0 |

### Performance

| Parameter | Description | Default |
|-----------|-------------|---------|
| `-t, --threads N` | CPU threads for generation | -1 (auto) |
| `-tb, --threads-batch N` | Threads for batch processing | same as -t |
| `-ngl, --gpu-layers N` | GPU layers (exact, 'auto', or 'all') | auto |
| `-fa, --flash-attn [on\|off\|auto]` | Flash Attention | auto |
| `-b, --batch-size N` | Logical batch size | 2048 |
| `-ub, --ubatch-size N` | Physical batch size | 512 |

### Sampling

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--temp N` | Temperature | 0.80 |
| `--top-k N` | Top-k sampling (0=disabled) | 40 |
| `--top-p N` | Top-p sampling (1.0=disabled) | 0.95 |
| `--min-p N` | Min-p sampling (0.0=disabled) | 0.05 |
| `-s, --seed SEED` | RNG seed (-1=random) | -1 |
| `--repeat-penalty N` | Repeat penalty (1.0=disabled) | 1.0 |

### KV Cache

| Parameter | Description | Default |
|-----------|-------------|---------|
| `-ctk, --cache-type-k TYPE` | K cache type (f32, f16, bf16, q8_0, q4_0, etc.) | f16 |
| `-ctv, --cache-type-v TYPE` | V cache type | f16 |
| `-np, --parallel N` | Parallel sequences | 1 |

---

## Usage Patterns

### One-Shot Completion

```bash
# Basic one-shot
./llama-completion -m model.gguf --prompt "Hello, world!"

# With system prompt
./llama-completion -m model.gguf -sys "You are a helpful assistant" -p "What is AI?"

# With JSON schema constraint
./llama-completion -m model.gguf -j '{"type":"object","properties":{"name":{"type":"string"}}}' -p "Generate a name"

# Specific token count
./llama-completion -m model.gguf -n 100 -p "Write a haiku about coding"
```

### Interactive Mode

```bash
# Basic interactive
./llama-completion -m model.gguf -i

# Interactive with reverse prompt
./llama-completion -m model.gguf -i -r "User:" --in-prefix " " --in-suffix "Assistant:"

# Interactive-first (wait for input before generating)
./llama-completion -m model.gguf --interactive-first
```

### Conversation Mode

```bash
# Auto-detect template
./llama-completion -m model.gguf -cnv

# Specific template
./llama-completion -m model.gguf --chat-template llama3 -cnv

# Jinja template
./llama-completion -m model.gguf --jinja -cnv

# Single turn conversation
./llama-completion -m model.gguf --jinja --single-turn -sys "You are a pirate" -p "Arr!"
```

### Infinite Generation

```bash
# Generate forever (with context shift)
./llama-completion -m model.gguf --context-shift -n -1

# Generate forever (stop when context full)
./llama-completion -m model.gguf -n -2

# Generate forever (ignore EOS)
./llama-completion -m model.gguf --ignore-eos -n -1
```

### Multimodal

```bash
# Image input
./llama-completion -m model.gguf --mmproj mmproj.gguf --image photo.jpg --prompt "Describe this image"

# Multiple images
./llama-completion -m model.gguf --mmproj mmproj.gguf --image img1.jpg,img2.jpg --prompt "Compare these images"
```

### Prompt Caching

```bash
# Create and use prompt cache
./llama-completion -m model.gguf --prompt-cache cache.bin --prompt "System: you are..."

# Subsequent runs use cache
./llama-completion -m model.gguf --prompt-cache cache.bin --prompt "Follow up question"

# Read-only cache
./llama-completion -m model.gguf --prompt-cache cache.bin --prompt-cache-ro --prompt "Question"
```

---

## Sampling Parameter Details

### Top-K vs Top-P vs Min-P

- **Top-k** (`--top-k`): Consider only the K most probable tokens. Lower = more focused.
- **Top-p** (`--top-p`): Consider tokens whose cumulative probability exceeds P. Higher = more diverse.
- **Min-p** (`--min-p`): Filter tokens with probability below P * max_probability. Higher = more selective.

### DRY Repetition Penalty

DRY (Don't Repeat Yourself) is more effective than simple repeat penalty for long contexts:

```bash
./llama-completion --dry-multiplier 0.8 --dry-base 1.75 \
  --dry-allowed-length 2 --dry-penalty-last-n 64 \
  --dry-sequence-breaker "##"
```

### XTC (Exclude Top Choices)

Removes top tokens to avoid obvious/repetitive outputs:

```bash
./llama-completion --xtc-probability 0.5 --xtc-threshold 0.1
```

### Adaptive-P

Selects tokens near a configurable target probability:

```bash
./llama-completion --adaptive-target 0.55 --adaptive-decay 0.9
```

### Logit Bias

Modify likelihood of specific tokens:

```bash
# Increase likelihood of "Hello"
./llama-completion --logit-bias 15043+1

# Never produce backslash (prevents LaTeX codes)
./llama-completion --logit-bias 29905-inf
```
