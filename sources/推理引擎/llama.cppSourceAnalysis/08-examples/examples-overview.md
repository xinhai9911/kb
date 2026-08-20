# Module 08: Examples Overview

**LLM**: deepseek-v3.2 | **Model**: gpt-5.3-codex-2 | **Tools**: find, rg, edit, read, write

---

## What It Covers

The `examples/` module contains ~40 example programs demonstrating llama.cpp features — from simple inference to speculative decoding, embeddings, web UIs, and educational tools. Each example is a self-contained, buildable program.

## Key Concepts

### Example Categories

| Category | Examples |
|----------|----------|
| **Inference** | `simple`, `main`, `speculative`, `lookup`, `llama-bench`, `imatrix` |
| **Embeddings** | `embedding`, `llama-embedding` |
| **Grammar** | `grammar-constrained`, `grammar-write`, `llama-gbnf-convert`, `glaive-function-calling` |
| **Server/UI** | `llama.cpp.demo`, `simple-ui`, `simple-tts`, `swagger`, `openai-compatibility` |
| **Benchmarks** | `llama-bench`, `llama-perf` |
| **Education** | `train-text-from-scratch`, `quantize-stats`, `vdot`, `llama-eval-callback` |
| **API/Libraries** | `simple-llama-runner-sdk`, `rpc`, `infill` |
| **Multi-modal** | `llava-cli`, `moondream-vision`, `minicpm-v` |

### Build & Run
- All examples can be built with CMake
- Run examples after building (or download release binaries)

## Files

| Directory | Purpose |
|-----------|---------|
| `examples/simple/` | Minimal example (simple completion) |
| `examples/embedding/` | Text embedding example |
| `examples/speculative/` | Speculative decoding (draft + target model) |
| `examples/main/` | Full-featured command-line inference |
| `examples/llava-cli/` | Vision/multimodal example (LLaVA) |
| `examples/llama-bench/` | Performance benchmarking tool |
| `examples/rpc/` | RPC server/client for distributed inference |
| `examples/infill/` | Code infilling (suffix/prefix completion) |

## Usage Guidance

1. Choose an example relevant to your use case
2. Build with CMake: `cmake --build build --config Release`
3. Run the example binary with appropriate model files
4. Check each example's `README.md` for specific CLI flags and options

## Cross-Module Links

- **04-API/llama-server**: Production server (the `examples/simple-ui` or `llama.cpp.demo` are simpler alternatives)
- **07-grammars**: Grammar usage is demonstrated in `grammar-constrained` and `grammar-write` examples
- **09-development**: `CONTRIBUTING.md` and `AGENTS.md` — how to contribute new examples
- **14-python**: Python API is used in several examples (e.g., `train-text-from-scratch`)
