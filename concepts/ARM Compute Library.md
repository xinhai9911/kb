---
title: ARM Compute Library
category: concepts
tags: [arm, acl, compute-library, neon, sve, gpu, performance, deep-learning, active]
created: 2026-09-07
updated: 2026-09-07
summary: >-
    ARM Compute Library（ACL）是 Arm 官方的 ML 与计算机视觉性能库，针对 Arm CPU（Neon/SVE）
    与 Mali GPU 高度优化 CNN/RNN/算子，支持 FP32/BF16/INT8，是 oneDNN 的 Arm 后端及
    TFLite/PyTorch ARM 后端的底层。
base_confidence: 0.85
lifecycle: draft
---

# ARM Compute Library（ACL）

> 前置 [[concepts/oneDNN 深度学习性能库]]（Arm 后端即 ACL）、[[concepts/CPU 指令集加速]]（Neon/SVE 向量化）、
> [[concepts/ARM Compute Library|Arm 体系]]。

## 1. 是什么

- **定位**：Arm 官方**计算性能库**，覆盖机器学习算子与计算机视觉函数，面向 Cortex-A、Neoverse（服务器）与 Mali GPU。
- **许可**：Apache 2.0 开源。
- **硬件目标**：Arm **CPU**（NEON 128-bit；SVE/SVE2 可伸缩向量）、Arm **Mali GPU**（OpenCL）、**Ethos-N NPU**（通过额外栈）。

## 2. 算子范围

- 神经网络：Convolution（直接/Winograd/im2col/GEMM）、Fully Connected、Pool、Batch/Layer/Group Norm、Activation、Softmax、RNN/LSTM/GRU、Elementwise、Concat/Split。
- 计算机视觉：颜色空间、滤波、几何变换、特征（Harris/ORB 等）。
- 数据类型：**FP32 / FP16 / BF16 / INT8(UINT8)** 量化推理。

## 3. 与生态关系

- **oneDNN 的 Arm 后端**：oneDNN 在 AArch64 上以 **ACL 为后端**实现卷积/matmul 等原语（同 oneDNN 接口，底层调 ACL）。
- **TensorFlow Lite / TFLite**：CPU delegate 基于 ACL。
- **ONNX Runtime / PyTorch**：ARM 后端（以及 ExecuTorch）复用 ACL 内核。
- **对比 x86**：在 Arm 服务器（Graviton/鲲鹏/飞腾）上角色 ≈ oneDNN/MKL 在 Intel 上的角色。

```
            Arm CPU (Neon/SVE)
   oneDNN(Arm) ─┐
   TFLite CPU   ─┼─► ARM Compute Library ─► NEON/SVE 内核
   ORT / PyTorch─┘
```

## 4. 调优要点

- **调度/亲和**：多核 AArch64 上用 `taskset`/`numactl` 绑定核，避免线程迁移。
- **布局**：ACL 内部用 blocked layout（类似 oneDNN 的 `nChw16c`），跨库传递需 reorder。
- **SVE**：可伸缩向量长度（128/256/512）下内核按 VL 适配，二进制可跨 SVE 宽度。

## 参考来源

- [[concepts/oneDNN 深度学习性能库]]
- [[concepts/CPU 指令集加速]]
- ARM Compute Library GitHub（https://github.com/ARM-software/ComputeLibrary）
- Arm Architecture Reference（NEON / SVE）
