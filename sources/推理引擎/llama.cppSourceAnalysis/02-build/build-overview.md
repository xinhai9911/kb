# llama.cpp Build Overview

> Source: [docs/build.md](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md)

## Prerequisites

- **Git** - version control
- **CMake** (3.14+) - build system
- **C++ compiler** - GCC, Clang, or MSVC (Visual Studio 2022 on Windows)

### Windows Specific

Install [Visual Studio 2022 Community Edition](https://visualstudio.microsoft.com/vs/community/) with these components:

- Workload: **Desktop development with C++**
- Components: C++ CMake Tools for Windows, Git for Windows, C++ Clang Compiler for Windows, MS-Build Support for LLVM-Toolset

Always use a **Developer Command Prompt / PowerShell** for VS2022 when building.

### Optional: OpenSSL

For HTTPS/TLS features. Without it, the project builds and runs without SSL support.

| Distro | Install Command |
|--------|----------------|
| Debian/Ubuntu | `sudo apt-get install libssl-dev` |
| Fedora/RHEL | `sudo dnf install openssl-devel` |
| Arch/Manjaro | `sudo pacman -S openssl` |

## Clone and Basic Build

```bash
git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp
cmake -B build
cmake --build build --config Release
```

## Static Library Build

```bash
cmake -B build -DBUILD_SHARED_LIBS=OFF
cmake --build build --config Release
```

## Debug Build

**Single-config generators** (Unix Makefiles, Ninja):

```bash
cmake -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build
```

**Multi-config generators** (Visual Studio, Xcode):

```bash
cmake -B build -G "Xcode"
cmake --build build --config Debug
```

## CMake Options Overview

### Backend Enable/Disable Flags

| Flag | Backend | Default |
|------|---------|---------|
| `-DGGML_CUDA=ON` | NVIDIA CUDA GPU | OFF |
| `-DGGML_HIP=ON` | AMD ROCm/HIP GPU | OFF |
| `-DGGML_VULKAN=ON` | Vulkan GPU | OFF |
| `-DGGML_METAL=ON` | Apple Metal GPU | ON (macOS) |
| `-DGGML_SYCL=ON` | Intel SYCL GPU | OFF |
| `-DGGML_MUSA=ON` | Moore Threads MUSA GPU | OFF |
| `-DGGML_CANN=ON` | Huawei Ascend NPU | OFF |
| `-DGGML_ZENDNN=ON` | AMD ZenDNN (EPYC CPU) | OFF |
| `-DGGML_OPENCL=ON` | OpenCL GPU | OFF |
| `-DGGML_BLAS=ON` | BLAS acceleration | OFF |
| `-DGGML_OPENMP=ON` | OpenMP threading | ON |

### Build Configuration Flags

| Flag | Description | Default |
|------|-------------|---------|
| `-DBUILD_SHARED_LIBS=OFF` | Build static libraries | ON (shared) |
| `-DGGML_NATIVE=ON` | Optimize for local CPU | ON |
| `-DGGML_BACKEND_DL=ON` | Build backends as dynamic libs | OFF |
| `-DCMAKE_BUILD_TYPE=` | Debug/Release/RelWithDebInfo | Release |
| `-DGGML_CPU_KLEIDIAI=ON` | Arm KleidiAI microkernels | OFF |

### Useful Patterns

**Non-native build** (run on any CUDA GPU):

```bash
cmake -B build -DGGML_CUDA=ON -DGGML_NATIVE=OFF
```

**Multiple backends simultaneously**:

```bash
cmake -B build -DGGML_CUDA=ON -DGGML_VULKAN=ON
```

**Override CUDA architectures**:

```bash
cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES="86;89"
```

## Runtime GPU Control

Even with GPU enabled, GPU layers can be controlled at runtime:

- `-ngl 0` - disable offloading (GPU may still accelerate some operations)
- `--device none` - fully disable GPU acceleration
- `--device <name>` - select specific backend device
- `--list-devices` - show available devices

## Dynamic Backend Loading

Build with `GGML_BACKEND_DL=ON` to compile backends as shared libraries. This allows a single binary to work across machines with different GPUs by loading the appropriate backend at runtime.
