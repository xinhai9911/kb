# llama.cpp Hardware Backends Overview

## Supported Backends Overview

llama.cpp supports multiple hardware backends for accelerating model inference. Each backend targets different hardware platforms and provides varying levels of optimization.

| Backend | Vendor | Platform | Status | Description |
|---------|--------|----------|--------|-------------|
| CPU | All | All | Stable | Default backend with AVX, AVX2, AVX-512, ARM NEON optimizations |
| CUDA | NVIDIA | Linux, Windows, macOS | Stable | NVIDIA GPU acceleration via CUDA toolkit |
| HIP/ROCm | AMD | Linux, Windows | Stable | AMD GPU acceleration via HIP/ROCm |
| Metal | Apple | macOS, iOS | Stable | Apple GPU acceleration via Metal API |
| Vulkan | Khronos | Linux, Windows, macOS | Stable | Cross-platform GPU acceleration via Vulkan |
| SYCL/oneAPI | Intel | Linux, Windows | Stable | Intel GPU acceleration (Arc, Data Center) |
| OpenCL | Khronos | Multi-platform | Experimental | Open standard for heterogeneous computing |
| CANN | Huawei | Linux | Stable | Huawei Ascend NPU acceleration |
| MUSA | Moore Threads | Linux | Experimental | Moore Threads GPU acceleration |
| zDNN | IBM | Linux (s390x) | Stable | IBM Z mainframe acceleration via zDNN library |
| OpenVINO | Intel | Linux, Windows | Experimental | Intel optimized inference via OpenVINO toolkit |
| ET | RISC-V | Linux | Experimental | RISC-V RISC-V vector extension acceleration |
| Hexagon | Qualcomm | Android, Windows on Snapdragon | Experimental | Qualcomm Hexagon NPU acceleration |
| VirtGPU | VirtIO | Linux (VMs) | Experimental | Virtual GPU for cloud/VM environments |
| RPC | llama.cpp | All | Stable | Remote GPU server via network |
| BLIS | AMD | Linux | Experimental | BLIS linear algebra library acceleration |
| ZenDNN | AMD | Linux | Experimental | AMD ZenDNN inference acceleration |

## CPU Backends

### Default CPU Backend
- **Build flag**: Default (always enabled)
- **Description**: Optimized CPU inference with SIMD support
- **Platforms**: All
- **Features**: AVX, AVX2, AVX-512, ARM NEON, Power VSX, SSE3
- **Build command**: `cmake -B build` (default)

### BLIS Backend
- **Build flag**: `-DGGML_BLAS=ON -DGGML_BLAS_VENDOR=FLAME`
- **Description**: BLIS linear algebra library acceleration
- **Platforms**: Linux, Windows
- **Requirements**: BLIS library installed
- **Use case**: High-performance BLAS operations on CPU
- **Docs**: [BLIS.md](https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/BLIS.md)

### Intel oneMKL Backend
- **Build flag**: `-DGGML_BLAS=ON -DGGML_BLAS_VENDOR=MKL`
- **Description**: Intel Math Kernel Library acceleration
- **Platforms**: Linux, Windows, macOS
- **Requirements**: Intel oneAPI MKL installed
- **Use case**: Optimized linear algebra on Intel CPUs
- **Build command**:
  ```bash
  cmake -B build -DGGML_BLAS=ON -DGGML_BLAS_VENDOR=MKL
  ```

### ZenDNN Backend
- **Build flag**: `-DGGML_ZENDNN=ON`
- **Description**: AMD ZenDNN inference acceleration for EPYC processors
- **Platforms**: Linux
- **Requirements**: AMD ZenDNN library
- **Use case**: Optimized inference on AMD EPYC CPUs
- **Docs**: [ZenDNN.md](https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/ZenDNN.md)

## GPU Backends

### CUDA (NVIDIA)
- **Build flag**: `-DGGML_CUDA=ON`
- **Description**: NVIDIA GPU acceleration via CUDA
- **Platforms**: Linux, Windows, macOS (limited)
- **Requirements**: NVIDIA GPU, CUDA Toolkit
- **Features**:
  - Support for all CUDA-capable GPUs
  - FlashAttention optimization
  - Multi-GPU support with NVLink/PCIe P2P
  - Unified memory support on Linux
  - Custom matrix multiplication kernels
- **Build command**:
  ```bash
  cmake -B build -DGGML_CUDA=ON
  ```
- **Environment variables**:
  - `CUDA_VISIBLE_DEVICES`: Select specific GPUs
  - `CUDA_SCALE_LAUNCH_QUEUES=4x`: Optimize multi-GPU pipeline parallelism
  - `GGML_CUDA_ENABLE_UNIFIED_MEMORY=1`: Enable unified memory on Linux
  - `GGML_CUDA_P2P=1`: Enable peer-to-peer GPU access
