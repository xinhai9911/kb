# llama-completion - Completion Tool Overview

## What is llama-completion?

`llama-completion` is the text completion and conversational AI tool in llama.cpp. It allows you to interact with LLaMA-family language models for text generation, chat, and instruction-following tasks. It shares the same underlying engine and parameter set as `llama-cli` but is specifically focused on completion-oriented workflows.

## Quick Start

### Download a model

```bash
# From Hugging Face (auto-download)
./llama-completion -hf ggml-org/gemma-1.1-7b-it-Q4_K_M-GGUF

# Or use a local model
./llama-completion -m models/gemma-1.1-7b-it.Q4_K_M.gguf
```

### One-shot completion

```bash
./llama-completion -m models/model.gguf -no-cnv --prompt "Once upon a time"
```

### Conversation mode

```bash
./llama-completion -m models/model.gguf --chat-template gemma
```

### Using Jinja template

```bash
./llama-completion -m models/model.gguf --jinja
```

## Modes of Operation

### One-Shot Mode (Default)

Generate text from a prompt and exit:

```bash
./llama-completion -m models/model.gguf --prompt "The capital of France is"
```

The `--predict` (`-n`) parameter controls how many tokens are generated:
- `-n -1` (default): Generate until EOS or context is full
- `-n -2`: Stop immediately when context fills
- `-n 128`: Generate exactly 128 tokens (or until EOS)

### Interactive Mode

Continuously interact with the model:

```bash
./llama-completion -m models/model.gguf -i
```

- Press `Ctrl+C` to interrupt generation and type your input
- Press `Return` to submit input
- End lines with `\` for multiline input (or use `-mli`)

### Conversation Mode

Automatic chat template handling with special token management:

```bash
./llama-completion -m models/model.gguf -cnv
```

Conversation mode:
- Uses the model's chat template (or a provided one)
- Manages special tokens automatically
- Disables suffix/prefix display
- Enables interactive mode by default

### Single Turn Mode

Process one conversation turn then exit:

```bash
./llama-completion -m models/model.gguf --jinja --single-turn -sys "You are a helpful assistant" -p "Hello"
```

## Server Mode

`llama-completion` can connect to an existing `llama-server` instance instead of loading a model directly:

```bash
./llama-completion --server-base http://localhost:8080 --prompt "Hello"
```

This is useful when:
- Running the model as a persistent service
- Sharing a single model instance across multiple clients
- Offloading model management to a separate process

## Client Mode (Default)

When no `--server-base` is specified, `llama-completion` loads the model locally and runs inference directly. This is the standard operating mode.

## Input Methods

| Method | Parameter | Description |
|--------|-----------|-------------|
| Command line | `--prompt PROMPT` | Provide prompt directly |
| File | `--file FNAME` | Read prompt from file |
| System prompt | `--system-prompt PROMPT` | Set system prompt |
| System prompt file | `--system-prompt-file FNAME` | Read system prompt from file |
| Interactive | `-i` / `--interactive-first` | Wait for user input |
| Multiline | `-mli` | Paste multiple lines without `\` |

## Context Management

### Context Size

```bash
./llama-completion -m models/model.gguf -c 8192 --prompt "Long text..."
```

Default context is loaded from the model. Increase for longer inputs/inference.

### Extended Context (RoPE Scaling)

For fine-tuned models with extended context:

```bash
./llama-completion -m models/model.gguf -c 32768 --rope-scale 8
```

### Context Shift

When generating infinite text (`-n -1`), context shift discards early tokens to make room:

```bash
./llama-completion -m models/model.gguf --context-shift -n -1
```

### Keep Prompt

Retain tokens from the initial prompt across context resets:

```bash
./llama-completion -m models/model.gguf --keep 100 -n -1
```

### Prompt Caching

Cache model state after initial prompt for faster startup:

```bash
./llama-completion -m models/model.gguf --prompt-cache cache.bin --prompt "System setup..."
```

## Chat Templates

### Built-in Templates

```bash
./llama-completion -m models/model.gguf --chat-template gemma
```

Available templates include: chatml, llama2, llama3, gemma, deepseek, mistral, phi3, phi4, vicuna, command-r, zephyr, and many more.

### Jinja Templates

Use the model's built-in Jinja template or provide a custom one:

```bash
# Use model's built-in template
./llama-completion -m models/model.gguf --jinja

# Custom template file
./llama-completion -m models/model.gguf --jinja --chat-template-file my_template.jinja
```

### Reverse Prompts

Pause generation when specific text is encountered:

```bash
./llama-completion -m models/model.gguf -r "User:" --in-prefix " "
```

### In-Prefix and In-Suffix

```bash
# Add space after reverse prompt
./llama-completion -r "User:" --in-prefix " "

# Add assistant prefix after user input
./llama-completion -r "User:" --in-prefix " " --in-suffix "Assistant:"
```

Note: `--in-prefix` and `--in-suffix` disable the chat template.

## Generation Control

### Temperature

```bash
./llama-completion --temp 0.5   # More focused
./llama-completion --temp 1.5   # More creative
./llama-completion --temp 0     # Deterministic
```

### Sampling Methods

```bash
# Top-k
./llama-completion --top-k 30

# Top-p (nucleus)
./llama-completion --top-p 0.95

# Min-p
./llama-completion --min-p 0.05

# Mirostat (controls perplexity)
./llama-completion --mirostat 2 --mirostat-lr 0.05 --mirostat-ent 3.0
```

### Repeat Penalties

```bash
./llama-completion --repeat-penalty 1.2 --repeat-last-n 64
```

### DRY Repetition Penalty

```bash
./llama-completion --dry-multiplier 0.8 --dry-base 1.75 --dry-allowed-length 2
```

### Constrained Generation

```bash
# BNF grammar
./llama-completion --grammar "root ::= [a-z]+"

# JSON schema
./llama-completion -j '{"type": "object", "properties": {"answer": {"type": "string"}}}'
```

## GPU and Performance

### GPU Offloading

```bash
./llama-completion -ngl 32    # Offload all layers
./llama-completion -ngl auto  # Auto-detect
```

### Multi-GPU

```bash
./llama-completion -sm layer -ts 3,1   # Layer split, 75%/25%
```

### Thread Tuning

```bash
./llama-completion -t 8 -tb 16   # 8 gen threads, 16 batch threads
```

### KV Cache Quantization

```bash
./llama-completion -ctk q4_0 -ctv q4_0   # Quantize KV cache to save memory
```

## LoRA Adapters

```bash
# Single adapter
./llama-completion -m models/base.gguf --lora adapters/adapter.gguf

# Multiple adapters with scaling
./llama-completion -m models/base.gguf \
  --lora-scaled adapters/task_a.gguf:0.5 \
  --lora-scaled adapters/task_b.gguf:0.5
```

LoRA adapters must be in GGUF format. Use `convert-lora-to-gguf.py` to convert from Hugging Face format.

## Usage Notes

- Parameters are identical to `llama-cli` (see [cli-params.md](cli-params.md) for full reference)
- The `--no-display-prompt` flag hides the prompt in output
- Use `--show-timings` to display tokens/second metrics
- `--ignore-eos` prevents the model from stopping at EOS tokens
- Use `--special` to display special tokens in output
