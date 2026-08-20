# llama cli - Main CLI Tool Overview

## What is llama cli?

`llama cli` is the primary command-line interface tool in llama.cpp for running LLM inference. It provides a unified entry point for text generation, chat conversations, and multimodal interactions (images, audio, video) with GGUF models on CPU and GPU.

## Quick Start

### Download a model from Hugging Face

```bash
llama-cli -hf ggml-org/gemma-1.1-7b-it-Q4_K_M-GGUF:Q4_K_M
```

### One-shot text generation

```bash
llama-cli -m models/model.gguf --prompt "Once upon a time"
```

### Conversation mode (interactive chat)

```bash
llama-cli -m models/model.gguf --chat-template gemma
```

### With Jinja chat template

```bash
llama-cli -m models/model.gguf --jinja
```

### Single turn with system prompt

```bash
llama-cli -m models/model.gguf --jinja --single-turn -sys "You are a helpful assistant" -p "Hello"
```

## Main Features

### Text Generation Modes
- **One-shot**: Provide a prompt, get a response, then exit
- **Interactive**: Continuously interact with the model, typing input and receiving responses
- **Conversation mode** (`-cnv`): Automatic chat template handling, special token management, and interactive mode

### Multimodal Support
- Load multimodal projector files via `-mm`/`--mmproj`
- Provide images, audio, or video via `--image`, `--audio`, `--video`
- Automatic mmproj download when using `--hf-repo`

### Chat Template System
- Built-in templates: chatml, llama2, llama3, gemma, deepseek, mistral, phi3/4, and many more
- Custom Jinja templates via `--chat-template` or `--chat-template-file`
- Jinja engine for full template compatibility

### Speculative Decoding
- Draft model support via `--spec-draft-model`
- Multiple draft types: `draft-simple`, `draft-eagle3`, `draft-mtp`, `ngram-*`
- Ngram-based speculation without a separate draft model

### GPU Offloading
- Layer-based GPU offloading with `-ngl`
- Multi-GPU split modes: `none`, `layer`, `row`, `tensor`
- Device selection via `-dev`

### Reasoning/Thinking Mode
- Control reasoning format with `--reasoning-format` (none, deepseek, deepseek-legacy)
- Set reasoning effort level with `--reasoning-effort`
- Token budget control with `--reasoning-budget`

## Usage Examples

### CPU-only inference

```bash
llama-cli -m models/llama-7b-q4_k_m.gguf -t 8 -c 4096 --prompt "Hello"
```

### GPU offloading

```bash
llama-cli -m models/llama-7b-q4_k_m.gguf -ngl 32 --prompt "Hello"
```

### With LoRA adapter

```bash
llama-cli -m models/base.gguf --lora adapters/adapter.gguf --prompt "Hello"
```

### With control vector

```bash
llama-cli -m models/base.gguf --control-vector vectors/cv.gguf --prompt "Hello"
```

### Custom chat template

```bash
llama-cli -m models/model.gguf --chat-template "chatml" --jinja -cnv
```

### Constrained generation with grammar

```bash
llama-cli -m models/model.gguf --grammar "root ::= [a-z]+" --prompt "Say hello"
```

### JSON schema output

```bash
llama-cli -m models/model.gguf -j '{"type": "object", "properties": {"name": {"type": "string"}}}' --prompt "Generate a person"
```

### From Hugging Face (auto-download)

```bash
llama-cli -hf ggml-org/GLM-4.7-Flash-GGUF:Q4_K_M
```

### Connect to existing server

```bash
llama-cli --server-base http://localhost:8080 --prompt "Hello"
```

### Infinite text generation

```bash
llama-cli -m models/model.gguf --ignore-eos -n -1
```

## CLI-Specific Parameters

| Parameter | Description |
|-----------|-------------|
| `--server-base URL` | Connect to an existing server instead of loading a model |
| `-cnv` / `-no-cnv` | Conversation mode (auto-enabled if chat template available) |
| `-st` / `--single-turn` | Single turn only, then exit |
| `-co` / `--color` | Colorize output (on/off/auto) |
| `-sys` / `--system-prompt` | System prompt for chat |
| `-mli` / `--multiline-input` | Allow multiline input without trailing backslashes |
| `--show-timings` / `--no-show-timings` | Show timing information |
| `--display-prompt` / `--no-display-prompt` | Print prompt at generation |
| `--reasoning-format` | Control thought tag parsing (none/deepseek/deepseek-legacy) |
| `--reasoning-effort` | Reasoning effort level (minimal/low/medium/high/max) |
| `--reasoning-budget` | Token budget for thinking (-1 = unlimited, 0 = immediate end) |