- **Docs**: [build.md#cuda](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md#cuda), [CUDA-FEDORA.md](https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/CUDA-FEDORA.md)

### HIP/ROCm (AMD)
- **Build flag**: `-DGGML_HIP=ON`
- **Description**: AMD GPU acceleration via HIP/ROCm
- **Platforms**: Linux, Windows
- **Requirements**: AMD GPU, ROCm toolkit
- **Features**:
  - Support for AMD Radeon and Instinct GPUs
  - HIP-based CUDA compatibility layer
  - Multi-GPU support
- **Build command**:
  ```bash
  HIPCXX="$(hipconfig -l)/clang" HIP_PATH="$(hipconfig -R)" \
      cmake -S . -B build -DGGML_HIP=ON -DGPU_TARGETS=gfx1030 -DCMAKE_BUILD_TYPE=Release
  ```
- **Environment variables**:
  - `HIP_VISIBLE_DEVICES`: Select specific GPUs
  - `GGML_CUDA_ENABLE_UNIFIED_MEMORY=1`: Enable unified memory on integrated GPUs
- **Docs**: [build.md#hip](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md#hip)

### Metal (Apple)
- **Build flag**: `-DGGML_METAL=ON` (default on macOS)
- **Description**: Apple GPU acceleration via Metal API
- **Platforms**: macOS, iOS, iPadOS
- **Requirements**: Apple Silicon or AMD GPU on macOS
- **Features**:
  - Optimized for Apple Silicon (M1/M2/M3/M4)
  - Automatic GPU selection
  - Unified memory architecture
- **Build command**:
  ```bash
  cmake -B build -DGGML_METAL=ON
  ```
- **Note**: Metal is enabled by default on macOS. Disable with `-DGGML_METAL=OFF`.
- **Docs**: [build.md#metal-build](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md#metal-build)

### Vulkan
- **Build flag**: `-DGGML_VULKAN=ON`
- **Description**: Cross-platform GPU acceleration via Vulkan
- **Platforms**: Linux, Windows, macOS (via MoltenVK)
- **Requirements**: Vulkan SDK or compatible drivers
- **Features**:
  - Cross-platform support (NVIDIA, AMD, Intel, Qualcomm)
  - No vendor lock-in
  - Good for mixed GPU environments
- **Build command**:
  ```bash
  cmake -B build -DGGML_VULKAN=ON
  ```
- **Docs**: [build.md#vulkan](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md#vulkan)

### SYCL/oneAPI (Intel)
- **Build flag**: `-DGGML_SYCL=ON`
- **Description**: Intel GPU acceleration via SYCL/oneAPI
- **Platforms**: Linux, Windows
- **Requirements**: Intel GPU (Arc, Data Center), oneAPI toolkit
- **Features**:
  - Support for Intel Arc GPUs
  - Multi-GPU support
  - FP16 and FP32 support
  - FlashAttention for FP16
- **Build command**:
  ```bash
  cmake -B build -DGGML_SYCL=ON -DGGML_SYCL_DEVICE_AOT=target_devices.txt
  ```
- **Docs**: [SYCL.md](https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/SYCL.md)

### MUSA (Moore Threads)
- **Build flag**: `-DGGML_MUSA=ON`
- **Description**: Moore Threads GPU acceleration via MUSA
- **Platforms**: Linux
- **Requirements**: Moore Threads GPU, MUSA toolkit
- **Features**:
  - Support for Moore Threads GPUs
  - Similar API to CUDA
- **Build command**:
  ```bash
  cmake -B build -DGGML_MUSA=ON
  ```
- **Note**: Most CUDA compilation options should also work for MUSA.

### OpenCL (Adreno/Multi-platform)
- **Build flag**: `-DGGML_OPENCL=ON`
- **Description**: Open standard for heterogeneous computing
- **Platforms**: Linux, Windows, Android (Adreno GPUs)
- **Requirements**: OpenCL runtime/drivers
- **Features**:
  - Cross-vendor GPU support
  - Mobile GPU support (Qualcomm Adreno)
  - Desktop GPU support
- **Build command**:
  ```bash
  cmake -B build -DGGML_OPENCL=ON
  ```
- **Docs**: [OPENCL.md](https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/OPENCL.md)

### CANN (Huawei Ascend)
- **Build flag**: `-DGGML_CANN=ON`
- **Description**: Huawei Ascend NPU acceleration
- **Platforms**: Linux (x86_64, aarch64)
- **Requirements**: Huawei Ascend NPU (910B, 310P), CANN toolkit
- **Features**:
  - Optimized for Ascend 910B/310P NPUs
  - Support for both 910B and 310P chips
- **Build command**:
  ```bash
  cmake -B build -DGGML_CANN=ON
  ```
- **Docs**: [CANN.md](https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/CANN.md)

### zDNN (IBM Z)
- **Build flag**: `-DGGML_ZDNN=ON`
- **Description**: IBM Z mainframe acceleration via zDNN library
- **Platforms**: Linux (s390x)
- **Requirements**: IBM Z with zDNN support
- **Features**:
  - Optimized for IBM Z mainframes
  - z/OS and Linux on Z support
- **Build command**:
  ```bash
  cmake -B build -DGGML_ZDNN=ON
  ```
- **Docs**: [zDNN.md](https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/zDNN.md)

## Special Backends

### RPC (Remote Procedure Call)
- **Build flag**: `-DGGML_RPC=ON`
- **Description**: Remote GPU server via network
- **Platforms**: All
- **Features**:
  - Run inference on remote GPU servers
  - Support for multiple remote backends
  - Network transparency
- **Use case**: Access GPUs on other machines, cluster computing
- **Build command**:
  ```bash
  cmake -B build -DGGML_RPC=ON
  ```

### VirtGPU
- **Build flag**: `-DGGML_VIRTGPU=ON`
- **Description**: Virtual GPU for cloud/VM environments
- **Platforms**: Linux (VMs)
- **Features**:
  - Virtual GPU support for cloud computing
  - Integration with VirtIO drivers
- **Use case**: Running llama.cpp in virtual machines
- **Docs**: [VirtGPU.md](https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/VirtGPU.md)

## Additional Backends

### OpenVINO (Intel)
- **Build flag**: `-DGGML_OPENVINO=ON`
- **Description**: Intel optimized inference via OpenVINO toolkit
- **Platforms**: Linux, Windows
- **Requirements**: Intel CPU/GPU, OpenVINO toolkit
- **Features**:
  - Optimized for Intel hardware
  - Support for Intel CPUs, GPUs, VPUs
- **Docs**: [OPENVINO.md](https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/OPENVINO.md)

### ET (RISC-V)
- **Build flag**: `-DGGML_ET=ON`
- **Description**: RISC-V vector extension acceleration
- **Platforms**: Linux (RISC-V)
- **Requirements**: RISC-V processor with vector extensions
- **Features**:
  - Optimized for RISC-V architecture
  - Vector extension support
- **Docs**: [ET.md](https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/ET.md)

### Hexagon (Qualcomm)
- **Build flag**: `-DGGML_HEXAGON=ON`
- **Description**: Qualcomm Hexagon NPU acceleration
- **Platforms**: Android, Windows on Snapdragon
- **Requirements**: Qualcomm Snapdragon processor with Hexagon NPU
- **Features**:
  - NPU acceleration for mobile devices
  - Support for multiple HTP sessions
  - OpenCL GPU acceleration on Adreno
- **Environment variables**:
  - `GGML_HEXAGON_NDEV=1`: Number of HTP devices/sessions
  - `GGML_HEXAGON_NHVX=0`: Number of HVX hardware threads
  - `GGML_HEXAGON_VERBOSE=1`: Enable verbose logging
  - `GGML_HEXAGON_PROFILE=1`: Enable profiling
- **Docs**: [snapdragon/README.md](https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/snapdragon/README.md)

## Backend Status Summary

| Backend | Status | Maturity | Notes |
|---------|--------|----------|-------|
| CPU | Stable | Production | Default backend, always available |
| CUDA | Stable | Production | Most mature GPU backend |
| HIP | Stable | Production | Good ROCm support |
| Metal | Stable | Production | Optimized for Apple Silicon |
| Vulkan | Stable | Production | Cross-platform, good compatibility |
| SYCL | Stable | Production | Intel GPU support |
| CANN | Stable | Production | Huawei Ascend NPU |
| zDNN | Stable | Production | IBM Z mainframe |
| OpenCL | Experimental | Beta | Mobile and cross-vendor GPU |
| MUSA | Experimental | Beta | Moore Threads GPU |
| OpenVINO | Experimental | Beta | Intel optimization toolkit |
| ET | Experimental | Alpha | RISC-V vector extensions |
| Hexagon | Experimental | Beta | Qualcomm NPU |
| VirtGPU | Experimental | Alpha | Virtual GPU for VMs |
| BLIS | Experimental | Beta | BLIS library acceleration |
| ZenDNN | Experimental | Beta | AMD EPYC optimization |
| RPC | Stable | Production | Remote GPU access |

## How to Choose a Backend

### Decision Guide

1. **What hardware do you have?**
   - **NVIDIA GPU** → CUDA
   - **AMD GPU** → HIP/ROCm (Linux) or Vulkan (cross-platform)
   - **Apple Silicon** → Metal (default on macOS)
   - **Intel GPU** → SYCL/oneAPI
   - **Qualcomm Adreno** → OpenCL or Hexagon (on Snapdragon)
   - **Huawei Ascend NPU** → CANN
   - **IBM Z mainframe** → zDNN
   - **AMD EPYC CPU** → ZenDNN
   - **Intel CPU** → oneMKL (via BLAS)
   - **RISC-V** → ET
   - **No GPU** → CPU (default)

2. **What platform are you on?**
   - **Linux**: All backends available
   - **Windows**: CUDA, HIP, Vulkan, SYCL, OpenCL
   - **macOS**: Metal (default), Vulkan (via MoltenVK)
   - **Android**: OpenCL, Hexagon
   - **Cloud/VM**: VirtGPU, RPC

3. **What's your use case?**
   - **Local development**: CPU, CUDA, Metal, Vulkan
   - **Production server**: CUDA, HIP, SYCL
   - **Mobile inference**: OpenCL, Hexagon
   - **Cloud computing**: RPC, VirtGPU
   - **Enterprise/mainframe**: zDNN

### Quick Selection Table

| Scenario | Recommended Backend | Build Command |
|----------|-------------------|---------------|
| NVIDIA GPU on Linux | CUDA | `cmake -B build -DGGML_CUDA=ON` |
| AMD GPU on Linux | HIP | `cmake -B build -DGGML_HIP=ON` |
| Apple Silicon Mac | Metal | `cmake -B build -DGGML_METAL=ON` |
| Intel Arc GPU | SYCL | `cmake -B build -DGGML_SYCL=ON` |
| Cross-platform GPU | Vulkan | `cmake -B build -DGGML_VULKAN=ON` |
| Mobile/Embedded | OpenCL | `cmake -B build -DGGML_OPENCL=ON` |
| Remote GPU server | RPC | `cmake -B build -DGGML_RPC=ON` |
| No GPU / CPU only | CPU (default) | `cmake -B build` |

### Backend Comparison

| Feature | CUDA | HIP | Metal | Vulkan | SYCL |
|---------|------|-----|-------|--------|------|
| Multi-GPU | ✓ | ✓ | ✗ | ✓ | ✓ |
| FlashAttention | ✓ | ✓ | ✓ | ✓ | ✓ |
| Unified Memory | ✓ | ✓ | ✓ | ✗ | ✓ |
| Cross-platform | ✗ | ✗ | ✗ | ✓ | ✗ |
| Mobile Support | ✗ | ✗ | ✗ | ✓ | ✗ |
| VM Support | ✗ | ✗ | ✗ | ✗ | ✗ |

## Performance Considerations

### GPU Backend Selection
- **Best performance**: CUDA (NVIDIA), Metal (Apple), HIP (AMD)
- **Best compatibility**: Vulkan (cross-platform)
- **Best for mobile**: OpenCL, Hexagon
- **Best for enterprise**: SYCL (Intel), zDNN (IBM)

### Multi-GPU Setup
- **NVLink/PCIe P2P**: Enable `GGML_CUDA_P2P=1`
- **Pipeline parallelism**: Set `CUDA_SCALE_LAUNCH_QUEUES=4x`
- **Device selection**: Use `CUDA_VISIBLE_DEVICES` or `HIP_VISIBLE_DEVICES`

### Memory Management
- **Unified memory**: `GGML_CUDA_ENABLE_UNIFIED_MEMORY=1` (Linux)
- **VRAM overflow**: Unified memory allows swapping to system RAM
- **Batch size tuning**: Adjust based on available VRAM

## Troubleshooting

### Common Issues
1. **Backend not found**: Ensure required toolkit is installed
2. **Compilation errors**: Check GPU architecture compatibility
3. **Performance issues**: Verify GPU is being used (check `-ngl` parameter)
4. **Memory errors**: Enable unified memory or reduce batch size

### Debug Commands
```bash
# Check CUDA devices
nvidia-smi

# Check ROCm devices
rocm-smi

# Check Vulkan devices
vulkaninfo

# Run with verbose output
./build/bin/llama-cli -m model.gguf --verbose
```

## Documentation Links

- [Build Instructions](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md)
- [Backend-Specific Guides](https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/)
- [CUDA Fedora Setup](https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/CUDA-FEDORA.md)
- [SYCL Guide](https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/SYCL.md)
- [CANN Guide](https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/CANN.md)
- [OpenCL Guide](https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/OPENCL.md)
- [VirtGPU Guide](https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/VirtGPU.md)
- [zDNN Guide](https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/zDNN.md)
- [ZenDNN Guide](https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/ZenDNN.md)
- [Snapdragon Guide](https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/snapdragon/README.md)
