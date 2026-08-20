# Auto-Parser Usage Guide

## How to Use the Auto-Parser

The auto-parser works automatically when `llama-server` is started with `--jinja`. It analyzes the model's chat template at startup and builds appropriate parsers for reasoning, content, and tool calls.

```bash
# Basic usage - auto-parser activates automatically
llama-server --jinja -fa -hf <model-gguf>

# With specific models known to work natively
llama-server --jinja -fa -hf bartowski/Qwen2.5-7B-Instruct-GGUF:Q4_K_M
llama-server --jinja -fa -hf bartowski/Llama-3.3-70B-Instruct-GGUF:Q4_K_M
```

## Function Calling

Function calling is supported via OpenAI-compatible API when `--jinja` is enabled.

### Request Format

```json
{
  "model": "model-name",
  "tools": [{
    "type": "function",
    "function": {
      "name": "get_weather",
      "description": "Get current weather",
      "parameters": {
        "type": "object",
        "properties": {
          "location": {"type": "string", "description": "City name"}
        },
        "required": ["location"]
      }
    }
  }],
  "messages": [
    {"role": "user", "content": "What is the weather in Paris?"}
  ]
}
```

### Response Format

```json
{
  "choices": [{
    "finish_reason": "tool",
    "message": {
      "content": null,
      "tool_calls": [{
        "name": "get_weather",
        "arguments": "{\"location\": \"Paris\"}"
      }],
      "role": "assistant"
    }
  }]
}
```

### Parallel Tool Calls

Enabled per-request:
```json
{"parallel_tool_calls": true}
```

## Configuration Options

### Chat Template Override

When a model lacks a native tool-use template, override it:

```bash
llama-server --jinja -fa -hf <model> \
  --chat-template-file models/templates/<template>.jinja
```

### Using Generic Format

Models without native support fall back to generic format. Use `--chat-template chatml` for a default that works with many models.

### Reasoning Format Control

The auto-parser detects reasoning markers automatically. The `reasoning_format` parameter can be set to:
- `COMMON_REASONING_FORMAT_AUTO` - auto-detect from template

### KV Quantization Warning

Extreme KV quantizations (e.g., `-ctk q4_0`) can substantially degrade tool calling performance. Use conservative quantization for tool-use workloads.

## Debugging

### Template Debugger

Inspect what the auto-parser detects for a given template:

```bash
./bin/llama-debug-template-parser path/to/template.jinja
```

Shows: detected format, markers, generated PEG parser, GBNF grammar.

### Template Analysis

```bash
./bin/llama-template-analysis path/to/template.jinja
```

### Debug Logging

Enable verbose analysis logging:
```bash
LLAMA_ARG_LOG_VERBOSITY=2 ./bin/llama-server --jinja ...
```

Shows detailed analysis steps, pattern extraction, and generated parser structure.

### PEG Test Builder (C++ Tests)

```cpp
auto tst = peg_tester("models/templates/Template.jinja");
tst.test("input text")
   .reasoning_format(COMMON_REASONING_FORMAT_AUTO)
   .tools({tool_json})
   .parallel_tool_calls(true)
   .enable_thinking(true)
   .expect(expected_message)
   .run();
```

## Adding Support for New Templates

### 1. Standard Patterns

If the template follows standard patterns (OpenAI-style JSON tools, Hermes-style XML tags), the auto-parser detects it automatically. Verify with `llama-debug-template-parser`.

### 2. Incorrect Marker Extraction

Add a workaround lambda to the `workarounds` vector in `common/chat-diff-analyzer.cpp`. Inspect the template source for a unique identifying substring.

### 3. Fundamentally Different Handling

Add a dedicated handler function in `common/chat.cpp` before the auto-parser block (as done for GPT-OSS, Functionary v3.2, and Ministral).

## Edge Cases

| Issue | Details |
|-------|---------|
| **Generation Prompt Prefill** | Extracted by diffing `add_generation_prompt=false` vs `true`; prepended to model output before parsing |
| **Per-Call vs Per-Section** | T2 disambiguates by checking if a 2-call output's second call starts with the section marker |
| **Tag Boundary Fixing** | `calculate_diff_split()` avoids splitting mid-tag |
| **Call ID Side Effects** | T7 clears `per_call_end` when call ID incorrectly incorporated |
| **Graceful Degradation** | Undetected tool format returns `eps()` rather than aborting |

## Workarounds for Known Templates

| Template | Workaround |
|----------|-----------|
| Old Qwen/DeepSeek thinking | `<think>`/`</think>` forced if `content.split('</think>')` in source |
| Granite 3.3 | Forced `<think>`/`</think>` + `<response>` markers |
| Cohere Command R+ | `ALWAYS_WRAPPED` content if `<\|CHATBOT_TOKEN\|>` present |
| Functionary 3.1 | Forced `PLAIN` content, specific per-call markers |
| DeepSeek-R1-Distill-Qwen | Unicode block character overrides for `tool_calls_begin` |
