# llama.cpp HTTP Server - Overview

## What is llama-server?

`llama-server` is a fast, lightweight, pure C/C++ HTTP server built on [httplib](https://github.com/yhirose/cpp-httplib), [nlohmann::json](https://github.com/nlohmann/json), and **llama.cpp**. It provides a set of LLM REST APIs and a web UI to interact with llama.cpp.

### Key Features

- LLM inference of F16 and quantized models on GPU and CPU
- OpenAI API compatible chat completions, responses, and embeddings routes
- Anthropic Messages API compatible chat completions
- Reranking endpoint
- Parallel decoding with multi-user support
- Continuous batching
- Multimodal support with OpenAI-compatible API
- Monitoring endpoints
- Schema-constrained JSON response format
- Prefilling of assistant messages similar to the Claude API
- Function calling / tool use for ~any model
- Speculative decoding
- Easy-to-use web UI

## Quick Start

### Unix-based systems (Linux, macOS, etc.)

```bash
./llama-server -m models/7B/ggml-model.gguf -c 2048
```

### Windows

```powershell
llama-server.exe -m models\7B\ggml-model.gguf -c 2048
```

The server listens on `127.0.0.1:8080` by default. You can consume the endpoints with Postman, NodeJS with axios, or visit the web UI at the same URL.

### Docker

```bash
# CPU only
docker run -p 8080:8080 -v /path/to/models:/models \
  ghcr.io/ggml-org/llama.cpp:server \
  -m models/7B/ggml-model.gguf -c 512 --host 0.0.0.0 --port 8080

# With CUDA
docker run -p 8080:8080 -v /path/to/models:/models --gpus all \
  ghcr.io/ggml-org/llama.cpp:server-cuda \
  -m models/7B/ggml-model.gguf -c 512 --host 0.0.0.0 --port 8080 --n-gpu-layers 99
```

### Docker Compose with Environment Variables

```yaml
services:
  llamacpp-server:
    image: ghcr.io/ggml-org/llama.cpp:server
    ports:
      - 8080:8080
    volumes:
      - ./models:/models
    environment:
      LLAMA_ARG_MODEL: /models/my_model.gguf
      LLAMA_ARG_CTX_SIZE: 4096
      LLAMA_ARG_N_PARALLEL: 2
      LLAMA_ARG_ENDPOINT_METRICS: 1
      LLAMA_ARG_PORT: 8080
```

## Build from Source

```bash
# Standard build
cmake -B build
cmake --build build --config Release -t llama-server
# Binary at ./build/bin/llama-server

# With SSL support (OpenSSL 3)
cmake -B build -DLLAMA_OPENSSL=ON
cmake --build build --config Release -t llama-server
```

## Basic Configuration

### Environment Variables

All command-line arguments can also be set via environment variables with `LLAMA_ARG_` prefix. If both are set, the command-line argument takes precedence.

**String options** example (`--load-mode`):
- `LLAMA_ARG_LOAD_MODE=auto` (default)
- `LLAMA_ARG_LOAD_MODE=none` disables special loading
- `LLAMA_ARG_LOAD_MODE=mmap` enables memory-mapping
- `LLAMA_ARG_LOAD_MODE=mlock` locks the model in RAM
- `LLAMA_ARG_LOAD_MODE=dio` uses DirectIO

**Boolean options** example (`--kv-offload`):
- `LLAMA_ARG_KV_OFFLOAD=true` / `1` / `on` / `enabled`
- `LLAMA_ARG_KV_OFFLOAD=false` / `0` / `off` / `disabled`

### Using with CURL

```sh
curl --request POST \
    --url http://localhost:8080/completion \
    --header "Content-Type: application/json" \
    --data '{"prompt": "Building a website can be done in 10 simple steps:","n_predict": 128}'
```

## Router Mode (Multiple Models)

`llama-server` supports a **router mode** for dynamically loading/unloading models. Launch without specifying a model:

```sh
llama-server
```

### Model Sources

1. **Cached models** (controlled by `LLAMA_CACHE` env var)
2. **Custom model directory** (`--models-dir` argument)
3. **Custom preset** (`--models-preset` argument)

### Model Presets

Define custom configurations using an `.ini` file:

```ini
version = 1

[*]
c = 8192
n-gpu-layers = 8

[ggml-org/MY-MODEL-GGUF:Q8_0]
chat-template = chatml
n-gpu-layers = 123
jinja = true
c = 4096
```

### Routing Requests

- **POST** endpoints: Uses `"model"` field in JSON body
- **GET** endpoints: Uses `model` query parameter

## Sleeping on Idle

The server supports automatic sleep mode after inactivity:

```bash
./llama-server -m model.gguf --sleep-idle-seconds 300
```

When sleeping, the model and KV cache are unloaded. New requests trigger automatic reload.

Exempt endpoints (don't trigger reload):
- `GET /health`
- `GET /props`
- `GET /models`
- `GET /metrics`

## CORS Configuration

| Deployment | Recommendation |
| ---------- | --------------- |
| Public | Set API key, use reverse proxy, `--cors-origins` optional |
| Local network | Set `--cors-origins` to your frontend's origin |
| Same machine | `--cors-origins localhost` (default with `--agent`) |

## Multimodal Support

Available in:
- OAI-compatible chat endpoint
- Non-OAI-compatible completions endpoint
- Non-OAI-compatible embeddings endpoint

## Server Tools

Enable LLM access to local file system from Web UI:

```bash
./llama-server -m model.gguf --tools all
```

Available tools: `read_file`, `file_glob_search`, `grep_search`, `exec_shell_command`, `write_file`, `edit_file`, `get_info`

## MCP Server Support

Configure MCP servers via JSON:

```json
{
  "mcpServers": {
    "example": { "command": "/path/to/server", "args": [] }
  }
}
```

```sh
llama-server -m model.gguf --mcp-servers-config mcp.json
```
