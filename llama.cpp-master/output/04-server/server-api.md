# llama.cpp HTTP Server - REST API Endpoints

## Overview

`llama-server` provides REST API endpoints compatible with OpenAI and Anthropic APIs, plus native endpoints. Errors follow the [OpenAI error format](https://github.com/openai/openai-openapi).

### Error Format

```json
{
    "error": {
        "code": 401,
        "message": "Invalid API Key",
        "type": "authentication_error"
    }
}
```

Error types: `authentication_error`, `not_supported_error`, `invalid_request_error`, `unavailable_error`

---

## Health & Status Endpoints

### GET `/health`

Returns health check result. Public endpoint (no API key check). `/v1/health` also works.

**Responses:**

| Status | Body | Meaning |
|--------|------|---------|
| 503 | `{"error": {"code": 503, "message": "Loading model", "type": "unavailable_error"}}` | Model still loading |
| 200 | `{"status": "ok"}` | Ready |

### GET `/props`

Get server global properties. By default read-only; start with `--props` for POST support.

**Response:**

```json
{
  "default_generation_settings": {
    "id": 0,
    "n_ctx": 1024,
    "speculative": false,
    "is_processing": false,
    "params": { ... },
    "next_token": {
      "has_next_token": true,
      "n_remain": -1,
      "n_decoded": 0
    }
  },
  "total_slots": 1,
  "model_path": "../models/Model.gguf",
  "chat_template": "...",
  "chat_template_caps": {},
  "modalities": { "vision": false },
  "is_sleeping": false
}
```

### POST `/props`

Change server global properties. Requires `--props` flag.

---

## OpenAI-Compatible Endpoints

### GET `/v1/models`

Returns information about the loaded model. See [OpenAI Models API](https://platform.openai.com/docs/api-reference/models).

The `id` field defaults to model path; use `--alias` for custom value.

**Response:**

```json
{
    "object": "list",
    "data": [
        {
            "id": "../models/Model.gguf",
            "object": "model",
            "created": 1735142223,
            "owned_by": "llamacpp",
            "meta": {
                "vocab_type": 2,
                "n_vocab": 128256,
                "n_ctx_train": 131072,
                "n_embd": 4096,
                "n_params": 8030261312,
                "size": 4912898304
            }
        }
    ]
}
```

### POST `/v1/chat/completions`

OpenAI-compatible chat completions. Supports synchronous and streaming modes. See [OpenAI Chat API](https://platform.openai.com/docs/api-reference/chat).

**Request:**

```json
{
  "model": "gpt-3.5-turbo",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Write a limerick about python exceptions"}
  ],
  "temperature": 0.7,
  "max_tokens": 512,
  "stream": true
}
```

**Additional options:**

- `response_format`: Supports `{"type": "json_object"}` and schema-constrained JSON
- `chat_template_kwargs`: Additional params for template (e.g., `{"enable_thinking": false}`)
- `reasoning_effort`: Disable reasoning with `"none"` or set effort level
- `reasoning_format`: Raw (`none`), `deepseek`, or `deepseek-legacy`
- `reasoning_control`: Enable realtime reasoning control
- `parse_tool_calls`: Parse generated tool calls
- `parallel_tool_calls`: Enable parallel tool calls

**Multimodal input** (`messages[i].content[j]`):

- `type: "image_url"` - URL, base64, or local file path
- `type: "input_audio"` - URL, base64, or local file (mp3, wav, flac)
- `type: "input_video"` - URL, base64, or local file

**Response (streaming):**

Uses [Server-Sent Events](https://html.spec.whatwg.org/multipage/server-sent-events.html).

**Response (non-streaming):**

```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1757141666,
  "model": "gpt-3.5-turbo",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 44,
    "completion_tokens": 48,
    "total_tokens": 92,
    "prompt_tokens_details": {
      "cached_tokens": 0
    }
  },
  "timings": {
    "cache_n": 236,
    "prompt_n": 1,
    "prompt_ms": 30.958,
    "prompt_per_second": 32.30,
    "predicted_n": 35,
    "predicted_ms": 661.064,
    "predicted_per_second": 52.94
  }
}
```

**Python example:**

```python
import openai

client = openai.OpenAI(
    base_url="http://localhost:8080/v1",
    api_key="sk-no-key-required"
)

completion = client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"}
    ]
)
print(completion.choices[0].message)
```

**curl example:**

```sh
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer no-key" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "Hello!"}
    ]
  }'
```

### POST `/v1/chat/completions/control`

Control a running chat completion in real time. Requires `reasoning_control: true` on original request.

**Request:**

```json
{
  "id": "chatcmpl-abc123",
  "action": "reasoning_end",
  "model": "model-name"
}
```

**Response:**

```json
{
  "success": true
}
```

### POST `/v1/completions`

OpenAI-compatible completions. See [OpenAI Completions API](https://platform.openai.com/docs/api-reference/completions).

**Python example:**

```python
import openai

client = openai.OpenAI(
    base_url="http://localhost:8080/v1",
    api_key="sk-no-key-required"
)

completion = client.completions.create(
    model="davinci-002",
    prompt="I believe the meaning of life is",
    max_tokens=8
)
print(completion.choices[0].text)
```

### POST `/v1/embeddings`

OpenAI-compatible embeddings. Requires model with pooling != `none`. Embeddings normalized with Euclidean norm.

**Request:**

```json
{
  "input": "hello",
  "model": "GPT-4",
  "encoding_format": "float"
}
```

**Request (array):**

```json
{
  "input": ["hello", "world"],
  "model": "GPT-4",
  "encoding_format": "float"
}
```

**curl example:**

```sh
curl http://localhost:8080/v1/embeddings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer no-key" \
  -d '{
    "input": "hello",
    "model": "GPT-4",
    "encoding_format": "float"
  }'
```

### POST `/v1/responses`

OpenAI-compatible Responses API. See [OpenAI Responses API](https://platform.openai.com/docs/api-reference/responses).

**Request:**

```json
{
  "model": "gpt-4.1",
  "instructions": "You are a helpful assistant.",
  "input": "Write a limerick about python exceptions"
}
```

**Python example:**

```python
import openai

client = openai.OpenAI(
    base_url="http://localhost:8080/v1",
    api_key="sk-no-key-required"
)

response = client.responses.create(
    model="gpt-4.1",
    instructions="You are a helpful assistant.",
    input="Write a limerick about python exceptions"
)
print(response.output_text)
```

---

## Anthropic-Compatible Endpoints

### POST `/v1/messages`

Anthropic-compatible Messages API. Tool use requires `--jinja` flag.

**Request:**

```json
{
  "model": "gpt-4",
  "max_tokens": 1024,
  "system": "You are a helpful assistant.",
  "messages": [
    {"role": "user", "content": "Hello!"}
  ],
  "stream": true
}
```

**Options:**

- `model`: Model identifier (required)
- `messages`: Array of message objects (required)
- `max_tokens`: Maximum tokens (default: 4096)
- `system`: System prompt
- `temperature`: 0-1 (default: 1.0)
- `top_p`: Nucleus sampling (default: 1.0)
- `top_k`: Top-k sampling
- `stop_sequences`: Array of stop sequences
- `stream`: Enable streaming (default: false)
- `tools`: Tool definitions (requires `--jinja`)
- `tool_choice`: `{"type": "auto"}`, `{"type": "any"}`, or `{"type": "tool", "name": "..."}`

**curl example:**

```sh
curl http://localhost:8080/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-api-key" \
  -d '{
    "model": "gpt-4",
    "max_tokens": 1024,
    "system": "You are a helpful assistant.",
    "messages": [
      {"role": "user", "content": "Hello!"}
    ]
  }'
```

### POST `/v1/messages/count_tokens`

Count tokens without generating a response. Same params as `/v1/messages` (max_tokens optional).

**Response:**

```json
{"input_tokens": 10}
```

---

## Token Counting Endpoints

### POST `/v1/responses/input_tokens`

Count tokens for Responses API input.

**Response:**

```json
{
  "object": "response.input_tokens",
  "input_tokens": 11
}
```

### POST `/v1/chat/completions/input_tokens`

Count tokens for Chat Completions input. Not an official OAI endpoint.

**Response:**

```json
{
  "object": "response.input_tokens",
  "input_tokens": 11
}
```

---

## Native Endpoints

### POST `/completion`

Non-OAI-compatible completion. Use `/v1/completions` for OAI clients.

**Request:**

```json
{
  "prompt": "Building a website can be done in 10 simple steps:",
  "n_predict": 128,
  "temperature": 0.8,
  "top_k": 40,
  "top_p": 0.95,
  "stream": true,
  "stop": ["\n\n"]
}
```

**Options:**

- `prompt`: String, token array, or mixed (supports multimodal JSON objects)
- `temperature`: Randomness (default: 0.8)
- `top_k`, `top_p`, `min_p`, `typical_p`: Sampling parameters
- `n_predict`: Max tokens to predict (-1 = infinity, 0 = eval only)
- `n_keep`: Tokens to keep from prompt
- `n_cmpl`: Number of completions
- `stop`: Array of stopping strings
- `stream`: Enable streaming
- `seed`: RNG seed (-1 = random)
- `grammar`: BNF grammar constraint
- `json_schema`: JSON schema constraint
- `logit_bias`: Modify token likelihoods
- `n_probs`: Return top N token probabilities
- `cache_prompt`: Re-use KV cache (default: true)
- `return_tokens`: Return raw token IDs
- `samplers`: Sampler order array
- `timings_per_token`: Include timing info
- `lora`: LoRA adapters `[{id, scale}]`

**Response:**

```json
{
  "content": "generated text",
  "tokens": [123, 456, ...],
  "stop": false,
  "stop_type": "eos",
  "stopping_word": "",
  "generation_settings": { ... },
  "model": "model-name",
  "prompt": "processed prompt",
  "timings": { "predicted_per_second": 52.94 },
  "tokens_cached": 100,
  "tokens_evaluated": 150,
  "truncated": false
}
```

`stop_type` values: `none`, `eos`, `limit`, `word`

### POST `/tokenize`

Tokenize text.

**Request:**

```json
{
  "content": "Hello, world!",
  "add_special": false,
  "parse_special": true,
  "with_pieces": false
}
```

**Response (with_pieces: false):**

```json
{"tokens": [123, 456, 789]}
```

**Response (with_pieces: true):**

```json
{
  "tokens": [
    {"id": 123, "piece": "Hello"},
    {"id": 456, "piece": " world"},
    {"id": 789, "piece": "!"}
  ]
}
```

### POST `/detokenize`

Convert tokens to text.

**Request:**

```json
{"tokens": [123, 456, 789]}
```

### POST `/apply-template`

Apply chat template without inference.

**Request:**

```json
{
  "messages": [
    {"role": "user", "content": "Hello!"}
  ]
}
```

**Response:**

```json
{"prompt": "<|begin_of_text|>...formatted prompt..."}
```

### POST `/embedding`

Non-OAI-compatible embeddings. Supports multimodal input.

**Request:**

```json
{
  "content": "text to embed",
  "embd_normalize": 2
}
```

Normalization: -1=none, 0=max absolute, 1=taxicab, 2=euclidean, >2=p-norm

### POST `/embeddings`

Non-OAI-compatible embeddings with different response format. Supports all poolings including `none`.

**Response:**

```json
[
  {
    "index": 0,
    "embedding": [
      [0.1, 0.2, ...],
      [0.3, 0.4, ...]
    ]
  }
]
```

### POST `/reranking`

Rerank documents by query. Requires reranker model and `--embedding --pooling rank`.

**Aliases:** `/rerank`, `/v1/rerank`, `/v1/reranking`

**Request:**

```json
{
  "model": "some-model",
  "query": "What is panda?",
  "top_n": 3,
  "documents": [
    "hi",
    "it is a bear",
    "The giant panda is a bear species endemic to China."
  ]
}
```

**curl example:**

```sh
curl http://127.0.0.1:8012/v1/rerank \
  -H "Content-Type: application/json" \
  -d '{
    "model": "some-model",
    "query": "What is panda?",
    "top_n": 3,
    "documents": ["hi", "it is a bear", "The giant panda is a bear species endemic to China."]
  }' | jq
```

### POST `/infill`

Code infilling (FIM - Fill In the Middle).

**Request:**

```json
{
  "input_prefix": "def fibonacci(n):",
  "input_suffix": "    return result",
  "input_extra": [
    {"filename": "utils.py", "text": "helper function..."}
  ],
  "prompt": ""
}
```

Accepts all options from `/completion`. Uses `FIM_REPO` and `FIM_FILE_SEP` tokens when available.

### GET `/slots`

Get current slots processing state. Enabled by default, disable with `--no-slots`.

Query param `?fail_on_no_slot=1` returns 503 if no slots available.

**Response:**

```json
[
  {
    "id": 0,
    "id_task": 135,
    "n_ctx": 65536,
    "is_processing": true,
    "params": { ... },
    "next_token": {
      "has_next_token": true,
      "n_remain": -1,
      "n_decoded": 136
    }
  }
]
```

### POST `/slots/{id_slot}?action=save`

Save slot prompt cache to file.

**Request:**

```json
{"filename": "slot_save_file.bin"}
```

**Response:**

```json
{
  "id_slot": 0,
  "filename": "slot_save_file.bin",
  "n_saved": 1745,
  "n_written": 14309796,
  "timings": { "save_ms": 49.865 }
}
```

### POST `/slots/{id_slot}?action=restore`

Restore slot prompt cache from file.

**Request:**

```json
{"filename": "slot_save_file.bin"}
```

**Response:**

```json
{
  "id_slot": 0,
  "filename": "slot_save_file.bin",
  "n_restored": 1745,
  "n_read": 14309796,
  "timings": { "restore_ms": 42.937 }
}
```

### POST `/slots/{id_slot}?action=erase`

Erase slot prompt cache.

**Response:**

```json
{
  "id_slot": 0,
  "n_erased": 1745
}
```

### GET `/lora-adapters`

Get loaded LoRA adapters.

**Response:**

```json
[
  {"id": 0, "path": "adapter1.gguf", "scale": 0.0},
  {"id": 1, "path": "adapter2.gguf", "scale": 0.0}
]
```

### POST `/lora-adapters`

Set LoRA adapter scales globally. Use `GET /lora-adapters` for IDs.

**Request:**

```json
[
  {"id": 0, "scale": 0.2},
  {"id": 1, "scale": 0.8}
]
```

---

## Monitoring Endpoints

### GET `/metrics`

Prometheus-compatible metrics. Requires `--metrics`. In router mode, add `?model={model_id}`.

**Available Metrics:**

| Metric | Type | Description |
| ------ | ---- | ----------- |
| `llamacpp:prompt_tokens_total` | Counter | Prompt tokens processed |
| `llamacpp:prompt_seconds_total` | Counter | Prompt process time (seconds) |
| `llamacpp:prompt_tokens_seconds` | Gauge | Prompt throughput (tokens/s) |
| `llamacpp:tokens_predicted_total` | Counter | Generation tokens processed |
| `llamacpp:tokens_predicted_seconds_total` | Counter | Predict time (seconds) |
| `llamacpp:predicted_tokens_seconds` | Gauge | Generation throughput (tokens/s) |
| `llamacpp:requests_processing` | Gauge | Requests processing |
| `llamacpp:requests_deferred` | Gauge | Requests deferred |
| `llamacpp:n_tokens_max` | Counter | High watermark of context size |
| `llamacpp:n_decode_total` | Counter | Total llama_decode() calls |
| `llamacpp:n_busy_slots_per_decode` | Gauge | Avg busy slots per decode |
| `llamacpp:spec_decode_num_draft_tokens_total` | Counter | Draft tokens generated |
| `llamacpp:spec_decode_num_accepted_tokens_total` | Counter | Draft tokens accepted |
| `llamacpp:spec_decode_num_drafts_total` | Counter | Verification steps |

---

## Router Mode Endpoints

### GET `/models`

List all models in cache with status.

**Response:**

```json
{
  "data": [{
    "id": "ggml-org/model-GGUF:Q4_K_M",
    "path": "/path/to/model.gguf",
    "status": {
      "value": "loaded",
      "args": ["llama-server", "-ctx", "4096"]
    },
    "architecture": {
      "input_modalities": ["text", "image"],
      "output_modalities": ["text"]
    }
  }]
}
```

Status values: `unloaded`, `loading`, `loaded`, `sleeping`, `downloading`

Add `?reload=1` to refresh model list.

### POST `/models`

Download a new model (non-blocking). Track via `/models/sse`.

**Request:**

```json
{"model": "ggml-org/model-GGUF:Q4_K_M"}
```

### POST `/models/load`

Load a model.

**Request:**

```json
{"model": "ggml-org/model-GGUF:Q4_K_M"}
```

### POST `/models/unload`

Unload a model. Also cancels model downloading.

**Request:**

```json
{"model": "ggml-org/model-GGUF:Q4_K_M"}
```

### DELETE `/models`

Delete a model from cache. Only cached models can be deleted.

Model name via query param: `?model={name}`

### GET `/models/sse`

Real-time Server-Sent Events for model status changes.

**Events:**

- `model_status` - Status changes (loading, loaded, sleeping)
- `download_progress` - Download progress updates
- `download_finished` - Download completed
- `download_failed` - Download failed
- `model_remove` - Model removed
- `models_reload` - Model list reloaded

---

## Streaming (SSE) Format

Streaming endpoints use [Server-Sent Events](https://html.spec.whatwg.org/multipage/server-sent-events.html). Note: browser's `EventSource` cannot be used (lacks POST support).

**Format:**

```
data: {"content":"token","stop":false}

data: {"content":"","stop":true}

data: [DONE]
```

---

## API Key Authentication

Set with `--api-key` or `LLAMA_API_KEY` env var. Pass in requests:

```sh
curl -H "Authorization: Bearer your-api-key" http://localhost:8080/v1/chat/completions

# Or for Anthropic endpoint:
curl -H "x-api-key: your-api-key" http://localhost:8080/v1/messages
```
