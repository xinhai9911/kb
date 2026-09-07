---
title: Apache TVM 编译栈
category: concepts
tags: [tvm, compiler, mlc, autotvm, codegen, cuda, rocm, opencl, edge, performance, active]
created: 2026-09-07
updated: 2026-09-07
summary: >-
    Apache TVM 是开源的机器学习编译栈：把 PyTorch/TF/ONNX 等模型经 IR（Relay/Relax）降级，
    用自动调优（AutoTVM/Ansor）为 CUDA、ROCm、OpenCL、Metal、Vulkan 及各类 CPU/NPU
    自动生成高性能内核，实现跨硬件（含 GPU 与边缘设备）的推理加速部署。
base_confidence: 0.85
lifecycle: draft
---

# Apache TVM 编译栈

> 前置 [[concepts/TensorRT 推理优化器]]（厂商方案对照）、[[concepts/OpenVINO 推理工具包]]（厂商方案对照）、
> [[concepts/CUTLASS GEMM 库]]（手调内核对照）。

## 1. 是什么

- **定位**：**ML 编译器**（不是算子库）。核心思路：用编译 + 自动搜索替代手写内核，实现「一次建模，多后端部署」。
- **起源**：陈天奇等发起的 TVM 项目，后成为 Apache 顶级项目；衍生 **MLC-LLM**（LLM 通用部署）等。
- **许可**：Apache 2.0 开源。

## 2. 编译流程

```text
模型(PyTorch/TF/ONNX/MXNet)
   ↓ 导入前端
IR：Relay（经典）/ Relax（新一代，支持动态形状）
   ↓ 图级优化：算子融合、常量折叠、布局变换
   ↓ 算子级：Tensor IR / schedule（循环分块、向量化、并行、存储层级）
   ↓ 自动调优：AutoTVM / Ansor / MetaSchedule（搜索最优 schedule）
   ↓ 代码生成
后端：CUDA / ROCm / OpenCL / Metal / Vulkan / LLVM(CPU) / 各类 NPU
   ↓
可部署模块（含权重与内核）
```

## 3. 关键组件

| 组件 | 说明 |
|------|------|
| **Relay / Relax** | 高层计算图 IR（Relax 面向动态形状与 LLM） |
| **Tensor IR (TIR)** | 算子级循环/内存调度表示 |
| **AutoTVM / Ansor** | 自动搜索 schedule（分块、向量化、绑定） |
| **MetaSchedule** | 新一代自动调度框架（成本模型 + 演化搜索） |
| **VTA** | 开源深度学习加速器参考设计（教学/研究） |
| **MLC-LLM** | 基于 TVM 的 LLM 通用部署方案（CUDA/Metal/Vulkan/WebGPU） |

## 4. 适用场景与权衡

- **适合**：硬件无成熟厂商库（新 NPU/国产卡/边缘设备）、需要跨多后端统一部署、研究自定义算子调度。
- **权衡**：
  - 优点：覆盖面广、可自动生成内核、支持无厂商库硬件。
  - 代价：**编译/调优耗时**（搜索 schedule 可能数分钟到数小时）；在 NVIDIA 上通常**不及高度手调的 TensorRT/cuDNN**。

## 5. 与厂商库对照

| 方案 | 内核来源 | 硬件 | 典型性能 |
|------|---------|------|---------|
| TensorRT / cuDNN | 厂商手调 | NVIDIA GPU | 最高 |
| OpenVINO | oneDNN + 图编译器 | Intel CPU/iGPU/NPU | 高（Intel 上） |
| MIGraphX | MIOpen | AMD GPU | 高 |
| **TVM** | 编译自动生成 | 多硬件（含无库设备） | 中~高，覆盖面最广 |

## 参考来源

- [[concepts/TensorRT 推理优化器]]
- [[concepts/OpenVINO 推理工具包]]
- [[concepts/oneDNN 深度学习性能库]]
- Apache TVM 官网与 GitHub（https://github.com/apache/tvm）
- TVM 论文（Chen et al., OSDI 2018）/ Ansor (OSDI 2020) / MLC-LLM
