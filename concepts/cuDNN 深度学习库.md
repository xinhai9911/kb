---
title: cuDNN 深度学习库
category: concepts
tags: [cudnn, nvidia, cuda, deep-learning, gpu, convolution, tensor-core, performance, active]
created: 2026-09-07
updated: 2026-09-07
summary: >-
    cuDNN 是 NVIDIA 的 GPU 深度学习原语库，提供高度优化的卷积（Winograd/FFT/GEMM）、
    matmul、RNN、归一化、池化、softmax 与融合算子，利用 Tensor Core（TF32/FP16/BF16/INT8），
    是 PyTorch/TensorFlow GPU 后端的默认算子库，可视为 oneDNN 的 NVIDIA GPU 等价物。
base_confidence: 0.85
lifecycle: draft
---

# cuDNN 深度学习库

> 前置 [[concepts/oneDNN 深度学习性能库]]（对应 CPU/跨架构库）、[[concepts/cuBLAS 线性代数库]]（matmul/线性代数底层）、
> [[concepts/CPU 微架构内部]]（对照硬件加速思路）。

## 1. 是什么

- **定位**：NVIDIA **CUDA** 之上的深度学习算子原语库（非框架）。需配合 CUDA Toolkit。
- **角色**：PyTorch / TensorFlow / MXNet 的 **GPU 后端默认**算子库；是 oneDNN 在 NVIDIA GPU 上的对应物（oneDNN 在 NVIDIA GPU 上实际也可走 cuDNN 后端）。
- **许可**：闭源自由库（NVIDIA 提供预编译）。

## 2. 主要原语

| 算子 | 说明 |
|------|------|
| **卷积** | 算法：`IMPLICIT_GEMM` / `IMPLICIT_PRECOMPUTED_GEMM` / `GEMM` / `FFT` / `WINOGRAD`；分组/转置 |
| **MatMul** | 走 cuBLAS/cuBLASLt |
| **RNN** | LSTM / GRU / vanilla（cudnnRNN） |
| **归一化** | BatchNorm / LayerNorm / GroupNorm |
| **池化 / Softmax / 激活** | max/avg、各类激活、dropout |
| **融合** | cuDNN 8 起引入 **fusion engine**：Conv+BN+激活、偏置加、缩放等运行时融合 |

```cpp
// 典型：卷积前向，让 cuDNN 选最快算法
cudnnConvolutionFwdAlgo_t algo;
cudnnGetConvolutionForwardAlgorithm(cudnn_handle, x_desc, w_desc, conv_desc,
                                    y_desc, CUDNN_CONVOLUTION_FWD_PREFER_FASTEST,
                                    0, &algo);
cudnnConvolutionForward(cudnn_handle, &alpha, x_desc, x, w_desc, w,
                        conv_desc, algo, ws, ws_size, &beta, y_desc, y);
```

## 3. 精度与 Tensor Core

- 数据类型：**FP32 / FP16 / BF16 / TF32 / INT8**。
- **Tensor Core**：Volta+ 的矩阵乘累加单元；TF32（Ampere 默认）、FP16/BF16/INT8 经 Tensor Core 获得数倍吞吐。
- cuDNN 8 起默认利用 TF32/比 EP 选择，无需改代码即可加速 fp32 训练。

## 4. 与 oneDNN 对照

| 维度 | cuDNN | oneDNN |
|------|-------|--------|
| 厂商 | NVIDIA | Intel |
| 硬件 | NVIDIA GPU | Intel CPU（+Intel GPU） |
| 编程模型 | CUDA | 原生 / SYCL |
| 等价性 | GPU 算子原语 | CPU/跨架构算子原语 |

## 参考来源

- [[concepts/oneDNN 深度学习性能库]]
- [[concepts/cuBLAS 线性代数库]]
- NVIDIA cuDNN Developer Guide / cuDNN GitHub（https://github.com/NVIDIA/cudnn）
- NVIDIA Tensor Core 白皮书
