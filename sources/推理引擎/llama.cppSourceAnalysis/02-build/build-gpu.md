# llama.cpp GPU Backend Builds

> Source: [docs/build.md](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md)

## CUDA (NVIDIA)

Requires the [CUDA toolkit](https://developer.nvidia.com/cuda-downloads).

### Basic Build

```bash
cmake -B build -DGGML_CUDA=ON
cmake --build build --config Release
```

### Non-Native Build (All CUDA GPUs)

```bash
cmake -B build -DGGML_CUDA=ON -DGGML_NATIVE=OFF
```

Larger binary, may require JIT compilation, but runs on all CUDA GPUs.

### Override Compute Capability

When `nvcc` cannot detect your GPU, specify architectures manually:

```bash
cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES="86;89"
```

Find your GPU's compute capability at [CUDA GPUs](https://developer.nvidia.com/cuda-gpus).

### Override CUDA Version

For multiple CUDA installations (e.g. CUDA 11.7 at `/opt/cuda-11.7`):

```bash
cmake -B build -DGGML_CUDA=ON \
  -DCMAKE_CUDA_COMPILER=/opt/cuda-11.7/bin/nvcc \
  -DCMAKE_INSTALL_RPATH="/opt/cuda-11.7/lib64;\$ORIGIN" \
  -DCMAKE_BUILD_WITH_INSTALL_RPATH=ON
```

### CUDA Compilation Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `GGML_CUDA_FORCE_MMQ` | bool | false | Force custom MM kernels for quantized models. Lower VRAM but slower at large batch sizes. |
| `GGML_CUDA_FORCE_CUBLAS` | bool | false | Force FP16 cuBLAS instead of custom MM kernels. May be faster on datacenter GPUs. |
| `GGML_CUDA_PEER_MAX_BATCH_SIZE` | int | 128 | Max batch size for peer-to-peer access between GPUs. |
| `GGML_CUDA_FA_ALL_QUANTS` | bool | false | Compile FlashAttention for all KV cache quantization types (longer compile). |

### CUDA Runtime Environment Variables

```bash
# Hide first GPU
CUDA_VISIBLE_DEVICES="-0" ./build/bin/llama-server --model model.gguf

# Scale launch queues (beneficial for multi-GPU pipeline parallelism)
CUDA_SCALE_LAUNCH_QUEUES=4x

# Override cuBLAS compute type (auto, f16, fp16, bf16, f32, fp32)
GGML_CUDA_CUBLAS_COMPUTE_TYPE=auto

# Enable unified memory (swap to RAM when VRAM exhausted, Linux only)
GGML_CUDA_ENABLE_UNIFIED_MEMORY=1

# Enable peer-to-peer access between GPUs (requires driver support)
GGML_CUDA_P2P=1
```

### Fix Old CUDA + New glibc

If using old CUDA (e.g. 11.7) with new glibc, patch `math_functions.h` in your CUDA installation to add `noexcept(true)` to `cospi`, `cospif`, `sinpi`, `sinpif`, `rsqrt`, `rsqrtf` declarations.

### Fedora Toolbox Container

For Atomic Desktops or unsupported CUDA platforms, see [CUDA-FEDORA.md](https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/CUDA-FEDORA.md).

---

## HIP (AMD ROCm)

Requires [ROCm](https://rocm.docs.amd.com/projects/install-on-linux/en/latest/tutorial/quick-start.html).

### Linux Build

```bash
HIPCXX="$(hipconfig -l)/clang" HIP_PATH="$(hipconfig -R)" \
    cmake -S . -B build -DGGML_HIP=ON -DGPU_TARGETS=gfx1030 -DCMAKE_BUILD_TYPE=Release \
    && cmake --build build --config Release -- -j 16
```

- `GPU_TARGETS` is optional; omitting it builds for all system GPUs.
- Find your GPU arch: `rocminfo | grep gfx | head -1 | awk '{print $2}'`
- Match against [AMDGPU targets](https://llvm.org/docs/AMDGPUUsage.html#processors)

### Windows Build

Using x64 Native Tools Command Prompt for VS:

```bash
set PATH=%HIP_PATH%\bin;%PATH%
cmake -S . -B build -G Ninja -DGPU_TARGETS=gfx1100 -DGGML_HIP=ON \
  -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ -DCMAKE_BUILD_TYPE=Release
cmake --build build
```

### ROCm Device Library Error Fix

If you get `cannot find ROCm device library`, locate `oclc_abi_version_400.bc` under `HIP_PATH` and prefix:

```bash
HIP_DEVICE_LIB_PATH=<directory-containing-oclc_abi_version_400.bc> \
    cmake -S . -B build -DGGML_HIP=ON -DGPU_TARGETS=gfx1030
```

### Runtime Variables

```bash
HIP_VISIBLE_DEVICES=0         # select GPU
HSA_OVERRIDE_GFX_VERSION=10.3.0  # for unsupported GPUs (Linux only)
```

### Unified Memory

```bash
GGML_CUDA_ENABLE_UNIFIED_MEMORY=1  # Linux only, for integrated GPUs
```

---

## Metal (Apple)

Enabled by default on macOS. No special flags needed.

```bash
cmake -B build
cmake --build build --config Release
```

To disable Metal at compile time:

```bash
cmake -B build -DGGML_METAL=OFF
```

To disable GPU inference at runtime (keep Metal compiled):

```bash
./build/bin/llama-cli -m model.gguf --n-gpu-layers 0
```

---

## Vulkan

### Linux

Install dependencies (Debian/Ubuntu):

```bash
sudo apt-get install libvulkan-dev glslc spirv-headers
```

Or use the [LunarG Vulkan SDK](https://vulkan.lunarg.com/doc/sdk/latest/linux/getting_started.html):

```bash
source /path/to/vulkan-sdk/setup-env.sh
```

Verify: `vulkaninfo` should run without errors.

```bash
cmake -B build -DGGML_VULKAN=1
cmake --build build --config Release
```

Test: `./build/bin/llama-cli -m model.gguf -ngl 99`

### Windows

**w64devkit:** Download [w64devkit](https://github.com/skeeto/w64devkit/releases) and [Vulkan SDK](https://vulkan.lunarg.com/sdk/home#windows). Copy Vulkan files into w64devkit, then:

```bash
cmake -B build -DGGML_VULKAN=ON
cmake --build build --config Release
```

**MSYS2 (UCRT terminal):**

```bash
pacman -S git mingw-w64-ucrt-x86_64-gcc mingw-w64-ucrt-x86_64-cmake \
    mingw-w64-ucrt-x86_64-vulkan-devel mingw-w64-ucrt-x86_64-shaderc \
    mingw-w64-ucrt-x86_64-spirv-headers
cmake -B build -DGGML_VULKAN=ON
cmake --build build --config Release
```

### macOS (Vulkan via MoltenVK/KosmicKrisp)

Install [LunarG Vulkan SDK](https://vulkan.lunarg.com/doc/sdk/latest/mac/getting_started.html) and source the env. Then build with Metal disabled:

```bash
cmake -B build -DGGML_VULKAN=1 -DGGML_METAL=OFF
cmake --build build --config Release
```

To switch between MoltenVK and KosmicKrisp:

```bash
export VK_ICD_FILENAMES=$VULKAN_SDK/share/vulkan/icd.d/libkosmickrisp_icd.json
```

### Docker

```bash
docker build -t llama-cpp-vulkan --target light -f .devops/vulkan.Dockerfile .
docker run -it --rm -v "$(pwd):/app:Z" \
  --device /dev/dri/renderD128 --device /dev/dri/card1 \
  llama-cpp-vulkan -m /app/models/model.gguf -ngl 33
```

---

## SYCL (Intel GPU)

Supports Intel Data Center Max, Flex, Arc, Built-in, and iGPU.

For detailed instructions, see [SYCL.md](https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/SYCL.md).

---

## MUSA (Moore Threads)

Requires the [MUSA SDK](https://developer.mthreads.com/musa/musa-sdk).

```bash
cmake -B build -DGGML_MUSA=ON
cmake --build build --config Release
```

### Override Compute Capabilities

```bash
cmake -B build -DGGML_MUSA=ON -DMUSA_ARCHITECTURES="21"  # MTT S80 only
```

### Static Build

```bash
cmake -B build -DGGML_MUSA=ON -DBUILD_SHARED_LIBS=OFF -DCMAKE_POSITION_INDEPENDENT_CODE=ON
cmake --build build --config Release
```

### Runtime

```bash
MUSA_VISIBLE_DEVICES="-0" ./build/bin/llama-server --model model.gguf
GGML_CUDA_ENABLE_UNIFIED_MEMORY=1  # Linux, unified memory
```

---

## CANN (Huawei Ascend NPU)

Requires the [CANN Toolkit](https://www.hiascend.com/developer/download/community/result?module=cann).

```bash
cmake -B build -DGGML_CANN=on -DCMAKE_BUILD_TYPE=release
cmake --build build --config release
```

Verify CANN backend is active (look for `CANN model buffer size` in output):

```bash
./build/bin/llama-cli -m model.gguf -ngl 32
```

See [CANN.md](https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/CANN.md) for details.

---

## OpenCL

GPU acceleration through OpenCL on recent Adreno GPUs (primarily Android).

See [OPENCL.md](https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/OPENCL.md).

### Android Build

Requires Android NDK. Install OpenCL headers and ICD loader first, then:

```bash
cmake .. -G Ninja \
  -DCMAKE_TOOLCHAIN_FILE=$ANDROID_NDK/build/cmake/android.toolchain.cmake \
  -DANDROID_ABI=arm64-v8a \
  -DANDROID_PLATFORM=android-28 \
  -DBUILD_SHARED_LIBS=OFF \
  -DGGML_OPENCL=ON
ninja
```

### Windows ARM64

Install OpenCL headers and ICD loader, then build with the LLVM ARM64 toolchain and `-DGGML_OPENCL=ON`.

---

## OpenVINO

Optimized inference toolkit for Intel hardware (CPUs, GPUs, NPUs).

See [OPENVINO.md](https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/OPENVINO.md).

---

## Runtime Environment Variables Summary

| Variable | Description |
|----------|-------------|
| `CUDA_VISIBLE_DEVICES` | Select/hide NVIDIA GPUs |
| `CUDA_SCALE_LAUNCH_QUEUES` | CUDA command buffer size (e.g. `4x` for multi-GPU) |
| `GGML_CUDA_CUBLAS_COMPUTE_TYPE` | cuBLAS compute type (`auto`, `f16`, `f32`, etc.) |
| `GGML_CUDA_ENABLE_UNIFIED_MEMORY` | Enable RAM swap when VRAM exhausted (Linux) |
| `GGML_CUDA_P2P` | Enable peer-to-peer GPU access |
| `HIP_VISIBLE_DEVICES` | Select/hide AMD GPUs |
| `HSA_OVERRIDE_GFX_VERSION` | Override GPU arch for unsupported AMD GPUs (Linux) |
| `MUSA_VISIBLE_DEVICES` | Select/hide Moore Threads GPUs |
| `GGML_KLEIDIAI_SME` | Control Arm SME (`0`=off, `N`=force N units) |

## Multi-GPU and Backend Notes

- Multiple backends can be compiled simultaneously (e.g. `-DGGML_CUDA=ON -DGGML_VULKAN=ON`)
- Use `--device` at runtime to select which backend devices to use
- Use `--list-devices` to see available devices
- Use `--device none` to fully disable GPU acceleration
- Build with `GGML_BACKEND_DL=ON` to compile backends as dynamically loadable libraries
