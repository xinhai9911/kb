# Module 13: CI/CD Overview

**LLM**: deepseek-v3.2 | **Model**: gpt-5.3-codex-2 | **Tools**: find, rg, edit, read, write

---

## What It Covers

The CI/CD infrastructure of llama.cpp — continuous integration on self-hosted runners, supported hardware backends, and how to run tests locally. Includes the `ci/` directory with scripts and documentation.

## Key Concepts

### CI Infrastructure
- Uses **self-hosted runners** (not GitHub-hosted) for performance and hardware access
- `GG_BUILD_*` environment variables control which backends are enabled
- Supported CI targets include: CUDA, ROCm, SYCL, Vulkan, WebGPU, MUSA, BLAS/OpenBLAS, OpenVINO

### Local CI Execution
The `ci/run.sh` script allows running CI locally:
```bash
./ci/run.sh
```
This runs the same checks as the cloud CI, useful for pre-PR validation.

### Backends Tested in CI
| Backend | Env Var | Hardware |
|---------|---------|----------|
| CUDA | `GG_BUILD_CUDA` | NVIDIA GPU |
| ROCm | `GG_BUILD_ROCM` | AMD GPU |
| SYCL | `GG_BUILD_SYCL` | Intel GPU |
| Vulkan | `GG_BUILD_VULKAN` | Multi-vendor GPU |
| WebGPU | `GG_BUILD_WEBGPU` | Browser/WebGPU |
| MUSA | `GG_BUILD_MUSA` | Moore Threads GPU |
| BLAS/OpenBLAS | `GG_BUILD_BLAS` | CPU fallback |
| OpenVINO | `GG_BUILD_OPENVINO` | Intel inference |

## Files

| File | Purpose |
|------|---------|
| `ci/README.md` | CI documentation: runners, environment, local execution |
| `ci/run.sh` | Main CI script — runs tests, builds, checks |

## Usage Guidance

1. Run CI locally before pushing: `./ci/run.sh`
2. Check `ci/README.md` for required environment variables
3. For adding new CI targets, follow the pattern in `ci/run.sh`

## Cross-Module Links

- **09-development**: `CONTRIBUTING.md` requires CI checks to pass before merging
- **06-tensor-gguf**: CI tests GGUF format handling across backends
- **01-deepseek**: `contributing/` has custom CI workflows for DeepSeek support
