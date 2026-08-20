# llama.cpp CPU Build

> Source: [docs/build.md](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md)

## CPU Build

The simplest build uses only the CPU:

```bash
cmake -B build
cmake --build build --config Release
```

### Faster Compilation

**Parallel jobs** - add `-j` to run multiple build jobs:

```bash
cmake --build build --config Release -j 8
```

Or use the **Ninja** generator, which parallelizes automatically:

```bash
cmake -B build -G Ninja
cmake --build build
```

**ccache** - install [ccache](https://ccache.dev/) for faster repeated compilations by caching object files.

### Windows ARM (WoA) Build

```bash
cmake --preset arm64-windows-llvm-release -D GGML_OPENMP=OFF
cmake --build build-arm64-windows-llvm-release
```

### Windows x64 with Ninja + Clang

```bash
cmake --preset x64-windows-llvm-release
cmake --build build-x64-windows-llvm-release
```

## BLAS Build

BLAS support improves **prompt processing** performance with batch sizes > 32 (default 512). Does **not** affect generation performance.

### Accelerate Framework (macOS)

Enabled by default on Mac. No special flags needed.

### OpenBLAS

CPU-only BLAS acceleration. Requires OpenBLAS to be installed:

```bash
cmake -B build -DGGML_BLAS=ON -DGGML_BLAS_VENDOR=OpenBLAS
cmake --build build --config Release
```

### BLIS

See [BLIS.md](https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/BLIS.md) for details.

### Intel oneMKL

Provides BLAS with AVX-VNNI support for Intel CPUs without AVX-512. **Does not support Intel GPU** (use SYCL for that).

**Manual oneAPI installation:**

```bash
source /opt/intel/oneapi/setvars.sh
cmake -B build -DGGML_BLAS=ON -DGGML_BLAS_VENDOR=Intel10_64lp \
  -DCMAKE_C_COMPILER=icx -DCMAKE_CXX_COMPILER=icpx -DGGML_NATIVE=ON
cmake --build build --config Release
```

**Docker alternative:** Use the [oneAPI-basekit](https://hub.docker.com/r/intel/oneapi-basekit) image, then run the cmake commands above.

### Other BLAS Libraries

Set `GGML_BLAS_VENDOR` to any vendor supported by CMake's [FindBLAS](https://cmake.org/cmake/help/latest/module/FindBLAS.html#blas-lapack-vendors).

## Arm KleidiAI

Optimized microkernels for Arm CPUs (dotprod, int8mm, SVE, SME). Automatically selects best kernels at runtime:

```bash
cmake -B build -DGGML_CPU_KLEIDIAI=ON
cmake --build build --config Release
```

Verify with: output should contain `load_tensors: CPU_KLEIDIAI model buffer size = ...`

### SME Control

Environment variable `GGML_KLEIDIAI_SME`:

- Not set: auto-detect and enable if supported
- `0`: disable SME
- `N` (>0): enable SME assuming N available units

## ZenDNN (AMD EPYC)

Optimized matrix multiplication for AMD EPYC CPUs:

```bash
cmake -B build -DGGML_ZENDNN=ON
cmake --build build --config Release
```

First build auto-downloads ZenDNN (5-10 min). Subsequent builds are fast. Custom installation path:

```bash
cmake -B build -DGGML_ZENDNN=ON -DZENDNN_ROOT=/path/to/zendnn/install
```

See [ZenDNN.md](https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/ZenDNN.md) for details.
