---
title: OpenVINO 推理工具包
category: concepts
tags: [openvino, intel, inference, quantization, igpu, npu, oneapi, edge, performance, active]
created: 2026-09-07
updated: 2026-09-07
summary: >-
    OpenVINO（Open Visual Inference and Neural network Optimization）是 Intel 开源的推理
    优化与部署工具包，做图优化、算子融合与 INT8/FP16 后训练量化，把模型部署到 Intel CPU
    （底层 oneDNN）、集成 GPU、VPU 与 NPU，是边缘与 Intel 硬件上的推理加速主力。
base_confidence: 0.85
lifecycle: draft
---

# OpenVINO 推理工具包

> 前置 [[concepts/oneDNN 深度学习性能库]]（CPU 推理底层算子）、[[concepts/模型 压缩 蒸馏]]（PTQ/QAT 量化）、
> [[concepts/TensorRT 推理优化器]]（NVIDIA 对照）。

## 1. 是什么

- **定位**：Intel 的**推理优化 + 跨硬件部署**工具包（非训练）。
- **硬件**：Intel **CPU**（底层调用 oneDNN）、**集成/独立 GPU（iGPU/Xe）**、**VPU**（Myriad NCS）、**NPU**（Core Ultra 等）。
- **许可**：Apache 2.0 开源。

## 2. 主要能力

| 能力 | 说明 |
|------|------|
| **模型转换** | 支持 PyTorch/TF/ONNX/Paddle → OpenVINO IR（新版可直接读原生格式） |
| **图优化** | 常量折叠、算子融合、布局优化 |
| **后训练量化 (PTQ)** | INT8 / FP16，用 **POT** 工具或无数据量化做校准 |
| **QAT** | 通过 **NNCF** 做量化感知训练与剪枝/稀疏化 |
| **异构执行** | 多设备拆分（AUTO / MULTI / HETERO 插件），自动选设备 |
| **运行时** | C++/Python API，低开销推理 |

```python
from openvino.runtime import Core

core = Core()
model = core.read_model("resnet50.xml")          # 或 read_model("model.onnx")
compiled = core.compile_model(model, "AUTO")      # AUTO: CPU / GPU / NPU 自动选择
result = compiled(input_tensor)[0]
```

## 3. 与 oneDNN 关系

- OpenVINO 在 **Intel CPU** 上把算子下发给 **oneDNN** 执行；在 **iGPU/NPU** 上走 OpenCL / 图编译器。
- 相比直接用 oneDNN 写原语，OpenVINO 提供的是**模型级**的部署与自动化（量化、图优化、多设备）。

## 4. 与 NVIDIA / 跨平台对照

| 工具 | 硬件 | 特色 |
|------|------|------|
| OpenVINO | Intel CPU/iGPU/NPU | 边缘友好，PTQ 工具链完整 |
| TensorRT | NVIDIA GPU | INT8 校准 + 内核自动调优 |
| MIGraphX | AMD GPU（ROCm） | 图优化，底层 MIOpen |
| Apache TVM | 多硬件 | 编译自动生成内核 |

## 参考来源

- [[concepts/oneDNN 深度学习性能库]]
- [[concepts/模型 压缩 蒸馏]]
- [[concepts/TensorRT 推理优化器]]
- OpenVINO 文档与 GitHub（https://github.com/openvinotoolkit/openvino）
- NNCF / POT 量化工具文档
