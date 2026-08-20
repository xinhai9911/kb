# Module 11: UI Overview

**LLM**: deepseek-v3.2 | **Model**: gpt-5.3-codex-2 | **Tools**: find, rg, edit, read, write

---

## What It Covers

The web UI system in llama.cpp — a SvelteKit-based chat interface that connects to `llama-server`. Supports MODEL mode (direct to one model) or ROUTER mode (multiple models via load balancing).

## Key Concepts

### UI Architecture
- Built with **SvelteKit** (frontend) and communicates with `llama-server` via HTTP
- **MODEL mode**: Connects to a single model endpoint
- **ROUTER mode**: Connects to multiple models; load balancing/round-robin across them
- Streaming responses for real-time interaction
- File attachments and conversation branching supported

### Features
- Streaming chat interface
- File attachment support
- Conversation branching (fork conversations)
- Responsive design
- Server-side and client-side rendering (SvelteKit)

### Running the UI
1. Start `llama-server` with a model
2. Start the SvelteKit UI (separate process, or use `--host` flag)
3. Configure API endpoint in UI settings

## Files

| Directory | Purpose |
|-----------|---------|
| `tools/ui/` | SvelteKit-based web UI (main frontend) |
| `tools/ui/README.md` | UI documentation: installation, configuration, modes |

## Usage Guidance

- For simple web UI: `tools/ui/` (SvelteKit, production-ready)
- For lightweight/test UIs: `examples/simple-ui/` or `examples/llama.cpp.demo/`
- See `tools/ui/README.md` for full installation and configuration instructions

## Cross-Module Links

- **04-API/llama-server**: The backend that the UI connects to
- **02-prompt-engine**: Chat templates and formatting used by the UI
- **08-examples**: `simple-ui` and `llama.cpp.demo` are lighter-weight UI alternatives
