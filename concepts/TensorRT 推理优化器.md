---
title: TensorRT 推理优化器
category: concepts
tags: [tensorrt, nvidia, cuda, inference, optimization, int8, fp16, fusion, performance, active]
created: 2026-09-07
updated: 2026-09-07
summary: >-
    NVIDIA TensorRT 是 GPU 推理优化器与运行时：导入训练好的模型后做层/张量融合、
    内核自动调优、内存优化与精度校准（FP16/INT8/TF32），生成高度优化的推理 engine。
    是部署端 GPU 推理加速的事实标准，TensorRT-LLM 在其上构建。
base_confidence: 0.85
lifecycle: draft
---

# TensorRT 推理优化器

> 前置 [[concepts/cuDNN 深度学习库]]（算子原语）、[[concepts/cuBLAS 线性代数库]]（GEMM 底层）、
> [[concepts/模型 压缩 蒸馏]]（INT8 量化校准）、[[concepts/CUTLASS GEMM 库]]（融合内核底座）。

## 1. 是什么

- **定位**：NVIDIA 的**推理优化器 + 运行时**（非训练）。输入 ONNX / PyTorch / TF 模型，输出优化后的 **engine**。
- **与 cuDNN/cuBLAS 关系**：底层复用其内核，但在**图级别**做融合与调优；`TensorRT-LLM` 是在其上为 LLM 定制的构建块。
- **许可**：随 CUDA 提供（闭源预编译，开发者计划免费）。

## 2. 主要优化

| 优化 | 说明 |
|------|------|
| **层/张量融合** | Conv+BN+Act、Elemwise、Scale 等合并为单 kernel，省中间读写 |
| **内核自动调优** | 按目标 GPU 实测挑选最快 GEMM/卷积内核（kernel auto-tuning） |
| **精度校准** | FP16 / **INT8（PTQ 校准 QAT）** / TF32；INT8 需校准集生成 scale |
| **动态形状** | profile 支持变长输入（batch/seq 维度） |
| **内存优化** | 张量复用、workspace 管理，降低显存峰值 |
| **量化工具** | 提供 PTQ 校准器（entropy/percentile/MSE） |

## 3. 工作流

```text
训练模型(PyTorch/TF) → ONNX → TensorRT Builder(解析+优化+引擎编译) →
Engine Plan → TensorRT Runtime(反序列化+执行) → GPU 推理
```

- 构建一次（慢），部署多次（快）：engine 与具体 GPU 架构绑定，换卡需重建。
- 部署常配合 **Triton Inference Server** 做多模型并发服务。

## 4. 与生态对照

| 工具 | 范围 | 硬件 |
|------|------|------|
| TensorRT | 通用模型图优化+运行时 | NVIDIA GPU |
| TensorRT-LLM | LLM 专用（PagedAttention/量化） | NVIDIA GPU |
| OpenVINO | 图优化+PTQ | Intel CPU/iGPU/NPU |
| Apache TVM | 编译器，多后端代码生成 | 多硬件 |

## 参考来源

- [[concepts/cuDNN 深度学习库]]
- [[concepts/cuBLAS 线性代数库]]
- [[concepts/模型 压缩 蒸馏]]
- NVIDIA TensorRT Developer Guide
