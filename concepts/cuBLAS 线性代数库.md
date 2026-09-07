---
title: cuBLAS 线性代数库
category: concepts
tags: [cublas, nvidia, cuda, blas, gemm, tensor-core, gpu, performance, active]
created: 2026-09-07
updated: 2026-09-07
summary: >-
    cuBLAS 是 NVIDIA 在 CUDA 之上的 BLAS 实现，提供高度优化的 Level 1/2/3 例程，
    底层 GEMM 充分利用 Tensor Core（TF32/FP16/BF16/INT8），是 cuDNN 与 PyTorch GPU
    线性层/矩阵乘的底层加速基石。
base_confidence: 0.85
lifecycle: draft
---

# cuBLAS 线性代数库

> 前置 [[concepts/oneMKL 数学核心库]]（CPU 对照）、[[concepts/cuDNN 深度学习库]]（上层 DL 算子）、
> [[concepts/OpenBLAS 线性代数库]]（开源对照）。

## 1. 是什么

- **定位**：NVIDIA **CUDA** 之上的 BLAS（Level 1/2/3）实现；深度学习与 HPC 在 GPU 上的线性代数底座。
- **组成**：
  - **cuBLAS**（传统）：`cublasSgemm`/`cublasDgemm` 等，Host 驱动。
  - **cuBLASLt**（轻量，面向 ML）：支持 INT8/FP8/TF32、bias、epilogue（激活/偏置融合），更适合推理。
- **许可**：随 CUDA 提供（闭源预编译）。

## 2. GEMM 与 Tensor Core

- 核心：`cublasGemmEx` / `cublasLtMatmul`，按数据类型选内核。
- **Tensor Core 利用**：Volta+ 的矩阵乘累加单元；数据类型 **TF32（Ampere 起默认）/ FP16 / BF16 / INT8**（需 `CUBLAS_COMPUTE_*` 与缩放）。
- 典型：Transformer 的 `QK^T`、`Attention`、FFN 全连接都落在 cuBLAS GEMM 上。

```cpp
// FP16 GEMM（C = α·A·B + β·C），可走 Tensor Core
cublasGemmEx(handle, CUBLAS_OP_N, CUBLAS_OP_N,
             m, n, k, &alpha,
             A, CUDA_R_16F, m, B, CUDA_R_16F, k, &beta,
             C, CUDA_R_16F, m, CUBLAS_COMPUTE_32F, CUBLAS_GEMM_DEFAULT);
```

## 3. 与上层关系

- **cuDNN**：卷积/全连接中的矩阵乘路径调用 cuBLAS/cuBLASLt。
- **PyTorch / TensorFlow GPU**：`@`、`nn.Linear`、`F.scaled_dot_product_attention` 的底层 matmul 走 cuBLAS。
- **对比 CPU**：等价于 oneMKL/OpenBLAS 在 GPU 上的角色。

```bash
# 查看 GPU / CUDA 是否可用（PyTorch）
python -c "import torch; print(torch.cuda.is_available(), torch.backends.cuda.matmul.allow_tf32)"
```

## 4. 常见误区

- **TF32 默认开启**：Ampere+ 上 `allow_tf32` 默认可能开启，会牺牲 fp32 精度换取速度；需严格精度时关闭。
- **布局**：GPU GEMM 偏好列主元（Fortran order），框架负责 row/col 转换，跨库传张量注意 stride。

## 参考来源

- [[concepts/oneMKL 数学核心库]]
- [[concepts/cuDNN 深度学习库]]
- [[concepts/OpenBLAS 线性代数库]]
- NVIDIA cuBLAS Documentation / cuBLAS-LT Guide
