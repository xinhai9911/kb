# Module 10: Architecture Overview

**LLM**: deepseek-v3.2 | **Model**: gpt-5.3-codex-2 | **Tools**: find, rg, edit, read, write

---

## What It Covers

The high-level architecture of llama.cpp — core components, data flow, and how modules interact. Since `docs/specs/` and `docs/tech/` don't exist in the repo, architecture documentation is gathered from `docs/development/`, `docs/` top-level files, `CONTRIBUTING.md`, `AGENTS.md`, and README files.

## Key Concepts

### Core Components

| Component | Role |
|-----------|------|
| **llama.cpp** | Core inference engine — model loading, tokenization, sampling, text generation |
| **ggml** | Low-level tensor library — GPU/CPU compute, memory management |
| **gguf** | Binary model format — file format for quantized/optimized model weights |
| **llama-server** | HTTP API server for production deployment |
| **llama-cli** | Command-line interface for inference and testing |

### Data Flow
```
GGUF model file
    ↓ (llama.cpp: model loading)
Tensor graph (ggml)
    ↓ (ggml: compute)
Logits → Token samples
    ↓ (llama.cpp: tokenization/detokenization)
Output text
```

### Key Design Principles
- **No external dependencies** — fully self-contained
- **Cross-platform** — desktop, mobile, embedded (Raspberry Pi, etc.)
- **Multi-backend** — CPU (x86, ARM), GPU (CUDA, ROCm, Metal, SYCL, Vulkan, MUSA)
- **Quantization-first** — multiple quantization formats (Q4_0 through Q8_0, F16, F32)

### Build System
- CMake-based, no Meson/Ninja required (though supported)
- Builds both standalone tools and library (`libllama`)

## Files

| Directory | Purpose |
|-----------|---------|
| `llama.cpp` | Core inference engine (main source) |
| `ggml/` | Tensor library (low-level compute) |
| `gguf-py/` | Python GGUF package (model conversion utilities) |
| `gguf-py/gguf/` | GGUF format specification and reader/writer code |
| `common/` | Shared code for CLI, server, and examples |
| `src/` | llama library source files (headers for llama.cpp) |

## Usage Guidance

- Refer to `docs/` for overall project documentation
- `docs/development/` contains development-focused docs
- `CONTRIBUTING.md` covers architectural patterns expected in new code

## Cross-Module Links

- **05-model-api**: Core loading and tokenization (the `llama.cpp` engine)
- **06-tensor-gguf**: `ggml/` and `gguf-py/` — tensor operations and model format
- **04-API/llama-server**: `common/` — shared code between CLI and server
- **09-development**: Architectural patterns in contributing guidelines
