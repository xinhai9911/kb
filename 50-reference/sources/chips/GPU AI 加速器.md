---
aliases: ["gpu-ai-accelerator"]
---

﻿---
title: GPU 与 AI 加速芯片架构
tags: [chip, gpu, nvidia, ai, accelerator, active]
created: 2026-08-07
summary: >-
    GPU 与 AI 加速芯片全景：NVIDIA GPU 架构演进（Ampere-Hopper-Blackwell）、CUDA 编程模型、Tensor Core、国产 AI 芯片（华为昇腾/寒武纪/海光 DCU）、ASIC 路线（TPU/Grog/Cerebras）、性能指标与互联。
category: reference
updated: 2026-08-07
sources:
  - nvidia.com/data-center
base_confidence: 0.82
lifecycle: draft
---

# GPU 与 AI 加速芯片架构

> AI 大模型训练和推理的核心算力来自 GPU 和专用 AI 加速芯片。

## 1. AI 加速芯片分类

| 类型 | 代表 | 特点 |
|------|------|------|
| **GPU** | NVIDIA H100/B200、AMD MI300X | 通用并行计算，CUDA 生态 |
| **TPU** | Google TPU v5p/v6e | 矩阵乘法专用，JAX/XLA |
| **ASIC** | Grog LPU、Cerebras WSE-3 | 极致定制 |
| **NPU** | 华为昇腾 910B、寒武纪 MLU370 | 国产 AI 芯片 |
| **FPGA** | Xilinx Alveo、Intel Agilex | 可编程，低延迟 |

## 2. NVIDIA GPU 架构演进

| 架构 | 年份 | 芯片 | FP16 TFLOPS | HBM 带宽 | NVLink | 关键特性 |
|------|------|------|:-----------:|:--------:|:------:|----------|
| **Ampere** | 2020 | A100 | 312 | 2 TB/s | 3.0 (600GB/s) | TF32、MIG、稀疏 |
| **Hopper** | 2022 | H100 | 990 | 3.35 TB/s | 4.0 (900GB/s) | FP8、Transformer Engine |
| **Blackwell** | 2024 | B200 | 4500 (FP4) | 8 TB/s | 5.0 (1.8TB/s) | FP4、双芯封装 |
| **Rubin** | 2026 | R100 | TBD | TBD | NVLink 6 | HBM4 |

### H100 关键单元

| 单元 | 功能 |
|------|------|
| **SM** | 基本计算单元，128 CUDA 核心 + 4 Tensor Core |
| **Tensor Core** | 矩阵乘法加速（MxNxK），FP8/FP16/INT8 |
| **Transformer Engine** | 动态 FP8 精度，训练加速 2-3x |
| **MIG** | 1 GPU 切 7 个独立实例 |
| **HBM3** | 6 stack 80GB，带宽 3.35TB/s |

## 3. CUDA 编程模型

| 概念 | 说明 |
|------|------|
| **Grid** | 一个 kernel 启动的所有 thread 组 |
| **Block** | SM 上执行的 thread 组（共享 Shared Memory） |
| **Thread** | 最小执行单元 |
| **Shared Memory** | Block 内共享 SRAM（低延迟） |
| **Global Memory** | 所有 thread 可访问（HBM，高延迟） |

关键 API：
- `cudaMalloc` / `cudaMemcpy` — 内存管理
- `kernel<<<grid, block>>>()` — 启动 kernel
- `__syncthreads()` — Block 内同步
- `__shared__` — 共享内存声明

## 4. 国产 AI 芯片

| 厂商 | 产品 | 架构 | FP16 TFLOPS | HBM | 生态 |
|------|------|------|:-----------:|:---:|------|
| **华为** | 昇腾 910B | 达芬奇 | 320 | HBM2e 64GB | CANN/MindSpore |
| **寒武纪** | MLU370-X8 | 大量核心 | 256 | HBM2 48GB | BANG/CNeo |
| **海光** | DCU Z100 | GCN (类 AMD) | 256 | HBM2 32GB | ROCm 兼容 |
| **壁仞** | BR100 | 自研 | 1000+ (FP16) | HBM2e | BIRENSUPA |
| **摩尔线程** | MTT S4000 | 自研 MUSA | 144 (FP32) | HBM2e | MUSA |
| **燧原** | 云燧 T20 | GCU | 256 | HBM2e | 燧智 SDK |

## 5. ASIC 路线

| 产品 | 厂商 | 特点 |
|------|------|------|
| **TPU v5p** | Google | 459 TFLOPS BF16，专为大模型训练 |
| **TPU v6e (Trillium)** | Google | 918 TFLOPS BF16，HBM 升级 |
| **LPU** | Grog | 推理专用，超低延迟，SRAM 架构 |
| **WSE-3** | Cerebras | 整片晶圆级芯片（4T 晶体管） |

## 6. GPU 互联

| 互联 | 带宽 | 用途 |
|------|------|------|
| **NVLink 4.0** | 900 GB/s | GPU-GPU 高速直连 |
| **NVSwitch** | 全互联 | 8 GPU 全连接 |
| **NVLink 5.0** | 1.8 TB/s | B200 双芯互联 |
| **PCIe 5.0 x16** | 64 GB/s | GPU-CPU |
| **InfiniBand** | 400 Gbps | 跨节点 GPU 通信（AI 集群） |
| **RoCE** | 100-400 Gbps | 以太网 RDMA |

## 7. 性能指标速查

| 指标 | A100 | H100 SXM | B200 |
|------|:----:|:--------:|:----:|
| FP64 TFLOPS | 19.5 | 67 | 125 |
| FP32 TFLOPS | 19.5 | 67 | 125 |
| FP16 TFLOPS | 312 | 990 | 2250 |
| BF16 TFLOPS | 312 | 990 | 2250 |
| INT8 TOPS | 624 | 1980 | 4500 |
| HBM 容量 | 80GB | 80GB | 192GB |
| HBM 带宽 | 2 TB/s | 3.35 TB/s | 8 TB/s |
| TDP | 400W | 700W | 1000W |
| 晶体管数 | 54B | 80B | 208B |

## 常见坑

| 现象 | 原因 | 解决 |
|------|------|------|
| GPU 利用率低 | kernel launch 开销/数据搬运慢 | 合并内存访问、增大 batch |
| OOM | HBM 不足 | 梯度检查点、模型并行 |
| 多卡性能不线性 | NVLink 带宽瓶颈 | 优化通信模式、用 NVSwitch |
| 训练精度下降 | FP8 溢出 | 用 Transformer Engine 动态缩放 |

## 延伸

- FPGA：[[20-protocols/FPGA 2|FPGA 知识]]（FPGA 做 AI 推理加速）
- SmartNIC/DPU：[[50-reference/sources/chips/SmartNIC DPU|SmartNIC/DPU]]（GPU + DPU 组合加速）
- RDMA：[[50-reference/sources/chips/NIC DPDK|网卡与 DPDK]]（InfiniBand/RoCE 互联）
- 昇腾全栈：[[concepts/ascend software stack|昇腾 AI 软件栈]]（CANN / MindSpore / MindIE 分层架构）
- 大模型套件：[[entities/mindspore Transformer|MindSpore Transformers]]（昇腾大模型全流程开发套件）
