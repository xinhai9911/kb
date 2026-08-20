# llama.cpp Overview

## Project Summary

llama.cpp is a **C/C++ LLM (Large Language Model) and VLM (Vision Language Model) inference engine**. Its primary goal is to enable LLM inference with minimal setup and state-of-the-art performance on a wide range of hardware, locally and in the cloud.

- **License:** MIT
- **Repository:** [github.com/ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp)
- **Built on:** [ggml](https://github.com/ggml-org/ggml) tensor library

> Source: `llama.cpp-master/README.md` lines 52-66

## Key Features

### Design Philosophy

- Plain C/C++ implementation with **no external dependencies**
- Apple Silicon is a first-class citizen - optimized via ARM NEON, Accelerate, and Metal frameworks

### Hardware Support

| Architecture | Optimizations |
|---|---|
| **Apple Silicon** | ARM NEON, Accelerate, Metal |
| **x86 (Intel/AMD)** | AVX, AVX2, AVX512, AMX |
| **RISC-V** | RVV, ZVFH, ZFH, ZICBOP, ZIHINTPAUSE |

### Quantization

Supports 1.5-bit, 2-bit, 3-bit, 4-bit, 5-bit, 6-bit, and 8-bit integer quantization for faster inference and reduced memory use.

### GPU Acceleration

Custom CUDA kernels for NVIDIA GPUs, with support for AMD GPUs via HIP and Moore Threads GPUs via MUSA. Vulkan and SYCL backends also available.

### CPU+GPU Hybrid Inference

Partially accelerate models that exceed total VRAM capacity by offloading layers across CPU and GPU.

> Source: `llama.cpp-master/README.md` lines 54-65

## Supported Backends

| Backend | Target Devices | Notes |
|---|---|---|
| BLAS | All | |
| BLIS | All | |
| CANN | Ascend NPU | |
| CUDA | NVIDIA GPU | |
| HIP | AMD GPU | |
| Hexagon | Snapdragon | In Progress |
| IBM zDNN | IBM Z & LinuxONE | |
| MUSA | Moore Threads GPU | |
| Metal | Apple Silicon | |
| OpenCL | Adreno GPU | |
| OpenVINO | Intel CPUs, GPUs, NPUs | In Progress |
| RPC | All | Remote processing |
| SYCL | Intel GPU | |
| VirtGPU | VirtGPU APIR | |
| Vulkan | GPU | |
| WebGPU | All | |
| ZenDNN | AMD CPU | |

> Source: `llama.cpp-master/README.md` lines 68-88

## Installation

### Option 1: Pre-built Binaries

Download from the [releases page](https://github.com/ggml-org/llama.cpp/releases).

### Option 2: Docker

See [Docker documentation](https://github.com/ggml-org/llama.cpp/blob/master/docs/docker.md).

### Option 3: Build from Source

Clone the repository and follow the [build guide](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md).

### Option 4: llama.app

Visit [llama.app](https://llama.app) and follow the instructions.

> Source: `llama.cpp-master/README.md` lines 20-27

## Basic Usage

### CLI (Interactive / Batch)

```sh
# Download and run a model from Hugging Face
llama cli -hf ggml-org/Qwen3.5-0.8B-GGUF
```

### Server (OpenAI-Compatible API)

```sh
# Launch API server with built-in web UI
llama serve -hf ggml-org/Qwen3.5-0.8B-GGUF
```

> Source: `llama.cpp-master/README.md` lines 29-37

## Project Structure

Key directories in the llama.cpp repository:

| Path | Description |
|---|---|
| `tools/cli/` | CLI tool (`llama cli`) |
| `tools/server/` | HTTP server (`llama serve`) |
| `tools/completion/` | Completion tool |
| `grammars/` | GBNF grammar definitions |
| `common/` | Shared utilities and libraries |
| `ggml/` | Core tensor library |
| `docs/` | Documentation |

> Source: `llama.cpp-master/README.md` lines 90-110

## Related Modules

| Module | Path | Description |
|---|---|---|
| Build Guide | `02-build/` | Compilation instructions for all platforms |
| Backends | `03-backends/` | GPU/accelerator backend details |
| Server | `04-server/` | OpenAI-compatible API server |
| CLI Tools | `05-cli-tools/` | Command-line interface usage |
| Multimodal | `06-multimodal/` | Image/audio/video support |
| Grammars | `07-grammars/` | GBNF grammar & constrained generation |
| Examples | `08-examples/` | Sample programs & tutorials |
| Development | `09-development/` | Contributing guide & conventions |
| Architecture | `10-architecture/` | Technical specs & design docs |
| Web UI | `11-ui/` | Frontend interface documentation |
| Benchmarks | `12-benchmarks/` | Performance test results |
| CI/CD | `13-cicd/` | Continuous integration setup |
| Python | `14-python/` | gguf-py & Python tooling |

## Third-Party Dependencies (Bundled)

| Library | Usage | License |
|---|---|---|
| cpp-httplib | HTTP server for `llama-server` | MIT |
| stb | Image format decoder (VLM) | Public domain |
| nlohmann/json | JSON parsing | MIT |
| miniaudio | Audio format decoder (VLM) | Public domain |
| subprocess.h | Process launching | Public domain |

> Source: `llama.cpp-master/README.md` lines 120-126
