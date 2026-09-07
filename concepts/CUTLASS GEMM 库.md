---
title: CUTLASS GEMM 库
category: concepts
tags: [cutlass, nvidia, cuda, gemm, tensor-core, kernel-template, performance, active]
created: 2026-09-07
updated: 2026-09-07
summary: >-
    CUTLASS（CUDA Templates for Linear Algebra Subroutines）是 NVIDIA 开源的 CUDA C++
    模板库，提供分层抽象的 GEMM/卷积内核构件（Tile、MMA、Epilogue），用于编写可复用、
    可融合的高性能 GPU 内核，是 cuBLAS/cuDNN/TensorRT 的底层内核基础。
base_confidence: 0.85
lifecycle: draft
---

# CUTLASS GEMM 库

> 前置 [[concepts/cuBLAS 线性代数库]]（成品 BLAS 库）、[[concepts/cuDNN 深度学习库]]（上层算子）、
> [[concepts/TensorRT 推理优化器]]（融合内核消费者）、[[concepts/CPU 指令集加速]]（对照 SIMD 向量化）。

## 1. 是什么

- **定位**：**内核编写框架**（不是成品算子库）。用 C++ 模板拼装 GEMM/卷积的各级数据流，产出可裁剪的高性能 CUDA 内核。
- **许可**：BSD 开源（NVIDIA）。
- **作用**：把「手写汇编级 GEMM」变成可复用、可组合的模板，供 cuBLAS(Lt)、cuDNN、TensorRT 及自研算子复用。

## 2. 分层抽象

| 层级 | 概念 | 说明 |
|------|------|------|
| **Threadblock** | Tile 切分 | 把 A/B 切成块，映射到 SM 的 shared memory |
| **Warp** | Warp-level MMA | 用 Tensor Core 指令做矩阵乘累加 |
| **Thread** | 寄存器分块 | 每线程持有若干累加器 |
| **Epilogue** | 收尾融合 | 偏置、激活、缩放、量化在写出前融合 |
| **Iterator** | 数据搬运 | 异步拷贝（TMA / ldmatrix）与布局转换 |

```cpp
// 概念示意：用 CUTLASS 组装一个 FP16 GEMM（Tensor Core）
using Gemm = cutlass::gemm::device::Gemm<
    cutlass::half_t, cutlass::layout::RowMajor,   // A
    cutlass::half_t, cutlass::layout::RowMajor,   // B
    cutlass::half_t, cutlass::layout::RowMajor,   // C
    float,                                        // 累加类型
    cutlass::arch::OpClassTensorOp,
    cutlass::arch::Sm80,                          // Ampere
    cutlass::gemm::GemmShape<128, 256, 64>,       // Threadblock tile
    cutlass::gemm::GemmShape<64, 64, 64>,         // Warp tile
    cutlass::gemm::GemmShape<16, 8, 16>,          // MMA 指令形状
    cutlass::epilogue::thread::LinearCombination<
        cutlass::half_t, 4, float, float>,        // Epilogue（可换激活）
    cutlass::gemm::threadblock::GemmIdentityThreadblockSwizzle<>,
    3>;                                           // 流水线级数
```

## 3. 精度与架构

- 数据类型：**FP32 / TF32 / FP16 / BF16 / INT8 / FP8**（Hopper+ 支持 FP8）。
- 架构：Volta（第一代 MMA）→ Turing → Ampere（异步拷贝）→ Hopper（**TMA**、warp-group MMA、FP8）→ Blackwell。
- 新版引入 **Collective** 抽象与 **CuTe**（layout/tensor 代数），进一步简化 tile 编排。

## 4. 为什么重要

- 推理/训练里最热的内核（matmul、conv、attention）几乎都建立在 CUTLASS 之上。
- 自研融合算子（如自定义 attention epilogue）通常用 CUTLASS 写，而非从零写 CUDA。

## 参考来源

- [[concepts/cuBLAS 线性代数库]]
- [[concepts/cuDNN 深度学习库]]
- [[concepts/TensorRT 推理优化器]]
- CUTLASS GitHub（https://github.com/NVIDIA/cutlass）
- NVIDIA CUTLASS / CuTe 文档
