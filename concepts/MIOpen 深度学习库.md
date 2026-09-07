---
title: MIOpen 深度学习库
category: concepts
tags: [miopen, amd, rocm, gpu, deep-learning, convolution, hip, performance, active]
created: 2026-09-07
updated: 2026-09-07
summary: >-
    MIOpen（Machine Intelligence Open）是 AMD ROCm 平台的 GPU 深度学习原语库，
    提供卷积、激活、池化、归一化、RNN、softmax 等高度优化算子（FP32/FP16/BF16/INT8），
    是 cuDNN 在 AMD GPU 上的等价物，被 PyTorch ROCm、TensorFlow ROCm 与 MIGraphX 使用。
base_confidence: 0.85
lifecycle: draft
---

# MIOpen 深度学习库

> 前置 [[concepts/cuDNN 深度学习库]]（NVIDIA 对照）、[[concepts/cuBLAS 线性代数库]]（BLAS 对照：rocBLAS/hipBLAS）、
> [[concepts/CPU 指令集加速]]（向量化思路对照）。

## 1. 是什么

- **定位**：AMD **GPU 上的深度学习算子原语库**（非框架），运行在 **ROCm/HIP** 之上。
- **等价物**：在 AMD 生态中的角色 = **cuDNN** 在 NVIDIA 生态中的角色。
- **许可**：MIT 开源（ROCm 生态）。

## 2. 硬件与算子

- 硬件：**GCN / CDNA**（MI 系列数据中心卡）/ **RDNA**（Radeon）GPU。
- 算子：卷积（direct / Winograd / GEMM / FFT 自动选择）、激活、池化、Batch/Layer Norm、RNN、Softmax、CTC loss。
- 数据类型：**FP32 / FP16 / BF16 / INT8**（量化推理）。

## 3. 生态与相关组件

| 组件 | 作用 |
|------|------|
| **MIOpen** | DL 算子原语（卷积等） |
| **rocBLAS / hipBLAS** | GPU BLAS（GEMM），对标 cuBLAS |
| **Composable Kernel (CK)** | 现代 GEMM/attention 内核模板库，对标 CUTLASS，MIOpen 逐渐基于其构建 |
| **MIGraphX** | 图级推理优化器，对标 TensorRT（融合/量化），底层用 MIOpen |
| **PyTorch ROCm / TF ROCm** | 框架 HIP 后端，调用 MIOpen |

## 4. 与 NVIDIA 对照

| 维度 | NVIDIA | AMD |
|------|--------|-----|
| DL 算子库 | cuDNN | **MIOpen** |
| BLAS | cuBLAS / cuBLASLt | rocBLAS / hipBLAS |
| 内核模板 | CUTLASS | Composable Kernel (CK) |
| 推理图优化 | TensorRT | MIGraphX |
| 编程模型 | CUDA | HIP / ROCm |

## 5. 调优要点

- **算法选择**：卷积可用 `MIOPEN_FIND_MODE` 做离线/在线自动调优，首次运行有调优开销（可用缓存）。
- **精度**：在 MI 系列上用 FP16/BF16 与矩阵核心（MFMA 指令）获得高吞吐。
- **移植**：CUDA → HIP 可通过 HIPIFY 工具转换，但性能需按 AMD 架构重新调优。

## 参考来源

- [[concepts/cuDNN 深度学习库]]
- [[concepts/cuBLAS 线性代数库]]
- [[concepts/CUTLASS GEMM 库]]
- MIOpen GitHub（https://github.com/ROCmSoftwarePlatform/MIOpen）
- ROCm / Composable Kernel 文档
