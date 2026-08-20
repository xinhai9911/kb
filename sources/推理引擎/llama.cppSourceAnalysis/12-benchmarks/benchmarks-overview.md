# Module 12: Benchmarks Overview

**LLM**: deepseek-v3.2 | **Model**: gpt-5.3-codex-2 | **Tools**: find, rg, edit, read, write

---

## What It Covers

The benchmarking data and tooling in llama.cpp — performance measurements across different hardware, quantization formats, and configurations. Includes the `benches/` directory with real-world results from various hardware.

## Key Concepts

### Benchmark Categories

| Directory | Hardware Focus | Content |
|-----------|---------------|---------|
| `benches/dgx-spark/` | NVIDIA DGX Spark (arm64/aarch64) | Model performance, GPU offload comparisons |
| `benches/mac-m2-ultra/` | Apple M2 Ultra (macOS arm64) | Model performance at various quant levels |
| `benches/nemotron/` | NVIDIA Nemotron (CUDA) | Large-scale CUDA inference benchmarks |

### Benchmark Data Structure
Each benchmark typically includes:
- **Model**: Tested model name/version (e.g., `gpt-oss-20b`)
- **Quantization levels**: Tested Q-levels (Q4_0, Q4_K_M, Q5_K_M, Q8_0, etc.)
- **Performance metrics**: Tokens/second, memory usage, etc.
- **Hardware details**: GPU type, available memory, system specs

### Example (M2 Ultra, from `benches/mac-m2-ultra/mac-m2-ultra.md`)
- Model: gpt-oss-20b
- Quantizations: Q4_0 through Q8_0, F16
- Metrics: Real-time inference performance per quantization level

## Files

| Directory | Purpose |
|-----------|---------|
| `benches/dgx-spark/` | DGX Spark arm64 benchmarks |
| `benches/mac-m2-ultra/` | macOS M2 Ultra benchmarks |
| `benches/nemotron/` | NVIDIA CUDA benchmarks |
| `benches/mac-m2-ultra/mac-m2-ultra.md` | Detailed M2 Ultra results |

## Usage Guidance

- Check `benches/` for existing benchmark results relevant to your hardware
- Run benchmarks with `llama-bench` (from `examples/llama-bench/`) or `llama-perf`
- When adding new benchmarks, follow the pattern of existing results (README.md with structured data)

## Cross-Module Links

- **08-examples**: `llama-bench` and `llama-perf` — the tools that generate benchmark data
- **13-cicd**: CI includes performance regression testing on self-hosted runners
